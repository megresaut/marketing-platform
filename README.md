# Marketing Platform

Lead-generation and outreach intelligence platforms built as client pitch demos. The repo holds two projects:

| Project | Client | What it does |
|---|---|---|
| [`avm/`](avm/) | Absolute Value Management (concierge property management, CT + Westchester NY) | Finds new luxury-home buyers from public property records, works out who really owns the property, scores them, and manages outreach |
| [`marex/`](marex/) | Marex Boats USA | Profiles an existing HubSpot contact list, derives the ideal customer profile, and ranks lookalike prospects |

The top-level files are the original copy of the AVM demo (identical to `avm/`).

> **Privacy note:** every file containing real people's data is gitignored and kept local only. That covers real property owners from public records, client contacts, and Marex's HubSpot customer list. Excluded: `**/index.html` (the latest demo build embeds real properties), `**/build/`, `**/data/real_properties.json`, `**/BRIEF.md`, `**/DATA_SOURCES.md`, `**/DECISIONS.md`, `avm/client_email_draft.txt`, `avm/leads_engine/output/`, `marex/marex.html`, `marex/marex_engine/` and `marex/docs/`. In this repo, `index_16.html` is the runnable demo and uses only seeded, fictional data. The feature descriptions below cover the full platform, including the excluded parts.

---

## 1. AVM Concierge Marketing Platform

AVM finds concierge clients through referrals, which caps growth. This platform finds who just bought a $2.5M+ home, whether they actually live there, who is behind an LLC or trust, and whether they already know an existing AVM client. The goal is to reach them before a competitor does.

### Components

- **`avm/index.html`**: the interactive demo web app (single file, no backend). Earlier versions: `index_16.html`, `avm_marketing_hub_demo_8.html`.
- **`avm/leads_engine/`**: a standalone Python engine that pulls **real** data from free public sources, with no paid APIs and no fabricated data.
- **`avm/build/`**: scripts that fetch real properties, generate seed data and bake everything into the HTML.
- **`avm/data/`**: JSON inputs for the demo (real properties, seeded leads and clients, sequences, analytics, fee tracker).
- **Docs**: `BRIEF.md` (full feature spec + demo script), `BUILD_PLAN.md`, `TECHNICAL_ARCHITECTURE.md`, `DATA_SOURCES.md`, `DECISIONS.md`, `FILE_STRUCTURE.md`.

### Features (demo app)

**Lead intake**
- **Public records engine**: pulls recent sales above a configurable price threshold. The "Run Search" button animates real pre-fetched properties into the leads table.
- **Manual upload / single entry**: CSV or one address at a time. Each lead is permanently tagged *platform-generated* or *manual*, and only platform leads count toward the platform fee.

**Enrichment and profiling**
- **Absentee owner detection**: flags owners whose mailing address differs from the property address. This is the strongest single signal of need.
- **LLC / trust detection**: classifies buyer names as entities (LLC, Trust, Holdings, Partners…) and flags them for resolution.
- **Three-layer client profile**:
  - *Property*: price, sale date, assessed value, sqft, year built, beds/baths, lot, ownership history.
  - *Owner*: resolved name, mailing address, portfolio size (other properties owned).
  - *Professional intelligence*: nonprofit board roles (ProPublica / IRS 990), SEC EDGAR filings, state business registries and press mentions, each tagged by source.
- **Network matching**: cross-references every prospect's affiliations against existing AVM clients and alerts when there's a match, e.g. *"This prospect may know your client X — both are directors of Y."*
- **Network graph**: an interactive node graph of clients and prospects, with edges colour-coded by connection type.

**Scoring and routing**
- **Lead scoring (0–100)**: weighted on price, absentee status, multi-property ownership, property age and how recent the purchase was. Weights are configurable in Settings.
- High scores go to the **manual outreach queue** with AI-generated talking points. Lower scores go to **automated email**.

**Outreach automation**
- **Personalized emails**: generated per lead from the property profile, not from a template.
- **Sequence builder**: multi-touch email and rep-task sequences (e.g. "Concierge intro", "New closing fast-track").
- **Call notes and timeline**: paste in Zoom AI call summaries. Every email, call, note and status change appears on a timeline.
- **AI follow-up recommendations**: next-contact timing, objection flags and angles to push, generated from the call notes.
- **Re-engagement queue**: brings cold leads back after 60/90 days, or immediately when a new public-records event appears (deed transfer, new purchase, permit).
- **Property watchlist**: monitors chosen properties and owners and alerts on changes.

**Reporting and billing**
- **Pipeline report**: funnel from intake → contacted → call booked → proposal → signed, split by lead source.
- **Fee tracker and cap monitor**: platform fees earned against the $60K annual cap, with a projected date for hitting the cap.
- **Outreach analytics**: open, reply and conversion rates by score tier, sequence and segment.
- **Monthly billing summary**: an invoice-ready report of converted platform leads and fees owed (10% of first-year value).

App pages: Dashboard · Leads · Queue · Email · Sequences · Re-engagement · Watchlist · Pipeline · Analytics · Fees · Billing · Network · Settings.

### Leads engine: what it scrapes and automates

`avm/leads_engine/` runs the real data pipeline end to end:

| Step | Source | What it gets |
|---|---|---|
| Sales scan | Vision Government Solutions (VGSI) town assessor sites: Westport, Fairfield, Stamford CT | Recent sales above a min price: address, price, date, style, year built, sqft, beds/baths, lot, pool |
| Owner resolution | VGSI parcel card | Owner of record, mailing address, prior sales of the parcel |
| Absentee / entity flags | Derived | Mailing ≠ property address; owner name contains LLC/Trust/Inc… |
| LLC resolution | CT Secretary of the State business registry (data.ct.gov open data) | Entity status, principals, registered agent, and sometimes a direct phone/email when the owner is their own agent |
| Nonprofit signal | ProPublica Nonprofit Explorer API | Possible foundation/nonprofit match (labelled low-confidence) |
| SEC signal | SEC EDGAR full-text search | Filings that mention the owner's name (labelled low-confidence) |
| Scoring | `score.py` | A transparent, rule-based score where every point carries a written reason |

```bash
cd avm
python3 -m leads_engine.run --min-price 2500000 --months 18 --limit 30
python3 -m leads_engine.lookup_name "Surname"   # find all parcels owned by a name
```

Output (`leads_engine/output/<run>/`) contains `SUMMARY.md` (ranked table), one markdown brief per lead, and `leads.csv`.

**Limits:** VGSI covers only Westport, Fairfield and Stamford. Greenwich, Darien, New Canaan and Westchester County have no free working source. Nominee trusts cannot be unmasked. Requests are deliberately rate-limited, so a 30-lead run takes a few minutes.

---

## 2. Marex Boats: Contact Profiling and Lookalike Engine

### Components

- **`marex/marex_engine/`**: a headless Python engine (standard library only, plus `dig` for MX lookups) that runs over Marex's HubSpot contact export.
- **`marex/marex.html`**: the Lead Intelligence Platform demo UI. Pages: Dashboard, Leads, Queue, Email, Sequences, Re-engagement, Watchlist, Pipeline, Analytics, Network, **Boat Shows**, **Market Map**, Settings.
- **`marex/brief.html`**: strategic brief.
- **`marex/docs/superpowers/`**: design spec, implementation plan and review reports.

### What the engine automates

1. **Load and clean**: normalizes and dedupes contacts, removes suppressions, flags cohorts.
2. **Classify**: separates real consumers from marine-trade businesses, placeholder names and business entities.
3. **Enrich**:
   - Resolves each email domain: MX records, scraped site title, company name.
   - Checks SEC EDGAR and ProPublica for name matches.
   - Caches results so re-runs are near-instant.
4. **Derive the ICP**: builds the modal ideal-customer profile, with evidence for each trait.
5. **Score and rank**: a fit score ("resembles the list") plus a separate `quality_rank` (positive evidence).
6. **Derived insights** (offline, no network):
   - Owner-operator detection (surname appears in a corporate email domain).
   - Birth-year estimate from the email handle, with a confidence level.
   - Boat-show-season acquisition timing.
   - Generational suffixes, professional credentials, and days since last contact.
7. **Reports**:
   - `ranked_prospects.csv`, `contacts_clean.csv` and `profiles.json`.
   - `icp_profile.md`, `personas.md` and `targeting_spec.md` (criteria for buying or building net-new lists).
   - `triage_report.md`.

```bash
cd marex/marex_engine
python3 run.py --input "<path to HubSpot export.csv>"
python3 run.py --offline               # no network
python3 -m unittest discover -s tests -t . -v
```

**Notes:**
- Scores measure *fit*, not purchase intent.
- No net-new names are generated, since the USCG removed owner names from public vessel data in 2017.
- Engine outputs and caches contain customer contact data and are **not committed** (gitignored).

---

## Tech

- Front ends: static single-file HTML/CSS/JS with no build step, deployable to Vercel as-is.
- Engines: Python 3 using only the standard library.
- All data sources are free public records or APIs: VGSI, data.ct.gov, ProPublica, SEC EDGAR and DNS.
