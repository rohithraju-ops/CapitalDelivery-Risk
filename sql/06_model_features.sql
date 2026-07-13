-- Model-ready feature table: one row per project, with rare categories bucketed per Day 3's
-- n>=30 modeling threshold (applied uniformly to project_type, road_system, and district for
-- consistency), a log-scaled budget-size feature, and the at_risk target.
--
-- has_label: true for projects with a real Dashboard on-time/on-budget grade (data_source IN
-- ('both','dashboard_only')) — the training population.
-- is_currently_active: true for projects still in the current SYIP program (data_source IN
-- ('both','syip_only')) — the population we actually want risk scores for. 'both' rows are
-- in both sets: still active, but already have an interim real grade too.
--
-- at_risk = 1 if EITHER on_time_status or on_budget_status is Y or R (not just R) — a risk
-- flag should catch early-warning signs, not just certified failures. NULL where there's no
-- label (see docs/data_cleaning_rules.md for why syip_only rows have none).
CREATE OR REPLACE TABLE model_features AS
WITH qualifying_project_types AS (
    SELECT cut_value FROM kpi_rates WHERE cut_type = 'project_type' AND n_rated >= 30
),
qualifying_road_systems AS (
    SELECT cut_value FROM kpi_rates WHERE cut_type = 'road_system' AND n_rated >= 30
),
qualifying_districts AS (
    SELECT cut_value FROM kpi_rates WHERE cut_type = 'district' AND n_rated >= 30
)
SELECT
    p.upc,
    p.data_source,
    (p.data_source IN ('both', 'dashboard_only'))                          AS has_label,
    (p.data_source IN ('both', 'syip_only'))                                AS is_currently_active,

    CASE WHEN p.project_type IN (SELECT cut_value FROM qualifying_project_types)
         THEN p.project_type ELSE 'Other/Small Category' END                AS project_type_bucketed,
    CASE WHEN p.road_system IN (SELECT cut_value FROM qualifying_road_systems)
         THEN p.road_system ELSE 'Other/Small Category' END                 AS road_system_bucketed,
    CASE WHEN p.district IN (SELECT cut_value FROM qualifying_districts)
         THEN p.district ELSE 'Other/Small Category' END                    AS district_bucketed,

    p.allocated_budget,
    ln(NULLIF(p.allocated_budget, 0))                                       AS log_allocated_budget,

    CASE WHEN p.data_source IN ('both', 'dashboard_only')
         THEN ((p.on_time_status IN ('Y', 'R')) OR (p.on_budget_status IN ('Y', 'R')))::INT
         ELSE NULL END                                                     AS at_risk
FROM projects p;
