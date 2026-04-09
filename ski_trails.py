#!/usr/bin/env python3
"""
Fetch live Ski API (RapidAPI: Ski Resorts and Conditions) data and print trail/run/lift
status in a simple table. API key is read from .env (RAPIDAPI_KEY).

Usage:
  python ski_trails.py                    # prompt for resort slug
  python ski_trails.py palisades          # resort slug as argument
  python ski_trails.py --list-resorts     # list resort slugs (RapidAPI if available, else Liftie on GitHub)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from dotenv import load_dotenv

RAPIDAPI_HOST = "ski-resorts-and-conditions.p.rapidapi.com"
BASE_URL = f"https://{RAPIDAPI_HOST}"

# Slugs that changed or merged in the upstream feed (Liftie / Ski API).
RESORT_SLUG_ALIASES: dict[str, str] = {
    "alpine": "palisades",
    "alpine-meadows": "palisades",
    "squaw": "palisades",
    "squaw-valley": "palisades",
}

_SCRIPT_DIR = Path(__file__).resolve().parent


def load_dotenv_file() -> None:
    load_dotenv(_SCRIPT_DIR / ".env")


def load_api_key(required: bool = True) -> str:
    load_dotenv_file()
    key = (os.environ.get("RAPIDAPI_KEY") or "").strip()
    if not key and required:
        print(
            "Missing RAPIDAPI_KEY. Add it to .env (see .env.example).",
            file=sys.stderr,
        )
        sys.exit(1)
    return key


def api_headers(key: str) -> dict[str, str]:
    return {
        "X-RapidAPI-Key": key,
        "X-RapidAPI-Host": RAPIDAPI_HOST,
    }


def resolve_resort_slug(slug: str) -> str:
    key = slug.strip().lower()
    if key in RESORT_SLUG_ALIASES:
        resolved = RESORT_SLUG_ALIASES[key]
        print(
            f"Note: using slug {resolved!r} (Ski API name for former {slug!r}).",
            file=sys.stderr,
        )
        return resolved
    return slug.strip()


def fetch_resort(key: str, slug: str) -> dict[str, Any]:
    url = f"{BASE_URL}/v1/resort/{quote(slug, safe='')}"
    r = requests.get(url, headers=api_headers(key), timeout=30)
    if r.status_code != 200:
        err = r.text[:500]
        print(f"HTTP {r.status_code}: {err}", file=sys.stderr)
        if r.status_code == 404:
            print(
                "Try: python ski_trails.py --list-resorts   (valid slugs change over time; "
                "e.g. Palisades Tahoe is palisades, not alpine).",
                file=sys.stderr,
            )
        sys.exit(1)
    body = r.json()
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    if isinstance(body, dict):
        return body
    print("Unexpected JSON shape from API.", file=sys.stderr)
    sys.exit(1)


def try_fetch_resort_index_api(key: str) -> Any | None:
    """
    Some RapidAPI plans expose an index endpoint; many do not. Return parsed JSON or None.
    """
    candidates = (
        "/v1/export",
        "/export",
        "/v1/resorts",
        "/resorts",
        "/v1/all",
        "/api/meta",
        "/meta",
    )
    for path in candidates:
        url = BASE_URL + path
        r = requests.get(url, headers=api_headers(key), timeout=120)
        if r.status_code != 200:
            continue
        try:
            return r.json()
        except json.JSONDecodeError:
            continue
    return None


def _github_next_url(link_header: str) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        if 'rel="next"' not in part:
            continue
        m = re.search(r"<([^>]+)>", part.strip())
        return m.group(1) if m else None
    return None


def fetch_liftie_slugs_from_github() -> list[str]:
    """
    Directory names under github.com/pirxpilot/liftie/lib/resorts — same slugs the Ski API
    (Liftie-based) uses for /v1/resort/{slug}.
    """
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "skimap-ski-trails/1.0",
    }
    url: str | None = "https://api.github.com/repos/pirxpilot/liftie/contents/lib/resorts"
    params: dict[str, str] | None = {"ref": "main", "per_page": "100"}
    slugs: list[str] = []
    first = True
    while url:
        r = requests.get(
            url,
            params=params if first else None,
            headers=headers,
            timeout=60,
        )
        if r.status_code != 200:
            print(
                f"GitHub resort list failed: HTTP {r.status_code} {r.text[:400]}",
                file=sys.stderr,
            )
            sys.exit(1)
        page = r.json()
        if not isinstance(page, list):
            print("Unexpected GitHub API response.", file=sys.stderr)
            sys.exit(1)
        for item in page:
            if isinstance(item, dict) and item.get("type") == "dir" and item.get("name"):
                slugs.append(str(item["name"]))
        first = False
        params = None
        url = _github_next_url(r.headers.get("Link", ""))
    return sorted(slugs, key=str.lower)


def _iter_slug_name_pairs(payload: Any) -> list[tuple[str, str]]:
    """Normalize various index/export JSON shapes into (slug, display_name) rows."""
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        for k in ("data", "resorts", "meta", "items"):
            v = payload.get(k)
            if isinstance(v, list):
                return _iter_slug_name_pairs(v)
        # Mapping slug -> resort object
        if payload and all(isinstance(v, dict) for v in payload.values()):
            out: list[tuple[str, str]] = []
            for slug, info in payload.items():
                name = info.get("name") or info.get("title") or str(slug)
                out.append((str(slug), str(name)))
            return sorted(out, key=lambda x: x[0].lower())
        return []
    else:
        return []

    rows: list[tuple[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        slug = (
            item.get("slug")
            or item.get("id")
            or item.get("code")
            or item.get("name")
        )
        if slug is None:
            continue
        title = item.get("name") or item.get("title") or str(slug)
        rows.append((str(slug), str(title)))
    return sorted(rows, key=lambda x: x[0].lower())


def _status_map_from_block(block: Any) -> dict[str, str]:
    if not isinstance(block, dict):
        return {}
    status = block.get("status")
    if isinstance(status, dict):
        return {str(k): str(v) for k, v in status.items()}
    return {}


def _pairs_from_list(items: list[Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("title") or item.get("id")
        if name is None:
            continue
        st: str | None = None
        if "status" in item:
            st = str(item["status"])
        elif "state" in item:
            st = str(item["state"])
        elif item.get("open") is not None:
            st = "open" if item.get("open") else "closed"
        if st is not None:
            pairs.append((str(name), st))
    return pairs


def extract_trail_like(data: dict[str, Any]) -> tuple[str, list[tuple[str, str]]]:
    """Return (source_description, sorted list of (name, raw_status))."""
    for section_key, label in (
        ("trails", "Trails"),
        ("runs", "Runs"),
        ("terrain", "Terrain"),
    ):
        block = data.get(section_key)
        if isinstance(block, dict):
            m = _status_map_from_block(block)
            if m:
                return (label, sorted(m.items(), key=lambda x: x[0].lower()))
        if isinstance(block, list):
            pairs = _pairs_from_list(block)
            if pairs:
                return (label, sorted(pairs, key=lambda x: x[0].lower()))

    lifts = data.get("lifts")
    if isinstance(lifts, dict):
        m = _status_map_from_block(lifts)
        if m:
            return (
                "Lifts (API does not expose separate trail/run status for this resort)",
                sorted(m.items(), key=lambda x: x[0].lower()),
            )

    return ("", [])


def normalize_status(raw: str) -> tuple[str, str]:
    """
    Return (short_label, human_readable).
    short_label is OPEN, CLOSED, HOLD, or UNKNOWN.
    """
    s = raw.strip().lower()
    if s in ("open", "yes", "true", "1", "on"):
        return ("OPEN", "Open")
    if s in ("closed", "no", "false", "0", "off"):
        return ("CLOSED", "Closed")
    if s in ("hold", "on-hold", "on hold", "stopped"):
        return ("HOLD", "On hold")
    if s in ("scheduled", "schedule"):
        return ("SCHEDULED", "Scheduled")
    if not s:
        return ("UNKNOWN", "Unknown")
    return ("OTHER", raw.strip())


def print_resort_table(slug: str, data: dict[str, Any]) -> None:
    name = data.get("name") or data.get("title") or slug
    source, rows = extract_trail_like(data)
    if not rows:
        print(f"Resort: {name} ({slug})")
        print("No trail, run, or lift status data found in this response.")
        return

    print(f"Resort: {name} ({slug})")
    print(f"Data: {source}")
    cond = data.get("conditions")
    if isinstance(cond, dict) and cond:
        base = cond.get("base")
        season = cond.get("season")
        parts = []
        if base is not None:
            parts.append(f"base {base} cm")
        if season is not None:
            parts.append(f"season {season} cm")
        if parts:
            print(f"Snow: {', '.join(parts)}")
    print()

    col_name = "Name"
    col_stat = "Open?"
    col_raw = "Raw status"
    w = max(len(col_name), max(len(r[0]) for r in rows))
    header = f"{col_name.ljust(w)}  {col_stat.ljust(8)}  {col_raw}"
    print(header)
    print("-" * len(header))
    for trail_name, raw in rows:
        short, human = normalize_status(raw)
        open_yes = short == "OPEN"
        flag = "Yes" if open_yes else "No"
        print(f"{trail_name.ljust(w)}  {flag.ljust(8)}  {human}")


def print_resort_index_rows(rows: list[tuple[str, str]], source_note: str) -> None:
    print(source_note)
    print(f"{'Slug':<32}  Name")
    print("-" * 76)
    for slug, title in rows:
        print(f"{slug[:32]:<32}  {title}")


def print_resort_slug_only_list(slugs: list[str]) -> None:
    print(
        "Source: Liftie resort folders on GitHub (slug = path name; matches Ski API /v1/resort/{slug}).",
    )
    print(f"{'Slug':<36}")
    print("-" * 40)
    for s in slugs:
        print(s)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ski API (RapidAPI) — print trail/run/lift open status.",
    )
    parser.add_argument(
        "resort",
        nargs="?",
        help="Resort slug (e.g. palisades, brighton). Omit to be prompted.",
    )
    parser.add_argument(
        "--list-resorts",
        action="store_true",
        help="List resort slugs (RapidAPI index if available, else Liftie on GitHub).",
    )
    parser.add_argument(
        "--raw-json",
        action="store_true",
        help="Print full resort JSON after the table (debugging).",
    )
    args = parser.parse_args()

    if args.list_resorts:
        load_dotenv_file()
        key = (os.environ.get("RAPIDAPI_KEY") or "").strip()
        api_payload: Any | None = None
        if key:
            api_payload = try_fetch_resort_index_api(key)
        if api_payload is not None:
            rows = _iter_slug_name_pairs(api_payload)
            if rows:
                print_resort_index_rows(
                    rows,
                    "Source: Ski API (RapidAPI) index response.",
                )
                return
            print(
                "RapidAPI returned JSON but no resort list was recognized; "
                "falling back to Liftie slugs on GitHub.",
                file=sys.stderr,
            )
        else:
            print(
                "No working RapidAPI list endpoint (or no RAPIDAPI_KEY); "
                "using Liftie slugs from GitHub.",
                file=sys.stderr,
            )
        print_resort_slug_only_list(fetch_liftie_slugs_from_github())
        return

    key = load_api_key(required=True)

    slug = (args.resort or "").strip()
    if not slug:
        slug = input("Resort slug (e.g. palisades): ").strip()
    if not slug:
        print("No resort slug given.", file=sys.stderr)
        sys.exit(1)

    slug = resolve_resort_slug(slug)
    data = fetch_resort(key, slug)
    print_resort_table(slug, data)
    if args.raw_json:
        print()
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
