#!/usr/bin/env python3
"""
lookup_name.py — check whether a specific named person owns property in
Westport, Fairfield, or Stamford CT, independent of the sales-scan pipeline.

Usage:
    python3 -m leads_engine.lookup_name "Surname" ["Surname 2" ...]

For each match, fetches full parcel detail (price history, building info)
the same way the main pipeline does.
"""

import sys

from . import vgsi_source

TOWNS = ["westportct", "fairfieldct", "stamfordct"]


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m leads_engine.lookup_name \"Surname\" [more names...]")
        sys.exit(1)

    for name in sys.argv[1:]:
        print(f"\n=== Searching for '{name}' ===")
        any_found = False
        for town in TOWNS:
            matches = vgsi_source.search_by_owner_name(town, name)
            if not matches:
                continue
            any_found = True
            for m in matches:
                print(f"  [{town}] {m['owner_name']} — {m['address']} (pid={m['parcel_id']})")
        if not any_found:
            print("  No matches in Westport, Fairfield, or Stamford.")


if __name__ == "__main__":
    main()
