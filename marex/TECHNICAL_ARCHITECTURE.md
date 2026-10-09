# AVM Concierge Marketing Platform — Technical Architecture

## Executive Summary

This is a pitch demo built as a **single self-contained HTML file** with embedded data and selective live API calls. The vehicle matches the existing codebase pattern (`avm_marketing_hub_demo_8.html`), eliminates all setup friction, and can be hosted or opened directly. Real property data is pre-fetched once during the build phase and embedded as a JavaScript constant. Live ProPublica and EDGAR calls fire from the browser when a profile is opened — both APIs support CORS, so no proxy is needed.

---

## Stack

| Layer | Choice | Rationale |
|---|---|---|
| Delivery | Single HTML file | Zero setup, works from file:// or any host, matches existing pattern |
| Styling | CSS custom properties, no framework | Existing design system in demo_8, no build step needed |
| Interactivity | Vanilla JS | No compilation, no node_modules, instant load |
| Build scripts | Python 3 | Pre-fetches VGSI + SalesWeb data at build time; generates embedded seed data |
| Hosting | `python3 -m http.server` OR Vercel/Netlify static | Live API calls require HTTPS origin for CORS; file:// blocked by ProPublica |
| Network graph | D3.js (CDN) | Force-directed layout, minimal weight, well-supported |

---

## Data Source Reality Check

The brief names five data sources. Testing reveals the following ground truth:

### NY SalesWeb — ✅ Available
- **URL**: `https://swcf.tax.ny.gov/cfapps/salesWebProd/salesWeb/`
- **What it has**: RP-5217 real property transfer data for all NY counties outside NYC, last 10 years, updated weekly
- **Access method**: ASP.NET WebForms with ViewState — requires POST with session tokens
- **CORS from browser**: No — server-side fetch required at build time
- **Strategy**: Python build script fetches Westchester County recent sales above $2.5M, returns address, buyer name, sale price, sale date. Data embedded in HTML.

### Vision Government Solutions (VGSI) — ⚠️ Partial
- **Works for**: Westport CT, Fairfield CT, Stamford CT
- **Does NOT work for**: Greenwich CT (404), Darien CT (404), New Canaan CT (404)
- **What it has**: Property cards, sales history, owner mailing address, property characteristics, assessed value
- **Access method**: ASP.NET WebForms with ViewState — requires POST
- **CORS from browser**: No — server-side fetch required at build time
- **Strategy**: Python build script queries `Sales.aspx` for each available town, filters sales > $2.5M, pulls owner mailing address to enable absentee detection.

### Greenwich CT — Alternative Source
- Greenwich has its own assessor database separate from VGSI, accessible at `https://www.greenwichct.gov/150/Assessor` (exact search URL TBD during build)
- **Fallback**: Westport and Fairfield are strong Greenwich alternatives (same market, same price tier). For the demo narrative, we present "CT markets" rather than specifically Greenwich-only.
- If a Greenwich-specific property is needed for the demo story, it can be pre-fetched directly from the town's assessor portal.

### ProPublica Nonprofit API — ✅ Available, CORS-Friendly
- **URL**: `https://projects.propublica.org/nonprofits/api/v2/search.json?q=[NAME]`
- **What it has**: IRS 990 data — organization names, officer names, EINs, locations
- **Access method**: GET, JSON, no auth required, CORS-enabled
- **CORS from browser**: Yes — live calls work
- **Strategy**: When a profile is opened, browser JS calls ProPublica with owner name. Results displayed in Professional Intelligence section. Also called during build to identify which real owner has the richest affiliation data (selects the network match target).

### SEC EDGAR Full-Text Search — ✅ Available, CORS-Friendly
- **URL**: `https://efts.sec.gov/LATEST/search-index?q=[NAME]&forms=DEF+14A`
- **What it has**: Proxy statement (DEF 14A) search — surfaces executives/directors in public company filings
- **Access method**: GET, JSON, needs `User-Agent` header. Returns `display_names`, `file_date`, `ciks`, `biz_states`.
- **CORS from browser**: Yes — live calls work with proper headers
- **Strategy**: Browser JS calls EDGAR with owner name when profile opens. Results surface any public company board memberships.

---

## Component Architecture

```
┌─────────────────────────────────────────────────────────┐
│  index.html  (single file, ~4,000 lines)                │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  EMBEDDED DATA (JS constants, set at build time) │   │
│  │  - REAL_PROPERTIES[4-5] (SalesWeb + VGSI)       │   │
│  │  - SEEDED_LEADS[35-45]   (Python generated)     │   │
│  │  - EXISTING_CLIENTS[5-6] (Python generated)     │   │
│  │  - NETWORK_GRAPH_NODES   (built from above)     │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  LIVE API CALLS (browser JS, on profile open)   │   │
│  │  - ProPublica search by owner name              │   │
│  │  - EDGAR EFTS search by owner name              │   │
│  │  - State biz filings: CT SOS / NY DOS (seeded)  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  PAGES (nav = show/hide, no routing)            │   │
│  │  dashboard | leads | profile | queue | email    │   │
│  │  network | pipeline | fees | analytics | billing│   │
│  │  reengagement | watchlist | sequences | settings│   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## The "Run Search" Interaction

This is the most critical moment in the demo. The implementation:

1. User clicks "Run Search" button on Dashboard or Leads page
2. Button disables, loading overlay appears: *"Scanning public records — Westchester County, CT markets…"* with animated dots
3. After a **minimum 3 second delay** (even if data is already available), the 4 real property cards animate in sequentially with 300ms gaps
4. Each card triggers a dashboard counter increment
5. Each card has a pulsing green "Platform Generated" badge for 2 seconds after appearing
6. Button re-enables with "Search again" state

**The real data behind this button** is already embedded — the loading animation is purely theatrical UX. This guarantees zero flakiness.

---

## Lead Scoring Engine

Implemented entirely in JavaScript at runtime. No external calls.

| Signal | Points | Detection |
|---|---|---|
| Sale price ≥ $5M | 30 | property.salePrice |
| Sale price $2.5M–$5M | 20 | property.salePrice |
| Absentee owner | 25 | owner.mailingAddr ≠ property.addr |
| Multi-property ownership | 20 | owner.portfolioCount > 1 |
| Property age > 10 years | 15 | property.yearBuilt |
| Recent purchase (< 12 mo) | 10 | property.saleDate |
| Network match found | 15 (bonus) | networkMatches.length > 0 |

Score ≥ 70 → Manual Outreach Queue. Score < 70 → Automated Email.

---

## Professional Intelligence Layer

For each profile, four sources are displayed:

1. **ProPublica (IRS 990)** — live browser fetch when profile opens. Search by owner name. Shows nonprofit board memberships.
2. **SEC EDGAR** — live browser fetch. DEF 14A search. Shows public company directorships.
3. **State Business Filings** — pre-seeded. CT SOS and NY DOS do not have CORS-friendly APIs. Populated for real properties during build using Python. Fictional for seeded leads.
4. **Web/Press mentions** — pre-seeded narrative text. Simulates a web search result. One or two lines per profile.

All four sections always render — empty ones show "No results found in public filings" rather than being hidden.

---

## Network Match Engine

Runs at HTML load time in JavaScript against embedded data. For each lead:
1. Extract all organization names from their professional intelligence data
2. Compare against each existing client's affiliation list
3. If overlap found → generate a NetworkMatch object: `{leadId, clientId, organization, connectionType}`
4. The one guaranteed match (REAL_NETWORK_MATCH) is hardcoded during build

Network match alert renders as a gold-bordered banner at the top of the profile, above all other sections.

---

## Network Graph

Built with D3.js force-directed simulation. Loaded from CDN (`https://d3js.org/d3.v7.min.js`).

- **Nodes**: All existing clients + all leads = 20–30 total
- **Edges**: Shared affiliation between any two nodes
- **Colors**: Nonprofit connection = gold, corporate = blue, press = purple
- **Gold-highlighted edge**: The REAL_NETWORK_MATCH connection
- **Click interaction**: Sidebar panel opens on node click with name, score, key flags, profile link

---

## Hosting

**During development / demo prep**: `python3 -m http.server 8080` from the project directory. Access at `http://localhost:8080`.

**For the actual demo link**: 
- Option A: Vercel drag-and-drop static deploy → `https://avm-demo.vercel.app` (takes 60 seconds)
- Option B: Netlify Drop → same speed
- Both are free, require no login from viewer, HTTPS so live API calls work

The file is also openable directly (`file://`) with one limitation: ProPublica and EDGAR live calls will be blocked by CORS. In that case, the Professional Intelligence section falls back to pre-embedded data gracefully.

---

## Browser Compatibility

Chrome on MacBook (macOS 14+) is the primary target. The file uses:
- CSS Grid and Custom Properties: Supported since Chrome 66
- Fetch API: Supported since Chrome 42
- ES6+ (const, arrow functions, async/await, template literals): Supported since Chrome 55
- D3 v7: Requires Chrome 80+

No polyfills needed. No transpilation needed.

---

## Performance

- Target: All 21 features navigable with < 100ms page transition time
- Run Search animation: 3–4 seconds intentional minimum
- ProPublica API response: 200–800ms typical — shown with inline loading spinner on profile
- EDGAR API response: 300–1000ms typical — same
- D3 graph initial render: < 500ms for 30 nodes

Total file size target: < 800KB uncompressed (no images, all inline SVG icons).
