"""Read-only, dependency-free environment inventory; never reads API credentials."""
import argparse
import ctypes
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def windows_memory():
    if os.name != "nt":
        return {"status": "unavailable_on_this_platform"}

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in (
                "total_physical", "available_physical", "total_pagefile",
                "available_pagefile", "total_virtual", "available_virtual", "extended"
            )
        ]

    state = MemoryStatus()
    state.length = ctypes.sizeof(state)
    try:
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
            return {"status": "detected", "total_bytes": state.total_physical,
                    "available_bytes": state.available_physical}
    except (OSError, AttributeError):
        pass
    return {"status": "unavailable"}


def inspect():
    root = Path(__file__).resolve().parents[1]
    disk = shutil.disk_usage(root)
    gpu = {"status": "not_detected"}
    command = shutil.which("nvidia-smi")
    if command:
        try:
            proc = subprocess.run(
                [command, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            gpu = {"status": "detected" if proc.returncode == 0 else "unavailable",
                   "inventory": proc.stdout.strip() if proc.returncode == 0 else None}
        except (OSError, subprocess.TimeoutExpired):
            gpu = {"status": "unavailable"}
    modules = ("torch", "transformers", "sentence_transformers", "duckdb", "pyarrow", "ir_measures")
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "environment_inventory_not_a_benchmark",
        "python": sys.version.split()[0], "platform": platform.platform(),
        "logical_processors": os.cpu_count(), "processor": platform.processor(),
        "memory": windows_memory(), "gpu": gpu,
        "disk": {"total_bytes": disk.total, "free_bytes": disk.free},
        "commands_in_path": {name: shutil.which(name) is not None for name in ("docker", "wsl", "git", "uv")},
        "modules_in_current_interpreter": {name: importlib.util.find_spec(name) is not None for name in modules},
        "notes": ["PATH and modules describe this interpreter/session only.",
                  "No API requests, installs or credential inspection performed."]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(inspect(), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result + "\n", encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
