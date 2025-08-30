import subprocess
import threading
import time
import sys
from dataclasses import dataclass
from typing import List, Optional, TextIO
from .cancellation_token import CancellationToken, OperationCanceledError


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    return_code: int


class CommandExecutor:
    """
    Executes shell commands in a non-blocking (threaded) way by default.
    If exec_in_thread=False, runs in the current thread via subprocess.run.
    """

    def execute(
        self,
        command: List[str],
        cancellation_token: Optional[CancellationToken] = None,
        timeout: float = 30.0,
        sudo: bool = False,
        exec_in_new_thread: bool = True,  # NEW: set to False to run in this thread
        infite_loop: bool = False,
    ) -> CommandResult:

        if not exec_in_new_thread:
            return self._execute_foreground_run(command, timeout, sudo, infinite_loop=infite_loop)

        result_container = {}
        execution_thread = threading.Thread(
            target=self._execute_in_thread,
            args=(command, cancellation_token, timeout, sudo, result_container)
        )
        execution_thread.start()
        execution_thread.join()

        if "error" in result_container:
            raise result_container["error"]
        return result_container["result"]

    # ---------- NEW: foreground single-thread path using subprocess.run ----------
    def _execute_foreground_run(
        self,
        command: List[str],
        timeout: float,
        sudo: bool,
        infinite_loop: bool
    ) -> CommandResult:
        """
        Run command in the current thread using subprocess.run.
        Captures stdout/stderr and returns CommandResult.
        Ctrl+C (KeyboardInterrupt) is surfaced as OperationCanceledError.
        """
        full_command = ["sudo"] + command if sudo else command
        # None means no timeout; allow 0/None to mean "no timeout"
        # effective_timeout = None if (timeout is None or timeout <= 0) else timeout
        if not infinite_loop:
            return self._exec(full_command=full_command, timeout=timeout, is_infinite_loop=infinite_loop)
        stdout_lines = []
        stderr_lines = []
        while True:
            try:
                result = self._exec(full_command, timeout, infinite_loop)
                stdout_lines.append(result.stdout)
                stderr_lines.append(result.stderr)
            except KeyboardInterrupt:
                print("Operation Cancelled")
                break
        return CommandResult("".join(stdout_lines), "".join(stderr_lines))
        
        
    def _exec(self,
        full_command: List[str],
        timeout: float,
        is_infinite_loop: bool,
        ) -> CommandResult:
        try:
            process = subprocess.Popen(
                                    full_command,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    text=True
                                )
            if process is None:
                return CommandResult("", "", 1)  # Command failed to start
            stdout_lines, stderr_lines = [], []

            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                stdout_lines.append(line)

            for line in process.stderr:
                sys.stderr.write(line)
                sys.stderr.flush()
                stderr_lines.append(line)

            process.wait()

            return CommandResult(
                stdout="".join(stdout_lines),
                stderr="".join(stderr_lines),
                return_code=process.returncode
            )
        except subprocess.TimeoutExpired:
            # mimic threaded path semantics
            raise TimeoutError(f"Command timed out after {timeout} seconds.")
        except KeyboardInterrupt:
            # user hit Ctrl+C
            if is_infinite_loop:
                pass
            print("Operation Cancelled")
        except FileNotFoundError:
            raise FileNotFoundError(f"Command not found: '{full_command[0]}'")
        except Exception as e:
            # bubble up unexpected errors
            raise e
    

    # ---------- existing threaded path (unchanged) ----------
    def _execute_in_thread(
        self,
        command: List[str],
        cancellation_token: Optional[CancellationToken],
        timeout: float,
        sudo: bool,
        result_container: dict
    ):
        try:
            full_command = ["sudo"] + command if sudo else command
            stdin_pipe = subprocess.PIPE if not sudo else None
            process = subprocess.Popen(
                full_command,
                stdin=stdin_pipe,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            stdout_lines, stderr_lines = [], []
            stdout_thread = threading.Thread(target=self._read_stream, args=(process.stdout, stdout_lines))
            stderr_thread = threading.Thread(target=self._read_stream, args=(process.stderr, stderr_lines))
            stdout_thread.start()
            stderr_thread.start()

            start_time = time.time()
            while process.poll() is None:
                if cancellation_token and cancellation_token.is_cancelled():
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    raise OperationCanceledError()

                if timeout and time.time() - start_time > timeout:
                    process.kill()
                    raise TimeoutError(f"Command timed out after {timeout} seconds.")

                time.sleep(0.1)

            stdout_thread.join()
            stderr_thread.join()

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
        try:
            for line in iter(process_stream.readline, ''):
                output_list.append(line)
        finally:
            try:
                process_stream.close()
            except Exception:
                pass


class SudoHelper:
    def __init__(self):
        self.exec = CommandExecutor()

    def is_sudo_cached(self) -> bool:
        try:
            res = self.exec.execute(["sudo", "-n", "true"], timeout=5, sudo=False)
            return res.return_code == 0
        except Exception:
            return False

    def ensure_sudo(self) -> bool:
        if self.is_sudo_cached():
            return True
        print("[i] Sudo authentication required. Please enter your password…")
        try:
            res = self.exec.execute(["sudo", "-v"], timeout=60, sudo=False, exec_in_thread=False)
            return res.return_code == 0
        except Exception:
            return False
