from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union
from ..enums.interface_mode import InterfaceMode
from ..enums.attack_enums import Manufacturer, Model, AttackType
from ..datatable import DataTable


@dataclass
class AttackResult:
    status: bool
    stdout: str
    stderr: str
    message: str = ""


@dataclass
class InterfaceInfo:
    """Represents a Wi-Fi interface and its evolving state (tracked by MAC)."""
    iface_name: str                           # current/active name (always use this for commands)
    original_name: Optional[str] = None       # first-seen name
    monitor_name: Optional[str] = None        # typical renamed mon iface (e.g., wlan0mon)
    is_name_changed: bool = False
    mode: InterfaceMode = InterfaceMode.MANAGED
    bssid: Optional[str] = None               # MAC of the NIC
    channel: Optional[int] = None

    @classmethod
    def from_row(cls, row: dict) -> "InterfaceInfo":
        """
        Build from a table row but don't trust the interface name; we will
        re-resolve by MAC just before actions.
        """
        name = row.get("Updated_Interface") or row.get("Interface") or ""
        mode_raw = str(row.get("Mode", "")).strip().lower()
        mode = InterfaceMode.MONITOR if mode_raw == "monitor" else InterfaceMode.MANAGED
        return cls(
            iface_name=name,
            original_name=row.get("Interface"),
            monitor_name=(name if name and name != row.get("Interface") else None),
            is_name_changed=(bool(name) and name != row.get("Interface")),
            mode=mode,
            bssid=(row.get("BSSID") or row.get("MAC") or row.get("Addr")),
        )

    def to_dict(self) -> dict:
        return {
            "iface_name": self.iface_name,
            "original_name": self.original_name,
            "monitor_name": self.monitor_name,
            "is_name_changed": self.is_name_changed,
            "mode": self.mode.value if hasattr(self.mode, "value") else str(self.mode),
            "bssid": self.bssid,
            "channel": self.channel,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "InterfaceInfo":
        mode_raw = d.get("mode", InterfaceMode.MANAGED)
        mode = mode_raw
        # accept value/name/str
        try:
            if isinstance(mode_raw, str):
                # try by name first, then by raw value
                try:
                    mode = InterfaceMode[mode_raw]
                except KeyError:
                    mode = InterfaceMode(mode_raw)
        except Exception:
            mode = InterfaceMode.MANAGED
        return cls(
            iface_name=d.get("iface_name",""),
            original_name=d.get("original_name"),
            monitor_name=d.get("monitor_name"),
            is_name_changed=bool(d.get("is_name_changed", False)),
            mode=mode,
            bssid=d.get("bssid"),
            channel=d.get("channel"),
        )

        
@dataclass
class DroneTargetInfo:
    drone_mac: Optional[str] = None
    controller_mac: Optional[str] = None
    manufacturer: Optional[Manufacturer] = None
    model: Optional[Model] = None
    interface: Optional[InterfaceInfo] = None
    channel: Optional[int] = None
    ssid: Optional[str] = None
    use_sudo: bool = True
    ip_through_drone_ap: Optional[str] = None   #TODO Move it to interface info if its interface MAC
    data: Dict[str, Any] = field(default_factory=dict) 
    
    def to_dict(self) -> dict:
        return {
            "drone_mac": self.drone_mac,
            "controller_mac": self.controller_mac,
            "manufacturer": self.manufacturer.value,
            "model": self.model.value,
            "interface": self.interface.to_dict() if self.interface else None,
            "channel": self.channel,
            "ssid": self.ssid,
            "use_sudo": self.use_sudo,
            "ip_through_drone_ap": self.ip_through_drone_ap,
            "data": self.data or {},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DroneTargetInfo":
        # interface_mode could be a value or name
        im_raw = d.get("interface_mode", InterfaceMode.MANAGED)
        im = im_raw
        try:
            if isinstance(im_raw, str):
                try:
                    im = InterfaceMode[im_raw]
                except KeyError:
                    im = InterfaceMode(im_raw)
        except Exception:
            im = InterfaceMode.MANAGED

        iface = d.get("interface")
        iface_obj = InterfaceInfo.from_dict(iface) if isinstance(iface, dict) else None

        return cls(
            drone_mac=d.get("drone_mac"),
            controller_mac=d.get("controller_mac"),
            manufacturer=Manufacturer(d.get("manufacturer")),
            model=Model(d.get("model")),
            interface=iface_obj,
            channel=d.get("channel"),
            ssid=d.get("ssid"),
            use_sudo=bool(d.get("use_sudo", True)),
            ip_through_drone_ap=d.get("ip_through_drone_ap"),
            data=d.get("data") or {},
        )

@dataclass
class AirodumpResult:
    success: bool
    message: str
    csv_path: Optional[str] = None
    cap_path: Optional[str] = None
    logs: Optional[str] = None
    errors: Optional[str] = None


@dataclass
class DroneInfo:
    is_drone: bool
    drone_type: Manufacturer
    model: Model
    vendor: Optional[str] = None
    detection_method: Optional[str] = None

@dataclass
class AccessPoint:
    bssid: str
    first_seen: str
    last_seen: str
    channel: Optional[int]
    speed: Optional[str]
    privacy: Optional[str]
    cipher: Optional[str]
    auth: Optional[str]
    power: Optional[int]
    beacons: Optional[int]
    iv: Optional[str]
    lan_ip: Optional[str]
    id_length: Optional[int]
    essid: str
    key: Optional[str]
    raw: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Station:
    station_mac: str
    first_seen: str
    last_seen: str
    power: Optional[int]
    packets: Optional[int]
    bssid: Optional[str]   # AP BSSID (or "not associated")
    probed_essids: Optional[str]
    raw: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DroneAPResult:
    drone_ap: Optional[AccessPoint]
    connected_devices: List[Station]
    info: Optional[DroneInfo] = None
    source_csv: Optional[str] = None
    
def results_to_datatable(results: List[DroneAPResult]) -> DataTable:
    table = DataTable(headers=["S.No", "BSSID", "ESSID", "Channel", "Vendor", "Detected By", "Clients"])
    for i, res in enumerate(results, 1):
        ap = res.drone_ap
        if not ap:
            continue
        vendor = res.info.vendor if res.info else "Unknown"
        det = res.info.detection_method if res.info else "-"
        clients = len(res.connected_devices) if res.connected_devices else 0
        table.add_row([
            i,
            ap.bssid,
            ap.essid or "<hidden>",
            ap.channel if ap.channel is not None else "-",
            vendor,
            det,
            clients
        ])
    return table

def stations_to_datatable(stations: List[Station]) -> DataTable:
    table = DataTable(headers=["S.No", "Station MAC", "Power", "Packets", "Probed ESSIDs"])
    for i, s in enumerate(stations, 1):
        table.add_row([
            i,
            s.station_mac,
            s.power if s.power is not None else "-",
            s.packets if s.packets is not None else "-",
            (s.probed_essids or "").strip() or "-"
        ])
    return table

def build_target_info_from_selection(
    chosen: DroneAPResult,
    iface: InterfaceInfo,
    controller_mac: Optional[str],
    use_sudo: bool = True
) -> DroneTargetInfo: # TODO Fix this part and also update all the other values and update the datacalss and enums to be consistent
    if not chosen or chosen.drone_ap is None or chosen.info is None or chosen.info.drone_type is None:
        return DroneTargetInfo()
    return DroneTargetInfo(
        drone_mac=chosen.drone_ap.bssid,
        controller_mac=controller_mac,
        manufacturer=chosen.info.drone_type,
        model=chosen.info.model,
        interface=iface,                      # InterfaceInfo object
        channel=chosen.drone_ap.channel,
        ssid=chosen.drone_ap.essid or None,
        use_sudo=use_sudo,
        ip_through_drone_ap=None,
        data={}
    )