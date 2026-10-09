"""
vgsi_source.py
Live sourcing of real property sales from Vision Government Solutions (VGSI)
assessor sites for CT towns. No fallback/fabricated data — if a fetch fails,
that town is skipped and reported as skipped.

Confirmed working towns (as of 2026-08-20): westportct, fairfieldct, stamfordct.
Confirmed NOT working: Westchester County NY (propaccess/salesperson.westchestergov.com
have no DNS; the state-level swcf/swcf.orpts.tax.ny.gov SalesWeb resets TLS
connections from non-browser clients). Do not add Westchester here without a
different data source.
"""

import re
import time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REQUEST_DELAY_SECONDS = 0.6

ENTITY_KEYWORDS = ("LLC", "TRUST", "TRUSTEE", "INC", "CORP", "L P", "LP", "LLP", "FOUNDATION", "HOLDINGS")


def _entity_flag(owner_name):
    upper = owner_name.upper()
    return any(kw in upper for kw in ENTITY_KEYWORDS)


def _hidden_fields(soup):
    fields = {}
    for tag in soup.find_all("input"):
        name = tag.get("name")
        if not name:
            continue
        if tag.get("type") in ("checkbox", "image"):
            continue
        fields[name] = tag.get("value", "")
    return fields


def _all_checkboxes_checked(soup):
    return {
        cb["name"]: cb["value"]
        for cb in soup.find_all("input", {"type": "checkbox"})
        if cb.has_attr("name")
    }


def _parse_results_table(soup):
    table = soup.find("table", {"id": "MainContent_grdResults"})
    if not table:
        return [], None
    rows = table.find_all("tr")
    out = []
    for row in rows:
        link = row.find("a", href=re.compile(r"Parcel\.aspx\?pid=\d+"))
        cells = row.find_all("td")
        if not link or len(cells) < 6:
            continue
        pid_match = re.search(r"pid=(\d+)", link["href"])
        if not pid_match:
            continue
        price_text = cells[2].get_text(strip=True).replace("$", "").replace(",", "")
        try:
            price = int(float(price_text))
        except ValueError:
            continue
        out.append(
            {
                "parcel_id": int(pid_match.group(1)),
                "location": link.get_text(strip=True),
                "sale_date_raw": cells[1].get_text(strip=True),
                "sale_price": price,
                "model": cells[3].get_text(strip=True),
                "style": cells[4].get_text(strip=True),
                "living_area": cells[5].get_text(strip=True),
            }
        )
    return out, table


def search_town_sales(town_slug, min_price=2500000, months_back=24, max_pages=15, residential_only=True):
    """Live search of a VGSI town's Sales.aspx for sales >= min_price in the
    trailing `months_back` months. Returns list of raw sale dicts (no owner
    info yet — that requires a follow-up parcel fetch). Returns [] and prints
    a warning if the live fetch fails for any reason.
    """
    base_url = f"https://gis.vgsi.com/{town_slug}/Sales.aspx"
    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    try:
        r = session.get(base_url, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  [{town_slug}] WARNING: could not reach {base_url}: {e}")
        return []

    soup = BeautifulSoup(r.text, "lxml")
    today = datetime.now()
    from_date = (today - timedelta(days=months_back * 30)).strftime("%m/%d/%Y")
    to_date = today.strftime("%m/%d/%Y")

    fields = _hidden_fields(soup)
    fields.update(_all_checkboxes_checked(soup))
    fields["ctl00$MainContent$txtSalesFrom"] = from_date
    fields["ctl00$MainContent$txtSalesTo"] = to_date
    fields["ctl00$MainContent$txtSalePriceFrom"] = str(min_price)
    fields["ctl00$MainContent$txtSalePriceTo"] = "100000000"
    fields["ctl00$MainContent$txtBldAreaFrom"] = ""
    fields["ctl00$MainContent$txtBldAreaTo"] = ""
    # Some towns' forms (e.g. Fairfield) carry extra filters Westport's form
    # doesn't have — a land-size range that defaults to a narrow band. Clear
    # anything that looks like a min/max filter field so we only filter by
    # price and date, never an unintended default range.
    for key in list(fields.keys()):
        if key.startswith("ctl00$MainContent$txtLand") or key.startswith("ctl00$MainContent$txtAcre"):
            fields[key] = ""
    fields["ctl00$MainContent$hdnMode"] = "search"
    fields["__EVENTTARGET"] = ""
    fields["__EVENTARGUMENT"] = ""

    time.sleep(REQUEST_DELAY_SECONDS)
    try:
        r2 = session.post(base_url, data=fields, timeout=25)
        r2.raise_for_status()
    except requests.RequestException as e:
        print(f"  [{town_slug}] WARNING: search POST failed: {e}")
        return []

    soup2 = BeautifulSoup(r2.text, "lxml")
    results, _ = _parse_results_table(soup2)

    page = 1
    while page < max_pages:
        pagination_targets = set(
            re.findall(r"__doPostBack\('ctl00\$MainContent\$grdResults','(Page\$\d+)'\)", r2.text)
        )
        next_page_arg = f"Page${page + 1}"
        if next_page_arg not in pagination_targets:
            break

        page_fields = _hidden_fields(soup2)
        page_fields["__EVENTTARGET"] = "ctl00$MainContent$grdResults"
        page_fields["__EVENTARGUMENT"] = next_page_arg
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            r2 = session.post(base_url, data=page_fields, timeout=25)
            r2.raise_for_status()
        except requests.RequestException as e:
            print(f"  [{town_slug}] WARNING: pagination failed on page {page + 1}: {e}")
            break
        soup2 = BeautifulSoup(r2.text, "lxml")
        more, _ = _parse_results_table(soup2)
        if not more:
            break
        results.extend(more)
        page += 1

    # The VGSI price filter is unreliable server-side (confirmed empirically) —
    # always enforce the threshold ourselves rather than trusting the form.
    results = [r for r in results if r["sale_price"] >= min_price]

    # Concierge property management targets homes, not commercial/vacant land.
    if residential_only:
        results = [r for r in results if r["model"].strip().upper() == "RESIDENTIAL"]

    for rec in results:
        rec["town_slug"] = town_slug

    print(f"  [{town_slug}] {len(results)} sales >= ${min_price:,} since {from_date}")
    return results, session


def search_by_owner_name(town_slug, name_query):
    """Direct owner-name lookup against a town's VGSI records (not limited
    to recent sales — this searches every parcel on file). Useful for
    checking whether a specific named person owns property in a given town,
    e.g. a known executive, rather than waiting for them to appear in a
    sales-list scan.

    Note: VGSI's Search.aspx uses a single visible text box whose target
    field is chosen by a dropdown (0=Address, 1=Owner, 2=Acct#, 3=Mblu,
    4=PID, 5=All); the underlying named inputs are hidden and JS-driven, so
    both the visible-field name and its dropdown-selected value must be set
    for the server to actually filter (confirmed empirically — omitting
    either returns the entire unfiltered parcel list).
    """
    url = f"https://gis.vgsi.com/{town_slug}/Search.aspx"
    session = requests.Session()
    session.headers.update({"User-Agent": UA})
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  [{town_slug}] WARNING: could not reach {url}: {e}")
        return []

    soup = BeautifulSoup(r.text, "lxml")
    fields = _hidden_fields(soup)
    fields["ctl00$MainContent$ddlSearchSource"] = "1"  # Owner
    fields["ctl00$MainContent$txtSearch"] = name_query
    fields["ctl00$MainContent$txtSearchOwner"] = name_query
    fields["ctl00$MainContent$hdnSearch"] = name_query
    fields["ctl00$MainContent$hdnSearchOwner"] = name_query
    fields["__EVENTTARGET"] = ""
    fields["__EVENTARGUMENT"] = ""

    time.sleep(REQUEST_DELAY_SECONDS)
    try:
        r2 = session.post(url, data=fields, timeout=25)
        r2.raise_for_status()
    except requests.RequestException as e:
        print(f"  [{town_slug}] WARNING: owner search failed: {e}")
        return []

    soup2 = BeautifulSoup(r2.text, "lxml")
    table = soup2.find("table", {"id": "MainContent_grdSearchResults"})
    if not table:
        return []

    results = []
    for row in table.find_all("tr")[1:]:
        cells = [c.get_text(strip=True) for c in row.find_all("td")]
        link = row.find("a", href=re.compile(r"Parcel\.aspx\?pid=\d+"))
        if len(cells) < 2:
            continue
        pid_match = re.search(r"pid=(\d+)", link["href"]) if link else None
        results.append(
            {
                "town_slug": town_slug,
                "address": cells[0],
                "owner_name": cells[1],
                "parcel_id": int(pid_match.group(1)) if pid_match else None,
            }
        )
    return results


def fetch_parcel_detail(session, town_slug, parcel_id):
    """Fetch owner name, mailing address, and building attributes for a parcel."""
    url = f"https://gis.vgsi.com/{town_slug}/Parcel.aspx?pid={parcel_id}"
    time.sleep(REQUEST_DELAY_SECONDS)
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"    WARNING: parcel fetch failed for pid={parcel_id}: {e}")
        return None

    soup = BeautifulSoup(r.text, "lxml")
    text_lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]

    def line_after(label, lines):
        # VGSI omits the value line entirely for empty/zero fields, so the
        # "next" line is sometimes actually the following field's label. A
        # real value here never ends in ':' — a label always does — so use
        # that to detect "no value present" rather than misreading the next
        # label as this field's value.
        for i, l in enumerate(lines):
            if l == label and i + 1 < len(lines):
                candidate = lines[i + 1]
                if candidate == label or candidate.endswith(":"):
                    return ""
                return candidate
        return ""

    def leading_number(raw):
        m = re.match(r"^([\d.,]+)", raw or "")
        return m.group(1) if m else ""

    owner = line_after("Owner", text_lines)
    location = line_after("Location", text_lines)

    addr_idx = None
    for i, l in enumerate(text_lines):
        if l == "Address" and i > 0 and text_lines[i - 1] in ("Co-Owner", owner):
            addr_idx = i
            break
    mailing_addr = ""
    if addr_idx is not None:
        parts = []
        for j in range(addr_idx + 1, min(addr_idx + 3, len(text_lines))):
            if text_lines[j] in ("Sale Price",):
                break
            parts.append(text_lines[j])
        mailing_addr = ", ".join(parts)

    year_built = line_after("Year Built:", text_lines)
    living_area = line_after("Living Area:", text_lines)
    style = line_after("Style:", text_lines)
    grade = line_after("Grade:", text_lines)
    bedrooms = leading_number(line_after("Total Bedrooms:", text_lines))
    full_baths = leading_number(line_after("Total Bthrms:", text_lines))
    half_baths = leading_number(line_after("Total Half Baths:", text_lines))
    total_rooms = leading_number(line_after("Total Rooms:", text_lines))
    fireplaces = leading_number(line_after("Fireplaces", text_lines))
    heat_type = line_after("Heat Type:", text_lines)
    ac_type = line_after("AC Type:", text_lines)
    lot_acres = line_after("Size (Acres)", text_lines)
    assessed_value = line_after("Assessed Value", text_lines)
    appraised_value = line_after("Appraisal", text_lines)
    page_text_upper = soup.get_text(" ").upper()
    has_pool = "POOL" in page_text_upper
    has_garage = "GARAGE" in page_text_upper

    ownership_history = []
    hist_table = None
    for table in soup.find_all("table"):
        header_text = table.get_text(" ", strip=True)
        if "Ownership History" in header_text and "Sale Price" in header_text:
            hist_table = table
            break
    if hist_table:
        rows = hist_table.find_all("tr")
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all("td")]
            if len(cells) >= 5 and cells[0] not in ("Owner", ""):
                ownership_history.append(
                    {
                        "owner": cells[0],
                        "sale_price": cells[1],
                        "sale_date": cells[4] if len(cells) > 4 else "",
                    }
                )

    town_zip_prefix = {
        "westportct": "0688",
        "fairfieldct": "0682",
        "stamfordct": "0690",
    }.get(town_slug, "")
    mailing_upper = mailing_addr.upper()
    location_upper = location.upper()
    same_street = location_upper and location_upper.split(",")[0] in mailing_upper
    absentee = bool(mailing_addr) and not same_street and town_zip_prefix and town_zip_prefix not in mailing_addr

    return {
        "owner_name": owner,
        "mailing_address": mailing_addr,
        "absentee_flag": absentee,
        "entity_flag": _entity_flag(owner) if owner else False,
        "year_built": year_built,
        "living_area_sqft": living_area,
        "style": style,
        "grade": grade,
        "bedrooms": bedrooms,
        "full_baths": full_baths,
        "half_baths": half_baths,
        "total_rooms": total_rooms,
        "fireplaces": fireplaces,
        "heat_type": heat_type,
        "ac_type": ac_type,
        "lot_acres": lot_acres,
        "assessed_value": assessed_value,
        "appraised_value": appraised_value,
        "has_pool": has_pool,
        "has_garage": has_garage,
        "ownership_history": ownership_history,
        "parcel_url": url,
    }
