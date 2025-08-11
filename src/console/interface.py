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
from modules.exploit import get_attack_factory, BaseAttackScript
from shared.dataclass.info import InterfaceInfo



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

    def _stop_scan_internal(self):
        """Internal method to stop the active AP scan and clean up resources."""
        if self.airodump_process and self.airodump_process.poll() is None:
            self.stop_scan_event.set() # Signal the monitoring thread to stop
            if self.scan_thread and self.scan_thread.is_alive():
                print("[*] Waiting for scan monitoring thread to finish...")
                self.scan_thread.join(timeout=5) # Give the thread time to exit
                if self.scan_thread.is_alive():
                    print("[!] Scan monitoring thread did not stop gracefully. Proceeding to stop airodump-ng.")
            
            if self.wifi_card_handler.stop_airodump_scan():
                self.scanning_interface = None
                self.airodump_output_file = None
                self.airodump_process = None
                # Don't clear known_aps or detected_drones immediately here,
                # so 'show_drones' and 'show_aps' can still display results after stopping.
                print("[*] AP scan successfully stopped.")
            else:
                print("[!] Failed to stop airodump-ng process.")
        else:
            print("[*] No active AP scan to stop.")
            self.airodump_process = None # Ensure state is reset if process crashed
            self.scanning_interface = None
            self.airodump_output_file = None
            
    
    def _trigger_stop(self, duration: int):
        time.sleep(duration)
        self._stop_scan_internal()
        print("[!] Scanning process stopped...")
    

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
                self._stop_scan_internal() # Stop the scan gracefully
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
        try:
            args = parser.parse_args(shlex.split(arg))
        except SystemExit:
            print("[!] Invalid arguments. Usage: ap_scan --duration <seconds>")
            return
        if self.airodump_process and self.airodump_process.poll() is None:
            print("[!] AP scanning is already active. Use Ctrl+C to stop it first.")
            return

        # Reset detected APs and drones for a new scan
        self.known_aps.clear()
        self.detected_drones.clear()
        self.current_target_drone = None

        interface_to_scan: Optional[Dict[str, Union[str, int, None]]] = None
        
        last_mon_iface = self._get_last_toggled_monitor_interface()
        if last_mon_iface:
            current_name = last_mon_iface.get("Updated_Interface") or last_mon_iface.get("Interface")
            print(f"[*] Found previously toggled monitor interface: '{current_name}'. Attempting to use it.")
            interface_to_scan = last_mon_iface
        else:
            print("\n--- No previously selected monitor interface found or it's no longer active. ---")
            print("--- Scanning for Wi-Fi Cards to find a suitable interface. ---")
            datatable: DataTable = self.wifi_card_handler.get_wifi_cards()
            
            monitor_interfaces = [row for row in datatable.get_all_rows_as_dicts() if row.get("Mode") == "monitor"]
            
            if monitor_interfaces:
                print("\n--- Select an existing Monitor Mode Interface for AP Scan ---")
                monitor_dt = DataTable(headers=datatable.headers)
                for row in monitor_interfaces:
                    monitor_dt.add_row([row[h] for h in datatable.headers])
                
                interface_to_scan = monitor_dt.show_table_and_select(
                    title="Available Monitor Mode Interfaces"
                )
            
            if not interface_to_scan:
                print("\n[!] No monitor mode interface selected.")
                print("[*] Would you like to set an interface to monitor mode now?")
                user_choice = input("Enter 'y' or 'n': ").strip().lower()

                if user_choice == 'y':
                    self.do_toggle(arg="")
                    interface_to_scan = self._get_last_toggled_monitor_interface()
                    if not interface_to_scan:
                        print("[!] Interface toggling failed or no monitor interface was set. Cannot proceed with AP scan.")
                        return
                else:
                    print("[*] AP scan cancelled.")
                    return

        if interface_to_scan:
            interface_name = interface_to_scan.get("Updated_Interface") or interface_to_scan.get("Interface")
            if not interface_name:
                print("[!] Could not determine interface name for scanning.")
                return

            self.scanning_interface = str(interface_name)
            self.airodump_output_file = f"airodump_output_{self.scanning_interface}"
            
            # self.stop_thread = threading.Thread(target=self._trigger_stop, args=(args.duration,), daemon=True)
            # self.stop_thread.start()
            # Start airodump-ng process (this writes to disk for reliable parsing)
            # The key here is that this call must be non-blocking.
            self.airodump_process = self.wifi_card_handler.start_airodump_scan(
                self.scanning_interface, self.airodump_output_file
            )
            # self.do_analyze_airodump_result()

        #     if self.airodump_process:
        #         self.stop_scan_event.clear() # Clear event for new scan
        #         self.scan_thread = threading.Thread(target=self._monitor_airodump_output, daemon=True)
        #         self.scan_thread.start()
        #         print(f"[*] Started AP scan on {self.scanning_interface}. Monitoring output...")
        #         print("Press Ctrl+C to stop the scan. Use 'show_drones' or 'show_aps' at any time.")
        #         print("When a drone is detected, use 'select_drone' to target it.")
        #     else:
        #         print("[!] Failed to start AP scan.")
        # else:
        #     print("[!] No suitable monitor mode interface found or selected. AP scan aborted.")
        
        
    # def do_command_executor(self, arg):
    #     executor = CommandExecutor()
    #     result : CommandResult = executor.execute(command=["ls", "-l"], timeout=5, sudo=True)
    #     print(f"Command executed with return code: {result.return_code}")
    #     print(f"STDOUT: {result.stdout.strip()}")
        
    
    def do_list_exploits(self,arg):
        """To list all the available exploits based on the drone type and model."""
        
        print("Available Exploits:" )
        
        
        
    def do_analyze_airodump_result(self, arg): # This is a private method, not a command,  after testing change it back.    
        """
        Internal method to analyze airodump-ng results and detect drones.
        This is called after starting the airodump-ng process.
        """
        airodump_output : tuple[DataTable, DataTable]  = convert_airodump_csv_to_datatables("/home/chan/code/skyfall/airodump_output_wlx3460f9f53faf-02.csv")
        self._filter_drones(airodump_output[0])
        print("\n--- Drone Detection Results ---")
        if self.drone_data.get_row_count() == 0:
            print("[!] No drones detected.")
        else:
            self.selected_drone = self.drone_data.show_table_and_select(title="Detected Drones", selection_message="\nSelect the drone to do next actions (or 'q' to quit): ") 
            if not self.selected_drone:
                print("[*] No drone selected or selection cancelled.")
                return
            print("\n--- Checking for devices connected to the drone ---")      
            self._get_connected_devices(self.selected_drone.get("BSSID", ""), airodump_output[1])
            if self.connected_devices.get_row_count() == 0:
                print("[!] No connected devices found for this drone.")
            else:
                print("\n--- Connected Devices to the Drone ---")
                self.connected_devices.show_table_and_select(title="Connected Devices", selection_message="\nSelect a device by S.No to do next actions (or 'q' to quit): ")
        
        
        
        
    def _filter_drones(self, ap_datatable: DataTable):
        self.drone_data = DataTable(headers=["S.No", "BSSID", "ESSID", "Channel", "Power", "DroneType", "Vendor", "Method"])
        if ap_datatable.get_row_count() == 0:
            print("[!] No Access Points found to analyze.")
        for row in ap_datatable.get_all_rows_as_dicts():
            bssid = row.get("BSSID", "")
            if not bssid:
                continue
            result : DroneInfo | None = self.ap_analyzers[0].is_drone(bssid)
            if result is None:
                continue
            self.drone_data.add_row([
                len(self.drone_data.rows) + 1,
                bssid,
                row.get("ESSID", "N/A"),
                row.get("Channel", "N/A"),
                row.get("Power", "N/A"),
                result.drone_type,
                result.vendor,
                result.detection_method
            ])    
    
    
    def _get_connected_devices(self, ap_bssid: str, connected_devices: DataTable):
        """
        Returns a DataTable of devices connected to the given BSSID.
        This is a placeholder implementation; actual implementation may vary.
        """
        ap_bssid = ap_bssid.strip().upper()
        self.connected_devices = DataTable(headers=["Device_MAC", "BSSID"])
        for row in connected_devices.get_all_rows_as_dicts():
            bssid = row.get("BSSID", "").strip().upper()
            if bssid == ap_bssid:
                device_mac = row.get("Station MAC", "N/A")
                self.connected_devices.add_row([device_mac, ap_bssid])            
    
    
    
        
    # def _anaylze_airodump_result(self):
    #     try:
    #         csv_file_path = f"{self.airodump_output_file}-01.csv"
    #         with open(csv_file_path, 'rb') as f_bytes:
    #             lines = f_bytes.read().decode('utf-8', errors='ignore').strip().splitlines()
    #             for line in lines:
    #                 if line.__contains__('BSSID'):
    #                     continue
    #                 if lines.__contains__('Station MAC'):
    #                     continue
    #                 if line is None or line.strip() == "":
    #                     continue
    #                 try:
    #                     import io
    #                     reader = csv.reader(io.StringIO(line))
    #                     row_data = next(reader)
                        
    #                     if len(row_data) >= 13: # this is not needed actually
    #                         ap_bssid = row_data[0].strip()
    #                         if ap_bssid not in self.known_aps:
    #                             ap_info = {
    #                                 "BSSID": ap_bssid,
    #                                 "ESSID": row_data[13].strip() if row_data[13].strip() != "" else "<Hidden>",
    #                                 "Channel": row_data[3].strip(),
    #                                 "Power": row_data[8].strip(),
    #                                 "RawData": row_data
    #                             }
    #                             self.known_aps[ap_bssid] = ap_info
    #                             self._analyze_ap_for_drone(ap_info)
    #                 except csv.Error:
    #                     pass
    #     except Exception as e:
    #         print(f"[!] Error in _anaylze_airodump_result: {e}")
    #         pass

    # def _monitor_airodump_output(self):
    #     """
    #     Internal method to continuously monitor and parse airodump-ng CSV output file live.
    #     Runs in a separate thread.
    #     """
    #     csv_file_path = f"{self.airodump_output_file}-01.csv"
    #     last_read_byte = 0
        
    #     print(f"\n[*] Monitoring airodump-ng CSV: {csv_file_path}")

    #     # The loop condition is correct
    #     while not self.stop_scan_event.is_set():
    #         # Check if the airodump-ng process is still running
    #         if self.airodump_process and self.airodump_process.poll() is not None:
    #             print("[!] airodump-ng process has terminated unexpectedly.")
    #             self.stop_scan_event.set()
    #             break
            
    #         # Wait for file to exist
    #         if not os.path.exists(csv_file_path):
    #             time.sleep(1)
    #             continue
            
    #         try:
    #             # The file reading logic looks correct, reading from the last known position.
    #             with open(csv_file_path, 'rb') as f_bytes:
    #                 f_bytes.seek(last_read_byte)
    #                 new_content_bytes = f_bytes.read()
    #                 last_read_byte = f_bytes.tell()

    #                 if not new_content_bytes:
    #                     time.sleep(1)
    #                     continue
                    
    #                 new_content = new_content_bytes.decode('utf-8', errors='ignore')
    #                 lines = new_content.strip().splitlines()
    #                 ap_section_started = False
                    
    #                 for line in lines:
    #                     if line.startswith("BSSID,"):
    #                         ap_section_started = True
    #                         continue
    #                     if line.startswith("Station MAC,"):
    #                         ap_section_started = False
    #                         break
                        
    #                     if ap_section_started and line.strip():
    #                         try:
    #                             import io
    #                             reader = csv.reader(io.StringIO(line))
    #                             row_data = next(reader)

    #                             if len(row_data) >= 17:
    #                                 ap_bssid = row_data[0].strip()
    #                                 # ... rest of parsing logic ...
    #                                 if ap_bssid not in self.known_aps:
    #                                     ap_info = {
    #                                         "BSSID": ap_bssid,
    #                                         "ESSID": row_data[13].strip() if row_data[13].strip() != "" else "<Hidden>",
    #                                         "Channel": row_data[3].strip(),
    #                                         "Power": row_data[8].strip(),
    #                                         "RawData": row_data
    #                                     }
    #                                     self.known_aps[ap_bssid] = ap_info
    #                                     self._analyze_ap_for_drone(ap_info)
    #                         except csv.Error:
    #                             pass
    #                         except Exception as e:
    #                             print(f"[!] Warning: Error parsing AP line: {line} - {e}")
    #                             pass
                
    #         except FileNotFoundError:
    #             pass
    #         except Exception as e:
    #             print(f"\n[!] Error reading airodump-ng CSV: {e}")
            
    #         time.sleep(1) # Wait before checking for new content again

    #     print("[*] AP scan monitoring thread stopped.")

    # def _analyze_ap_for_drone(self, ap_data: Dict[str, Any]):
    #     """
    #     Runs the AP data through all registered drone analyzers.
    #     If a drone is detected, adds it to `detected_drones` and prints an alert.
    #     """
    #     for analyzer in self.ap_analyzers:
    #         detection_result = analyzer.analyze(ap_data)
    #         if detection_result and detection_result.get("is_drone"):
    #             drone_bssid = ap_data["BSSID"]
    #             if drone_bssid not in self.detected_drones:
    #                 # Construct drone info with a unique S.No for selection later
    #                 s_no = len(self.detected_drones) + 1 
    #                 drone_info = {
    #                     "S.No": s_no, # Add S.No for selection
    #                     "BSSID": drone_bssid,
    #                     "ESSID": ap_data.get("ESSID", "N/A"),
    #                     "DroneType": detection_result.get("drone_type", "Unknown"),
    #                     "Vendor": detection_result.get("vendor", "N/A"),
    #                     "Method": detection_result.get("detection_method", "N/A")
    #                 }
    #                 self.detected_drones[drone_bssid] = drone_info
    #                 # Print an immediate, prominent alert
    #                 sys.stdout.write(f"\n[!!!] DRONE DETECTED: {drone_info.get('DroneType')} ({drone_info.get('Vendor')}) - BSSID: {drone_info.get('BSSID')} (S.No: {drone_info.get('S.No')})\n")
    #                 sys.stdout.write(self.prompt) # Reprint prompt after alert
    #                 sys.stdout.flush()
    #             break # Stop after first analyzer detects it

    def do_show_drones(self, arg):
        """
        Displays currently detected drones.
        Usage: show_drones
        """
        if not self.detected_drones:
            print("[*] No drones detected yet.")
            return

        drone_dt = DataTable(headers=["S.No", "BSSID", "ESSID", "DroneType", "Vendor", "Method"])
        # Populate DataTable from self.detected_drones (which already have S.No)
        for drone_info in self.detected_drones.values():
            drone_dt.add_row([
                drone_info.get("S.No"),
                drone_info.get("BSSID"),
                drone_info.get("ESSID"),
                drone_info.get("DroneType"),
                drone_info.get("Vendor"),
                drone_info.get("Method")
            ])
        drone_dt.print_table(title="Filtered Drone (Detected Drones)")
        if self.current_target_drone:
            print(f"\n[*] Current Target Drone: {self.current_target_drone.get('BSSID')} (Type: {self.current_target_drone.get('DroneType')})")


    def do_show_aps(self, arg):
        """
        Displays all discovered Access Points (including non-drones).
        Usage: show_aps
        """
        if not self.known_aps:
            print("[*] No Access Points discovered yet.")
            return

        ap_dt = DataTable(headers=["S.No", "BSSID", "ESSID", "Channel", "Power", "Is Drone?"])
        s_no_counter = 1
        for ap_bssid, ap_info in self.known_aps.items():
            is_drone = "Yes" if ap_bssid in self.detected_drones else "No"
            ap_dt.add_row([
                s_no_counter,
                ap_info.get("BSSID"),
                ap_info.get("ESSID"),
                ap_info.get("Channel"),
                ap_info.get("Power"),
                is_drone
            ])
            s_no_counter += 1
        ap_dt.print_table(title="Access Point Infos (All Discovered APs)")

    def do_select_drone(self, arg):
        """
        Selects a detected drone as the current target for further processing/attack.
        Usage: select_drone <S.No>
        """
        if not self.detected_drones:
            print("[!] No drones detected yet. Use 'ap_scan' first.")
            return

        # Display detected drones for selection
        drone_dt = DataTable(headers=["S.No", "BSSID", "ESSID", "DroneType", "Vendor"])
        for drone_info in self.detected_drones.values():
            drone_dt.add_row([
                drone_info.get("S.No"),
                drone_info.get("BSSID"),
                drone_info.get("ESSID"),
                drone_info.get("DroneType"),
                drone_info.get("Vendor")
            ])
        drone_dt.print_table(title="Select a Drone to Target")

        if arg: # If an argument is provided, try to use it directly
            try:
                selected_s_no = int(arg)
            except ValueError:
                print("[!] Invalid S.No. Please enter a number from the table.")
                return
        else: # Otherwise, prompt interactively
            while True:
                choice = input("\nEnter S.No of drone to select (or 'q' to cancel): ").strip().lower()
                if choice == 'q':
                    print("[*] Drone selection cancelled.")
                    self.current_target_drone = None # Clear target if cancelled
                    return
                if not choice.isdigit():
                    print("[!] Please enter a valid S.No or 'q'.")
                    continue
                selected_s_no = int(choice)
                break
        
        selected_drone_info = None
        for drone_info in self.detected_drones.values():
            if drone_info.get("S.No") == selected_s_no:
                selected_drone_info = drone_info
                break

        if selected_drone_info:
            self.current_target_drone = selected_drone_info
            print(f"[*] Drone '{selected_drone_info.get('ESSID')} ({selected_drone_info.get('BSSID')})' selected as current target.")
            print(f"[*] Context set for: {self.current_target_drone.get('DroneType')} from {self.current_target_drone.get('Vendor')}")
        else:
            print(f"[!] S.No {selected_s_no} not found in detected drones. Please select a valid S.No.")
            self.current_target_drone = None # Ensure no invalid target is set

    def complete_select_drone(self, text, line, begidx, endidx):
        if not self.detected_drones:
            return []
        
        # Suggest S.No values for detected drones
        s_nos = [str(d.get("S.No")) for d in self.detected_drones.values() if str(d.get("S.No")).startswith(text)]
        return s_nos
    
    
    def do_list_attacks(self, arg):
        """
        Lists all available attacks based on the selected drone.
        Usage: list_attacks
        """
        # if not self.current_target_drone:
        #     print("[!] No drone selected. Use 'select_drone' first.")
        #     return
        self.attack_factory = get_attack_factory()
        supported_attacks : List[AttackType] = self.attack_factory.get_supported_attacks(Manufacturer.PARROT, ParrotModel.AR2.value)
        print("\n--- Available Attacks for Selected Drone ---")
        for attack in supported_attacks:
            print(f"- {attack.name} ({attack.value})")
            
        attack_type = input("Enter the attack type number").strip().upper()
        
        attack  = self.attack_factory.create(Manufacturer.PARROT, ParrotModel.AR2.value, AttackType.ARP_SPOOF, DroneTargetInfo("", "", "", "", "", 1))
        if not attack:
            print("[!] Invalid attack type selected.")
            return
        result = attack.attack()



    def do_scan(self, arg):
        """
        Performs a scan.
        Usage: scan --wifi
        """
        args = shlex.split(arg)
        if "--wifi" in args:
            print("Scanning wifi frequencies....")
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
        self._stop_scan_internal() # Ensure any active scan is stopped before quitting
        print("Exiting Skyfall. Goodbye!")
        return True 
    
    def do_exit(self, line):
        """Exit the CLI."""
        self._stop_scan_internal() # Ensure any active scan is stopped before exiting
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