import json
from pathlib import Path
from typing import Optional
from modules.exploit.base_attack_script import DroneTargetInfo

DEFAULT_CONTEXT_FILE = Path(".skyfall_context.json")

def save_context(info: DroneTargetInfo, path: Optional[str] = None) -> str:
    p = Path(path) if path else DEFAULT_CONTEXT_FILE
    data = info.to_dict()
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return str(p)

def load_context(path: Optional[str] = None) -> Optional[DroneTargetInfo]:
    p = Path(path) if path else DEFAULT_CONTEXT_FILE
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return DroneTargetInfo.from_dict(data)
    except Exception:
        return None

def clear_context(path: Optional[str] = None) -> bool:
    p = Path(path) if path else DEFAULT_CONTEXT_FILE
    try:
        if p.exists():
            p.unlink()
        return True
    except Exception:
        return False
