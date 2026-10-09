"""
score.py
Transparent, rule-based scoring for concierge-property-management fit.
Every point is attached to a human-readable reason so the score can be
audited line by line — no black box.
"""

from datetime import datetime

_ENTITY_WORDS = ("LLC", "LP", "LLP", "INC", "CORP", "GROUP", "COMPANY", "CO.", "TRUST", "P.C.", "PLLC")


def _looks_like_entity_name(name):
    upper = f" {name.upper()} "
    return any(f" {w} " in upper or upper.endswith(f" {w} ") for w in _ENTITY_WORDS)


def score_lead(lead):
    score = 0
    reasons = []

    price = lead.get("sale_price", 0)

    living_area_raw = (lead.get("living_area_sqft") or "").replace(",", "")
    try:
        living_area = int(living_area_raw)
    except ValueError:
        living_area = None
    likely_teardown = living_area is not None and living_area < 1500 and price >= 2500000
    if likely_teardown:
        score -= 20
        reasons.append(
            f"-20: only {living_area} sqft existing structure for a ${price:,} purchase — likely a "
            "land-value/teardown play, not a livable luxury home. May not be a near-term concierge "
            "candidate; worth a follow-up if/when they build."
        )

    if price >= 7500000:
        score += 30
        reasons.append(f"+30: sale price ${price:,} is ultra-high-end (>= $7.5M)")
    elif price >= 5000000:
        score += 22
        reasons.append(f"+22: sale price ${price:,} is high-end (>= $5M)")
    elif price >= 2500000:
        score += 12
        reasons.append(f"+12: sale price ${price:,} meets luxury threshold (>= $2.5M)")

    if lead.get("absentee_flag"):
        score += 22
        reasons.append("+22: owner mailing address differs from property address (absentee owner — higher need for on-the-ground concierge management)")

    if lead.get("entity_flag"):
        score += 15
        reasons.append(f"+15: property held in an entity/trust ({lead.get('owner_name', '')}) — indicates sophisticated wealth structure")

    portfolio_count = lead.get("portfolio_count", 0)
    if portfolio_count > 1:
        pts = min(15, 8 * (portfolio_count - 1))
        score += pts
        reasons.append(f"+{pts}: owner appears on {portfolio_count} properties in this dataset (repeat luxury buyer)")

    year_built_raw = lead.get("year_built", "")
    try:
        year_built = int(year_built_raw)
        age = datetime.now().year - year_built
        if age > 25:
            score += 10
            reasons.append(f"+10: home built {year_built} ({age} years old) — likely higher maintenance/management need")
        elif age > 10:
            score += 5
            reasons.append(f"+5: home built {year_built} ({age} years old)")
    except (ValueError, TypeError):
        pass

    sale_date_raw = lead.get("sale_date", "")
    try:
        sale_date = datetime.strptime(sale_date_raw, "%m/%d/%Y")
        days_since = (datetime.now() - sale_date).days
        if 0 <= days_since <= 180:
            score += 12
            reasons.append(f"+12: sale closed {days_since} days ago — prime window to pitch concierge onboarding to a new owner")
        elif 0 <= days_since <= 365:
            score += 6
            reasons.append(f"+6: sale closed within the last year ({days_since} days ago)")
    except (ValueError, TypeError):
        pass

    enrichment = lead.get("enrichment", {})
    nonprofit_matches = enrichment.get("nonprofit_matches") or []
    if nonprofit_matches:
        score += 6
        reasons.append(
            f"+6: possible nonprofit/foundation name match — {nonprofit_matches[0]['org_name']} "
            f"({nonprofit_matches[0]['confidence']})"
        )

    ct_reg = lead.get("ct_registry")
    if ct_reg:
        agent = ct_reg.get("agent")
        person_principals = [p for p in (ct_reg.get("principals") or []) if not _looks_like_entity_name(p["name"])]
        if agent and agent.get("type") == "Individual" and (agent.get("email") or agent.get("phone")):
            score += 10
            reasons.append(
                f"+10: entity resolved to a named individual with direct contact info via CT SOS registry "
                f"({agent['name']}, registered as their own agent) — real outreach target identified"
            )
        elif person_principals:
            score += 5
            reasons.append(
                f"+5: entity resolved to a named principal via CT SOS registry "
                f"({person_principals[0]['name']}) — verify whether this is the beneficial owner or filing attorney"
            )

    sec_matches = enrichment.get("sec_matches")
    if sec_matches and sec_matches.get("total_hits"):
        score += 8
        companies = ", ".join(sec_matches.get("companies", [])[:2])
        reasons.append(
            f"+8: name appears in {sec_matches['total_hits']} SEC EDGAR filings"
            + (f" (incl. {companies})" if companies else "")
            + " — role unverified, review filings before referencing"
        )

    return min(score, 100), reasons


def tier_for_score(score):
    if score >= 75:
        return "Top Priority"
    if score >= 55:
        return "High Priority"
    if score >= 35:
        return "Moderate"
    return "Low Priority"
