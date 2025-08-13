from abc import ABC, abstractmethod
import re
from typing import Optional
from shared import AccessPoint, DroneInfo
from shared import Manufacturer, Model

class APAnalyzer(ABC):
    @abstractmethod
    def analyze(self, ap: AccessPoint) -> Optional[DroneInfo]: ...
    @abstractmethod
    def is_drone(self, bssid: str) -> Optional[DroneInfo]: ...

class MacVendorLookup:
    def __init__(self):
        self.drone_mac_prefixes = {
            "90:03:B7": "Parrot SA (Bebop/Anafi)",
            "A0:14:3D": "Parrot SA (AR series)",
            "00:12:1C": "DJI Technology Co., Ltd.",
            "60:60:1F": "DJI Technology Co., Ltd.",
            "D8:8C:7A": "Autel Robotics",
            "C4:4E:AC": "Yuneec International",
        }
    def get_vendor_info(self, mac: str) -> Optional[str]:
        if not mac or len(mac) < 8: return None
        return self.drone_mac_prefixes.get(mac[:8].upper())

class ParrotDroneAnalyzer(APAnalyzer):
    """Detect Parrot by OUI and by ESSID patterns (ardrone, bebop, anafi)."""
    def __init__(self):
        self.mac_lookup = MacVendorLookup()
        self.ouis = {"90:03:B7", "A0:14:3D"}
        self.ssid_re = re.compile(r"(ardrone|bebop|anafi)", re.IGNORECASE)

    def analyze(self, ap: AccessPoint) -> Optional[DroneInfo]:
        if not ap or not ap.bssid: return None
        oui = ap.bssid[:8].upper()
        if oui in self.ouis:
            vendor = self.mac_lookup.get_vendor_info(ap.bssid) or "Parrot"
            return DroneInfo(True, drone_type=Manufacturer.PARROT, model=Model.PARROT_AR2, vendor=vendor, detection_method="MAC OUI")
        if ap.essid and self.ssid_re.search(ap.essid):
            return DroneInfo(True, drone_type=Manufacturer.PARROT, model=Model.PARROT_AR2, vendor="Parrot (ESSID pattern)", detection_method="ESSID pattern")
        return None

    def is_drone(self, bssid: str) -> Optional[DroneInfo]:
        if not bssid: return None
        oui = bssid[:8].upper()
        if oui in self.ouis:
            vendor = self.mac_lookup.get_vendor_info(bssid) or "Parrot"
            return DroneInfo(True, drone_type=Manufacturer.PARROT, model=Model.PARROT_AR2, vendor=vendor, detection_method="MAC OUI")
        return None

# Add more analysers (DJI, Autel, …) implementing APAnalyzer