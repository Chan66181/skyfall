from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class DroneInfo:
    is_drone: bool
    drone_type: str
    vendor: Optional[str] = None
    detection_method: Optional[str] = None


class APAnalyzer(ABC):
        
    @abstractmethod
    def analyze(self, ap_data: Dict[str, Any]) -> DroneInfo | None:
        """
        Analyzes a single AP's data.
        Returns a dictionary with detection results (e.g., {'is_drone': True, 'drone_type': 'Parrot'})
        or None if no drone is detected by this analyzer.
        """
        pass
    
    @abstractmethod
    def is_drone(self, bssid: str) -> DroneInfo | None:
        """
        Checks if the given BSSID belongs to a known drone.
        Returns True if it is a drone, False otherwise.
        """
        pass
    
class MacVendorLookup:
    """
    A utility to look up MAC address prefixes (OUI => Organizationally Unique Identifier) for vendor identification.
    This is a simplified example. A real-world implementation would use a larger,
    regularly updated OUI database.
    """
    def __init__(self):
        # Simplified list of known drone MAC prefixes (OUIs)
        # Format: "OUI": "Vendor Name"
        self.drone_mac_prefixes = {
            "90:03:B7": "Parrot SA (Bebop, Anafi)",
            "A0:14:3D": "Parrot SA (older models)",
            "00:12:1C": "DJI Technology Co., Ltd.",
            "60:60:1F": "DJI Technology Co., Ltd.",
            "D8:8C:7A": "Autel Robotics",
            "C4:4E:AC": "Yuneec International"
            # Add more as needed for your research
        }

    def get_vendor_info(self, mac_address: str) -> Optional[str]:
        """
        Returns the vendor name if the MAC address prefix is known.
        """
        if not mac_address or len(mac_address) < 8: # Need at least 3 octets for OUI
            return None
        
        oui = mac_address[:8].upper() # First 3 octets, uppercase
        return self.drone_mac_prefixes.get(oui)
    
class ParrotDroneAnalyzer(APAnalyzer):
    """
    Analyzes AP data specifically for Parrot drones based on MAC address prefixes.
    """
    def __init__(self):
        self.mac_lookup = MacVendorLookup()
        self.parrot_ouis = ["90:03:B7", "A0:14:3D"] # Specific OUIs for Parrot

    def analyze(self, ap_data: Dict[str, Any]) -> DroneInfo | None:
        bssid = ap_data.get("BSSID")
        if not bssid:
            return None

        oui = bssid[:8].upper()
        if oui in self.parrot_ouis:
            vendor = self.mac_lookup.get_vendor_info(bssid)
            return DroneInfo(is_drone=True, drone_type="Parrot", vendor=vendor if vendor else "Unknown Parrot Model", detection_method="MAC OUI Lookup")
        return None
    
    def is_drone(self, bssid: str) -> DroneInfo | None:
        """
        Checks if the given BSSID belongs to a Parrot drone.
        """
        oui = bssid[:8].upper()
        if oui in self.parrot_ouis:
            vendor = self.mac_lookup.get_vendor_info(bssid)
            return DroneInfo(is_drone=True, drone_type="Parrot", vendor=vendor if vendor else "Unknown Parrot Model", detection_method="MAC OUI Lookup")
        return None

    
# Not needed for now, but can be implemented later    
# class GenericDroneAnalyzer(APAnalyzer):
#     def __init__(self):
#         self.mac_lookup = MacVendorLookup()
#     def analyze(self, ap_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
#         bssid = ap_data.get("BSSID")
#         if not bssid:
#             return None
#         vendor = self.mac_lookup.get_vendor_info(bssid)
#         if vendor and "drone" in vendor.lower():
#             return {
#                 "is_drone": True,
#                 "drone_type": "Generic Drone",
#                 "vendor": vendor,
#                 "detection_method": "Generic MAC OUI Lookup"
#             }
#         return None
    
    