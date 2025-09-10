import os
from typing import Tuple
from .datatable import DataTable
import csv

def load_shell_binaries() -> list[str]:
    """
    Loads common shell binaries from typical PATH locations.
    This is a simplified example. A more robust version might parse $PATH
    and check for executable files in each directory.
    """
    common_paths = ['/usr/local/bin', '/usr/bin', '/bin', '/sbin', '/usr/sbin']
    binaries = set()
    for path in common_paths:
        if os.path.isdir(path):
            try:
                for item in os.listdir(path):
                    full_path = os.path.join(path, item)
                    if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                        binaries.add(item)
            except PermissionError:
                # Handle cases where the script might not have permission to list a directory
                pass
    # Add some very common built-in commands that might not be in PATH directories
    binaries.update(["ls", "cd", "pwd", "echo", "cat", "grep", "mv", "cp", "rm", "mkdir", "rmdir", "which", "man"])
    return sorted(list(binaries))


def convert_airodump_csv_to_datatables(csv_file_path: str) -> Tuple[DataTable, DataTable]:
    """
    Converts airodump-ng CSV output into two DataTables: AP info and Station info.
    Returns: (ap_datatable, station_datatable)
    """
    ap_headers = ["BSSID", "First_Seen", "Last_Seen", "Channel", "Speed", "Privacy", "Cipher", "Authentication", "Power", "Beacons", "IV", "LAN_IP", "ID_Length", "ESSID", "Key"]
    station_headers = ["Station MAC", "First_Seen", "Last_Seen", "Power", "Packets", "BSSID", "Probed ESSIDs"]
    ap_datatable = DataTable(headers=ap_headers)
    station_datatable = DataTable(headers=station_headers)
    try:
        with open(csv_file_path, 'r') as f:
            reader = csv.reader(f)
            is_ap_section = False
            is_station_section = False

            for row in reader:
                if not row or len(row) < 2:
                    continue  # Skip empty/malformed rows
                first_cell = row[0].strip()
                if first_cell == "BSSID":
                    is_ap_section = True
                    is_station_section = False
                    continue
                if first_cell == "Station MAC":
                    is_ap_section = False
                    is_station_section = True
                    continue
                if is_ap_section:
                    if len(row) >= len(ap_headers):
                        ap_datatable.add_row(row[:len(ap_headers)])
                elif is_station_section:
                    if len(row) >= len(station_headers):
                        station_datatable.add_row(row[:len(station_headers)])
    except Exception as e:
        print(f"[!] Error in convert_airodump_csv_to_datatables: {e}")
    return ap_datatable, station_datatable