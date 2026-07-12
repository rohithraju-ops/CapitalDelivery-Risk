-- Coalesced project-level table: full outer join of SYIP (current active program) and
-- Dashboard (historical + current on-time/on-budget outcomes) on UPC. Neither source is
-- dropped — data_source records provenance instead. See docs/data_cleaning_rules.md.
CREATE OR REPLACE TABLE projects AS
SELECT
    COALESCE(s.UPC, d.UPC)                          AS upc,
    CASE
        WHEN s.UPC IS NOT NULL AND d.UPC IS NOT NULL THEN 'both'
        WHEN s.UPC IS NOT NULL THEN 'syip_only'
        ELSE 'dashboard_only'
    END                                              AS data_source,

    COALESCE(s.district, d.district)                 AS district,
    COALESCE(s.road_system, d.road_system)            AS road_system,
    COALESCE(s.project_type, d.project_type)          AS project_type,
    COALESCE(s.project_status, d.project_status)      AS project_status,

    -- budget/estimate: SYIP's PE/RW/CN breakdown is kept as-is (syip_only/both rows only);
    -- allocated/current_estimate are unified across both sources for KPI rollups.
    s.has_pe, s.has_rw, s.has_cn,
    s.current_pe_estimate, s.current_rw_estimate, s.current_cn_estimate,
    COALESCE(s.total_allocated, d.budget)             AS allocated_budget,
    COALESCE(s.total_current_estimate, d.estimate)    AS current_estimate,

    s.pe_start_date, s.rw_start_date, s.cn_start_date, s.cn_end_date,
    s.syip_vintage_year,
    d.dashboard_fiscal_year,

    d.on_time_status,
    d.on_time_status_reason,
    d.on_budget_status,
    d.on_budget_status_reason
FROM stg_syip s
FULL OUTER JOIN stg_dashboard d USING (UPC);
