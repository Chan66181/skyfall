import subprocess
import threading
import time
import sys
from dataclasses import dataclass
from typing import List, Optional, TextIO
from .cancellation_token import CancellationToken, OperationCanceledError


@dataclass
class CommandResult:
    """
    A data class to hold the results of a command execution.
    This provides a structured way to return the output, error, and
    exit code of a completed process.
    """
    stdout: str
    stderr: str
    return_code: int

class CommandExecutor:
    """
    Executes shell commands in a non-blocking way with advanced features.

    This executor runs commands in a separate thread, allowing the main
    application to remain responsive. It supports graceful cancellation
    via a CancellationToken, enforces timeouts, and can execute commands
    with superuser privileges (sudo). All command output (stdout, stderr)
    is captured in memory and returned upon completion.
    """

    def execute(
        self,
        command: List[str],
        cancellation_token: Optional[CancellationToken] = None,
        timeout: float = 30.0,
        sudo: bool = False,
    ) -> CommandResult:
        """
        Executes a given command and waits for its completion.

        Args:
            command: The command and its arguments as a list of strings.
            cancellation_token: A token to monitor for cancellation requests.
            timeout: The maximum time in seconds to allow the command to run.
            sudo: If True, the command will be executed with 'sudo'.

        Returns:
            A CommandResult object containing the full stdout, stderr,
            and return code.

        Raises:
            ValueError: If sudo is True but no password is provided.
            FileNotFoundError: If the command does not exist.
            TimeoutError: If the command exceeds the specified timeout.
            OperationCanceledError: If the operation is canceled via the token.
        """
        result_container = {}
        # The command is executed in a separate thread to keep the main thread responsive
        # and to manage the execution lifecycle (timeout, cancellation).
        execution_thread = threading.Thread(
            target=self._execute_in_thread,
            args=(command, cancellation_token, timeout, sudo, result_container)
        )
        execution_thread.start()
        execution_thread.join()  # Wait for the thread to complete

        if "error" in result_container:
            raise result_container["error"]
        return result_container["result"]

    def _execute_in_thread(
        self,
        command: List[str],
        cancellation_token: Optional[CancellationToken],
        timeout: float,
        sudo: bool,
        result_container: dict
    ):
        """
        The internal method that runs the command in a thread.
        This handles the subprocess creation, in-memory I/O capturing,
        and monitoring for cancellation or timeout.
        """
        try:
            full_command = ["sudo"] + command if sudo else command

            # When using 'sudo', we let the process handle the password prompt directly.
            # We explicitly set stdin to None so it inherits from the parent process.
            stdin_pipe = subprocess.PIPE if not sudo else None

            # Popen is used to get fine-grained control for cancellation and timeouts.
            process = subprocess.Popen(
                full_command,
                stdin=stdin_pipe,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            # Threads are used to read stdout and stderr concurrently without blocking.
            stdout_lines, stderr_lines = [], []
            stdout_thread = threading.Thread(target=self._read_stream, args=(process.stdout, stdout_lines))
            stderr_thread = threading.Thread(target=self._read_stream, args=(process.stderr, stderr_lines))
            stdout_thread.start()
            stderr_thread.start()

            start_time = time.time()
            # This loop monitors the process while it's running.
            while process.poll() is None:
                # Check for a cancellation signal.
                if cancellation_token and cancellation_token.is_cancelled():
                    process.terminate()  # Attempt a graceful shutdown.
                    # Wait for a short period before killing
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    raise OperationCanceledError()

                # Check if the command has exceeded its time limit.
                if time.time() - start_time > timeout:
                    process.kill()  # Forcefully stop the process.
                    raise TimeoutError(f"Command timed out after {timeout} seconds.")
                
                time.sleep(0.1)  # Prevent the loop from consuming too much CPU.

            # Wait for the stream-reading threads to finish to ensure all output is captured.
            stdout_thread.join()
            stderr_thread.join()

            # Store the final result in the shared container.
            result_container["result"] = CommandResult(
                stdout="".join(stdout_lines),
                stderr="".join(stderr_lines),
                return_code=process.returncode
            )

        except FileNotFoundError:
            result_container["error"] = FileNotFoundError(f"Command not found: '{command[0]}'")
        except Exception as e:
            result_container["error"] = e

    def _read_stream(self, process_stream: TextIO, output_list: List[str]):
        """Reads from a process stream line by line and stores it in a list."""
        try:
            for line in iter(process_stream.readline, ''):
                output_list.append(line)
        finally:
            # It's important to close the stream to free up resources.
            process_stream.close()