# KPI Definitions

Covers `sql/05_kpi_summary.sql` (and `sql/04_stage_contracts.sql` for the underlying
schedule-variance fields), producing `kpi_rates`, `kpi_cost_variance`,
`kpi_schedule_variance_overall`, and `kpi_schedule_variance_by_cut`.

## On-time / on-budget rates (`kpi_rates`)

VDOT's own Performance Dashboard judgment (`on_time_status` / `on_budget_status`, G/Y/R),
computed only over rows with `data_source IN ('both', 'dashboard_only')` — i.e. projects
that have actually reached construction and been graded. `syip_only` rows (763 of 5,506)
are excluded entirely, not counted as either on-time or not: they simply haven't reached
construction yet, so including them would dilute the rate with not-yet-gradable projects
(see `docs/data_cleaning_rules.md`).

**Overall (n=4,743 rated projects):** 23.4% flagged not-on-time (R), 0.8% partial (Y), 75.8%
on-time (G). 16.2% flagged not-on-budget (R), 13.7% partial (Y), 70.2% on-budget (G).

## Cost variance (`kpi_cost_variance`)

`current_estimate - allocated_budget`, in dollars and as a percent of `allocated_budget`.
Computed over *any* row with both fields populated (not restricted to rated rows) — this is
our own computed figure, independent of the Dashboard's `on_budget_status` judgment, and
still meaningful pre-construction (an early cost-growth signal).

**Important caveat — read before quoting a single "average % overrun" number:** median
variance is $0 / 0%, but the mean is +$352,888 / **+118.6%**. These disagree this wildly
because `allocated_budget` (`TOTAL_ALLOCATIONS_CURRENT`) reflects money *actually
programmed so far*, not the project's full lifecycle cost — for a project newly entered
into the pipeline (e.g. UPC 124264, status "No Dates Set Yet - PE Open"), allocated can be a
few thousand dollars against a multi-million-dollar total estimate. That's "not yet funded,"
not "cost overrun," and a handful of these early-stage projects blow up the mean. **Always
report median alongside mean for this metric, and prefer `on_budget_status` (above) as the
primary "is this project over budget" answer** — this $ variance is a secondary, exploratory
view, not the headline.

## Schedule variance (`kpi_schedule_variance_overall`, `kpi_schedule_variance_by_cut`)

`days_late = actual_completion_date - original_specified_completion_date`, computed from the
Dashboard's contract-level data (`Project_Delivery (Contract,UPC)`), not the project-level
G/Y/R flag — this is what gives an actual day count instead of just a category.

Two grains, used for different purposes (see `sql/04_stage_contracts.sql` /
`sql/05_kpi_summary.sql` for why):
- **Overall summary** (`kpi_schedule_variance_overall`): contract grain
  (`stg_contracts_distinct`, one row per `CONTRACT_ID`) — a contract shared across multiple
  projects (621 of 3,986 contracts bundle 2+ projects) is counted once, so this answers "how
  late does a typical *contract* run."
- **Breakdowns by district/project_type/road_system** (`kpi_schedule_variance_by_cut`):
  project grain (`stg_contracts` exploded, joined to `projects` via `UPC`) — a shared
  contract contributes one data point per project it affects, which is legitimate for
  answering "what fraction of *projects* of this type saw delay," but means those points
  aren't fully independent observations. Don't read too much precision into small
  differences between similar categories.

**Overall (n=3,459 completed contracts):** median 2 days *early*, mean 3.6 days *late*. Same
skew pattern as cost variance — most contracts land close to on schedule, a tail of delayed
ones pulls the mean past the median. This mirrors WSP's own Mega Project Framework framing
(a small share of projects driving most of the overrun, not a uniform pattern) more usefully
than either number alone.

## Headline stat for the write-up

> VDOT's own Performance Dashboard flags **23.4%** of graded projects as not on-time and
> **16.2%** as not on-budget. But the pain isn't evenly spread: median cost and schedule
> variance are both close to zero, while a tail of projects — concentrated in categories
> like Facilities for Pedestrians and Bicycles (36.9% not-on-time) versus Resurfacing (4.2%
> not-on-time) — drives the average cost variance to +118.6% and average schedule slip to
> 3.6 days late. That concentration-in-a-tail pattern is the same shape WSP's own Mega
> Project Framework describes (~9 of 101 megaprojects overrunning 50%+).

## Subgroup sample sizes for Day 4 modeling

Minimum threshold: **n ≥ 30** rated projects for a cut to support reliable rate/variance
statistics or contribute its own category to the Day 4 classifier; below that, report
descriptively only (per the PRD's small-subgroup mitigation).

- **district:** only `Statewide` (n=16) falls below threshold; all 9 real districts have
  n≥263 — no problem here.
- **road_system:** only `Public Transportation` (n=8) falls below threshold; the other 6
  categories range from n=241 to n=1,163.
- **project_type:** 18 of 31 categories fall below threshold (mostly single-digit or
  low-teens n — e.g. `Ferry Boats` n=10, `Transit` n=12, several n≤2). Only **13 categories**
  (Safety, Facilities For Pedestrians And Bicycles, Resurfacing, Reconstruction W/O Added
  Capacity, Bridge Replacement W/O Added Capacity, Reconstruction W/ Added Capacity, Bridge
  Rehab W/O Added Capacity, Traffic Management/Engineering, Other, Restoration And
  Rehabilitation, and a few more in the n=30-100 range) have enough data to model
  individually — Day 4 should either fold the rest into an "Other/small-category" bucket or
  report them descriptively rather than as their own model feature level.
