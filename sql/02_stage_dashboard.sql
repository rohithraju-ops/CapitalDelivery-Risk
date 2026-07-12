-- Clean/standardize the Performance Dashboard's Project_Development (UPC) sheet.
-- Only this sheet is in scope for now — the two contract/milestone-level Delivery sheets
-- are deferred until a later phase actually needs that granularity (see docs).
CREATE OR REPLACE TABLE stg_dashboard AS
SELECT
    UPC,
    trim(DISTRICT)                 AS district,
    trim(ROAD_SYSTEM)              AS road_system,
    trim(SCOPE_OF_WORK)            AS project_type,
    trim(PROJECT_STATUS)           AS project_status,
    BUDGET::DOUBLE                 AS budget,
    ESTIMATE::DOUBLE               AS estimate,
    trim(FISCAL_YEAR)              AS dashboard_fiscal_year,
    trim(ON_TIME_STATUS)           AS on_time_status,
    trim(ON_TIME_STATUS_REASON)    AS on_time_status_reason,
    trim(ON_BUDGET_STATUS)         AS on_budget_status,
    trim(ON_BUDGET_STATUS_REASON)  AS on_budget_status_reason
FROM raw_dashboard;
