import os
import csv
import time
import threading
from typing import Any, Iterable, Optional, List, Dict, Tuple
from shared import InterfaceInfo, InterfaceMode, AirodumpResult, AccessPoint, Station, DroneAPResult, DroneInfo, CommandExecutor, CancellationToken, OperationCanceledError, SudoHelper
from hardware_handler import APAnalyzer, ParrotDroneAnalyzer

SPINNER = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]


class AircrackNgHandler:
    """
    Runs airodump-ng using CommandExecutor for a fixed duration, shows a spinner,
    and returns paths to CSV/CAP. Uses `timeout -s INT <duration>` so airodump
    receives SIGINT and flushes files cleanly. Supports early cancel via token.
    """

    def __init__(self):
        self._executor = CommandExecutor()
        self._worker_thread: Optional[threading.Thread] = None
        self._token: Optional[CancellationToken] = None
        self._result_container: Dict[str, object] = {}
        self._running: bool = False
        self._last_prefix: Optional[str] = None

    # ---------- internal helpers ----------

    def _remove_old_outputs(self, prefix: str) -> None:
        """Delete common airodump output files for the given prefix."""
        candidates = {
            f"{prefix}-01.csv",
            f"{prefix}-01.kismet.csv",
            f"{prefix}-01.log.csv",
            f"{prefix}-01.cap",
            f"{prefix}.csv",
            f"{prefix}.kismet.csv",
            f"{prefix}.log.csv",
            f"{prefix}.cap",
        }
        for fp in candidates:
            if os.path.exists(fp):
                try:
                    os.remove(fp)
                    print(f"[*] Removed old airodump-ng output: {fp}")
                except OSError as e:
                    print(f"[!] Could not remove {fp}: {e}")

    def _build_cmd(
        self,
        iface: str,
        prefix: str,
        channel: Optional[int],
        ignore_negative_one: bool,
        duration_sec: int,
    ) -> List[str]:
        """
        Build the command list; wrap airodump with `timeout -s INT <duration>`
        so airodump writes/flushes outputs on SIGINT at the end of the run.
        """
        cmd = [
            "timeout", "-s", "INT", str(duration_sec),
            "airodump-ng", iface,
            "-w", prefix,
            "--output-format", "csv",
            "--write-interval", "1",
        ]
        if channel is not None:
            cmd.extend(["-c", str(channel)])
        if ignore_negative_one:
            cmd.append("--ignore-negative-one")
        return cmd

    def _run_airodump(self, cmd: List[str], use_sudo: bool, duration_sec: int):
        """Background runner invoking CommandExecutor with a cancellation token."""
        try:
            res = self._executor.execute(
                cmd,
                cancellation_token=self._token,
                timeout=duration_sec + 60,  # buffer over the timeout duration
                sudo=use_sudo,
            )
            self._result_container["result"] = res
        except OperationCanceledError:
            self._result_container["canceled"] = True
        except Exception as e:
            self._result_container["error"] = e
        finally:
            self._running = False

    # ---------- public API ----------

    def start_airodump_scan(
        self,
        interface: InterfaceInfo,
        output_prefix: str = "airodump_output",
        duration_sec: int = 20,
        channel: Optional[int] = None,
        use_sudo: bool = True,
        ignore_negative_one: bool = True,
    ) -> AirodumpResult:
        """
        Start a timed airodump-ng capture using CommandExecutor.
        Shows a spinner while running and returns CSV/CAP paths when finished.
        """
        if interface.mode != InterfaceMode.MONITOR:
            return AirodumpResult(False, "Interface is not in MONITOR mode. Switch first.")
        if not interface.iface_name:
            return AirodumpResult(False, "Interface name is empty.")

        self._remove_old_outputs(output_prefix)
        cmd = self._build_cmd(interface.iface_name, output_prefix, channel, ignore_negative_one, duration_sec)

        self._token = CancellationToken()
        self._result_container = {}
        self._running = True
        self._last_prefix = output_prefix
        if use_sudo:
            sudo_helper = SudoHelper().ensure_sudo()

        self._worker_thread = threading.Thread(
            target=self._run_airodump,
            args=(cmd, use_sudo, duration_sec),
            daemon=True,
        )
        self._worker_thread.start()

        print(f"[*] airodump-ng started on {interface.iface_name} for {duration_sec}s. Writing to '{output_prefix}-01.*'")

        start = time.time()
        spin_idx = 0
        while self._running:
            elapsed = int(time.time() - start)
            remaining = max(0, duration_sec - elapsed)
            print(f"\r{SPINNER[spin_idx % len(SPINNER)]} scanning… {elapsed}s elapsed | {remaining}s left", end="", flush=True)
            spin_idx += 1
            time.sleep(0.15)
            if elapsed >= duration_sec:
                break

        if self._worker_thread:
            self._worker_thread.join(timeout=5)

        print("\r✓ scan finished".ljust(60))

        stdout = ""
        stderr = ""
        if "result" in self._result_container:
            stdout = self._result_container["result"].stdout
            stderr = self._result_container["result"].stderr
        elif "error" in self._result_container:
            return AirodumpResult(False, f"Failed: {self._result_container['error']}", None, None, "", "")
        elif "canceled" in self._result_container:
            return AirodumpResult(False, "Scan canceled", None, None, "", "")

        csv_path = f"{output_prefix}-01.csv" if os.path.exists(f"{output_prefix}-01.csv") else None
        cap_path = f"{output_prefix}-01.cap" if os.path.exists(f"{output_prefix}-01.cap") else None

        msg = "Scan complete"
        if not csv_path:
            msg += " (no CSV found; check permissions or interface state)"

        return AirodumpResult(True, msg, csv_path=csv_path, cap_path=cap_path, logs=stdout, errors=stderr)

    def stop_airodump_scan(self) -> bool:
        """
        Request early stop of the running scan via CancellationToken.
        """
        if not self._running or not self._token:
            print("[*] No active airodump-ng scan.")
            return True
        self._token.cancel()
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        self._running = False
        print("[*] airodump-ng stop requested.")
        return True


class AirodumpCsvParser:
    AP_HEADER_PREFIX = "BSSID"
    STATION_HEADER_PREFIX = "Station MAC"

    def parse(self, csv_path: str) -> Tuple[List[AccessPoint], List[Station]]:
        if not os.path.exists(csv_path):
            return [], []
        with open(csv_path, newline="", encoding="utf-8", errors="ignore") as f:
            rows = list(csv.reader(f))
        ap_rows, sta_rows = self._split_sections(rows)
        return self._parse_aps(ap_rows), self._parse_stations(sta_rows)

    def _split_sections(self, rows: List[List[str]]) -> Tuple[List[List[str]], List[List[str]]]:
        ap_rows, sta_rows, current = [], [], "ap"
        for r in rows:
            if not r: continue
            if r[0].startswith(self.AP_HEADER_PREFIX):
                current = "ap"; ap_rows.append(r); continue
            if r[0].startswith(self.STATION_HEADER_PREFIX):
                current = "sta"; sta_rows.append(r); continue
            (ap_rows if current == "ap" else sta_rows).append(r)
        return ap_rows, sta_rows

    def _parse_aps(self, ap_rows: List[List[str]]) -> List[AccessPoint]:
        if not ap_rows: return []
        header = ap_rows[0]
        out: List[AccessPoint] = []
        for r in ap_rows[1:]:
            if len(r) < len(header): continue
            data = {header[i].strip(): (r[i].strip() if i < len(r) else "") for i in range(len(header))}
            out.append(AccessPoint(
                bssid=data.get("BSSID",""),
                first_seen=data.get("First time seen",""),
                last_seen=data.get("Last time seen",""),
                channel=_to_int(data.get("channel") or data.get("channel ")),
                speed=data.get("Speed") or data.get("speed"),
                privacy=data.get("Privacy"),
                cipher=data.get("Cipher"),
                auth=data.get("Authentication") or data.get("Auth"),
                power=_to_int(data.get("Power") or data.get("power")),
                beacons=_to_int(data.get("beacons") or data.get("Beacons")),
                iv=data.get("IV"),
                lan_ip=data.get("LAN IP") or data.get("LAN IP "),
                id_length=_to_int(data.get("ID-length") or data.get("ID length")),
                essid=data.get("ESSID",""),
                key=data.get("Key"),
                raw=data,
            ))
        return [ap for ap in out if ap.bssid]

    def _parse_stations(self, sta_rows: List[List[str]]) -> List[Station]:
        if not sta_rows: return []
        header = sta_rows[0]
        out: List[Station] = []
        for r in sta_rows[1:]:
            if len(r) < len(header): continue
            data = {header[i].strip(): (r[i].strip() if i < len(r) else "") for i in range(len(header))}
            out.append(Station(
                station_mac=data.get("Station MAC",""),
                first_seen=data.get("First time seen",""),
                last_seen=data.get("Last time seen",""),
                power=_to_int(data.get("Power")),
                packets=_to_int(data.get("# packets") or data.get("Packets")),
                bssid=data.get("BSSID") or data.get("BSSID "),
                probed_essids=data.get("Probed ESSIDs") or data.get("Probed ESSIDs "),
                raw=data,
            ))
        return [s for s in out if s.station_mac]

def _to_int(x: Optional[str]) -> Optional[int]:
    try: return int(str(x).strip())
    except Exception: return None
    
    
class DroneCSVAnalyser:
    """
    Sweep the whole CSV:
      - run all analysers against every AP
      - for each AP flagged as a drone, collect its connected stations
      - return a list of DroneAPResult (one per detected drone AP)
    """
    def __init__(self, analyzers: Optional[List[APAnalyzer]] = None):
        self.parser = AirodumpCsvParser()
        self.analyzers: List[APAnalyzer] = analyzers or [ParrotDroneAnalyzer()]

    def analyse_csv_all(self, csv_path: str) -> List[DroneAPResult]:
        aps, stations = self.parser.parse(csv_path)
        if not aps: return []

        # Map AP BSSID -> stations
        stations_by_bssid: Dict[str, List[Station]] = {}
        for st in stations:
            key = (st.bssid or "").lower()
            stations_by_bssid.setdefault(key, []).append(st)

        results: List[DroneAPResult] = []
        seen_bssids: set[str] = set()

        for ap in aps:
            b = ap.bssid.lower()
            if b in seen_bssids:
                continue
            info = self._match_with_any_analyzer(ap)
            if info and info.is_drone:
                connected = stations_by_bssid.get(b, [])
                results.append(DroneAPResult(drone_ap=ap, connected_devices=connected, info=info, source_csv=csv_path))
                seen_bssids.add(b)

        return results

    def _match_with_any_analyzer(self, ap: AccessPoint) -> Optional[DroneInfo]:
        for a in self.analyzers:
            res = a.analyze(ap)
            if res and res.is_drone:
                return res
        return None