from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union
from ..enums.interface_mode import InterfaceMode


@dataclass
class AttackResult:
    status: bool
    stdout: str
    stderr: str
    message: str = ""


@dataclass
class InterfaceInfo:
    """Represents a Wi‑Fi interface and its evolving state."""
    iface_name: str                           # current/active name (always use this for commands)
    original_name: Optional[str] = None       # first-seen name
    monitor_name: Optional[str] = None        # typical renamed mon iface (e.g., wlan0mon)
    is_name_changed: bool = False
    mode: InterfaceMode = InterfaceMode.MANAGED
    bssid: Optional[str] = None               # MAC of the NIC
    channel: Optional[int] = None

    @classmethod
    def from_row(cls, row: dict) -> "InterfaceInfo":
        name = row.get("Updated_Interface") or row.get("Interface")
        if not name:
            raise ValueError("Interface name is required to create InterfaceInfo.")
        return cls(
            iface_name=name,
            original_name=row.get("Interface"),
            monitor_name=(name if name != row.get("Interface") else None),
            is_name_changed=(name != row.get("Interface")),
            mode=InterfaceMode.MONITOR if str(row.get("Mode","")).lower() == "monitor" else InterfaceMode.MANAGED,
            bssid=row.get("BSSID"),
        )


@dataclass
class DroneTargetInfo:
    drone_mac: Optional[str] = None
    controller_mac: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    interface: Optional[InterfaceInfo] = None
    channel: Optional[int] = None
    ssid: Optional[str] = None
    use_sudo: bool = True
    ip_through_drone_ap: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)



