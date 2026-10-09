# AVM Concierge Marketing Platform — Build Plan

## Critical Path

The demo script defines a precise viewing path. All build work is ordered to ensure this path is perfect before anything else is touched:

1. Dashboard landing → 2. Run Search → 3. Open REAL_PROPERTY_1 profile → 4. Professional intelligence → 5. Network match alert → 6. Manual outreach queue → 7. Automated email preview → 8. Call notes + follow-up → 9. Network graph → 10. Fee tracker + billing

Work that is off the critical path (re-engagement, watchlist, sequences, settings, analytics) is implemented last and can have rough edges.

---

## Phase 0 — Environment & Data Probe (Day 1, first 2 hours)

**Goal**: Confirm which real data sources are actually accessible and what data they return. All subsequent decisions depend on this.

### Task 0.1 — Set up Python build environment
```bash
mkdir -p build data
pip3 install requests beautifulsoup4 lxml
```
No virtual environment needed for a build script; system Python 3 is sufficient.

### Task 0.2 — Probe SalesWeb (Westchester NY)
- Load `https://swcf.tax.ny.gov/cfapps/salesWebProd/salesWeb/` in browser
- Identify form fields: county selector, sale amount min/max, date range
- Capture ViewState and session cookie from browser DevTools
- Write minimal `probe_salesweb.py`: POST with Westchester + $2.5M+ filter, print first 5 results
- **Success criterion**: Returns at least 5 real Westchester sales above $2.5M from last 6 months

### Task 0.3 — Probe VGSI
- Confirm: westportct, fairfieldct, stamfordct work; greenwichct does not
- Load `https://gis.vgsi.com/westportct/Sales.aspx` in browser
- Identify date range and price filter inputs
- Write minimal `probe_vgsi.py`: POST with last-6-months and $2.5M+ filter for westportct
- **Success criterion**: Returns real properties with owner mailing addresses (absentee detection)

### Task 0.4 — Probe ProPublica and EDGAR
- Test ProPublica: `curl 'https://projects.propublica.org/nonprofits/api/v2/search.json?q=[OWNER_NAME]'`
- Test EDGAR: `curl 'https://efts.sec.gov/LATEST/search-index?q="[OWNER_NAME]"&forms=DEF+14A'`
- **Success criterion**: Both return JSON without auth. Check CORS headers (needed for browser calls).

### Task 0.5 — Decision point
Based on probe results, confirm or adjust the following:
- Which 4–5 real properties will be REAL_PROPERTY_1 through 4
- Which owner has the richest ProPublica/EDGAR profile (will become the first-clicked profile)
- What the real network match organization will be
- If SalesWeb is hard to query, pivot to: VGSI Westport + Fairfield, scrape town assessor pages via requests

---

## Phase 1 — Real Data Acquisition (Day 1, hours 2–5)

**Goal**: Have `data/real_properties.json` and `data/owner_profiles.json` locked before writing any HTML.

### Task 1.1 — Write `build/fetch_properties.py`
Full implementation. Queries SalesWeb for Westchester (5+ towns: Greenwich NY, Scarsdale, Harrison, Rye, White Plains) and VGSI for Westport CT + Fairfield CT. Filters: sale price ≥ $2,500,000, date ≥ 6 months ago. Returns structured property objects. Includes:
- Entity name detection (LLC/Trust/Holdings/Partners/Group/Associates/Family/Estate suffix match)
- Absentee detection (compare owner mailing zip to property zip)
- Portfolio detection (search same owner name across all results)

Writes `data/real_properties.json`.

### Task 1.2 — Run and inspect
Run `python3 build/fetch_properties.py`, inspect output. Manually select the 4–5 best properties:
- REAL_PROPERTY_1: Highest sale price, absentee preferred, will be the "Top lead"
- REAL_PROPERTY_2: Entity name (LLC or Trust) preferred
- REAL_PROPERTY_3: CT source
- REAL_PROPERTY_4: Westchester source
- REAL_PROPERTY_5 (optional): Reserved if none of 1–4 produce a good network match

### Task 1.3 — Write `build/enrich_owners.py`
For each selected property, resolve the owner:
- If entity → check if state filings name returns an individual officer (CT SOS: `https://service.ct.gov/business/s/onlinebusinesssearch`, NY DOS: `https://apps.dos.ny.gov/publicInquiry/`)
- Run ProPublica search on resolved owner name
- Run EDGAR search on resolved owner name
- Record all results, flag any that have ≥ 2 nonprofit affiliations or 1+ public company board

Writes `data/owner_profiles.json`.

### Task 1.4 — Identify REAL_NETWORK_MATCH
From `owner_profiles.json`, pick the owner with the best (most specific, most name-recognizable) affiliation. If none of the 4 real properties returns a useful affiliation, find a 5th property from the same search whose owner does.

Writes `data/network_match.json`.

**Exit criteria for Phase 1**: 
- `data/real_properties.json` has 4 complete property objects with all required fields
- At least 1 owner has ≥ 2 genuine nonprofit or EDGAR affiliations
- `data/network_match.json` identifies the confirmed connection

---

## Phase 2 — Seed Data Generation (Day 1, hours 5–7)

**Goal**: Have complete fictional data that makes the dashboard feel live.

### Task 2.1 — Write `build/generate_seed_data.py`
Generates seeded leads with realistic CT/Westchester addresses and names. Requirements:
- 40 total seeded leads (combined with 4–5 real = 44–45 total, hitting the "40–60" target)
- Pipeline distribution: 15 cold, 10 contacted, 7 call_booked, 5 proposal_sent, 3 signed
- All addresses are real street names in target towns (not made-up)
- Fee values: use AVM actual data: avg $566/mo, median $600/mo, range $400–$3,600/mo
- One lead in `call_completed` state with:
  - Realistic Zoom call summary (~150 words, covers: prospect away most of year, vendor coordination concern, pricing transparency ask)
  - 3 AI follow-up recommendations derived from the summary
- Two leads in `reengagement` state with trigger reasons
- Two watchlist alerts (format: "New deed transfer detected at [address]")
- At least 5 leads in the manual outreach queue (score ≥ 70) with talking points
- All leads have realistic CT/Westchester property data (address, est. value, year built)

### Task 2.2 — Generate seeded existing clients
5–6 fictional AVM clients:
- Names: realistic for CT/Westchester market demographic
- Properties: realistic Greenwich, Darien, Westport, Scarsdale, Rye addresses
- Signed dates: spread across last 12 months
- Fee structures: $600–$3,600/month (matching AVM actuals)
- **At least 1 client** shares the exact organization from `data/network_match.json`
- Each client has 2–3 nonprofit/organization affiliations (pre-loaded for network graph)

### Task 2.3 — Generate outreach analytics seed data
- 4 score tiers: 70–79, 80–89, 90–100, and automated (<70)
- Open rates: high tier 38%, mid-high 31%, mid 24%, automated 18%
- Reply rates: high tier 14%, mid-high 9%, mid 5%, automated 2.8%
- Conversion rates: high tier 4.2%, others lower
- Numbers must tell the story: higher score = better performance

---

## Phase 3 — HTML Template (Day 2, first half)

**Goal**: Working single-file HTML with all navigation, sidebar, design system, and empty page stubs.

### Task 3.1 — Start from `avm_marketing_hub_demo_8.html`
The existing demo has:
- The correct design language (Inter Tight, Fraunces, serif headlines)
- Working sidebar navigation
- CSS custom property palette
- Multiple page patterns (dashboard, prospects, pipeline, etc.)

Key changes needed:
- Market reframe: Naples FL → CT/Westchester
- Add network graph page (new)
- Add fee tracker / billing pages (new)
- Rename/restructure pages per the brief's 21 features

### Task 3.2 — Build data injection layer
At the top of the `<script>` block, inject all embedded data:
```html
<script>
// === INJECTED BY build.py — DO NOT EDIT ===
const REAL_PROPERTIES = /* INJECT:real_properties */[];
const SEEDED_LEADS = /* INJECT:seeded_leads */[];
const EXISTING_CLIENTS = /* INJECT:seeded_clients */[];
const NETWORK_MATCH = /* INJECT:network_match */{};
// === END INJECTED DATA ===
```

The `build.py` script replaces `/* INJECT:key */` with the actual JSON content.

### Task 3.3 — Scoring engine
Implement `scoreLeads(leads)` in JS. Runs at page load, populates `lead.score` for all leads. Manual queue shows all leads with score ≥ 70 sorted descending. Automated queue shows score < 70.

---

## Phase 4 — Critical Path Features (Day 2, second half + Day 3, first half)

Implement in exactly this order — the demo path order.

### Task 4.1 — Dashboard (demo Step 1)
- KPI cards: total leads (counter), pipeline value, fee cap progress, new this week
- "3 new leads this week" notification banner at top
- Manual queue widget (top 3 scored leads with score badges)
- Pipeline funnel mini-chart
- Fee tracker bar (seeded at 30–40% of $60K)
- All seeded to look live: realistic numbers, not empty

### Task 4.2 — Run Search (demo Step 2) — MOST IMPORTANT
This interaction must be pixel-perfect. Implementation:
1. "Run Search" button on leads page and dashboard
2. Click → button disabled, modal overlay: "Scanning public records — Westchester County, CT markets…" with 3-dot pulsing animation
3. `setTimeout(reveal, 3000)` — never shorter
4. After delay: 4 real property cards animate in sequentially with `animationDelay: n*300ms`
5. Each card: green "Platform Generated" badge, absentee flag if applicable, entity flag if applicable
6. Dashboard leads counter increments with each new lead appearing
7. Button re-enables with "✓ Search complete" state for 2 seconds, then resets

**Test this 5 times in a row before moving on. It must be reliable.**

### Task 4.3 — Profile View (demo Steps 3 + 4 + 5)
The full profile page for REAL_PROPERTY_1. Sections:
- Property layer (real data from JSON)
- Owner layer with absentee + entity flags
- Portfolio section
- Professional intelligence: ProPublica + EDGAR (live fetch on profile open, loading spinner while fetching, graceful fallback if fetch fails)
- State filings (pre-seeded from owner_profiles.json)
- Network match alert (gold border, prominent, at TOP of profile if match exists)
- Contact placeholder

**The network match banner is non-negotiable.** It fires reliably because it reads from embedded `NETWORK_MATCH` data — not from a live API call.

### Task 4.4 — Manual Outreach Queue (demo Step 6)
- Sortable table: score, address, price, flags, last_action
- Each row expandable to show: AI talking points, action buttons (Schedule call, Draft email, Move to automated)
- AI talking points are pre-generated from property characteristics and embedded in seeded data — NOT generated live
- Real properties should appear at the top (highest scores)
- "Top Lead" badge on REAL_PROPERTY_1

### Task 4.5 — Automated Email Preview (demo Step 7)
- One seeded lead (score 62, NOT a real property) has "Draft email" action
- Email preview panel shows full email text: addresses specific property, realistic pain points
- "Send" button → toast notification "Email queued for sending"
- Email reads like a thoughtful rep wrote it, references: property address, recent purchase date, absentee status if applicable

### Task 4.6 — Call Notes + Follow-Up (demo Step 8)
- One seeded lead in "Call completed" state
- Zoom summary already attached and visible on profile timeline
- 3 AI follow-up recommendations visible below summary (pre-seeded)
- "Import Zoom notes" button on every profile → paste field modal
- Modal has realistic placeholder: "Paste Zoom AI summary here…"
- Pasting any text → timestamp added to timeline, 3 new recommendations generated (from keyword matching: "pricing" → rec about pricing sheet, "vendor" → rec about vendor list, "away" → rec about seasonal coverage)

### Task 4.7 — Network Graph (demo Step 9)
D3.js force-directed graph:
- Load D3 from CDN on graph page entry
- Render nodes for all existing clients + all leads with affiliations
- Draw edges for shared affiliations
- Node colors: existing client = gold fill, lead = blue fill, high-scored lead = darker blue
- Edge colors: nonprofit = gold, corporate = blue, press = purple
- The REAL_NETWORK_MATCH edge: thicker stroke + gold color + slight animation
- Click node → sidebar slides in from right: name, score, property address, "View full profile →" link
- Click edge → tooltip: shared organization name and type

### Task 4.8 — Fee Tracker + Billing (demo Step 10)
- Cap progress bar: $18,450 earned of $60,000 cap (30.75%)
- "This month": $3,200
- "Projected cap date": August 14, 2026 (calculated from pace)
- Billing summary table: 2 seeded signed clients
  - Client 1: management fee $72,000/yr, platform fee $7,200 (10%), signed month
  - Client 2: management fee $54,000/yr, platform fee $5,400, signed prior month
- "Export as PDF" button → browser print dialog (use `window.print()`)

---

## Phase 5 — Off-Critical-Path Features (Day 3, second half)

These are shown during the demo but the demo script doesn't call them out as critical moments. Implement quickly.

### Task 5.1 — Re-engagement Queue
- 2 seeded leads with trigger type: "Timer (90 days)" and "New deed transfer detected"
- List view with: days since last touch, trigger reason, last outreach summary
- "Resume outreach" and "Archive" actions

### Task 5.2 — Property Watchlist
- 3–4 watchlisted properties
- 2 pre-seeded alerts: "New deed recorded" and "Property listed for sale"
- Add-to-watchlist flow: address input, confirmation

### Task 5.3 — Pipeline Report
- Funnel chart (CSS bars, not D3): Intake → Contacted → Call booked → Proposal → Signed
- Split by source: platform-generated vs manual
- Numbers match seeded data distribution
- "Platform-generated leads convert 2.3× better than manual" callout

### Task 5.4 — Outreach Analytics
- 4 bar charts (CSS, not D3): open rate, reply rate, conversion rate by score tier
- Numbers per Task 2.3 seed data
- Score tier differentiation must be visually obvious

### Task 5.5 — Outreach Sequence Builder
- 2 pre-built sequences: "Concierge Introduction" (5-touch, 30 days) and "New Closing Fast-Track" (3-touch, 10 days)
- Each step shows: day number, type (email/call prompt), subject/prompt
- Assign-to-lead flow on each lead card

### Task 5.6 — Settings
- Lead score threshold slider (default 70)
- Score weight configurables for each signal
- Run schedule toggle

---

## Phase 6 — QA and Demo Path Hardening (Day 4)

### Task 6.1 — Critical path walkthrough × 3
Walk the exact 10-step demo path three times in a row without any issues. Document each friction point.

### Task 6.2 — Run Search stress test × 5
Click Run Search five times in a row. Must:
- Complete in 3–5 seconds each time
- Never show blank cards
- Never crash the counter animation
- Look exactly the same every time (deterministic, no randomness in order)

### Task 6.3 — Network match reliability test
Open REAL_PROPERTY_1's profile 10 times. Network match banner must appear every time.

### Task 6.4 — ProPublica/EDGAR failure handling
Disconnect from the internet, open profile. Verify:
- Loading spinner appears then disappears
- "No results found — public filings unavailable" placeholder shows
- Rest of profile renders normally

### Task 6.5 — Console error audit
Open DevTools, walk entire critical path. Zero console errors allowed.

### Task 6.6 — Mobile responsiveness (nice-to-have)
If time permits: add a single CSS breakpoint at 768px for sidebar collapse.

### Task 6.7 — Deploy
Push to Vercel or Netlify. Test from the live URL. Verify ProPublica + EDGAR calls work from HTTPS origin. Share URL.

---

## Schedule

| Day | Focus | Deliverable |
|---|---|---|
| Day 1 AM | Phase 0: Data probe | Confirmed data sources, REAL_PROPERTY_1–4 identified |
| Day 1 PM | Phase 1–2: Data acquisition + seeding | `data/*.json` files complete |
| Day 2 AM | Phase 3: HTML template | Working navigation, design system, empty pages |
| Day 2 PM | Phase 4 (4.1–4.3): Dashboard + Run Search + Profile | Critical path working through Step 5 |
| Day 3 AM | Phase 4 (4.4–4.8): Queue → Graph → Fees | Critical path complete end-to-end |
| Day 3 PM | Phase 5: Remaining features | All 21 features stubbed or complete |
| Day 4 | Phase 6: QA + Deploy | Live URL delivered |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| SalesWeb blocks automated queries | Medium | High | Fall back to VGSI Westport/Fairfield only; supplement with 1 manual entry from public assessor lookup |
| VGSI sales results < $2.5M in past 6 months for target towns | Low | Medium | Expand date range to 12 months, lower threshold to $2M for demo |
| Real owner returns no ProPublica/EDGAR results | Medium | High | Run enrichment on 10 candidates, not 4; select the richest for REAL_PROPERTY_1 |
| EDGAR CORS blocked from browser | Low | Medium | Pre-embed EDGAR results at build time, show as static data with "Last refreshed: today" label |
| Network match never fires | Very low | Critical | Network match reads from embedded NETWORK_MATCH constant, not live computation; guaranteed to fire |
| D3 graph performance with 30 nodes | Low | Low | Set alpha decay high, limit simulation ticks, freeze on stabilization |
