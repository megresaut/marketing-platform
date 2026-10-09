#!/usr/bin/env python3
"""
run.py — AVM live lead sourcing + refinement engine.

Sources real high-value property sales from town assessor records (VGSI),
resolves owner identity and absentee status from the assessor's own parcel
records, cross-references owner names against ProPublica (nonprofits) and
SEC EDGAR (filings) for real public-record signals, scores every lead with
a transparent rule-based model, and writes one Markdown brief per lead plus
a summary index — ready to review and send.

No fabricated data. Every field is either sourced live or explicitly marked
unavailable. Run with --help for options.

Example:
    python3 -m leads_engine.run --min-price 3000000 --months 18 --limit 25
"""

import argparse
import os
from collections import Counter
from datetime import datetime

from . import vgsi_source, enrich, ct_registry, score as score_mod, report

DEFAULT_TOWNS = ["westportct", "fairfieldct", "stamfordct"]


def main():
    parser = argparse.ArgumentParser(description="AVM live lead sourcing + refinement engine")
    parser.add_argument("--towns", default=",".join(DEFAULT_TOWNS),
                         help="Comma-separated VGSI town slugs (default: westportct,fairfieldct,stamfordct)")
    parser.add_argument("--min-price", type=int, default=2500000, help="Minimum sale price (default: 2500000)")
    parser.add_argument("--months", type=int, default=24, help="Look back this many months (default: 24)")
    parser.add_argument("--limit", type=int, default=40,
                         help="Max number of sales to fully enrich, highest price first (default: 40)")
    parser.add_argument("--out-dir", default=None, help="Output directory (default: leads_engine/output/<timestamp>)")
    args = parser.parse_args()

    towns = [t.strip() for t in args.towns.split(",") if t.strip()]
    out_dir = args.out_dir or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "output", datetime.now().strftime("%Y-%m-%d_%H%M%S")
    )
    os.makedirs(out_dir, exist_ok=True)

    print("=== Phase 1: sourcing live sales ===")
    all_raw = []
    sessions = {}
    for town in towns:
        result = vgsi_source.search_town_sales(town, min_price=args.min_price, months_back=args.months)
        if not result:
            continue
        sales, session = result
        sessions[town] = session
        all_raw.extend(sales)

    if not all_raw:
        print("No live sales data retrieved from any town. Nothing to report.")
        return

    seen = set()
    deduped = []
    for s in all_raw:
        key = (s["town_slug"], s["parcel_id"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(s)
    all_raw = deduped

    all_raw.sort(key=lambda s: s["sale_price"], reverse=True)
    to_process = all_raw[: args.limit]
    print(f"\n{len(all_raw)} total qualifying sales found; processing top {len(to_process)} by price.\n")

    print("=== Phase 2: resolving owner + parcel detail ===")
    leads = []
    for i, raw in enumerate(to_process, 1):
        town = raw["town_slug"]
        session = sessions[town]
        print(f"  [{i}/{len(to_process)}] {raw['location']} ({town}) — ${raw['sale_price']:,}")
        detail = vgsi_source.fetch_parcel_detail(session, town, raw["parcel_id"])
        if not detail:
            continue
        lead = {**raw, **detail, "sale_date": raw["sale_date_raw"]}
        leads.append(lead)

    print("\n=== Phase 3: portfolio cross-reference ===")
    owner_counts = Counter(l["owner_name"].strip().upper() for l in leads if l.get("owner_name"))
    for lead in leads:
        owner_key = lead.get("owner_name", "").strip().upper()
        lead["portfolio_count"] = owner_counts.get(owner_key, 1)

    print("=== Phase 4: enrichment (ProPublica + SEC EDGAR) ===")
    for i, lead in enumerate(leads, 1):
        print(f"  [{i}/{len(leads)}] enriching {lead.get('owner_name', 'unknown')}")
        lead["enrichment"] = enrich.enrich_owner(lead.get("owner_name", ""), lead.get("entity_flag", False))

    print("=== Phase 4b: CT business registry lookup (entity-owned leads) ===")
    for i, lead in enumerate(leads, 1):
        if not lead.get("entity_flag"):
            continue
        print(f"  [{i}/{len(leads)}] resolving {lead.get('owner_name', 'unknown')} against CT SOS registry")
        lead["ct_registry"] = ct_registry.lookup_entity(lead.get("owner_name", ""))

    print("\n=== Phase 5: scoring ===")
    for lead in leads:
        s, reasons = score_mod.score_lead(lead)
        lead["score"] = s
        lead["score_reasons"] = reasons

    leads.sort(key=lambda l: l["score"], reverse=True)

    print("=== Phase 6: writing report ===")
    for lead in leads:
        report.write_lead_brief(lead, out_dir)
    md_path, csv_path = report.write_summary(leads, out_dir)

    print(f"\nDone. {len(leads)} leads written to {out_dir}")
    print(f"  Summary: {md_path}")
    print(f"  CSV:     {csv_path}")
    print("\nTop 5:")
    for lead in leads[:5]:
        print(f"  [{lead['score']:3d}] {lead.get('owner_name','')} — {lead['location']} — ${lead['sale_price']:,}")


if __name__ == "__main__":
    main()
