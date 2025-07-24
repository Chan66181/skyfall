import cmd
import shlex
import subprocess
from utils import *
from modules.hardware_handler import *
from typing import Optional, Dict, Union

class SkyFallConsole(cmd.Cmd):
    intro = "Welcome to Skyfall — The Drone Killer Console. Type ? or 'help' to see commands.\n"
    prompt = "skyfall> "
    
    def __init__(self, completekey = "tab", stdin = None, stdout = None):
        super().__init__(completekey, stdin, stdout)
        self.shell_binaries = load_shell_binaries()
        self.wifi_card_handler = WifiCardHandler() # Initialize handler once

    def do_toggle(self, arg):
        """
        Interactively select a Wi-Fi interface and toggle its mode (managed/monitor).
        Usage: toggle
        """
        print("\n--- Scanning for Wi-Fi Cards ---")
        datatable: DataTable = self.wifi_card_handler.get_wifi_cards()
        
        if not datatable.rows:
            print("[!] No Wi-Fi interfaces found. Please ensure your card is connected and drivers are loaded.")
            return

        # Display the table and allow user to select an interface
        selected_interface: Optional[Dict[str, Union[str, int, None]]] = datatable.show_table_and_select(
            title="Available Wi-Fi Interfaces"
        )

        if selected_interface:
            # Determine the current interface name for toggle operation
            # Prioritize 'Updated_Interface' if it exists, otherwise use 'Interface'
            current_interface_name = selected_interface.get("Updated_Interface") or selected_interface.get("Interface")
            
            # Update the dictionary to ensure 'Interface' key holds the correct current name
            # This is important because toggle_mode_airmon expects 'Interface' to be the current name
            selected_interface["Interface"] = current_interface_name 

            print(f"\n--- Attempting to toggle mode for '{current_interface_name}' (S.No: {selected_interface.get('S.No')}) ---")
            self.wifi_card_handler.toggle_mode_airmon(selected_interface)
            
            print("\n--- Final Wi-Fi Card State After Toggle ---")
            # Re-scan and display the table to show the new state
            final_datatable = self.wifi_card_handler.get_wifi_cards()
            final_datatable.print_table(title="Updated Wi-Fi Interfaces")
        else:
            print("[*] No interface selected or selection cancelled.")

    def do_list_wifi(self, arg):
        """
        List all detected Wi-Fi interfaces and their current modes.
        Usage: list_wifi
        """
        print("\n--- Scanning for Wi-Fi Cards ---")
        datatable: DataTable = self.wifi_card_handler.get_wifi_cards()
        if not datatable.rows:
            print("[!] No Wi-Fi interfaces found.")
        datatable.print_table(title="Available Wi-Fi Interfaces")


    def do_scan(self, arg):
        """
        Performs a scan.
        Usage: scan --wifi
        """
        args = shlex.split(arg)
        if "--wifi" in args:
            print("Scanning wifi frequencies....")
            # Add your wifi scanning logic here
        else:
            print("[!] Invalid 'scan' command. Use 'scan --wifi'.")
 
    def complete_scan(self, text, line, begidx, endidx):
        options = ["--wifi"]
        return [opt for opt in options if opt.startswith(text)]

    def do_shell(self, arg):
        """
        Execute a shell command.
        Usage: shell <command_and_args>
        Example: shell ls -l /tmp
        """
        if not arg:
            print("[!] Please provide a shell command to execute.")
            return
        try:
            # Use shell=True for convenience, but be cautious with untrusted input
            subprocess.run(arg, shell=True, check=True, text=True, capture_output=False)
        except subprocess.CalledProcessError as e:
            print(f"[!] Shell command '{e.cmd}' failed with exit code {e.returncode}.")
            print(f"STDOUT: {e.stdout.strip()}")
            print(f"STDERR: {e.stderr.strip()}")
        except Exception as e:
            print(f"[!] An error occurred while executing shell command: {e}")

    def complete_shell(self, text, line, begidx, endidx):
        # The line format for 'shell' command is typically "shell <command> [args]"
        # We want to autocomplete the *first* word after 'shell'
        parts = shlex.split(line[:endidx])
        if len(parts) > 1 and line.endswith(text):
            # User is typing the command itself
            return [b for b in self.shell_binaries if b.startswith(text)]
        elif len(parts) == 1 and line.endswith(' '):
            # User has typed 'shell ' and is looking for the first command
            return self.shell_binaries
        return []


    def do_quit(self, line):
        """Exit the CLI."""
        print("Exiting Skyfall. Goodbye!")
        return True 
    
    def do_exit(self, line):
        """Exit the CLI."""
        print("Exiting Skyfall. Goodbye!")
        return True 
    
    def default(self, line):
        """Fallback: Execute unknown commands as shell commands"""
        print(f"[*] Unknown command: '{line}'. Attempting to execute as shell command...")
        try:
            # Using shell=True for convenience, but for security,
            # consider using shlex.split and passing as list for subprocess.run
            # if line originates from untrusted input.
            subprocess.run(line, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"[!] Shell command '{e.cmd}' failed with exit code {e.returncode}.")
            # print(f"STDOUT: {e.stdout.strip()}") # Can capture if desired
            # print(f"STDERR: {e.stderr.strip()}") # Can capture if desired
        except FileNotFoundError:
            print(f"[!] Command '{line.split()[0]}' not found in PATH.")
        except Exception as e:
            print(f"[!] Shell command failed: {e}")
                        
    def completenames(self, text, *ignored):
        dotext = 'do_'+text
        # Autocomplete internal commands (do_*)
        op = [a[3:] for a in self.get_names() if a.startswith(dotext)]
        # Autocomplete direct shell binaries
        op += [a for a in self.shell_binaries if a.startswith(text)]
        return op