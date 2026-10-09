# AVM Lead Sourcing + Refinement Engine

Standalone script. Sources real high-value home sales, resolves the owner
from the assessor's own record, resolves LLC/entity owners against
Connecticut's own business registry, and cross-references the owner's name
against two more free public-record APIs — no fabricated data, no paid APIs.

## Run it

```
cd avm
python3 -m leads_engine.run --min-price 2500000 --months 18 --limit 30
```

Output lands in `leads_engine/output/<timestamp>/`:
- `SUMMARY.md` — sortable table of every lead, scored, with a link to each brief
- `<town>-<parcel_id>.md` — one brief per lead: sale record, ownership history, public-record signals, and the itemized reasoning behind the score
- `leads.csv` — same data, flat, for a spreadsheet

Flags: `--towns` (default `westportct,fairfieldct,stamfordct`), `--min-price`,
`--months` (lookback window), `--limit` (how many sales to fully enrich,
highest price first — enrichment is the slow part), `--out-dir`.

### Looking up a specific named person

Separate from the sales-scan pipeline above: if you already have a name (a
known executive, a referral, anyone) and want to know if they own property
in Westport/Fairfield/Stamford, query the assessor's own name index directly
rather than waiting for them to turn up in a sales scan:

```
python3 -m leads_engine.lookup_name "Surname" ["Another Surname" ...]
```

This hits VGSI's `Search.aspx` owner-name index for all parcels on file
(not just recent sales), across all three towns. See
`leads_engine/vgsi_source.py:search_by_owner_name` — note the form requires
both the visible search box and its dropdown-selected mode set correctly,
or it silently returns the entire unfiltered parcel list instead of erroring
(confirmed empirically; the code accounts for this).

## What's real vs. a heuristic

**Fact, sourced live, no fallback data:**
- Sale price, sale date, property style/year built/sqft — from the town
  assessor's own sales record (Vision Government Solutions / VGSI)
- Owner of record and owner mailing address — from the assessor's parcel
  card for that specific property
- Absentee status — owner mailing address compared to the property address
- Entity/trust ownership — owner name contains LLC/Trust/Inc/etc.
- Ownership history — prior sales of the same parcel, from the assessor record
- Portfolio count — how many times the same owner name appears in this run
- **LLC/entity resolution** (for entity-owned properties) — Connecticut
  Secretary of the State's business registry, published as free open data
  on data.ct.gov (Socrata; no signup, no API key, no rate-limit wall — this
  is the actual primary-source registry, not a paid aggregator like
  OpenCorporates, whose free tier has since moved behind a paywall). Pulls
  the matched entity's status/formation state, the principal(s) filed with
  the state, and the statutory registered agent. When the agent is an
  individual (not a registered-agent service company), it usually means
  the owner is acting as their own agent, and the record includes a direct
  phone/email — see `leads_engine/ct_registry.py`. This resolves plain
  LLCs; it does not unmask nominee trusts (those aren't filed with the SOS
  the same way, and their beneficiary schedules are legally non-public —
  see "Known limitations" below).

**Heuristic signal, explicitly labeled low-confidence in every brief:**
- Nonprofit/foundation "possible match" — ProPublica Nonprofit Explorer only
  searches *organization* names, not officer names. A hit means an org
  exists whose name resembles the owner's surname (e.g. a family
  foundation) — it is not proof the owner is affiliated with it. Verify
  before using in outreach.
- SEC EDGAR filing hits — full-text search on the owner's exact name across
  all EDGAR filings since 2001. A hit means the name appears somewhere in
  that filing — not a confirmed role (director, officer, fund manager, or
  incidental mention are all indistinguishable without reading the filing).
  Verify before referencing a specific role.

Entity-held properties only run person-name enrichment when the entity name
looks like an individual/family trust (e.g. "SMITH JOHN A REVOC TRUST"). Pure
business-named LLCs ("39 COMPO LLC") are skipped — there's no real person's
name to search, and searching the project name produces irrelevant noise.

## Known limitations

- **Geographic scope**: Westport, Fairfield, and Stamford CT only. VGSI does
  not serve Greenwich, Darien, or New Canaan (404s). Westchester County NY
  has no working public source — `propaccess.westchestergov.com` and
  `salesperson.westchestergov.com` don't resolve, and the state-level
  SalesWeb (`swcf.orpts.ny.gov`) resets connections from non-browser
  clients (a network-level WAF, not something to script around). A real
  Westchester source would need either a paid data provider or a different
  public endpoint we haven't found.
- **Nominee trusts can't be resolved by anyone without a subpoena** — their
  whole legal purpose is to keep beneficiaries off the public record. Not a
  gap in this tool.
- **CT SOS registry only covers Connecticut-registered entities.** An LLC
  formed in Delaware or another state and never registered to do business
  in CT (rare for CT property purchases, but possible) won't be found.
- **Entity name matching is fuzzy-but-imperfect.** The registry is
  searched by the assessor's rendering of the owner name; unusual
  abbreviations or punctuation differences can cause a miss even when the
  entity is on file. A "no match found" in a brief means "not found under
  this name," not "definitely unregistered."
- **VGSI's own price filter is unreliable** — confirmed empirically, so the
  script always re-filters by price itself rather than trusting the site.
- Rate-limited and deliberately paced (SEC/ProPublica/VGSI) — a 30-lead run
  takes a few minutes. This is a one-off/periodic tool, not a live service.
