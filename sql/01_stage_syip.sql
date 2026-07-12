-- Clean/standardize the SYIP raw export into one row per active-program project.
-- Null semantics are structural, not missing data, unless noted otherwise — see
-- docs/data_cleaning_rules.md for the full rationale.
CREATE OR REPLACE TABLE stg_syip AS
SELECT
    UPC,
    trim(DISTRICT_CODE_DESC)                                            AS district,
    trim(STATE_HIGHWAY_DESC)                                            AS road_system,   -- funding-source proxy, see docs
    trim(SCOPE_OF_WORK_DESC)                                            AS project_type,
    trim(POOL_PRJ_STATUS_DSC)                                           AS project_status,
    HAS_PE::BOOLEAN                                                     AS has_pe,
    HAS_RW::BOOLEAN                                                     AS has_rw,
    HAS_CN::BOOLEAN                                                     AS has_cn,
    strptime(PE_START_DATE, '%-m/%-d/%Y %I:%M:%S %p')::DATE             AS pe_start_date,
    strptime(RW_START_DATE, '%-m/%-d/%Y %I:%M:%S %p')::DATE             AS rw_start_date,
    strptime(CN_START_DATE, '%-m/%-d/%Y %I:%M:%S %p')::DATE             AS cn_start_date,
    strptime(CN_END_DATE, '%-m/%-d/%Y %I:%M:%S %p')::DATE               AS cn_end_date,
    TOTAL_ALLOCATIONS_CURRENT::DOUBLE                                   AS total_allocated,
    Y1_Y6_ALLOCATIONS::DOUBLE                                           AS y1_y6_allocated,
    CURRENT_PE_ESTIMATE::DOUBLE                                         AS current_pe_estimate,
    CURRENT_RW_ESTIMATE::DOUBLE                                         AS current_rw_estimate,
    CURRENT_CN_ESTIMATE::DOUBLE                                         AS current_cn_estimate,
    TOTAL_EST_CURRENT::DOUBLE                                           AS total_current_estimate,
    CURRENT_YEAR::INTEGER                                               AS syip_vintage_year
FROM raw_syip;
