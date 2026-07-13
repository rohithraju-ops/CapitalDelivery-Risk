# Risk-Scoring Model

Covers `sql/06_model_features.sql` and `scripts/{compare_models,train_risk_model,
explain_model,score_projects,risk_model_lib}.py`.

**These are risk flags, not predictions.** Every score below states how closely a project's
profile resembles historically Y/R-graded projects along the same dimensions VDOT itself
already tracks — it is not a forecast of what will happen to any specific project, and
should never be described as one in a write-up or interview.

## Target

`at_risk` = 1 if VDOT's own Dashboard grade (`on_time_status` or `on_budget_status`) is `Y`
or `R` on *either* dimension, 0 if both are `G`. Computed only for the 4,743 rated projects
(`data_source IN ('both','dashboard_only')` — see `docs/data_cleaning_rules.md`). Deliberately
includes `Y` (partial/early-warning), not just `R` (certified failure) — a risk-flagging tool
that only catches things after they've fully failed misses the point of an early warning
system. Base rate: 41.9% at-risk.

## Features

- `project_type_bucketed`, `road_system_bucketed`, `district_bucketed` — Day 3's n≥30
  modeling threshold applied uniformly to all three (even though only `project_type` and one
  category each in the other two actually needed it, for consistency). Categories below
  threshold, and null `project_type` (see `docs/data_cleaning_rules.md`), fold into
  `'Other/Small Category'`.
- `log_allocated_budget` — project size (log-scaled `allocated_budget`), since WSP's own
  Mega Project Framework specifically calls out project *size* as a risk driver. ~3% of rows
  have no allocated-budget figure; `SimpleImputer(add_indicator=True)` supplies a median fill
  plus a `log_allocated_budget_missing` indicator feature, so "we don't have this project's
  budget yet" is itself a visible, explainable signal rather than a silent fill.

## Model selection — tested, not assumed

Compared 4 candidates with **stratified 5-fold CV** (not a single train/test split — with
~4,700 rows, real class imbalance, and small subgroups, a single split is noisy):

| model | AUC (mean ± std) | F1 |
|---|---|---|
| random_forest | 0.719 ± 0.007 | 0.526 |
| gradient_boosting | 0.715 ± 0.006 | 0.577 |
| **logistic_regression** | **0.707 ± 0.008** | 0.558 |
| decision_tree | 0.683 ± 0.012 | 0.479 |

Plots: `reports/figures/model_comparison_roc.png`, `model_comparison_metrics.png`.

**Verdict: logistic regression**, confirmed empirically rather than assumed going in. The
AUC gap to the best performer (random forest, +1.2 points) is well within the error bars —
not a meaningful difference — and logistic regression is the only candidate that gives an
*exact*, additive per-project decomposition (contribution = coefficient × feature value, no
interaction ambiguity) without needing SHAP or similar. Given the PRD's hard requirement
that "every risk score must be explainable in one sentence," that tips it decisively.

Final model performance (same 5-fold CV, reported rather than a single held-out split for
the same noisy-subgroup reason above): **AUC 0.707 ± 0.008, precision 0.602 ± 0.010, recall
0.521 ± 0.022, F1 0.558 ± 0.011.**

## Explainability

`OneHotEncoder(drop='first')` so each category's coefficient reads as "vs. a reference
category" (reference: `project_type_bucketed`='Bridge Rehab W/O Added Capacity',
`road_system_bucketed`='Enhancement', `district_bucketed`='Bristol' — alphabetically first
in each, not otherwise special). Global feature table + sentences:
`uv run python scripts/explain_model.py`.

**Top risk-increasing factors:**
- `district_bucketed`='Other/Small Category' (i.e. Statewide, n=16): 2.53x baseline odds
- `project_type_bucketed`='Facilities For Pedestrians And Bicycles': 2.01x baseline odds
- `project_type_bucketed`='Reconstruction W/ Added Capacity': 1.72x baseline odds
- `log_allocated_budget`: 1.39x odds per unit increase — bigger projects trend riskier

**Top risk-decreasing factors:**
- `project_type_bucketed`='Resurfacing': 0.31x baseline odds (clearly the safest category)
- `road_system_bucketed`='Interstate': 0.31x baseline odds
- `district_bucketed`='Lynchburg': 0.31x baseline odds

**Directionality validated against Day 3, not just asserted:** correlation between each
project_type's model coefficient and its actual observed on-time/on-budget R-rate (from
`kpi_rates`) is **0.77** across all 13 non-bucketed categories — the model learned a pattern
that agrees with what Day 3 already found in the raw data, it didn't invent a new one.

**Per-project explanations** (`scripts/score_projects.py`, via `risk_model_lib.score_and_explain`):
for each active project, transform its features through the fitted pipeline, multiply by
coefficients to get each feature's exact contribution to the logit, and report the top 2
by magnitude as a plain-language sentence — e.g. "project_type_bucketed='Facilities For
Pedestrians And Bicycles' (raises risk); log_allocated_budget_missing (raises risk)."

## Scoring & the dollar-denominated headline stat

Scored all 2,853 currently-active projects (`data_source IN ('both','syip_only')` —
`is_currently_active` in `model_features`) into `risk_scores` (score 0-100, min 3 / median
48 / max 98). **Elevated-risk threshold: score ≥ 60** — a fixed, documented cutoff (not
recomputed each refresh) that happened to land exactly on the 75th percentile when set,
2026-07-12.

> **728 of 2,853 active projects (25.5%) are flagged elevated-risk, representing $23.06B in
> allocated budget** — the PRD's dollar-denominated headline stat.

## Known caveats

- 157 of 2,853 scored projects (5.5%) have the missing-budget indicator as a top
  contributing factor — their risk score partly reflects "we don't know this project's
  budget yet" rather than a substantive risk driver. Worth a caveat if one of these surfaces
  in the dashboard's top-risk list.
- `'Other/Small Category'` conflates several different things depending on which feature:
  18 low-n project types (plus the 2 rows with no project type at all) for
  `project_type_bucketed`; just `Public Transportation` (n=8) for `road_system_bucketed`;
  just `Statewide` (n=16) for `district_bucketed`. Its coefficient shouldn't be read as
  describing any one of those in particular.
