import subprocess
from utils import DataTable


class WifiCardHandler:
    def __init__(self):
        self.table = DataTable(headers=["S.No", "Interface", "Mode", "BSSID"])

    def get_wifi_cards(self) -> DataTable:
        """List wireless interfaces using `iw dev` and return as DataTable."""
        try:
            result = subprocess.run(['iw', 'dev'], capture_output=True, text=True, check=True)
            output_lines = result.stdout.splitlines()
            interfaces = []

            current_iface = None
            mode = None
            mac = None

            for line in output_lines:
                line = line.strip()
                if line.startswith("Interface"):
                    current_iface = line.split()[1]
                elif line.startswith("type") and current_iface:
                    mode = line.split()[1]
                elif line.startswith("addr") and current_iface:
                    mac = line.split()[1]
                    interfaces.append((current_iface, mode, mac))
                    current_iface = None  # Reset for next block

            # Fill the DataTable
            self.table = DataTable(headers=["S.No", "Interface", "Mode", "BSSID"])
            for idx, (iface, mode, bssid) in enumerate(interfaces, 1):
                self.table.add_row([idx, iface, mode, bssid])
            return self.table

        except subprocess.CalledProcessError as e:
            print(f"[!] Failed to get WiFi interfaces: {e}")
            return self.table

    def toggle_mode_airmon(self, iface_row: dict):
        """
        Toggle interface mode using airmon-ng.
        Detects interface renaming using BSSID tracking.
        """
        old_iface = iface_row["Interface"]
        mode = iface_row["Mode"]
        bssid = iface_row["BSSID"]

        # Snapshot of interfaces before toggle
        before = self.get_interface_mac_mapping()

        if mode == "managed":
            print(f"[*] Interface {old_iface} is in MANAGED mode. Switching to MONITOR mode...")
            self.enable_monitor_mode_airmon(old_iface)
        elif mode == "monitor":
            print(f"[*] Interface {old_iface} is in MONITOR mode. Reverting to MANAGED mode...")
            self.disable_monitor_mode_airmon(old_iface)
        else:
            print(f"[!] Unknown mode '{mode}' for interface {old_iface}.")
            return

        # Snapshot after toggling
        after = self.get_interface_mac_mapping()
        new_iface = self.get_iface_by_mac(after, bssid)

        if new_iface and new_iface != old_iface:
            print(f"[i] Interface name changed from {old_iface} ➜ {new_iface}")
        elif new_iface:
            print(f"[i] Interface name remains unchanged: {new_iface}")
        else:
            print("[!] Could not verify interface rename.")

    def enable_monitor_mode_airmon(self, iface: str):
        print("[*] Killing interfering processes (airmon-ng check kill)...")
        subprocess.run(['sudo', 'airmon-ng', 'check', 'kill'])

        print(f"[*] Enabling monitor mode on {iface} using airmon-ng...")
        subprocess.run(['sudo', 'airmon-ng', 'start', iface])

    def disable_monitor_mode_airmon(self, iface: str):
        print(f"[*] Disabling monitor mode on {iface} using airmon-ng...")
        subprocess.run(['sudo', 'airmon-ng', 'stop', iface])

        print("[*] Restarting networking services...")
        subprocess.run(['sudo', 'systemctl', 'start', 'NetworkManager'])
        subprocess.run(['sudo', 'systemctl', 'start', 'wpa_supplicant'])

    def get_interface_mac_mapping(self) -> dict:
        """Returns { interface_name: mac_address } mapping from iw dev."""
        mapping = {}
        try:
            result = subprocess.run(['iw', 'dev'], capture_output=True, text=True, check=True)
            current_iface = None

            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("Interface"):
                    current_iface = line.split()[1]
                elif line.startswith("addr") and current_iface:
                    mac = line.split()[1]
                    mapping[current_iface] = mac
                    current_iface = None
        except subprocess.CalledProcessError:
            pass

        return mapping

    def get_iface_by_mac(self, mapping: dict, mac: str) -> str | None:
        """Return interface name from MAC address."""
        for iface, bssid in mapping.items():
            if bssid.lower() == mac.lower():
                return iface
        return None
