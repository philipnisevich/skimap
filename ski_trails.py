#!/usr/bin/env python3
"""
Display live lift and run (trail) status using ski-resort-status
(https://github.com/marcushyett/ski-lift-status, npm: ski-resort-status).

Requires Node.js and: npm install

Usage:
  npm install
  python ski_trails.py --list-resorts
  python ski_trails.py les-trois-vallees
  python ski_trails.py --raw-json espace-diamant
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_BRIDGE = _SCRIPT_DIR / "node" / "ski_resort_bridge.cjs"


def run_bridge(arg: str | None) -> dict[str, Any]:
    if not _BRIDGE.is_file():
        print(
            f"Missing {_BRIDGE}. Run: npm install",
            file=sys.stderr,
        )
        sys.exit(1)
    cmd = ["node", str(_BRIDGE)]
    if arg is not None:
        cmd.append(arg)
    try:
        proc = subprocess.run(
            cmd,
            cwd=_SCRIPT_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        print("Node bridge timed out.", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(
            "Node.js not found. Install from https://nodejs.org/ and ensure `node` is on PATH.",
            file=sys.stderr,
        )
        sys.exit(1)
    raw = (proc.stdout or "").strip()
    if not raw:
        err = (proc.stderr or "").strip() or f"exit {proc.returncode}"
        print(f"Bridge failed: {err}", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print("Invalid JSON from bridge:\n", raw[:2000], file=sys.stderr)
        sys.exit(1)


def fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    s = str(v).strip()
    return s if s else "—"


def print_supported_resorts(payload: dict[str, Any]) -> None:
    resorts = payload.get("resorts")
    if not isinstance(resorts, list):
        print("Unexpected list payload.", file=sys.stderr)
        sys.exit(1)
    print("Supported resorts (ski-resort-status / OpenSkiMap-backed)")
    print(f"{'id':<28}  {'platform':<12}  name")
    print("-" * 80)
    for r in sorted(resorts, key=lambda x: str(x.get("id", "")).lower()):
        if not isinstance(r, dict):
            continue
        rid = str(r.get("id", "?"))[:28]
        plat = str(r.get("platform", "?"))[:12]
        name = r.get("name", "")
        print(f"{rid:<28}  {plat:<12}  {name}")


LIFT_LINES: list[tuple[str, str]] = [
    ("status", "Status"),
    ("liftType", "Lift type"),
    ("operating", "Operating now"),
    ("openingStatus", "Opening status"),
    ("openingTimesReal", "Hours (reported)"),
    ("openingTimesTheoretic", "Hours (scheduled)"),
    ("capacity", "Capacity (p/h)"),
    ("duration", "Duration (min)"),
    ("length", "Length (m)"),
    ("speed", "Speed (m/s)"),
    ("departureAltitude", "Bottom alt (m)"),
    ("arrivalAltitude", "Top alt (m)"),
    ("uphillCapacity", "Uphill capacity"),
    ("message", "Message"),
    ("openskimap_ids", "OpenSkiMap lift IDs"),
]


RUN_LINES: list[tuple[str, str]] = [
    ("status", "Status"),
    ("level", "Difficulty"),
    ("trailType", "Trail type"),
    ("operating", "Operating now"),
    ("openingStatus", "Opening status"),
    ("openingTimesReal", "Hours (reported)"),
    ("openingTimesTheoretic", "Hours (scheduled)"),
    ("groomingStatus", "Grooming"),
    ("snowQuality", "Snow quality"),
    ("length", "Length (m)"),
    ("averageSlope", "Avg slope (°)"),
    ("surface", "Surface"),
    ("departureAltitude", "Top alt (m)"),
    ("arrivalAltitude", "Bottom alt (m)"),
    ("exposure", "Exposure"),
    ("guaranteedSnow", "Guaranteed snow"),
    ("message", "Message"),
    ("openskimap_ids", "OpenSkiMap run IDs"),
]


def _print_entity_block(title: str, items: list[dict[str, Any]], field_rows: list[tuple[str, str]]) -> None:
    print(f"\n=== {title} ({len(items)}) ===\n")
    for item in sorted(items, key=lambda x: str(x.get("name", "")).lower()):
        name = item.get("name", "?")
        print(name)
        print("-" * min(72, max(len(str(name)), 8)))
        for key, label in field_rows:
            if key not in item:
                continue
            val = item[key]
            if val is None or val == "" or val == []:
                continue
            if key == "openskimap_ids" and isinstance(val, list):
                val = ", ".join(str(x) for x in val[:6])
                if len(item.get("openskimap_ids") or []) > 6:
                    val += ", …"
            print(f"  {label}: {fmt(val)}")
        print()


def print_resort_report(data: dict[str, Any]) -> None:
    resort = data.get("resort") or {}
    rname = resort.get("name", "?")
    rid = resort.get("id", "?")
    osm = resort.get("openskimap_id", "")
    print(f"Resort: {rname}")
    print(f"id: {rid}")
    if osm:
        print(f"OpenSkiMap: https://openskimap.org/?obj=skiArea&id={osm}")

    lifts = data.get("lifts") or []
    runs = data.get("runs") or []
    if not isinstance(lifts, list):
        lifts = []
    if not isinstance(runs, list):
        runs = []

    if lifts:
        _print_entity_block("Lifts", lifts, LIFT_LINES)
    else:
        print("\n(No lift list in response.)\n")

    if runs:
        _print_entity_block("Runs (trails)", runs, RUN_LINES)
    else:
        print("(No run/trail list in response.)\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Live lift & run status via ski-resort-status (Node).",
    )
    parser.add_argument(
        "resort",
        nargs="?",
        help="Resort id (see --list-resorts). Omit to be prompted.",
    )
    parser.add_argument(
        "--list-resorts",
        action="store_true",
        help="List resorts supported by ski-resort-status.",
    )
    parser.add_argument(
        "--raw-json",
        action="store_true",
        help="Print full JSON from the library after the report.",
    )
    args = parser.parse_args()

    if args.list_resorts:
        out = run_bridge("--list")
        if not out.get("ok"):
            print(out.get("error", out), file=sys.stderr)
            sys.exit(1)
        print_supported_resorts(out)
        return

    rid = (args.resort or "").strip()
    if not rid:
        rid = input("Resort id (e.g. les-trois-vallees): ").strip()
    if not rid:
        print("No resort id given.", file=sys.stderr)
        sys.exit(1)

    out = run_bridge(rid)
    if not out.get("ok"):
        print(out.get("error", "Unknown error"), file=sys.stderr)
        print("Run: python ski_trails.py --list-resorts", file=sys.stderr)
        sys.exit(1)

    data = out.get("data")
    if not isinstance(data, dict):
        print("Unexpected data shape from bridge.", file=sys.stderr)
        sys.exit(1)

    print_resort_report(data)
    if args.raw_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
