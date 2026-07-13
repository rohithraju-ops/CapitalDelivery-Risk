-- Headline KPI tables. See docs/kpi_definitions.md for exact definitions and why each
-- table uses the grain it uses.

-- On-time/on-budget rates: only rows with an actual Dashboard judgment (data_source IN
-- ('both','dashboard_only')) — syip_only rows haven't reached construction, so including
-- them would understate the "not on time/budget" share by diluting it with not-yet-gradable
-- projects.
CREATE OR REPLACE TABLE kpi_rates AS
WITH rated AS (
    SELECT * FROM projects WHERE data_source IN ('both', 'dashboard_only')
),
cuts AS (
    SELECT 'overall' AS cut_type, 'ALL' AS cut_value, * FROM rated
    UNION ALL
    SELECT 'district', district, * FROM rated
    UNION ALL
    SELECT 'project_type', project_type, * FROM rated
    UNION ALL
    SELECT 'road_system', road_system, * FROM rated
)
SELECT
    cut_type,
    cut_value,
    count(*)                                              AS n_rated,
    avg((on_time_status = 'G')::INT)                      AS on_time_g_rate,
    avg((on_time_status = 'Y')::INT)                      AS on_time_y_rate,
    avg((on_time_status = 'R')::INT)                      AS on_time_r_rate,
    avg((on_budget_status = 'G')::INT)                     AS on_budget_g_rate,
    avg((on_budget_status = 'Y')::INT)                     AS on_budget_y_rate,
    avg((on_budget_status = 'R')::INT)                     AS on_budget_r_rate
FROM cuts
GROUP BY cut_type, cut_value
ORDER BY cut_type, n_rated DESC;

-- Cost variance: current_estimate vs allocated_budget, computed over ANY row where both are
-- populated (not restricted to "rated" rows) — this is our own computed figure, independent
-- of the Dashboard's own on_budget_status judgment, and meaningful even pre-construction.
CREATE OR REPLACE TABLE kpi_cost_variance AS
WITH base AS (
    SELECT *, (current_estimate - allocated_budget) AS variance_dollars,
           (current_estimate - allocated_budget) / NULLIF(allocated_budget, 0) AS variance_pct
    FROM projects
    WHERE current_estimate IS NOT NULL AND allocated_budget IS NOT NULL
),
cuts AS (
    SELECT 'overall' AS cut_type, 'ALL' AS cut_value, * FROM base
    UNION ALL
    SELECT 'district', district, * FROM base
    UNION ALL
    SELECT 'project_type', project_type, * FROM base
    UNION ALL
    SELECT 'road_system', road_system, * FROM base
)
SELECT
    cut_type,
    cut_value,
    count(*)                          AS n,
    median(variance_dollars)          AS median_variance_dollars,
    avg(variance_dollars)             AS avg_variance_dollars,
    median(variance_pct)              AS median_variance_pct,
    avg(variance_pct)                 AS avg_variance_pct
FROM cuts
GROUP BY cut_type, cut_value
ORDER BY cut_type, n DESC;

-- Schedule variance, overall: contract grain (stg_contracts_distinct) so a contract shared
-- across multiple projects isn't counted once per project — this is "the typical contract."
CREATE OR REPLACE TABLE kpi_schedule_variance_overall AS
SELECT
    count(*) FILTER (WHERE schedule_variance_days_actual IS NOT NULL) AS n_completed,
    median(schedule_variance_days_actual)                             AS median_days_late_actual,
    avg(schedule_variance_days_actual)                                AS avg_days_late_actual,
    count(*) FILTER (WHERE schedule_variance_days_current IS NOT NULL) AS n_with_current_date,
    median(schedule_variance_days_current)                            AS median_days_late_current,
    avg(schedule_variance_days_current)                               AS avg_days_late_current
FROM stg_contracts_distinct;

-- Schedule variance, by project attribute: project grain (stg_contracts exploded, joined to
-- projects for district/project_type/road_system) — a contract shared across N projects
-- contributes N data points here, one per real project it affects. Not used for the overall
-- summary number (see above) to avoid multi-counting; used here because we're describing
-- what fraction of PROJECTS of a given type/district experienced a delay, which is legitimate
-- even when several share one underlying contract. See docs for the caveat this implies
-- (non-independent observations within a shared contract).
CREATE OR REPLACE TABLE kpi_schedule_variance_by_cut AS
WITH base AS (
    SELECT c.*, p.district AS proj_district, p.project_type AS proj_project_type, p.road_system AS proj_road_system
    FROM stg_contracts c
    JOIN projects p ON c.upc = p.upc
    WHERE c.schedule_variance_days_actual IS NOT NULL
),
cuts AS (
    SELECT 'district' AS cut_type, proj_district AS cut_value, * FROM base
    UNION ALL
    SELECT 'project_type', proj_project_type, * FROM base
    UNION ALL
    SELECT 'road_system', proj_road_system, * FROM base
)
SELECT
    cut_type,
    cut_value,
    count(*)                                 AS n,
    median(schedule_variance_days_actual)    AS median_days_late,
    avg(schedule_variance_days_actual)       AS avg_days_late
FROM cuts
GROUP BY cut_type, cut_value
ORDER BY cut_type, n DESC;
