from typing import List, Tuple, Optional
from typing import Literal
from shared import CommandExecutor, DataTable
import re
from shared import InterfaceMode


# TODO: Create a template for this like the attack modules, so that it will register automatically and will be available via factory for scanning the interface

class WifiCardHandler:
    """Query and switch Wi‑Fi interface modes using CommandExecutor."""
    def __init__(self):
        self.exec = CommandExecutor()
        
    def get_wifi_cards(self) -> DataTable:
        """Return a DataTable of Wi‑Fi interfaces with Interface/Mode/BSSID and an Updated_Interface column."""
        from shared import DataTable  # if not already imported module-wide

        table = DataTable(headers=["S.No", "Interface", "Mode", "BSSID", "Updated_Interface"])
        try:
            res = self.exec.execute(["iw", "dev"], timeout=10)
            output = res.stdout or ""
        except Exception:
            return table

        if not output.strip():
            return table

        interfaces_raw = []
        lines = output.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("Interface "):
                iface = line.split()[1]
                mode = None
                bssid = None
                j = i + 1
                while j < len(lines):
                    s = lines[j].strip()
                    if s.startswith("Interface ") or s.startswith("phy#"):
                        break
                    if s.startswith("type "):
                        parts = s.split()
                        if len(parts) >= 2:
                            mode = parts[1]
                    elif s.startswith("addr "):
                        m = re.search(r"addr\s+([0-9a-fA-F:]{17})", s)
                        if m:
                            bssid = m.group(1)
                    j += 1
                if iface and mode and bssid:
                    interfaces_raw.append({"Interface": iface, "Mode": mode, "BSSID": bssid})
                i = j
                continue
            i += 1

        unique: dict[str, dict] = {}
        for info in interfaces_raw:
            name = info["Interface"]
            if name not in unique or len(info) > len(unique[name]):
                unique[name] = info

        for idx, info in enumerate(unique.values(), 1):
            table.add_row([
                idx,
                info.get("Interface", "N/A"),
                info.get("Mode", "N/A"),
                info.get("BSSID", "N/A"),
                info.get("Interface", "N/A"),
            ])

        return table


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

    def ensure_mode_by_mac(
        self,
        mac: str,
        required_mode: InterfaceMode,
        use_sudo: bool = True,
        channel: Optional[int] = None,
    ) -> Tuple[bool, str, str, str, Optional[str]]:
        """
        Ensure the interface identified by `mac` is in `required_mode`.
        Returns (ok, stdout, stderr, msg, final_iface_name_if_ok_else_None).
        Resolves the live interface name before and after, so renames are handled.
        """
        mac = self._normalise_mac(mac)
        name = self.resolve_iface_by_mac(mac)
        if not name:
            return False, "", "", f"Could not resolve interface for MAC {mac}", None

        # short-circuit if already in required mode
        current = self.get_interface_mode(name)
        if str(current).lower() == required_mode.value:
            return True, "", "", f"Interface already in {required_mode.value} mode", name

        if required_mode == InterfaceMode.MONITOR:
            return self._to_monitor_by_mac(mac, use_sudo, channel)
        else:
            return self._to_managed_by_mac(mac, use_sudo)

    # ======= MONITOR via MAC =======
    def _to_monitor_by_mac(self, mac: str, use_sudo: bool, channel: Optional[int]):
        out_acc, err_acc = [], []

        # Resolve current name
        name_before = self.resolve_iface_by_mac(mac)
        if not name_before:
            return False, "", "", f"Could not resolve interface for MAC {mac}", None

        # Kill conflicting services and start monitor
        r = self.exec.execute(["airmon-ng", "check", "kill"], timeout=15, sudo=use_sudo)
        self._acc(out_acc, err_acc, r)

        r = self.exec.execute(["airmon-ng", "start", name_before], timeout=25, sudo=use_sudo)
        self._acc(out_acc, err_acc, r)

        # Re-resolve name by MAC in case of rename (e.g., wlan0 -> wlan0mon)
        name_after = self.resolve_iface_by_mac(mac) or name_before

        # Optional: set channel on the *current* name
        if channel is not None:
            try:
                r2 = self.exec.execute(["iw", name_after, "set", "channel", str(channel)], timeout=5, sudo=use_sudo)
                self._acc(out_acc, err_acc, r2)
            except Exception:
                pass

        mode = self.get_interface_mode(name_after)
        ok = mode.value == InterfaceMode.MONITOR.value
        msg = "Switched to monitor" if ok else "Failed to switch to monitor"
        return ok, "\n".join(out_acc), "\n".join(err_acc), msg, (name_after if ok else None)

    # ======= MANAGED via MAC =======
    def _to_managed_by_mac(self, mac: str, use_sudo: bool):
        out_acc, err_acc = [], []

        # Resolve current name
        name = self.resolve_iface_by_mac(mac)
        if not name:
            return False, "", "", f"Could not resolve interface for MAC {mac}", None

        # Try to stop any airmon-created device (both possibilities are cheap)
        try:
            r = self.exec.execute(["airmon-ng", "stop", name], timeout=20, sudo=use_sudo)
            self._acc(out_acc, err_acc, r)
        except Exception:
            pass
        try:
            r = self.exec.execute(["airmon-ng", "stop", name + "mon"], timeout=20, sudo=use_sudo)
            self._acc(out_acc, err_acc, r)
        except Exception:
            pass

        # Re-resolve again (name could have changed back)
        name = self.resolve_iface_by_mac(mac) or name

        # Put interface down -> managed -> up
        r = self.exec.execute(["ip", "link", "set", name, "down"], timeout=10, sudo=use_sudo)
        self._acc(out_acc, err_acc, r)

        r = self.exec.execute(["iw", name, "set", "type", "managed"], timeout=10, sudo=use_sudo)
        self._acc(out_acc, err_acc, r)

        r = self.exec.execute(["ip", "link", "set", name, "up"], timeout=10, sudo=use_sudo)
        self._acc(out_acc, err_acc, r)

        # Bring back services (best-effort)
        try:
            r = self.exec.execute(["systemctl", "start", "NetworkManager"], timeout=10, sudo=use_sudo)
            self._acc(out_acc, err_acc, r)
            r = self.exec.execute(["systemctl", "start", "wpa_supplicant"], timeout=10, sudo=use_sudo)
            self._acc(out_acc, err_acc, r)
        except Exception:
            pass

        # Final check using the *current* name for this MAC
        final_name = self.resolve_iface_by_mac(mac) or name
        mode = self.get_interface_mode(final_name)
        ok = (str(mode.value).lower() == "managed")
        msg = "Switched to managed" if ok else "Failed to switch to managed"
        return ok, "\n".join(out_acc), "\n".join(err_acc), msg, (final_name if ok else None)

    
    def _iw_snapshot(self) -> List[dict]:
        try:
            r = self.exec.execute(["iw", "dev"], timeout=10)
            return self._parse_iw_dev(r.stdout)
        except Exception:
            return []

    def resolve_iface_by_mac(self, mac: str) -> Optional[str]:
        mac = self._normalise_mac(mac)
        if not mac:
            return None
        for itf in self._iw_snapshot():
            if itf.get("mac") == mac:
                return itf.get("name")
        return None

    def _find_interface(self, name: str) -> bool:
        try:
            res = self.exec.execute(["iw", "dev"], timeout=10)
            return f"Interface {name}" in res.stdout
        except Exception:
            return False
        
    def _acc(self, out_acc: list, err_acc: list, result) -> None:
        out_acc.append(result.stdout)
        err_acc.append(result.stderr)

    def get_interface_mode_by_mac(self, mac: str) -> Optional[InterfaceMode]:
        """Resolve name by MAC, then reuse existing mode check."""
        name = self.resolve_iface_by_mac(mac)
        if not name:
            return None
        mode_str = self.get_interface_mode(name)  # your existing function returning "managed"/"monitor"
        return InterfaceMode.MONITOR if str(mode_str).lower() == "monitor" else InterfaceMode.MANAGED

    def _find_interface(self, name: str) -> bool:
        # unchanged behaviour, still used internally
        try:
            res = self.exec.execute(["iw", "dev"], timeout=10)
            return f"Interface {name}" in res.stdout
        except Exception:
            return False

    def _parse_iw_dev(self, stdout: str) -> List[dict]:
        """
        Parse `iw dev` into a list of interfaces:
        [{"name": "...", "mac": "...", "type": "managed"/"monitor"}]
        """
        results, current = [], {}
        for raw in stdout.splitlines():
            line = raw.strip()
            if line.startswith("Interface "):
                # push previous
                if current:
                    results.append(current)
                current = {"name": line.split()[1]}
            elif line.startswith("addr ") and current:
                current["mac"] = line.split()[1].lower()
            elif line.startswith("type ") and current:
                current["type"] = line.split()[1].lower()
        if current:
            results.append(current)
        return results
    
    def _normalise_mac(self, mac: Optional[str]) -> Optional[str]:
        return mac.lower() if mac else None

    def parse_ipv4_from_ip(self, iface: str) -> Optional[str]:
        res = self.exec.execute(["ip", "-4", "addr", "show", "dev", iface], timeout=5)
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", res.stdout)
        return m.group(1) if m else None