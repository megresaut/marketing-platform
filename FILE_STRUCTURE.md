# AVM Concierge Marketing Platform — File Structure

```
marketing_platform/
│
├── index.html                    ← THE DEMO (single deliverable, built from template)
│                                    All CSS, JS, and data inline. This is what gets hosted.
│
├── avm_marketing_hub_demo_8.html ← Prior iteration (reference for UI patterns only)
├── index_16.html                 ← Prior iteration (reference for layout patterns only)
│
├── build/                        ← Build-time scripts (not shipped, only run during dev)
│   ├── fetch_properties.py       ← Fetches real property data from SalesWeb + VGSI
│   ├── enrich_owners.py          ← Runs ProPublica + EDGAR lookups on real owner names
│   ├── find_network_match.py     ← Identifies best network match from enriched owners
│   ├── generate_seed_data.py     ← Generates 35–45 fictional leads + 5–6 existing clients
│   └── build.py                  ← Orchestrator: runs all above, outputs data/
│
├── data/                         ← Intermediate data files (git-ignored after first run)
│   ├── real_properties.json      ← 4–5 real Westchester/CT properties from public records
│   ├── owner_profiles.json       ← Enriched owner data: ProPublica + EDGAR results per owner
│   ├── network_match.json        ← The confirmed real network match: owner, client, org
│   ├── seeded_leads.json         ← 35–45 fictional leads in various pipeline stages
│   └── seeded_clients.json       ← 5–6 fictional existing AVM clients with affiliations
│
├── TECHNICAL_ARCHITECTURE.md    ← This project's technical spec (this file's sibling)
├── FILE_STRUCTURE.md             ← This file
└── BUILD_PLAN.md                 ← Ordered build tasks with dependencies
```

---

## File Descriptions

### `index.html` (primary deliverable)

The entire application. Structured as follows internally:

```html
<head>
  <!-- Google Fonts: Fraunces (headlines) + Inter Tight (body) + JetBrains Mono (data) -->
  <!-- D3.js v7 from CDN for network graph -->
</head>
<body>
  <div id="app">
    <nav id="sidebar">...</nav>
    <main id="main">
      <header id="topbar">...</header>
      <div id="content">
        <!-- 14 page divs, show/hide via CSS class -->
        <div id="page-dashboard">...</div>
        <div id="page-leads">...</div>
        <div id="page-profile">...</div>
        <div id="page-queue">...</div>
        <div id="page-email">...</div>
        <div id="page-sequences">...</div>
        <div id="page-network">...</div>
        <div id="page-pipeline">...</div>
        <div id="page-fees">...</div>
        <div id="page-billing">...</div>
        <div id="page-analytics">...</div>
        <div id="page-reengagement">...</div>
        <div id="page-watchlist">...</div>
        <div id="page-settings">...</div>
      </div>
    </main>
  </div>

  <script>
    // === DATA LAYER ===
    // Injected by build script — do not edit manually
    const REAL_PROPERTIES = [...];  // 4-5 real properties
    const SEEDED_LEADS = [...];     // 35-45 fictional leads
    const EXISTING_CLIENTS = [...]; // 5-6 fictional existing clients
    const NETWORK_GRAPH_DATA = {...}; // nodes + edges for D3

    // === SCORING ENGINE ===
    function scoreLeads(leads) {...}

    // === LIVE API CALLS ===
    async function fetchProPublica(ownerName) {...}
    async function fetchEdgar(ownerName) {...}

    // === NETWORK MATCH ENGINE ===
    function findNetworkMatches(lead, clients) {...}

    // === UI CONTROLLERS ===
    function navigate(pageId) {...}
    function renderLeadsTable(leads) {...}
    function renderProfile(leadId) {...}
    function runSearch() {...}  // The magic button
    function renderNetworkGraph(data) {...}
    // ... etc
  </script>
</body>
```

### `build/fetch_properties.py`

Fetches real property data at build time. Output is `data/real_properties.json`.

- **SalesWeb (Westchester NY)**: POST to `https://swcf.tax.ny.gov/cfapps/salesWebProd/salesWeb/` with county=Westchester, sale amount filter > $2,500,000, date range last 6 months. Parses HTML response. Returns: address, buyer_name, sale_price, sale_date, municipality.
- **VGSI (CT towns)**: POST to `https://gis.vgsi.com/westportct/Sales.aspx` and `fairfieldct` and `stamfordct`. ViewState-handled requests. Returns: property_id, address, sale_price, sale_date, owner_name, owner_mailing_address, property_characteristics.
- **Selection criteria**: Picks 4–5 best properties based on: sale price (higher = better), absentee status (yes = preferred), entity name buyer (LLC/Trust = preferred), recency (more recent = preferred).

### `build/enrich_owners.py`

For each real property in `data/real_properties.json`, runs:
1. ProPublica API: `GET https://projects.propublica.org/nonprofits/api/v2/search.json?q=[owner_name]`
2. EDGAR EFTS: `GET https://efts.sec.gov/LATEST/search-index?q="[owner_name]"&forms=DEF+14A`
3. Returns structured profile: `{owner_name, nonprofits: [...], public_companies: [...], state_filings: []}`

Output: `data/owner_profiles.json`

### `build/find_network_match.py`

Takes `data/owner_profiles.json`, scans all nonprofit and public company affiliations, identifies which real owner has at least one verifiable organization membership. Outputs:
```json
{
  "property_id": "REAL_PROPERTY_1",
  "real_owner": "John Smith",
  "organization": "Greenwich Hospital Board",
  "connection_type": "nonprofit_board",
  "seeded_client_name": "William Thornton",
  "seeded_client_property": "14 Old Church Rd, Greenwich CT"
}
```
Output: `data/network_match.json`

### `build/generate_seed_data.py`

Generates all fictional data:

**35–45 seeded leads** at realistic CT and Westchester addresses, with:
- Pipeline stage distribution: ~15 cold, ~10 contacted, ~7 call booked, ~5 proposal sent, ~3 signed
- Fee values consistent with AVM actuals: avg $566/mo, median $600/mo, high tier $1,000–$3,600/mo
- 2 leads in re-engagement state with trigger reasons
- 2 watchlist alerts
- 1 lead with a completed call summary + AI follow-up recommendations
- Names drawn from realistic CT/NY demographics

**5–6 fictional existing clients** with:
- Real nonprofit/organization affiliations (same ones found for REAL_NETWORK_MATCH)
- At least 1 client sharing the REAL_NETWORK_MATCH organization
- Signed dates spread across the last 12 months
- Fee structures consistent with AVM actuals

Output: `data/seeded_leads.json`, `data/seeded_clients.json`

### `build/build.py`

Master orchestrator. Runs all scripts in order, injects results into `index.html` template, writes final `index.html`.

```python
# Pseudocode
run(fetch_properties)        # → data/real_properties.json
run(enrich_owners)           # → data/owner_profiles.json
run(find_network_match)      # → data/network_match.json
run(generate_seed_data)      # → data/seeded_leads.json, data/seeded_clients.json
inject_into_html_template()  # → index.html
```

### `data/` directory

All intermediate JSON files. Structure for `real_properties.json`:

```json
[
  {
    "id": "rp1",
    "address": "47 Round Hill Road, Greenwich CT 06831",
    "sale_price": 6250000,
    "sale_date": "2026-03-15",
    "buyer_name": "Round Hill Holdings LLC",
    "entity_flag": true,
    "absentee_flag": true,
    "owner_mailing_address": "330 Park Avenue, New York NY 10022",
    "property": {
      "year_built": 1987,
      "sqft": 7400,
      "bedrooms": 6,
      "bathrooms": 7,
      "lot_acres": 2.1,
      "assessed_value": 4100000
    },
    "source": "vgsi_westportct",
    "intel": {
      "propublica": [...],
      "edgar": [...],
      "state_filings": [],
      "press": ""
    }
  }
]
```

---

## What Is and Isn't in Git

**In source control**:
- All HTML/CSS/JS source
- Build scripts
- This documentation

**Not in source control** (`.gitignore`):
- `data/` — regenerated each build
- `index.html` if it contains real owner PII (mailing addresses, names) — check legal before committing

---

## Build Artifacts Size Estimates

| File | Estimated size |
|---|---|
| `index.html` (final) | 600–900 KB |
| `data/real_properties.json` | 15–30 KB |
| `data/seeded_leads.json` | 80–120 KB |
| `data/owner_profiles.json` | 20–40 KB |
| D3.js (CDN, not local) | ~280 KB (cached) |

Total initial download: < 1 MB. No additional requests on page load.
