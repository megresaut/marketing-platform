"""
report.py
Renders scored, enriched leads into human-readable output: one Markdown
brief per lead (ready to forward internally) plus a summary index and CSV.
"""

import csv
import os

from .score import tier_for_score

TOWN_LABELS = {
    "westportct": "Westport, CT",
    "fairfieldct": "Fairfield, CT",
    "stamfordct": "Stamford, CT",
}


def _lead_address(lead):
    town_label = TOWN_LABELS.get(lead["town_slug"], lead["town_slug"])
    return f"{lead['location'].title()}, {town_label}"


def write_lead_brief(lead, out_dir):
    address = _lead_address(lead)
    tier = tier_for_score(lead["score"])
    lines = []
    lines.append(f"# Lead Brief — {address}")
    lines.append("")
    lines.append(f"**Score: {lead['score']}/100 — {tier}**")
    lines.append("")
    lines.append("## Sale record (source: Vision Government Solutions / town assessor)")
    lines.append(f"- Sale price: ${lead['sale_price']:,}")
    lines.append(f"- Sale date: {lead.get('sale_date', 'unknown')}")
    lines.append(f"- Owner of record: {lead.get('owner_name', 'unknown')}")
    if lead.get("mailing_address"):
        lines.append(f"- Owner mailing address: {lead['mailing_address']}")
    lines.append(f"- Absentee owner: {'Yes' if lead.get('absentee_flag') else 'No'}")
    lines.append(f"- Held in entity/trust: {'Yes' if lead.get('entity_flag') else 'No'}")
    if lead.get("year_built"):
        lines.append(f"- Year built: {lead['year_built']}")
    if lead.get("living_area_sqft"):
        lines.append(f"- Living area: {lead['living_area_sqft']} sqft")
    if lead.get("lot_acres"):
        lines.append(f"- Lot size: {lead['lot_acres']} acres")
    if lead.get("style"):
        lines.append(f"- Style: {lead['style']}")
    bed_bath_bits = []
    if lead.get("bedrooms"):
        bed_bath_bits.append(f"{lead['bedrooms']} bed")
    if lead.get("full_baths"):
        bed_bath_bits.append(f"{lead['full_baths']} full bath" + ("s" if lead["full_baths"] != "1" else ""))
    if lead.get("half_baths"):
        bed_bath_bits.append(f"{lead['half_baths']} half bath" + ("s" if lead["half_baths"] != "1" else ""))
    if bed_bath_bits:
        lines.append(f"- Bed/bath: {' / '.join(bed_bath_bits)}")
    if lead.get("total_rooms"):
        lines.append(f"- Total rooms: {lead['total_rooms']}")
    if lead.get("fireplaces"):
        lines.append(f"- Fireplaces: {lead['fireplaces']}")
    amenities = []
    if lead.get("has_pool"):
        amenities.append("pool")
    if lead.get("has_garage"):
        amenities.append("garage")
    if lead.get("ac_type"):
        amenities.append(f"{lead['ac_type']} A/C")
    if lead.get("heat_type"):
        amenities.append(f"{lead['heat_type']} heat")
    if amenities:
        lines.append(f"- Amenities: {', '.join(amenities)}")
    if lead.get("assessed_value"):
        lines.append(f"- Assessed value: {lead['assessed_value']}")
    if lead.get("appraised_value"):
        lines.append(f"- Appraised value: {lead['appraised_value']}")
    if lead.get("portfolio_count", 0) > 1:
        lines.append(f"- Appears {lead['portfolio_count']}x in this dataset under the same owner name (possible portfolio owner)")
    lines.append(f"- Source: {lead.get('parcel_url', '')}")
    lines.append("")

    history = lead.get("ownership_history", [])
    if history:
        lines.append("## Ownership history (from assessor record)")
        for h in history[:6]:
            lines.append(f"- {h['owner']} — {h['sale_price']} — {h['sale_date']}")
        lines.append("")

    ct_reg = lead.get("ct_registry")
    if ct_reg:
        lines.append("## CT Secretary of State business registry (official, free, no signup)")
        lines.append(f"- Matched entity: {ct_reg.get('matched_name', '')} — status: {ct_reg.get('status', '')}")
        if ct_reg.get("formation_state"):
            lines.append(f"- Formed in: {ct_reg['formation_state']}")
        if ct_reg.get("business_email"):
            lines.append(f"- Business email on file: {ct_reg['business_email']}")
        principals = ct_reg.get("principals") or []
        if principals:
            lines.append("- Principal(s) of record (may be beneficial owner or filing attorney — verify):")
            for p in principals:
                lines.append(f"  - {p['name']} — {p['address']}")
        agent = ct_reg.get("agent")
        if agent:
            if agent.get("type") == "Individual":
                contact_bits = [b for b in [agent.get("phone"), agent.get("email")] if b]
                lines.append(
                    f"- Registered agent: {agent['name']} (individual, likely the owner acting as their own agent)"
                    + (f" — {', '.join(contact_bits)}" if contact_bits else "")
                )
            else:
                lines.append(f"- Registered agent: {agent['name']} (commercial registered-agent service — not a personal lead)")
        lines.append("")
    elif lead.get("entity_flag"):
        lines.append("## CT Secretary of State business registry")
        lines.append("- No match found (not registered in CT, or registered under a different name variant)")
        lines.append("")

    enrichment = lead.get("enrichment", {})
    nonprofit_matches = enrichment.get("nonprofit_matches") or []
    sec_matches = enrichment.get("sec_matches")
    if nonprofit_matches or sec_matches:
        lines.append("## Public-record signals (unverified — confirm before outreach)")
        for m in nonprofit_matches:
            lines.append(
                f"- Possible nonprofit/foundation name match: **{m['org_name']}** "
                f"(EIN {m['ein']}, {m['city']}, {m['state']}) — {m['confidence']}"
            )
        if sec_matches:
            companies = ", ".join(sec_matches.get("companies", []))
            lines.append(
                f"- Name appears in {sec_matches['total_hits']} SEC EDGAR filings"
                + (f", including: {companies}" if companies else "")
                + " — verify actual role (filer, officer, fund manager, or incidental mention) before referencing"
            )
        lines.append("")
    else:
        lines.append("## Public-record signals")
        lines.append("- No nonprofit or SEC EDGAR name matches found.")
        lines.append("")

    lines.append("## Why this lead scored the way it did")
    for reason in lead.get("score_reasons", []):
        lines.append(f"- {reason}")
    lines.append("")

    filename = f"{lead['town_slug']}-{lead['parcel_id']}.md"
    path = os.path.join(out_dir, filename)
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path


def write_summary(leads, out_dir):
    md_lines = ["# Lead Sourcing Run — Summary", ""]
    md_lines.append(f"{len(leads)} leads sourced from live VGSI records (Westport/Fairfield/Stamford CT), enriched against ProPublica and SEC EDGAR.")
    md_lines.append("")
    md_lines.append("| Score | Tier | Address | Sale Price | Owner | Absentee | Entity | Brief |")
    md_lines.append("|---|---|---|---|---|---|---|---|")
    for lead in leads:
        address = _lead_address(lead)
        tier = tier_for_score(lead["score"])
        brief_name = f"{lead['town_slug']}-{lead['parcel_id']}.md"
        md_lines.append(
            f"| {lead['score']} | {tier} | {address} | ${lead['sale_price']:,} | "
            f"{lead.get('owner_name', '')} | {'Y' if lead.get('absentee_flag') else 'N'} | "
            f"{'Y' if lead.get('entity_flag') else 'N'} | [{brief_name}]({brief_name}) |"
        )
    md_path = os.path.join(out_dir, "SUMMARY.md")
    with open(md_path, "w") as f:
        f.write("\n".join(md_lines))

    csv_path = os.path.join(out_dir, "leads.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["score", "tier", "address", "sale_price", "sale_date", "owner_name",
                          "mailing_address", "absentee_flag", "entity_flag", "portfolio_count",
                          "year_built", "living_area_sqft", "lot_acres", "bedrooms", "full_baths",
                          "half_baths", "has_pool", "assessed_value",
                          "nonprofit_match", "sec_filing_hits", "parcel_url"])
        for lead in leads:
            enrichment = lead.get("enrichment", {})
            nonprofit_matches = enrichment.get("nonprofit_matches") or []
            sec_matches = enrichment.get("sec_matches")
            writer.writerow([
                lead["score"],
                tier_for_score(lead["score"]),
                _lead_address(lead),
                lead["sale_price"],
                lead.get("sale_date", ""),
                lead.get("owner_name", ""),
                lead.get("mailing_address", ""),
                lead.get("absentee_flag", False),
                lead.get("entity_flag", False),
                lead.get("portfolio_count", 0),
                lead.get("year_built", ""),
                lead.get("living_area_sqft", ""),
                lead.get("lot_acres", ""),
                lead.get("bedrooms", ""),
                lead.get("full_baths", ""),
                lead.get("half_baths", ""),
                lead.get("has_pool", False),
                lead.get("assessed_value", ""),
                nonprofit_matches[0]["org_name"] if nonprofit_matches else "",
                sec_matches["total_hits"] if sec_matches else 0,
                lead.get("parcel_url", ""),
            ])

    return md_path, csv_path
