import cmd
import shlex
import subprocess
from shared import *
from hardware_handler import *
from typing import Optional, Dict, Union, List, Any
import sys
import threading
import time
import argparse
from modules.exploit import get_attack_factory
from shared.dataclass.info import InterfaceInfo
from external_dependencies.aircrack_ng_handler import AircrackNgHandler, DroneCSVAnalyser


class SkyFallConsole(cmd.Cmd):
    intro = "Welcome to Skyfall — The Drone Killer Console. Type ? or 'help' to see commands.\n"
    prompt = "skyfall> "
    
    def __init__(self, completekey = "tab", stdin = None, stdout = None):
        super().__init__(completekey, stdin, stdout)
        self.shell_binaries = load_shell_binaries()
        self.wifi_card_handler = WifiCardHandler()
        self.ap_analyzers: List[APAnalyzer] = [
            ParrotDroneAnalyzer()
        ]

        self.scanning_interface: Optional[str] = None
        self.airodump_output_file: Optional[str] = None
        self.airodump_process: Optional[subprocess.Popen] = None
        self.scan_thread: Optional[threading.Thread] = None
        self.stop_scan_event = threading.Event() # Used to signal scan thread to stop

        self.known_aps: Dict[str, Dict[str, Any]] = {} # Stores all unique APs found
        self.detected_drones: Dict[str, Dict[str, Any]] = {} # Stores unique drones found
        self._last_monitor_interface: Optional[Dict[str, Union[str, int, None]]] = None
        self.current_target_drone: Optional[Dict[str, Any]] = None # The drone selected for 'context'
        self.drone_target_info: Optional[DroneTargetInfo] = None

    def _get_last_toggled_monitor_interface(self) -> Optional[Dict[str, Union[str, int, None]]]:
        """
        Attempts to find if the previously toggled interface is still in monitor mode.
        Returns the interface row as a dictionary if found, else None.
        """
        if not self._last_monitor_interface:
            return None

        # Re-scan to get the current state of interfaces
        current_datatable = self.wifi_card_handler.get_wifi_cards()
        
        # Look for the interface by its current/updated name and check its mode
        for row_dict in current_datatable.get_all_rows_as_dicts():
            iface_name = row_dict.get("Updated_Interface") or row_dict.get("Interface")
            if (iface_name == self._last_monitor_interface.get("Updated_Interface") or \
                iface_name == self._last_monitor_interface.get("Interface")) and \
               row_dict.get("Mode") == "monitor":
                return row_dict # Found the last toggled interface and it's in monitor mode
        return None

    # def _stop_scan_internal(self):
    #     """Internal method to stop the active AP scan and clean up resources."""
    #     if self.airodump_process and self.airodump_process.poll() is None:
    #         self.stop_scan_event.set() # Signal the monitoring thread to stop
    #         if self.scan_thread and self.scan_thread.is_alive():
    #             print("[*] Waiting for scan monitoring thread to finish...")
    #             self.scan_thread.join(timeout=5) # Give the thread time to exit
    #             if self.scan_thread.is_alive():
    #                 print("[!] Scan monitoring thread did not stop gracefully. Proceeding to stop airodump-ng.")
            
    #         if self.wifi_card_handler.stop_airodump_scan():
    #             self.scanning_interface = None
    #             self.airodump_output_file = None
    #             self.airodump_process = None
    #             # Don't clear known_aps or detected_drones immediately here,
    #             # so 'show_drones' and 'show_aps' can still display results after stopping.
    #             print("[*] AP scan successfully stopped.")
    #         else:
    #             print("[!] Failed to stop airodump-ng process.")
    #     else:
    #         print("[*] No active AP scan to stop.")
    #         self.airodump_process = None # Ensure state is reset if process crashed
    #         self.scanning_interface = None
    #         self.airodump_output_file = None
    

    def cmdloop(self, intro=None):
        """
        Overrides cmd.Cmd.cmdloop to handle KeyboardInterrupt (Ctrl+C) gracefully.
        """
        print(self.intro if intro is None else intro)
        while True:
            try:
                # Call the base cmdloop, but handle the KeyboardInterrupt
                # Pass empty intro to avoid reprinting it on subsequent loops after Ctrl+C
                super().cmdloop(intro="")
                break # Exit the loop if cmdloop exits normally (e.g., via do_quit)
            except KeyboardInterrupt:
                print("\n[!] Ctrl+C detected. Attempting to stop active scan...")
                # self._stop_scan_internal() # Stop the scan gracefully
                # Reprint the prompt to make it clear the CLI is ready for new input
                sys.stdout.write(self.prompt)
                sys.stdout.flush()
            except Exception as e:
                print(f"[!] An unexpected error occurred in the main loop: {e}")
                break # Exit on other unexpected errors

    def do_toggle(self, arg):
        """
        Select a Wi‑Fi interface and switch it to MONITOR mode.
        - Shows interfaces
        - Lets you pick one
        - Toggles to monitor mode via ensure_mode
        - Updates DroneTargetInfo.interface (InterfaceInfo) including rename + mode
        """
        self.drone_target_info = DroneTargetInfo()  # Reset or create a new DroneTargetInfo
        if self.airodump_process and self.airodump_process.poll() is None:
            print("[!] Cannot toggle mode while AP scanning is active. Please stop it first.")
            return
        print("\n--- Scanning for Wi‑Fi Cards ---")
        datatable: DataTable = self.wifi_card_handler.get_wifi_cards()
        if not datatable.rows:
            print("[!] No Wi‑Fi interfaces found. Please ensure your card is connected and drivers are loaded.")
            return
        selected_row = datatable.show_table_and_select(title="Available Wi‑Fi Interfaces")
        if not selected_row:
            print("[*] No interface selected or selection cancelled.")
            return
        # Build InterfaceInfo from the chosen row and attach it to DroneTargetInfo
        ii = InterfaceInfo.from_row(selected_row)
        self.drone_target_info.interface = ii
        print(f"\n--- Switching '{ii.iface_name}' to MONITOR mode ---")
        ok, out, err, msg, updated_iface = self.wifi_card_handler.ensure_mode(
            interface=ii.iface_name,
            required_mode=InterfaceMode.MONITOR,
            use_sudo=True
        )
        print(f"[i] {msg}")
        if not ok:
            if out.strip(): print("[stdout]\n" + out.strip())
            if err.strip(): print("[stderr]\n" + err.strip())
            return
        # Persist rename + mode in InterfaceInfo and DroneTargetInfo
        if updated_iface and updated_iface != ii.iface_name:
            ii.is_name_changed = True
            ii.monitor_name = updated_iface
            ii.iface_name = updated_iface
        ii.mode = InterfaceMode.MONITOR
        print(f"[*] Interface now in MONITOR mode: {ii.iface_name}")
        print("\n--- Final Wi‑Fi Card State ---")
        final_table = self.wifi_card_handler.get_wifi_cards()
        final_table.print_table(title="Updated Wi‑Fi Interfaces")
        # Optional: remember UX helper
        for row in final_table.get_all_rows_as_dicts():
            row_iface = row.get("Updated_Interface") or row.get("Interface")
            if row_iface == ii.iface_name and str(row.get("Mode","")).lower() == "monitor":
                self._last_monitor_interface = row
                break
            
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
    
    
    def do_ap_scan(self, arg):
        """
        Starts scanning for Access Points (APs) using airodump-ng.
        Automatically uses last monitor mode interface if available, or prompts to toggle one.
        Live detects and displays drones.
        Stop with Ctrl+C.
        Usage: ap_scan
        """
        parser = argparse.ArgumentParser(prog='ap_scan', add_help=False)
        parser.add_argument('--duration', type=int, help="Scan duration in seconds", default=10)
        duration = 10  # Default duration if not specified
        try:
            args = parser.parse_args(shlex.split(arg))
            duration = args.duration
        except SystemExit:
            print("[!] Defaulting to 10 seconds for scan duration.")
        if self.airodump_process and self.airodump_process.poll() is None:
            print("[!] AP scanning is already active. Use Ctrl+C to stop it first.")
            return

        # Reset detected APs and drones for a new scan
        self.known_aps.clear()
        self.detected_drones.clear()
        self.current_target_drone = None

        if self.drone_target_info  and self.drone_target_info.interface is None:
            self.do_toggle(arg="")  # Ensure we have a DroneTargetInfo with an interface set
        elif self.drone_target_info and self.drone_target_info.interface and  self.drone_target_info.interface.mode != InterfaceMode.MONITOR:
            print(f"[!] The selected interface {self.drone_target_info.interface.iface_name} is not in Monitor mode. Attempting to toggle it now.")
            self.do_toggle(arg="")
        
        # TODO: For now, its fine but move all the aircrack-ng commands to one module, make it used from there. 
        aircrackNgHandler = AircrackNgHandler()
        if not self.drone_target_info or not self.drone_target_info.interface:
            print("[!] No valid Wi-Fi interface selected. Please toggle one to MONITOR mode first.")
            return
        aircrackNgHandler.start_airodump_scan(self.drone_target_info.interface,
                                              output_prefix="airodump_output",
                                              duration_sec=duration,
                                              use_sudo=True,
                                              ignore_negative_one=True)
        analyser = DroneCSVAnalyser()  # includes Parrot analyser by default
        results = analyser.analyse_csv_all("airodump_output-01.csv")

        if not results:
            print("No drone APs detected.")
            return
        ap_table = results_to_datatable(results)
        selected_ap_row = ap_table.show_table_and_select(title="Detected Drone Access Points")
        if not selected_ap_row:
            return None

        # map S.No -> result
        idx = int(selected_ap_row["S.No"]) - 1
        if idx < 0 or idx >= len(results):
            print("[!] Invalid selection.")
            return None
        chosen = results[idx]

        # show clients for that AP
        sta_table = stations_to_datatable(chosen.connected_devices)
        selected_sta_row = sta_table.show_table_and_select(
            title=f"Clients connected to {chosen.drone_ap.essid or '<hidden>'} ({chosen.drone_ap.bssid})",
            selection_message="\nSelect a client S.No (or 'q' to skip client selection): "
        )
        # client selection can be optional; return None controller_mac if skipped
        controller_mac = None
        if selected_sta_row:
            controller_mac = selected_sta_row.get("Station MAC")

        sel = {
            "selected_ap": chosen,
            "selected_ap_row": selected_ap_row,
            "selected_client_row": selected_sta_row,
            "controller_mac": controller_mac
        }
        if not sel:
            print("[*] Selection cancelled.")
            return
        iface = InterfaceInfo(iface_name=self.drone_target_info.interface.iface_name, original_name=self.drone_target_info.interface.original_name, mode=self.drone_target_info.interface.mode)
        self.drone_target_info = build_target_info_from_selection(sel["selected_ap"], iface, sel["controller_mac"], use_sudo=True)

        print("\n[✓] Target ready:")
        print(f"  Drone   : {self.drone_target_info.ssid or '<hidden>'} ({self.drone_target_info.drone_mac}) ch={self.drone_target_info.channel}")
        print(f"  Controller MAC: {self.drone_target_info.controller_mac or '(not selected)'}")
        print(f"  NIC     : {self.drone_target_info.interface.iface_name} [{self.drone_target_info.interface.mode.value}]")
        print(f"[*] AP scan completed. Now execute the command list_attacks to see available attacks.")
        # return self.drone_target_info
    
    def complete_ap_scan(self, text, line, begidx, endidx):
        """
        Completes the ap_scan command with available options.
        """
        parts = shlex.split(line[:endidx])
        if len(parts) == 2 and parts[1].startswith('--'):
            return ['duration']
        return []
            
    def do_analyze_result(self, arg): # TODO: Remove after testing
        analyser = DroneCSVAnalyser()  # includes Parrot analyser by default
        results = analyser.analyse_csv_all("airodump_output_wlx3460f9f53faf-02.csv")

        if not results:
            print("No drone APs detected.")
            return
        ap_table = results_to_datatable(results)
        selected_ap_row = ap_table.show_table_and_select(title="Detected Drone Access Points")
        if not selected_ap_row:
            return None

        # map S.No -> result
        idx = int(selected_ap_row["S.No"]) - 1
        if idx < 0 or idx >= len(results):
            print("[!] Invalid selection.")
            return None
        chosen = results[idx]

        # show clients for that AP
        sta_table = stations_to_datatable(chosen.connected_devices)
        selected_sta_row = sta_table.show_table_and_select(
            title=f"Clients connected to {chosen.drone_ap.essid or '<hidden>'} ({chosen.drone_ap.bssid})",
            selection_message="\nSelect a client S.No (or 'q' to skip client selection): "
        )
        # client selection can be optional; return None controller_mac if skipped
        # TODO: Make sure no error is happening here.
        controller_mac = None
        if selected_sta_row:
            controller_mac = selected_sta_row.get("Station MAC")

        sel = {
            "selected_ap": chosen,
            "selected_ap_row": selected_ap_row,
            "selected_client_row": selected_sta_row,
            "controller_mac": controller_mac
        }
        if not sel:
            print("[*] Selection cancelled.")
            return
        iface = InterfaceInfo(iface_name='Wlan1Mon', original_name='Wlan1Mon', mode=InterfaceMode.MONITOR)
        info = build_target_info_from_selection(sel["selected_ap"], iface, sel["controller_mac"], use_sudo=True)

        print("\n[✓] Target ready:")
        print(f"  Drone   : {info.ssid or '<hidden>'} ({info.drone_mac}) ch={info.channel}")
        print(f"  Controller MAC: {info.controller_mac or '(not selected)'}")
        print(f"  NIC     : {info.interface.iface_name} [{info.interface.mode.value}]")
        # return info        

    def do_list_attacks(self, arg):
        """
        Lists all available attacks based on the selected drone.
        Usage: list_attacks
        """
        # if not self.current_target_drone:
        #     print("[!] No drone selected. Use 'select_drone' first.")
        #     return
        self.attack_factory = get_attack_factory()
        supported_attacks : List[AttackType] = self.attack_factory.get_supported_attacks(Manufacturer.PARROT, Model.PARROT_AR2.value)
        print("\n--- Available Attacks for Selected Drone ---")
        for attack in supported_attacks:
            print(f"- {attack.name} ({attack.value})")
            
        attack_number = int(input("Enter the attack type number").strip())
        attack_type = AttackType(attack_number)
        if self.drone_target_info is None:
            print("[!] No drone target info available. Please run 'ap_scan' first.")
            return        
        attack  = self.attack_factory.create(Manufacturer.PARROT, Model.PARROT_AR2.value, attack_type, self.drone_target_info)
        if not attack:
            print("[!] Invalid attack type selected.")
            return
        result = attack.attack()
        if result and result.stderr is None:
            print(f"\n[✓] Attack '{attack_type.name}' executed successfully.")
        print(f"=> Execution result: {result.stdout.strip()}")
        
        
        
    def do_save_context(self, arg):
        """
        Save current DroneTargetInfo to disk (JSON).
        Usage: save_ctx [optional_path]
        """
        if not self.drone_target_info:
            print("[!] No DroneTargetInfo to save. Run 'ap_scan' first.")
            return
        path = arg.strip() or None
        p = save_context(self.drone_target_info, "context.json" if not path else path)
        print(f"[✓] Context saved to {p}")
        
        
    def do_load_context(self, arg):
        """
        Load DroneTargetInfo from disk (JSON).
        Usage: load_ctx [optional_path]
        """
        path = arg.strip() or None
        info = load_context("context.json" if not path else path)
        if not info:
            print("[!] No saved context found.")
            return
        self.drone_target_info = info
        
        print(f"[✓] Context loaded. Target: {info.ssid or '<hidden>'} ({info.drone_mac}) ch={info.channel}")
        if info.interface:
            print(f"    NIC: {info.interface.iface_name} [{info.interface.mode.value}]")
        
        
        
        
        
        
        
        
        
        
        
        

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
            subprocess.run(arg, shell=True, check=True, text=True, capture_output=False)
        except subprocess.CalledProcessError as e:
            print(f"[!] Shell command '{e.cmd}' failed with exit code {e.returncode}.")
            print(f"STDOUT: {e.stdout.strip()}")
            print(f"STDERR: {e.stderr.strip()}")
        except Exception as e:
            print(f"[!] An error occurred while executing shell command: {e}")

    def complete_shell(self, text, line, begidx, endidx):
        parts = shlex.split(line[:endidx])
        if len(parts) > 1 and line.endswith(text):
            return [b for b in self.shell_binaries if b.startswith(text)]
        elif len(parts) == 1 and line.endswith(' '):
            return self.shell_binaries
        return []

    def do_quit(self, line):
        """Exit the CLI."""
        # self._stop_scan_internal() # Ensure any active scan is stopped before quitting
        print("Exiting Skyfall. Goodbye!")
        return True 
    
    def do_exit(self, line):
        """Exit the CLI."""
        # self._stop_scan_internal() # Ensure any active scan is stopped before exiting
        print("Exiting Skyfall. Goodbye!")
        return True 
    
    def default(self, line):
        """Fallback: Execute unknown commands as shell commands"""
        print(f"[*] Unknown command: '{line}'. Attempting to execute as shell command...")
        try:
            subprocess.run(line, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"[!] Shell command '{e.cmd}' failed with exit code {e.returncode}.")
        except FileNotFoundError:
            print(f"[!] Command '{line.split()[0]}' not found in PATH.")
        except Exception as e:
            print(f"[!] Shell command failed: {e}")
                        
    def completenames(self, text, *ignored):
        dotext = 'do_'+text
        op = [a[3:] for a in self.get_names() if a.startswith(dotext)]
        op += [a for a in self.shell_binaries if a.startswith(text)]
        return op