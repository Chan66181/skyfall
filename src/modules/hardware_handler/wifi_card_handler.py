# import subprocess
# import re 
# import time 
# from typing import Optional, List, Dict, Union 
# from shared import DataTable
# import os
# import signal
# import threading

# class WifiCardHandler:
#     def __init__(self):
#         self.table = DataTable(headers=["S.No", "Interface", "Mode", "BSSID", "Updated_Interface"])

#     def _run_command(self, command_list: List[str], description: str = "Executing command") -> Optional[str]:
#         print(f"[*] {description}: {' '.join(command_list)}")
#         try:
#             result = subprocess.run(command_list, capture_output=True, text=True, check=True, timeout=20)
#             if result.stderr:
#                 print(f"[i] STDERR ({' '.join(command_list)}):\n{result.stderr.strip()}")
#             return result.stdout.strip()
#         except subprocess.TimeoutExpired as e:
#             print(f"[!] Command '{command_list[0]}' execution is stopped after 20 seconds\n")
#             return ''
#         except subprocess.CalledProcessError as e:
#             print(f"[!] Command failed: {' '.join(command_list)}\nSTDOUT: {e.stdout.strip()}\nSTDERR: {e.stderr.strip()}")
#             return None
#         except FileNotFoundError:
#             print(f"[!] Error: Command '{command_list[0]}' not found. Is it installed and in your PATH?")
#             return None
        
        
        
#     # def run_command_in_background(self, command_list: List[str], description: str = "Executing command"):
#     #     thread = threading.Thread(target=self._run_command, args=(command_list, description))
#     #     thread.start()


#     def get_wifi_cards(self) -> DataTable:
#         output = self._run_command(['iw', 'dev'], "Getting WiFi interface details")
        
#         self.table = DataTable(headers=["S.No", "Interface", "Mode", "BSSID", "Updated_Interface"])
#         if not output:
#             return self.table

#         interfaces_raw_data = []
#         current_iface_info = {}

#         # Split output by blocks related to interface or phy
#         blocks = re.split(r'(?m)^(\s*phy#\S+|\s*Interface\s+\S+)', output)
        
#         # Iterate through block pairs (header + content)
#         for i in range(1, len(blocks), 2): # Increment by 2 to get header and content
#             block_header = blocks[i].strip()
#             if i + 1 >= len(blocks): # Ensure there's content for this header
#                 continue
#             block_content = blocks[i+1]
            
#             if block_header.startswith("Interface"):
#                 current_iface_info = {"Interface": block_header.split()[1]}
#             elif block_header.startswith("phy#"):
#                 # If a phy block starts, reset current_iface_info as it's a new device scope
#                 current_iface_info = {}
#                 # Extract interface name if it's directly under phy# (e.g., "phy#0\n\tInterface wlan0")
#                 if "Interface" in block_content:
#                     iface_line = next((line for line in block_content.splitlines() if line.strip().startswith("Interface")), None)
#                     if iface_line:
#                         current_iface_info["Interface"] = iface_line.strip().split()[1]
#                 else:
#                     continue # Skip if no interface immediately under phy# for this block
#             else:
#                 continue

#             for line in block_content.splitlines():
#                 line = line.strip()
                
#                 # If an Interface line appears within a block, it defines the current interface
#                 if line.startswith("Interface"):
#                     if "Interface" in current_iface_info and "BSSID" in current_iface_info and "Mode" in current_iface_info:
#                         interfaces_raw_data.append(current_iface_info.copy()) # Use .copy() to avoid modifying appended dict
#                     current_iface_info = {"Interface": line.split()[1]}
#                 elif line.startswith("addr"):
#                     match = re.search(r'addr\s+([0-9a-fA-F:]{17})', line)
#                     if match:
#                         current_iface_info["BSSID"] = match.group(1)
#                 elif line.startswith("type"):
#                     match = re.search(r'type\s+(\S+)', line)
#                     if match:
#                         current_iface_info["Mode"] = match.group(1)

#             # After processing all lines in a block, add the interface if complete
#             if "Interface" in current_iface_info and "BSSID" in current_iface_info and "Mode" in current_iface_info:
#                 interfaces_raw_data.append(current_iface_info.copy()) # Use .copy()

#         # Filter for unique interfaces, preferring more complete info if duplicates
#         unique_interfaces = {}
#         for info in interfaces_raw_data:
#             iface_name = info['Interface']
#             # Only add if it's new or if the current info is more complete
#             if iface_name not in unique_interfaces or \
#                (len(info) > len(unique_interfaces[iface_name]) and 'BSSID' in info and 'Mode' in info):
#                 unique_interfaces[iface_name] = info
        
#         for idx, iface_info in enumerate(unique_interfaces.values(), 1):
#             self.table.add_row([
#                 idx, 
#                 iface_info.get("Interface", "N/A"), 
#                 iface_info.get("Mode", "N/A"), 
#                 iface_info.get("BSSID", "N/A"),
#                 iface_info.get("Interface", "N/A") # Initialize Updated_Interface with current name
#             ])
#         return self.table

#     def toggle_mode_airmon(self, iface_row: Dict[str, Union[str, int, None]]):
#         old_iface_name = iface_row.get("Interface")
#         current_mode = iface_row.get("Mode")
#         bssid = iface_row.get("BSSID")
#         s_no = iface_row.get("S.No")

#         if not all([old_iface_name, current_mode, bssid, s_no is not None]):
#             print("[!] Missing required information for toggling mode. Please select a valid interface.")
#             return

#         # Ensure types are correct for subprocess calls
#         old_iface_name_str = str(old_iface_name)
#         bssid_str = str(bssid)
#         s_no_int = int(s_no)

#         before_toggle_mac_map = self.get_interface_mac_mapping()
        
#         success = False
#         if current_mode == "managed":
#             print(f"[*] Interface {old_iface_name_str} is in MANAGED mode. Switching to MONITOR mode...")
#             success = self.enable_monitor_mode_airmon(old_iface_name_str)
#         elif current_mode == "monitor":
#             print(f"[*] Interface {old_iface_name_str} is in MONITOR mode. Reverting to MANAGED mode...")
#             success = self.disable_monitor_mode_airmon(old_iface_name_str)
#         else:
#             print(f"[!] Unknown or unsupported mode '{current_mode}' for interface {old_iface_name_str}.")
#             return

#         if not success:
#             print(f"[!] Failed to toggle mode for {old_iface_name_str}. Table not updated.")
#             return

#         time.sleep(2) # Give the system a moment to update interface states

#         after_toggle_mac_map = self.get_interface_mac_mapping()
        
#         new_iface_name = self.get_iface_by_mac(after_toggle_mac_map, bssid_str)

#         if new_iface_name:
#             if new_iface_name != old_iface_name_str:
#                 print(f"[i] Interface name changed from {old_iface_name_str} ➜ {new_iface_name}")
#             else:
#                 print(f"[i] Interface name remains unchanged: {new_iface_name}")
            
#             target_mode = "monitor" if current_mode == "managed" else "managed"
#             self.table.update_row_by_sno(s_no_int, {
#                 "Mode": target_mode,
#                 "Updated_Interface": new_iface_name
#             })
#             print(f"[*] DataTable updated for S.No {s_no_int}: Interface='{old_iface_name_str}' -> '{new_iface_name}', Mode='{current_mode}' -> '{target_mode}'")
#         else:
#             print(f"[!] Could not find interface with BSSID {bssid_str} after toggling mode.")
#             print("[!] This might mean the interface was removed, renamed to something unexpected, or BSSID changed (unlikely for card's MAC).")

#     def enable_monitor_mode_airmon(self, iface: str) -> bool:
#         print("[*] Stopping interfering processes (airmon-ng check kill)...")
#         if self._run_command(['sudo', 'airmon-ng', 'check', 'kill'], "Running airmon-ng check kill") is None:
#             return False

#         print(f"[*] Enabling monitor mode on {iface} using airmon-ng...")
#         output = self._run_command(['sudo', 'airmon-ng', 'start', iface], f"Starting airmon-ng on {iface}")
#         if output is None:
#             return False
        
#         match = re.search(r'\(mac80211 monitor mode enabled for \[phy\d+\]\S+ on \[phy\d+\](\S+)\)', output)
#         if match:
#             new_iface = match.group(1)
#             print(f"[i] airmon-ng reports new monitor interface as: {new_iface}")
#         else:
#             print("[!] Could not reliably parse new monitor interface name from airmon-ng output.")
        
#         return True

#     def disable_monitor_mode_airmon(self, iface: str) -> bool:
#         print(f"[*] Disabling monitor mode on {iface} using airmon-ng...")
#         if self._run_command(['sudo', 'airmon-ng', 'stop', iface], f"Stopping airmon-ng on {iface}") is None:
#             return False

#         print("[*] Restarting networking services (NetworkManager, wpa_supplicant)...")
#         self._run_command(['sudo', 'systemctl', 'start', 'NetworkManager'], "Starting NetworkManager")
#         self._run_command(['sudo', 'systemctl', 'start', 'wpa_supplicant'], "Starting wpa_supplicant")
#         return True

#     def get_interface_mac_mapping(self) -> Dict[str, str]:
#         mapping = {}
#         output = self._run_command(['iw', 'dev'], "Getting current interface MAC mapping")
#         if not output:
#             return mapping

#         current_iface = None
#         # Improved parsing to handle complex iw dev output
#         lines = output.splitlines()
#         i = 0
#         while i < len(lines):
#             line = lines[i].strip()
#             if line.startswith("Interface"):
#                 current_iface = line.split()[1]
#                 # Look for 'addr' in the subsequent lines of this interface's block
#                 j = i + 1
#                 while j < len(lines) and not lines[j].strip().startswith("Interface") and not lines[j].strip().startswith("phy#"):
#                     if lines[j].strip().startswith("addr"):
#                         mac_match = re.search(r'addr\s+([0-9a-fA-F:]{17})', lines[j].strip())
#                         if mac_match and current_iface:
#                             mapping[current_iface] = mac_match.group(1)
#                         break # Found MAC, move to next interface block
#                     j += 1
#                 current_iface = None # Reset for next interface block
#             i += 1
#         return mapping


#     def get_iface_by_mac(self, mapping: Dict[str, str], mac: str) -> Optional[str]:
#         for iface, bssid in mapping.items():
#             if bssid.lower() == mac.lower():
#                 return iface
#         return None
        
#     def start_airodump_scan(self, interface: str, output_prefix: str = "airodump_output") -> Optional[subprocess.Popen]:
#         # Clean up old airodump-ng output files before starting a new scan
#         for ext in ['.csv', '.kismet.csv', '.log', '.cap']:
#             file_path = f"{output_prefix}{ext}" # change the file name getting part.
#             if os.path.exists(file_path):
#                 try:
#                     os.remove(file_path)
#                     print(f"[*] Removed old airodump-ng output file: {file_path}")
#                 except OSError as e:
#                     print(f"[!] Error removing old file {file_path}: {e}")
        
#         command = ['sudo', 'airodump-ng', interface, '-w', output_prefix, '--output-format', 'csv', '--ignore-negative-one']
        
#         # The key fix is here: call _run_command with the correct parameters
#         # The previous code in your screenshot was missing these.
#         process = self._run_command(command, f"Starting airodump-ng on {interface}")
        
#         # if isinstance(process, subprocess.Popen):
#         #     self.airodump_process = process
#         #     print(f"[*] airodump-ng started on {interface}. Output is being written to {output_prefix}-*.csv and monitored.")
#         #     return process
#         # else:
#         #     print("[!] Failed to start airodump-ng. Ensure it's installed and interface is in monitor mode.")
#         #     return None

#     def stop_airodump_scan(self) -> bool:
#         if self.airodump_process and self.airodump_process.poll() is None:
#             print("[*] Stopping airodump-ng process...")
#             try:
#                 # Send SIGTERM to the process group to ensure airodump-ng and any children stop
#                 os.killpg(os.getpgid(self.airodump_process.pid), signal.SIGTERM)
#                 self.airodump_process.wait(timeout=5) # Wait for it to terminate
#                 print("[*] airodump-ng stopped.")
#                 self.airodump_process = None
#                 return True
#             except (ProcessLookupError, subprocess.TimeoutExpired) as e:
#                 print(f"[!] Failed to stop airodump-ng gracefully: {e}. Attempting to kill.")
#                 self.airodump_process.kill() # Force kill if SIGTERM fails
#                 self.airodump_process.wait()
#                 self.airodump_process = None
#                 return True
#             except Exception as e:
#                 print(f"[!] An unexpected error occurred while stopping airodump-ng: {e}")
#                 return False
#         else:
#             print("[*] No active airodump-ng scan to stop.")
#             self.airodump_process = None # Ensure state is consistent
#             return True # If no process, it's considered stopped.


from typing import Tuple, Optional
from typing import Literal
from shared import CommandExecutor
import re
from shared import InterfaceMode


class WifiCardHandler:
    """Query and switch Wi‑Fi interface modes using CommandExecutor."""
    def __init__(self):
        self.exec = CommandExecutor()

    def get_interface_mode(self, interface: str) -> Optional[InterfaceMode]:
        try:
            res = self.exec.execute(["iw", "dev"], timeout=10)
            text = res.stdout
            if f"Interface {interface}" not in text:
                return None
            after = text.split(f"Interface {interface}", 1)[1]
            for line in after.splitlines():
                s = line.strip()
                if s.startswith("type "):
                    return InterfaceMode.MONITOR if s.split()[1].strip().lower() == "monitor" else InterfaceMode.MANAGED
            return None
        except Exception:
            return None

    def _find_interface(self, name: str) -> bool:
        try:
            res = self.exec.execute(["iw", "dev"], timeout=10)
            return f"Interface {name}" in res.stdout
        except Exception:
            return False

    def ensure_mode(
        self,
        interface: str,
        required_mode: InterfaceMode,
        use_sudo: bool = True,
        channel: Optional[int] = None,
    ) -> Tuple[bool, str, str, str, Optional[str]]:
        current = self.get_interface_mode(interface)
        if current == required_mode:
            return True, "", "", f"Interface already in {required_mode} mode", interface
        if required_mode == InterfaceMode.MONITOR:
            return self._to_monitor(interface, use_sudo, channel)
        return self._to_managed(interface, use_sudo)

    def _to_monitor(self, interface: str, use_sudo: bool, channel: Optional[int]):
        out_acc, err_acc = [], []
        r = self.exec.execute(["airmon-ng", "check", "kill"], timeout=15, sudo=use_sudo)
        out_acc.append(r.stdout); err_acc.append(r.stderr)
        r = self.exec.execute(["airmon-ng", "start", interface], timeout=25, sudo=use_sudo)
        out_acc.append(r.stdout); err_acc.append(r.stderr)
        new_iface = interface + "mon" if self._find_interface(interface + "mon") else interface
        if channel is not None:
            try:
                r2 = self.exec.execute(["iw", new_iface, "set", "channel", str(channel)], timeout=5, sudo=use_sudo)
                out_acc.append(r2.stdout); err_acc.append(r2.stderr)
            except Exception:
                pass
        mode = self.get_interface_mode(new_iface)
        ok = (mode == "monitor")
        return ok, "\n".join(out_acc), "\n".join(err_acc), ("Switched to monitor" if ok else "Failed to switch to monitor"), (new_iface if ok else None)

    def _to_managed(self, interface: str, use_sudo: bool):
        out_acc, err_acc = [], []
        try: self.exec.execute(["airmon-ng", "stop", interface], timeout=20, sudo=use_sudo)
        except Exception: pass
        try: self.exec.execute(["airmon-ng", "stop", interface + "mon"], timeout=20, sudo=use_sudo)
        except Exception: pass
        r = self.exec.execute(["ip", "link", "set", interface, "down"], timeout=10, sudo=use_sudo)
        out_acc.append(r.stdout); err_acc.append(r.stderr)
        r = self.exec.execute(["iw", interface, "set", "type", "managed"], timeout=10, sudo=use_sudo)
        out_acc.append(r.stdout); err_acc.append(r.stderr)
        r = self.exec.execute(["ip", "link", "set", interface, "up"], timeout=10, sudo=use_sudo)
        out_acc.append(r.stdout); err_acc.append(r.stderr)
        try:
            self.exec.execute(["systemctl", "start", "NetworkManager"], timeout=10, sudo=use_sudo)
            self.exec.execute(["systemctl", "start", "wpa_supplicant"], timeout=10, sudo=use_sudo)
        except Exception:
            pass
        mode = self.get_interface_mode(interface)
        ok = (mode == "managed")
        return ok, "\n".join(out_acc), "\n".join(err_acc), ("Switched to managed" if ok else "Failed to switch to managed"), (interface if ok else None)

    def parse_ipv4_from_ip(self, iface: str) -> Optional[str]:
        res = self.exec.execute(["ip", "-4", "addr", "show", "dev", iface], timeout=5)
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", res.stdout)
        return m.group(1) if m else None