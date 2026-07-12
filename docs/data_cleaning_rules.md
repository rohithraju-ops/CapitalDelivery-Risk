# Data Cleaning & Merge Rules

Covers `sql/01_stage_syip.sql`, `sql/02_stage_dashboard.sql`, and `sql/03_build_projects.sql`,
run via `scripts/build_db.py` into `data/processed/capital_delivery_risk.duckdb`.

## Sources

- **SYIP** (`raw_syip` → `stg_syip`): VDOT's current Six-Year Improvement Program export.
  2,853 rows, one per currently-programmed project. Richest current budget/estimate
  breakdown (PE/RW/CN split), but only covers the active program window.
- **Dashboard** (`raw_dashboard` → `stg_dashboard`): VDOT Performance Dashboard's
  `Project_Development (UPC)` sheet. 4,743 rows, one per project the dashboard tracks
  (active + historical/closed). Has `ON_TIME_STATUS`/`ON_BUDGET_STATUS` outcome flags that
  SYIP doesn't have. Only this sheet is used — the two contract/milestone-level
  `Project_Delivery` sheets, and the ~10 individual milestone planned/actual date pairs on
  this sheet, are deferred until a later phase actually needs that granularity.

Both are keyed by `UPC`, confirmed unique in each raw source before joining.

## Merge rule

`projects` is a `FULL OUTER JOIN` of `stg_syip` and `stg_dashboard` on `UPC` — deliberately
not an inner join, so neither source's rows are silently dropped. A `data_source` column
records which side(s) a row came from:

| data_source | count | meaning |
|---|---|---|
| `both` | 2,090 | tracked by both — current budget detail *and* an outcome |
| `syip_only` | 763 | currently programmed, not yet in construction — no outcome yet (expected, not a gap) |
| `dashboard_only` | 2,653 | historical/closed or otherwise off the current SYIP window — has an outcome, no current PE/RW/CN budget detail |

**Always filter or group by `data_source` before treating a column as populated** — e.g.
computing an on-time rate over all 5,506 rows would be wrong, since `syip_only` rows have no
outcome by construction (the Dashboard's "Projects" dial only reports on-time/on-budget for
projects that have reached construction).

For overlapping fields (`district`, `road_system`, `project_type`, `project_status`,
`allocated_budget`, `current_estimate`), the rule is `COALESCE(syip_value, dashboard_value)`
— SYIP is preferred when both exist, since it's the authoritative current-program record.
Spot-checked one `both` row (UPC 105563) where the two sources disagreed slightly
($3,904,126 SYIP allocation vs. $3,577,107 Dashboard budget) — most likely the two exports
refresh on different cadences. We trust SYIP's number in that case rather than averaging or
flagging it as an error.

PE/RW/CN cost and phase-date breakdowns are SYIP-only fields — left `NULL` for
`dashboard_only` rows. No attempt is made to estimate or backfill them.

## Null semantics (structural, not missing data)

- `rw_start_date` (and `has_rw` when null/false): most projects don't have a Right-of-Way
  phase at all — a null here means "no RW phase," not "unknown."
- `on_time_status` / `on_budget_status` null for `syip_only` rows: the project hasn't
  reached construction yet, so there's nothing to grade. Exclude these rows from on-time/
  on-budget rate KPIs; keep them as the population the eventual risk-flagging model scores.
- `road_system` stands in for "funding source" — no field in either source states an
  explicit state/federal/local funding split. This is a modeling proxy, not a literal label.

## Known source quirks (documented, not "fixed")

- **Placeholder UPCs:** 66 of 2,853 SYIP rows have a *negative* `UPC` (e.g. `-11780`). All
  are in pre-construction statuses (`Monitoring Funds`, `No Dates Set Yet`, `Study Only`,
  `Critical Decision Needed`) — this looks like VDOT's convention for a project that hasn't
  been assigned its permanent Unique Project Code yet. These rows are legitimate projects
  (real descriptions, districts, statuses), each with real budget figures, so they're kept
  in the `projects` table and **counted in headline project totals** — excluding them would
  arbitrarily undercount the active program by ~2.3% just because of an ID-assignment
  formality. They will always be `syip_only`, never `both`, since the Dashboard export has
  zero negative UPCs (they haven't reached construction, so naturally have no outcome yet)
  — don't mistake that for a join bug. If a write-up ever needs a project count restricted
  to projects with a permanent code, filter on `upc > 0`.
- **2 rows have no `project_type`:** `SCOPE_OF_WORK_DESC` is null in raw SYIP for 2 of 2,853
  rows (UPCs `101452` and `-11780`), and neither has a Dashboard match to fall back on. Left
  as a genuine `NULL` rather than inventing an "Unknown" category — small enough (0.07% of
  rows) to note and move on rather than build handling for.

## Duplicate handling

`UPC` was confirmed unique in both raw sources (see `tests/test_raw_data_sanity.py`). A full
outer join on a unique key is guaranteed 1:1; verified post-join that `count(distinct upc)`
equals total row count (5,506 = 5,506) with no fan-out.
