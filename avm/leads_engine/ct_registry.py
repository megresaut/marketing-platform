"""
ct_registry.py
Connecticut's Secretary of the State business registry, published as free
open data on data.ct.gov (Socrata). No signup, no API key, no rate-limit
wall — this is the actual primary-source registry, not a paid aggregator.

Three linked datasets:
  - Business Master (n7gp-d28j): the entity itself — status, formation
    state, mailing address, business email.
  - Principals (ka36-64k6), keyed by business_id: the members/managers/
    officers filed with the state. For a single-member LLC this is very
    often the real beneficial owner. For an LLC formed by a law firm on a
    client's behalf, it's sometimes the attorney instead — report both
    possibilities, don't assert which.
  - Agents (qh2m-n44y), keyed by business_key (same id, different column
    name — confirmed empirically): the statutory registered agent. When
    this is an individual (not a registered-agent service company like CT
    Corporation System), it's frequently the owner acting as their own
    agent, and the record includes a direct phone/email.

This does not "unmask" a nominee trust (those aren't filed with the SOS
the same way) — it only resolves LLCs/corporations that are on file.
"""

import time

import requests

REQUEST_DELAY_SECONDS = 0.4
BASE = "https://data.ct.gov/resource"
BUSINESS_MASTER = f"{BASE}/n7gp-d28j.json"
PRINCIPALS = f"{BASE}/ka36-64k6.json"
AGENTS = f"{BASE}/qh2m-n44y.json"

STRIP_SUFFIXES = (" LLC", " L.L.C.", " INC", " INC.", " CORP", " CORPORATION", " THE")


def _name_candidates(name):
    """VGSI sometimes renders 'The X LLC' as 'X LLC THE' on the assessor
    card. Try the assessor's ordering, the corrected ordering, and the
    bare name without 'THE' at all.
    """
    n = name.strip()
    candidates = [n]
    upper = n.upper()
    if upper.startswith("THE "):
        candidates.append(n[4:])
    if upper.endswith(" THE"):
        stripped = n[:-4].strip()
        candidates.append(f"The {stripped}")
        candidates.append(stripped)
    seen = set()
    out = []
    for c in candidates:
        if c and c.upper() not in seen:
            seen.add(c.upper())
            out.append(c)
    return out


def _get(url, params):
    time.sleep(REQUEST_DELAY_SECONDS)
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"    WARNING: CT business registry request failed: {e}")
        return []


def _soda_escape(value):
    return value.replace("'", "''")


def search_business(owner_name):
    """Find the best-matching CT business registry entry for an owner name.
    Tries an exact case-insensitive match first, then falls back to a
    substring match. Returns None if nothing plausible is found.
    """
    for name_variant in _name_candidates(owner_name):
        if len(name_variant) < 3:
            continue
        escaped = _soda_escape(name_variant)
        matches = _get(BUSINESS_MASTER, {"$where": f"upper(name) = upper('{escaped}')", "$limit": 5})
        if not matches:
            matches = _get(BUSINESS_MASTER, {"$where": f"upper(name) like upper('%{escaped}%')", "$limit": 5})
        if matches:
            matches.sort(key=lambda c: 0 if c.get("status") == "Active" else 1)
            return matches[0]
    return None


def get_principals(business_id):
    rows = _get(PRINCIPALS, {"business_id": business_id})
    return [
        {"name": r.get("name__c", ""), "address": r.get("residence_address") or r.get("business_street_address_1", "")}
        for r in rows
        if r.get("name__c")
    ]


def get_agent(business_id):
    rows = _get(AGENTS, {"business_key": business_id})
    if not rows:
        return None
    r = rows[0]
    return {
        "name": r.get("name__c", ""),
        "type": r.get("type", ""),
        "phone": r.get("agent_phone", ""),
        "email": r.get("email", ""),
        "address": r.get("business_address", ""),
    }


def lookup_entity(owner_name):
    """Full lookup for an entity-owned property. Returns None if the owner
    name doesn't resolve to anything in the CT registry (e.g. it's an
    out-of-state or unfiled nominee trust rather than a registered LLC).
    """
    business = search_business(owner_name)
    if not business:
        return None

    business_id = business.get("id")
    principals = get_principals(business_id) if business_id else []
    agent = get_agent(business_id) if business_id else None

    return {
        "matched_name": business.get("name", ""),
        "status": business.get("status", ""),
        "formation_state": business.get("state_or_territory_formation", ""),
        "business_email": business.get("business_email_address", ""),
        "mailing_address": business.get("mailing_address", ""),
        "principals": principals,
        "agent": agent,
        "source_url": f"https://data.ct.gov/resource/n7gp-d28j.json?id={business_id}" if business_id else "",
    }
