-- Contract-level staging from the Dashboard's Project_Delivery (Contract,UPC) sheet.
-- Grain of the raw sheet is (CONTRACT_ID, UPC) — a contract can bundle multiple projects
-- (621 of 3,986 contracts do), and financial/date/status fields repeat identically across
-- each contract's UPC rows (verified, 0 inconsistent contracts). Two tables:
--   stg_contracts          — one row per (CONTRACT_ID, UPC), for per-project breakdowns
--   stg_contracts_distinct — one row per CONTRACT_ID, for contract-level rollups (medians,
--                            totals) so a shared contract isn't multi-counted
CREATE OR REPLACE TABLE stg_contracts AS
SELECT
    CONTRACT_ID                                                        AS contract_id,
    UPC                                                                 AS upc,
    trim(DISTRICT)                                                      AS district,
    trim(ROAD_SYSTEM)                                                   AS road_system,
    ORIGINAL_SPECIFIED_COMPLETION_DATE::DATE                            AS original_completion_date,
    CURRENT_SPECIFIED_COMPLETION_DATE::DATE                             AS current_completion_date,
    ACCEPTANCE_DATE::DATE                                               AS actual_completion_date,
    CONTRACT_AWARD_AMOUNT::DOUBLE                                       AS award_amount,
    CURRENT_CONTRACT_AMOUNT::DOUBLE                                     AS current_amount,
    UN_AUDITED_FINAL_COST::DOUBLE                                       AS final_cost,
    trim(ON_TIME_STATUS)                                                AS on_time_status,
    trim(ON_BUDGET_STATUS)                                              AS on_budget_status,
    date_diff('day', ORIGINAL_SPECIFIED_COMPLETION_DATE, ACCEPTANCE_DATE)
                                                                         AS schedule_variance_days_actual,
    date_diff('day', ORIGINAL_SPECIFIED_COMPLETION_DATE, CURRENT_SPECIFIED_COMPLETION_DATE)
                                                                         AS schedule_variance_days_current,
    COALESCE(UN_AUDITED_FINAL_COST, CURRENT_CONTRACT_AMOUNT) - CONTRACT_AWARD_AMOUNT
                                                                         AS cost_variance_dollars,
    (COALESCE(UN_AUDITED_FINAL_COST, CURRENT_CONTRACT_AMOUNT) - CONTRACT_AWARD_AMOUNT)
        / NULLIF(CONTRACT_AWARD_AMOUNT, 0)                              AS cost_variance_pct
FROM raw_contracts;

-- district/road_system verified consistent across every contract's UPC rows (0 exceptions),
-- so picking any single row's values for those columns is safe. `upc` itself is dropped in
-- favor of `project_count` since a contract-level row doesn't belong to one project.
CREATE OR REPLACE TABLE stg_contracts_distinct AS
SELECT * EXCLUDE (upc, rn)
FROM (
    SELECT
        *,
        count(*) OVER (PARTITION BY contract_id)                          AS project_count,
        row_number() OVER (PARTITION BY contract_id ORDER BY upc)         AS rn
    FROM stg_contracts
)
WHERE rn = 1;
