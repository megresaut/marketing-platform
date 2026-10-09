"""
enrich.py
Real, live public-records enrichment. No fabricated data, no paid APIs.

ProPublica Nonprofit Explorer API is name-search over ORGANIZATION names, not
officer names (confirmed empirically — it will not tell you "this person is a
board member of X"). We use it as a heuristic: wealthy individuals often have
a foundation named after their own surname ("Smith Family Foundation").
Any hit is reported as a possible name match, not a confirmed affiliation.

SEC EDGAR full-text search indexes filings since 2001 and will surface a
person's name if it appears anywhere in a filing (bios, fund manager lists,
proxy statements, etc.). A hit means the name appears in that filing — it is
NOT proof of a specific role. We report filing counts/companies/dates as
found, and leave role interpretation to a human reviewer.
"""

import time

import requests

REQUEST_DELAY_SECONDS = 0.5
SEC_USER_AGENT = "avm-leads-research (contact: megkrishdev@gmail.com)"

BUSINESS_ENTITY_WORDS = (
    "LLC", "LP", "LLP", "INC", "CORP", "HOLDINGS", "REALTY", "GROUP", "PARTNERS",
    "CAPITAL", "PROPERTIES", "ASSOCIATES", "TOD", " CO ", "VENTURES", "MANAGEMENT",
)


def _looks_like_person_or_personal_trust(owner_name, entity_flag):
    """Decide whether a name is worth running through person-name enrichment.
    Plain individuals: yes. Individual/family revocable trusts ("SMITH JOHN A
    REVOC TRUST"): yes, the surname is real. Generic business/place-named
    entities ("SAUGATUCK TOD 606 LLC", "39 COMPO LLC"): no — the first word
    is not a surname and searching it produces false-positive noise.
    """
    if not owner_name:
        return False
    if not entity_flag:
        return True
    upper = f" {owner_name.upper()} "
    has_trust_marker = " TR " in upper or "TRUST" in upper
    has_business_word = any(word in upper for word in BUSINESS_ENTITY_WORDS)
    return has_trust_marker and not has_business_word


def propublica_name_match(owner_name):
    """Search ProPublica Nonprofit Explorer for organizations whose name
    resembles the owner's surname (e.g. a family foundation). Returns a list
    of possible matches, or [] on no match / failure.
    """
    surname = owner_name.split()[0].strip(",") if owner_name else ""
    if len(surname) < 3:
        return []

    try:
        time.sleep(REQUEST_DELAY_SECONDS)
        resp = requests.get(
            "https://projects.propublica.org/nonprofits/api/v2/search.json",
            params={"q": surname},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"    WARNING: ProPublica lookup failed for '{surname}': {e}")
        return []

    matches = []
    for org in data.get("organizations", [])[:5]:
        name = org.get("name", "")
        if surname.upper() in name.upper() and org.get("score", 0) > 40:
            matches.append(
                {
                    "org_name": name,
                    "ein": org.get("strein"),
                    "city": org.get("city"),
                    "state": org.get("state"),
                    "confidence": "name_match_only — verify officer identity manually",
                }
            )
    return matches


def edgar_name_match(owner_name):
    """Search SEC EDGAR full-text search for the owner's full name in quotes.
    Returns a dict with hit count, distinct companies, and a few sample
    filings, or None on failure / zero hits.
    """
    clean_name = owner_name.strip()
    if not clean_name or len(clean_name.split()) < 2:
        return None

    query = f'"{clean_name}"'
    try:
        time.sleep(REQUEST_DELAY_SECONDS)
        resp = requests.get(
            "https://efts.sec.gov/LATEST/search-index",
            params={"q": query},
            headers={"User-Agent": SEC_USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"    WARNING: EDGAR lookup failed for '{clean_name}': {e}")
        return None

    total = data.get("hits", {}).get("total", {}).get("value", 0)
    if not total:
        return None

    hits = data.get("hits", {}).get("hits", [])
    companies = {}
    for h in hits:
        src = h.get("_source", {})
        for name in src.get("display_names", []):
            companies.setdefault(name, {"form": src.get("form"), "file_date": src.get("file_date")})

    return {
        "total_hits": total,
        "companies": list(companies.keys())[:5],
        "sample_filings": [
            {"company": k, "form": v["form"], "file_date": v["file_date"]}
            for k, v in list(companies.items())[:3]
        ],
    }


def enrich_owner(owner_name, entity_flag):
    """Run both enrichment sources for a given owner name. For entity-held
    properties (LLC/Trust) we still attempt a search on any human-looking
    name fragment, but flag confidence as lower since the buyer of record
    isn't a natural person.
    """
    result = {"nonprofit_matches": [], "sec_matches": None, "entity_owned": entity_flag}
    if not _looks_like_person_or_personal_trust(owner_name, entity_flag):
        return result

    result["nonprofit_matches"] = propublica_name_match(owner_name)
    result["sec_matches"] = edgar_name_match(owner_name)
    return result
