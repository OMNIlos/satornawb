\set ON_ERROR_STOP on
\pset pager off

\if :{?runtime_checks}
\else
\set runtime_checks true
\endif

\if :{?owner_checks}
\else
\set owner_checks false
\endif

BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;

-- Role attributes must be false for rolsuper, rolcreatedb, rolcreaterole,
-- rolreplication and rolbypassrls when runtime_checks is enabled.
SELECT
    current_user AS effective_role,
    session_user AS login_role,
    roles.rolcanlogin,
    roles.rolinherit,
    roles.rolsuper,
    roles.rolcreatedb,
    roles.rolcreaterole,
    roles.rolreplication,
    roles.rolbypassrls
FROM pg_catalog.pg_roles AS roles
WHERE roles.rolname = current_user;

-- A NOINHERIT runtime role can still SET ROLE into granted memberships.
-- No reachable role may be privileged or own a canonical finance relation.
WITH RECURSIVE reachable_role_oids(role_oid) AS (
    SELECT roles.oid
    FROM pg_catalog.pg_roles AS roles
    WHERE roles.rolname = current_user

    UNION

    SELECT memberships.roleid
    FROM reachable_role_oids
    JOIN pg_catalog.pg_auth_members AS memberships
      ON memberships.member = reachable_role_oids.role_oid
)
SELECT
    roles.rolname,
    roles.rolname = current_user AS effective_role,
    roles.rolinherit,
    roles.rolsuper,
    roles.rolcreatedb,
    roles.rolcreaterole,
    roles.rolreplication,
    roles.rolbypassrls,
    EXISTS (
        SELECT 1
        FROM pg_catalog.pg_class AS relation
        JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE relation.relowner = roles.oid
          AND namespace.nspname = 'public'
          AND relation.relname IN (
              'wb_finance_sync_runs',
              'wb_finance_operations',
              'wb_finance_sync_run_operations',
              'wb_finance_sync_run_sku_rollups',
              'wb_finance_sync_run_sku_pnl_rollups',
              'wb_finance_sync_run_sku_daily_pnl_rollups'
          )
    ) AS owns_finance_relation
FROM reachable_role_oids
JOIN pg_catalog.pg_roles AS roles
  ON roles.oid = reachable_role_oids.role_oid
ORDER BY effective_role DESC, roles.rolname;

-- Every canonical finance relation must exist with ENABLE + FORCE RLS.
WITH expected(table_name) AS (
    VALUES
        ('wb_finance_sync_runs'),
        ('wb_finance_operations'),
        ('wb_finance_sync_run_operations'),
        ('wb_finance_sync_run_sku_rollups'),
        ('wb_finance_sync_run_sku_pnl_rollups'),
        ('wb_finance_sync_run_sku_daily_pnl_rollups')
)
SELECT
    expected.table_name,
    relation.oid IS NOT NULL AS relation_exists,
    owner_role.rolname AS table_owner,
    relation.relrowsecurity AS rls_enabled,
    relation.relforcerowsecurity AS rls_forced
FROM expected
LEFT JOIN pg_catalog.pg_namespace AS namespace
    ON namespace.nspname = 'public'
LEFT JOIN pg_catalog.pg_class AS relation
    ON relation.relnamespace = namespace.oid
    AND relation.relname = expected.table_name
    AND relation.relkind IN ('p', 'r')
LEFT JOIN pg_catalog.pg_roles AS owner_role
    ON owner_role.oid = relation.relowner
ORDER BY expected.table_name;

-- Each relation must expose its tenant policy with both USING and WITH CHECK.
SELECT
    policies.tablename,
    policies.policyname,
    policies.permissive,
    policies.roles,
    policies.cmd,
    policies.qual,
    policies.with_check
FROM pg_catalog.pg_policies AS policies
WHERE policies.schemaname = 'public'
  AND policies.tablename IN (
      'wb_finance_sync_runs',
      'wb_finance_operations',
      'wb_finance_sync_run_operations',
      'wb_finance_sync_run_sku_rollups',
      'wb_finance_sync_run_sku_pnl_rollups',
      'wb_finance_sync_run_sku_daily_pnl_rollups'
  )
ORDER BY policies.tablename, policies.policyname;

\if :runtime_checks

-- Required psql variables for runtime_checks:
-- organization_id, other_organization_id, marketplace_account_id,
-- date_from and date_to. The two organization values must differ.
SELECT
    :'organization_id'::integer AS organization_id,
    :'other_organization_id'::integer AS other_organization_id,
    :'marketplace_account_id'::integer AS marketplace_account_id,
    :'date_from'::date AS date_from,
    :'date_to'::date AS date_to,
    :'organization_id'::integer <> :'other_organization_id'::integer
        AS organization_contexts_distinct,
    :'date_from'::date <= :'date_to'::date AS period_valid;

-- No-context visibility: both JSON objects must contain only zeroes.
SET LOCAL app.organization_id = '';

SELECT
    'no_context' AS probe,
    NULLIF(current_setting('app.organization_id', true), '') AS tenant_context,
    jsonb_build_object(
        'sync_runs', (SELECT count(*) FROM public.wb_finance_sync_runs),
        'operations', (SELECT count(*) FROM public.wb_finance_operations),
        'memberships', (SELECT count(*) FROM public.wb_finance_sync_run_operations),
        'sku_rollups', (SELECT count(*) FROM public.wb_finance_sync_run_sku_rollups),
        'pnl_rollups', (SELECT count(*) FROM public.wb_finance_sync_run_sku_pnl_rollups),
        'daily_pnl_rollups', (
            SELECT count(*)
            FROM public.wb_finance_sync_run_sku_daily_pnl_rollups
        )
    ) AS visible_rows,
    jsonb_build_object(
        'sync_runs', (
            SELECT count(*) FROM public.wb_finance_sync_runs
            WHERE organization_id = :'organization_id'::integer
        ),
        'operations', (
            SELECT count(*) FROM public.wb_finance_operations
            WHERE organization_id = :'organization_id'::integer
        ),
        'memberships', (
            SELECT count(*) FROM public.wb_finance_sync_run_operations
            WHERE organization_id = :'organization_id'::integer
        ),
        'sku_rollups', (
            SELECT count(*) FROM public.wb_finance_sync_run_sku_rollups
            WHERE organization_id = :'organization_id'::integer
        ),
        'pnl_rollups', (
            SELECT count(*) FROM public.wb_finance_sync_run_sku_pnl_rollups
            WHERE organization_id = :'organization_id'::integer
        ),
        'daily_pnl_rollups', (
            SELECT count(*)
            FROM public.wb_finance_sync_run_sku_daily_pnl_rollups
            WHERE organization_id = :'organization_id'::integer
        )
    ) AS target_rows_visible;

-- Cross-tenant visibility: target_rows_visible must contain only zeroes.
SET LOCAL app.organization_id = :'other_organization_id';

SELECT
    'other_organization' AS probe,
    NULLIF(current_setting('app.organization_id', true), '') AS tenant_context,
    jsonb_build_object(
        'sync_runs', (SELECT count(*) FROM public.wb_finance_sync_runs),
        'operations', (SELECT count(*) FROM public.wb_finance_operations),
        'memberships', (SELECT count(*) FROM public.wb_finance_sync_run_operations),
        'sku_rollups', (SELECT count(*) FROM public.wb_finance_sync_run_sku_rollups),
        'pnl_rollups', (SELECT count(*) FROM public.wb_finance_sync_run_sku_pnl_rollups),
        'daily_pnl_rollups', (
            SELECT count(*)
            FROM public.wb_finance_sync_run_sku_daily_pnl_rollups
        )
    ) AS visible_rows,
    jsonb_build_object(
        'sync_runs', (
            SELECT count(*) FROM public.wb_finance_sync_runs
            WHERE organization_id = :'organization_id'::integer
        ),
        'operations', (
            SELECT count(*) FROM public.wb_finance_operations
            WHERE organization_id = :'organization_id'::integer
        ),
        'memberships', (
            SELECT count(*) FROM public.wb_finance_sync_run_operations
            WHERE organization_id = :'organization_id'::integer
        ),
        'sku_rollups', (
            SELECT count(*) FROM public.wb_finance_sync_run_sku_rollups
            WHERE organization_id = :'organization_id'::integer
        ),
        'pnl_rollups', (
            SELECT count(*) FROM public.wb_finance_sync_run_sku_pnl_rollups
            WHERE organization_id = :'organization_id'::integer
        ),
        'daily_pnl_rollups', (
            SELECT count(*)
            FROM public.wb_finance_sync_run_sku_daily_pnl_rollups
            WHERE organization_id = :'organization_id'::integer
        )
    ) AS target_rows_visible;

-- Target visibility: visible_rows and target_rows_visible must be identical.
SET LOCAL app.organization_id = :'organization_id';

SELECT
    'target_organization' AS probe,
    NULLIF(current_setting('app.organization_id', true), '') AS tenant_context,
    jsonb_build_object(
        'sync_runs', (SELECT count(*) FROM public.wb_finance_sync_runs),
        'operations', (SELECT count(*) FROM public.wb_finance_operations),
        'memberships', (SELECT count(*) FROM public.wb_finance_sync_run_operations),
        'sku_rollups', (SELECT count(*) FROM public.wb_finance_sync_run_sku_rollups),
        'pnl_rollups', (SELECT count(*) FROM public.wb_finance_sync_run_sku_pnl_rollups),
        'daily_pnl_rollups', (
            SELECT count(*)
            FROM public.wb_finance_sync_run_sku_daily_pnl_rollups
        )
    ) AS visible_rows,
    jsonb_build_object(
        'sync_runs', (
            SELECT count(*) FROM public.wb_finance_sync_runs
            WHERE organization_id = :'organization_id'::integer
        ),
        'operations', (
            SELECT count(*) FROM public.wb_finance_operations
            WHERE organization_id = :'organization_id'::integer
        ),
        'memberships', (
            SELECT count(*) FROM public.wb_finance_sync_run_operations
            WHERE organization_id = :'organization_id'::integer
        ),
        'sku_rollups', (
            SELECT count(*) FROM public.wb_finance_sync_run_sku_rollups
            WHERE organization_id = :'organization_id'::integer
        ),
        'pnl_rollups', (
            SELECT count(*) FROM public.wb_finance_sync_run_sku_pnl_rollups
            WHERE organization_id = :'organization_id'::integer
        ),
        'daily_pnl_rollups', (
            SELECT count(*)
            FROM public.wb_finance_sync_run_sku_daily_pnl_rollups
            WHERE organization_id = :'organization_id'::integer
        )
    ) AS target_rows_visible;

-- Physical counts for the selected organization/account.
SELECT
    (SELECT count(*)
     FROM public.wb_finance_sync_runs
     WHERE organization_id = :'organization_id'::integer
       AND marketplace_account_id = :'marketplace_account_id'::integer) AS sync_runs,
    (SELECT count(*)
     FROM public.wb_finance_operations
     WHERE organization_id = :'organization_id'::integer
       AND marketplace_account_id = :'marketplace_account_id'::integer) AS operations,
    (SELECT count(*)
     FROM public.wb_finance_sync_run_operations
     WHERE organization_id = :'organization_id'::integer
       AND marketplace_account_id = :'marketplace_account_id'::integer) AS memberships,
    (SELECT count(*)
     FROM public.wb_finance_sync_run_sku_rollups
     WHERE organization_id = :'organization_id'::integer
       AND marketplace_account_id = :'marketplace_account_id'::integer) AS sku_rollups,
    (SELECT count(*)
     FROM public.wb_finance_sync_run_sku_pnl_rollups
     WHERE organization_id = :'organization_id'::integer
       AND marketplace_account_id = :'marketplace_account_id'::integer) AS pnl_rollups,
    (SELECT count(*)
     FROM public.wb_finance_sync_run_sku_daily_pnl_rollups
     WHERE organization_id = :'organization_id'::integer
       AND marketplace_account_id = :'marketplace_account_id'::integer)
        AS daily_pnl_rollups;

-- Published, pending-rollup and incomplete run inventory.
WITH classified AS (
    SELECT
        CASE
            WHEN NOT is_materialized THEN 'incomplete'
            WHEN NOT (
                is_rollup_materialized
                AND is_pnl_rollup_materialized
                AND is_daily_pnl_rollup_materialized
            ) THEN 'pending_rollup'
            ELSE 'published'
        END AS lifecycle_state,
        captured_at,
        last_observed_at
    FROM public.wb_finance_sync_runs
    WHERE organization_id = :'organization_id'::integer
      AND marketplace_account_id = :'marketplace_account_id'::integer
)
SELECT
    lifecycle_state,
    count(*) AS run_count,
    min(captured_at) AS oldest_captured_at,
    max(last_observed_at) AS newest_last_observed_at,
    clock_timestamp() - min(captured_at) AS oldest_run_age
FROM classified
GROUP BY lifecycle_state
ORDER BY lifecycle_state;

-- Per-run chain, readiness, effective membership and zero-tolerance money checks.
WITH RECURSIVE
runs AS MATERIALIZED (
    SELECT *
    FROM public.wb_finance_sync_runs
    WHERE organization_id = :'organization_id'::integer
      AND marketplace_account_id = :'marketplace_account_id'::integer
),
snapshot_chain (
    root_sync_run_id,
    node_sync_run_id,
    parent_sync_run_id,
    depth,
    path,
    materialized_path,
    cycle
) AS (
    SELECT
        runs.sync_run_id,
        runs.sync_run_id,
        runs.parent_sync_run_id,
        0,
        ARRAY[runs.sync_run_id::text],
        runs.is_materialized,
        false
    FROM runs

    UNION ALL

    SELECT
        snapshot_chain.root_sync_run_id,
        parent.sync_run_id,
        parent.parent_sync_run_id,
        snapshot_chain.depth + 1,
        array_append(snapshot_chain.path, parent.sync_run_id::text),
        snapshot_chain.materialized_path AND parent.is_materialized,
        parent.sync_run_id::text = ANY(snapshot_chain.path)
    FROM snapshot_chain
    JOIN runs AS parent
      ON parent.sync_run_id = snapshot_chain.parent_sync_run_id
    WHERE NOT snapshot_chain.cycle
      AND snapshot_chain.parent_sync_run_id IS NOT NULL
      AND snapshot_chain.depth < 100
),
chain_health AS (
    SELECT
        root_sync_run_id,
        max(depth) FILTER (WHERE NOT cycle) AS snapshot_chain_depth,
        bool_or(cycle) AS cycle_detected,
        bool_or(parent_sync_run_id IS NULL AND NOT cycle) AS base_reached,
        bool_and(materialized_path) AS chain_fully_materialized,
        bool_or(depth = 100 AND parent_sync_run_id IS NOT NULL AND NOT cycle)
            AS depth_limit_reached
    FROM snapshot_chain
    GROUP BY root_sync_run_id
),
membership_ranked AS (
    SELECT
        snapshot_chain.root_sync_run_id,
        membership.operation_id,
        membership.is_present,
        row_number() OVER (
            PARTITION BY snapshot_chain.root_sync_run_id, membership.operation_id
            ORDER BY snapshot_chain.depth
        ) AS position
    FROM snapshot_chain
    JOIN public.wb_finance_sync_run_operations AS membership
      ON membership.organization_id = :'organization_id'::integer
     AND membership.marketplace_account_id = :'marketplace_account_id'::integer
     AND membership.sync_run_id = snapshot_chain.node_sync_run_id
    WHERE NOT snapshot_chain.cycle
      AND snapshot_chain.materialized_path
),
effective_memberships AS (
    SELECT root_sync_run_id, operation_id
    FROM membership_ranked
    WHERE position = 1 AND is_present
),
direct_memberships AS (
    SELECT
        sync_run_id,
        count(*) AS membership_changes,
        count(*) FILTER (WHERE is_present) AS membership_additions,
        count(*) FILTER (WHERE NOT is_present) AS membership_removals
    FROM public.wb_finance_sync_run_operations
    WHERE organization_id = :'organization_id'::integer
      AND marketplace_account_id = :'marketplace_account_id'::integer
    GROUP BY sync_run_id
),
effective_operations AS (
    SELECT
        membership.root_sync_run_id,
        count(*) AS effective_membership_count,
        count(operation.operation_id) AS operation_rows_found,
        count(operation.operation_id) FILTER (
            WHERE operation.business_date BETWEEN root_run.date_from AND root_run.date_to
        ) AS daily_expected_operation_count,
        COALESCE(sum(operation.revenue_kopecks), 0) AS revenue_kopecks,
        COALESCE(sum(operation.revenue_kopecks) FILTER (
            WHERE operation.report_type = 'main'
              AND NOT operation.is_late_correction
        ), 0) AS main_revenue_kopecks,
        COALESCE(sum(operation.revenue_kopecks) FILTER (
            WHERE operation.report_type = 'redemptions'
              AND NOT operation.is_late_correction
        ), 0) AS redemptions_revenue_kopecks,
        COALESCE(sum(operation.revenue_kopecks) FILTER (
            WHERE operation.is_late_correction
        ), 0) AS late_correction_revenue_kopecks,
        COALESCE(sum(operation.revenue_kopecks) FILTER (
            WHERE operation.report_type = 'unknown'
              AND NOT operation.is_late_correction
        ), 0) AS unknown_revenue_kopecks,
        COALESCE(sum(operation.revenue_kopecks) FILTER (
            WHERE operation.business_date BETWEEN root_run.date_from AND root_run.date_to
        ), 0) AS daily_revenue_kopecks,
        COALESCE(sum(operation.revenue_kopecks) FILTER (
            WHERE operation.business_date BETWEEN root_run.date_from AND root_run.date_to
              AND operation.report_type = 'main'
              AND NOT operation.is_late_correction
        ), 0) AS daily_main_revenue_kopecks,
        COALESCE(sum(operation.revenue_kopecks) FILTER (
            WHERE operation.business_date BETWEEN root_run.date_from AND root_run.date_to
              AND operation.report_type = 'redemptions'
              AND NOT operation.is_late_correction
        ), 0) AS daily_redemptions_revenue_kopecks,
        COALESCE(sum(operation.revenue_kopecks) FILTER (
            WHERE operation.business_date BETWEEN root_run.date_from AND root_run.date_to
              AND operation.is_late_correction
        ), 0) AS daily_late_correction_revenue_kopecks,
        COALESCE(sum(operation.revenue_kopecks) FILTER (
            WHERE operation.business_date BETWEEN root_run.date_from AND root_run.date_to
              AND operation.report_type = 'unknown'
              AND NOT operation.is_late_correction
        ), 0) AS daily_unknown_revenue_kopecks
    FROM effective_memberships AS membership
    JOIN runs AS root_run
      ON root_run.sync_run_id = membership.root_sync_run_id
    LEFT JOIN public.wb_finance_operations AS operation
      ON operation.organization_id = :'organization_id'::integer
     AND operation.marketplace_account_id = :'marketplace_account_id'::integer
     AND operation.operation_id = membership.operation_id
    GROUP BY membership.root_sync_run_id, root_run.date_from, root_run.date_to
),
sku_rollups AS (
    SELECT
        sync_run_id,
        count(*) AS row_count,
        COALESCE(sum(operation_count), 0) AS operation_count,
        COALESCE(sum(revenue_kopecks), 0) AS revenue_kopecks,
        COALESCE(sum(main_revenue_kopecks), 0) AS main_revenue_kopecks,
        COALESCE(sum(redemptions_revenue_kopecks), 0)
            AS redemptions_revenue_kopecks,
        COALESCE(sum(late_correction_revenue_kopecks), 0)
            AS late_correction_revenue_kopecks,
        COALESCE(sum(unknown_revenue_kopecks), 0)
            AS unknown_revenue_kopecks
    FROM public.wb_finance_sync_run_sku_rollups
    WHERE organization_id = :'organization_id'::integer
      AND marketplace_account_id = :'marketplace_account_id'::integer
    GROUP BY sync_run_id
),
pnl_rollups AS (
    SELECT
        sync_run_id,
        count(*) AS row_count,
        COALESCE(sum(operation_count), 0) AS operation_count,
        COALESCE(sum(revenue_kopecks), 0) AS revenue_kopecks,
        COALESCE(sum(main_revenue_kopecks), 0) AS main_revenue_kopecks,
        COALESCE(sum(redemptions_revenue_kopecks), 0)
            AS redemptions_revenue_kopecks,
        COALESCE(sum(late_correction_revenue_kopecks), 0)
            AS late_correction_revenue_kopecks,
        COALESCE(sum(unknown_revenue_kopecks), 0)
            AS unknown_revenue_kopecks
    FROM public.wb_finance_sync_run_sku_pnl_rollups
    WHERE organization_id = :'organization_id'::integer
      AND marketplace_account_id = :'marketplace_account_id'::integer
    GROUP BY sync_run_id
),
daily_pnl_rollups AS (
    SELECT
        sync_run_id,
        count(*) AS row_count,
        COALESCE(sum(operation_count), 0) AS operation_count,
        COALESCE(sum(revenue_kopecks), 0) AS revenue_kopecks,
        COALESCE(sum(main_revenue_kopecks), 0) AS main_revenue_kopecks,
        COALESCE(sum(redemptions_revenue_kopecks), 0)
            AS redemptions_revenue_kopecks,
        COALESCE(sum(late_correction_revenue_kopecks), 0)
            AS late_correction_revenue_kopecks,
        COALESCE(sum(unknown_revenue_kopecks), 0)
            AS unknown_revenue_kopecks
    FROM public.wb_finance_sync_run_sku_daily_pnl_rollups
    WHERE organization_id = :'organization_id'::integer
      AND marketplace_account_id = :'marketplace_account_id'::integer
    GROUP BY sync_run_id
),
reconciliation AS (
    SELECT
        runs.*,
        chain_health.snapshot_chain_depth,
        chain_health.cycle_detected,
        chain_health.base_reached,
        chain_health.chain_fully_materialized,
        chain_health.depth_limit_reached,
        COALESCE(direct_memberships.membership_changes, 0)
            AS membership_changes,
        COALESCE(direct_memberships.membership_additions, 0)
            AS membership_additions,
        COALESCE(direct_memberships.membership_removals, 0)
            AS membership_removals,
        COALESCE(effective_operations.effective_membership_count, 0)
            AS effective_membership_count,
        COALESCE(effective_operations.operation_rows_found, 0)
            AS operation_rows_found,
        COALESCE(effective_operations.daily_expected_operation_count, 0)
            AS daily_expected_operation_count,
        COALESCE(effective_operations.revenue_kopecks, 0)
            AS operation_revenue_kopecks,
        COALESCE(effective_operations.main_revenue_kopecks, 0)
            AS operation_main_revenue_kopecks,
        COALESCE(effective_operations.redemptions_revenue_kopecks, 0)
            AS operation_redemptions_revenue_kopecks,
        COALESCE(effective_operations.late_correction_revenue_kopecks, 0)
            AS operation_late_correction_revenue_kopecks,
        COALESCE(effective_operations.unknown_revenue_kopecks, 0)
            AS operation_unknown_revenue_kopecks,
        COALESCE(effective_operations.daily_revenue_kopecks, 0)
            AS daily_expected_revenue_kopecks,
        COALESCE(effective_operations.daily_main_revenue_kopecks, 0)
            AS daily_expected_main_revenue_kopecks,
        COALESCE(effective_operations.daily_redemptions_revenue_kopecks, 0)
            AS daily_expected_redemptions_revenue_kopecks,
        COALESCE(effective_operations.daily_late_correction_revenue_kopecks, 0)
            AS daily_expected_late_correction_revenue_kopecks,
        COALESCE(effective_operations.daily_unknown_revenue_kopecks, 0)
            AS daily_expected_unknown_revenue_kopecks,
        COALESCE(sku_rollups.row_count, 0) AS sku_rollup_rows,
        COALESCE(sku_rollups.operation_count, 0) AS sku_rollup_operation_count,
        COALESCE(sku_rollups.revenue_kopecks, 0) AS sku_rollup_revenue_kopecks,
        COALESCE(sku_rollups.main_revenue_kopecks, 0)
            AS sku_rollup_main_revenue_kopecks,
        COALESCE(sku_rollups.redemptions_revenue_kopecks, 0)
            AS sku_rollup_redemptions_revenue_kopecks,
        COALESCE(sku_rollups.late_correction_revenue_kopecks, 0)
            AS sku_rollup_late_correction_revenue_kopecks,
        COALESCE(sku_rollups.unknown_revenue_kopecks, 0)
            AS sku_rollup_unknown_revenue_kopecks,
        COALESCE(pnl_rollups.row_count, 0) AS pnl_rollup_rows,
        COALESCE(pnl_rollups.operation_count, 0) AS pnl_rollup_operation_count,
        COALESCE(pnl_rollups.revenue_kopecks, 0) AS pnl_rollup_revenue_kopecks,
        COALESCE(pnl_rollups.main_revenue_kopecks, 0)
            AS pnl_rollup_main_revenue_kopecks,
        COALESCE(pnl_rollups.redemptions_revenue_kopecks, 0)
            AS pnl_rollup_redemptions_revenue_kopecks,
        COALESCE(pnl_rollups.late_correction_revenue_kopecks, 0)
            AS pnl_rollup_late_correction_revenue_kopecks,
        COALESCE(pnl_rollups.unknown_revenue_kopecks, 0)
            AS pnl_rollup_unknown_revenue_kopecks,
        COALESCE(daily_pnl_rollups.row_count, 0) AS daily_pnl_rollup_rows,
        COALESCE(daily_pnl_rollups.operation_count, 0)
            AS daily_pnl_rollup_operation_count,
        COALESCE(daily_pnl_rollups.revenue_kopecks, 0)
            AS daily_pnl_rollup_revenue_kopecks,
        COALESCE(daily_pnl_rollups.main_revenue_kopecks, 0)
            AS daily_pnl_rollup_main_revenue_kopecks,
        COALESCE(daily_pnl_rollups.redemptions_revenue_kopecks, 0)
            AS daily_pnl_rollup_redemptions_revenue_kopecks,
        COALESCE(daily_pnl_rollups.late_correction_revenue_kopecks, 0)
            AS daily_pnl_rollup_late_correction_revenue_kopecks,
        COALESCE(daily_pnl_rollups.unknown_revenue_kopecks, 0)
            AS daily_pnl_rollup_unknown_revenue_kopecks
    FROM runs
    JOIN chain_health
      ON chain_health.root_sync_run_id = runs.sync_run_id
    LEFT JOIN direct_memberships
      ON direct_memberships.sync_run_id = runs.sync_run_id
    LEFT JOIN effective_operations
      ON effective_operations.root_sync_run_id = runs.sync_run_id
    LEFT JOIN sku_rollups
      ON sku_rollups.sync_run_id = runs.sync_run_id
    LEFT JOIN pnl_rollups
      ON pnl_rollups.sync_run_id = runs.sync_run_id
    LEFT JOIN daily_pnl_rollups
      ON daily_pnl_rollups.sync_run_id = runs.sync_run_id
)
SELECT
    CASE
        WHEN NOT is_materialized THEN 'incomplete'
        WHEN NOT (
            is_rollup_materialized
            AND is_pnl_rollup_materialized
            AND is_daily_pnl_rollup_materialized
        ) THEN 'pending_rollup'
        ELSE 'published'
    END AS lifecycle_state,
    sync_run_id,
    parent_sync_run_id,
    snapshot_checksum,
    date_from,
    date_to,
    formula_version,
    captured_at,
    last_observed_at,
    clock_timestamp() - last_observed_at AS last_observed_age,
    snapshot_chain_depth,
    cycle_detected,
    base_reached,
    chain_fully_materialized,
    depth_limit_reached,
    is_materialized,
    is_rollup_materialized,
    is_pnl_rollup_materialized,
    is_daily_pnl_rollup_materialized,
    membership_changes,
    membership_additions,
    membership_removals,
    operation_count AS declared_operation_count,
    effective_membership_count,
    operation_rows_found,
    daily_expected_operation_count,
    operation_rows_found - daily_expected_operation_count
        AS daily_excluded_operation_count,
    sku_rollup_rows,
    pnl_rollup_rows,
    daily_pnl_rollup_rows,
    jsonb_build_object(
        'operation_vs_classified_total',
            operation_revenue_kopecks - (
                operation_main_revenue_kopecks
                + operation_redemptions_revenue_kopecks
                + operation_late_correction_revenue_kopecks
                + operation_unknown_revenue_kopecks
            ),
        'sku_total', sku_rollup_revenue_kopecks - operation_revenue_kopecks,
        'sku_main',
            sku_rollup_main_revenue_kopecks - operation_main_revenue_kopecks,
        'sku_redemptions',
            sku_rollup_redemptions_revenue_kopecks
            - operation_redemptions_revenue_kopecks,
        'sku_late',
            sku_rollup_late_correction_revenue_kopecks
            - operation_late_correction_revenue_kopecks,
        'sku_unknown',
            sku_rollup_unknown_revenue_kopecks
            - operation_unknown_revenue_kopecks,
        'pnl_total', pnl_rollup_revenue_kopecks - operation_revenue_kopecks,
        'pnl_main',
            pnl_rollup_main_revenue_kopecks - operation_main_revenue_kopecks,
        'pnl_redemptions',
            pnl_rollup_redemptions_revenue_kopecks
            - operation_redemptions_revenue_kopecks,
        'pnl_late',
            pnl_rollup_late_correction_revenue_kopecks
            - operation_late_correction_revenue_kopecks,
        'pnl_unknown',
            pnl_rollup_unknown_revenue_kopecks
            - operation_unknown_revenue_kopecks,
        'daily_total',
            daily_pnl_rollup_revenue_kopecks - daily_expected_revenue_kopecks,
        'daily_main',
            daily_pnl_rollup_main_revenue_kopecks
            - daily_expected_main_revenue_kopecks,
        'daily_redemptions',
            daily_pnl_rollup_redemptions_revenue_kopecks
            - daily_expected_redemptions_revenue_kopecks,
        'daily_late',
            daily_pnl_rollup_late_correction_revenue_kopecks
            - daily_expected_late_correction_revenue_kopecks,
        'daily_unknown',
            daily_pnl_rollup_unknown_revenue_kopecks
            - daily_expected_unknown_revenue_kopecks
    ) AS revenue_deltas_kopecks,
    (
        is_materialized
        AND is_rollup_materialized
        AND is_pnl_rollup_materialized
        AND is_daily_pnl_rollup_materialized
        AND NOT cycle_detected
        AND base_reached
        AND chain_fully_materialized
        AND NOT depth_limit_reached
        AND operation_count = effective_membership_count
        AND operation_count = operation_rows_found
        AND operation_count = sku_rollup_operation_count
        AND operation_count = pnl_rollup_operation_count
        AND daily_expected_operation_count = daily_pnl_rollup_operation_count
        AND operation_revenue_kopecks = (
            operation_main_revenue_kopecks
            + operation_redemptions_revenue_kopecks
            + operation_late_correction_revenue_kopecks
            + operation_unknown_revenue_kopecks
        )
        AND sku_rollup_revenue_kopecks = operation_revenue_kopecks
        AND sku_rollup_main_revenue_kopecks = operation_main_revenue_kopecks
        AND sku_rollup_redemptions_revenue_kopecks
            = operation_redemptions_revenue_kopecks
        AND sku_rollup_late_correction_revenue_kopecks
            = operation_late_correction_revenue_kopecks
        AND sku_rollup_unknown_revenue_kopecks
            = operation_unknown_revenue_kopecks
        AND pnl_rollup_revenue_kopecks = operation_revenue_kopecks
        AND pnl_rollup_main_revenue_kopecks = operation_main_revenue_kopecks
        AND pnl_rollup_redemptions_revenue_kopecks
            = operation_redemptions_revenue_kopecks
        AND pnl_rollup_late_correction_revenue_kopecks
            = operation_late_correction_revenue_kopecks
        AND pnl_rollup_unknown_revenue_kopecks
            = operation_unknown_revenue_kopecks
        AND daily_pnl_rollup_revenue_kopecks = daily_expected_revenue_kopecks
        AND daily_pnl_rollup_main_revenue_kopecks
            = daily_expected_main_revenue_kopecks
        AND daily_pnl_rollup_redemptions_revenue_kopecks
            = daily_expected_redemptions_revenue_kopecks
        AND daily_pnl_rollup_late_correction_revenue_kopecks
            = daily_expected_late_correction_revenue_kopecks
        AND daily_pnl_rollup_unknown_revenue_kopecks
            = daily_expected_unknown_revenue_kopecks
    ) AS zero_tolerance_reconciled
FROM reconciliation
ORDER BY last_observed_at DESC, sync_run_id DESC;

-- Orphan operation rows can be transient during publication; membership orphans
-- violate foreign-key expectations and are always anomalous.
SELECT
    'operation_without_membership' AS orphan_type,
    count(*) AS orphan_count,
    min(operation.created_at) AS oldest_created_at,
    clock_timestamp() - min(operation.created_at) AS oldest_age
FROM public.wb_finance_operations AS operation
WHERE operation.organization_id = :'organization_id'::integer
  AND operation.marketplace_account_id = :'marketplace_account_id'::integer
  AND NOT EXISTS (
      SELECT 1
      FROM public.wb_finance_sync_run_operations AS membership
      WHERE membership.organization_id = operation.organization_id
        AND membership.marketplace_account_id = operation.marketplace_account_id
        AND membership.operation_id = operation.operation_id
  )

UNION ALL

SELECT
    'membership_without_operation',
    count(*),
    NULL::timestamptz,
    NULL::interval
FROM public.wb_finance_sync_run_operations AS membership
WHERE membership.organization_id = :'organization_id'::integer
  AND membership.marketplace_account_id = :'marketplace_account_id'::integer
  AND NOT EXISTS (
      SELECT 1
      FROM public.wb_finance_operations AS operation
      WHERE operation.organization_id = membership.organization_id
        AND operation.marketplace_account_id = membership.marketplace_account_id
        AND operation.operation_id = membership.operation_id
  )

UNION ALL

SELECT
    'membership_without_run',
    count(*),
    NULL::timestamptz,
    NULL::interval
FROM public.wb_finance_sync_run_operations AS membership
WHERE membership.organization_id = :'organization_id'::integer
  AND membership.marketplace_account_id = :'marketplace_account_id'::integer
  AND NOT EXISTS (
      SELECT 1
      FROM public.wb_finance_sync_runs AS run
      WHERE run.organization_id = membership.organization_id
        AND run.marketplace_account_id = membership.marketplace_account_id
        AND run.sync_run_id = membership.sync_run_id
  )
ORDER BY orphan_type;

-- This is the exact-period projection path used by cache-only finance reads.
EXPLAIN (ANALYZE, BUFFERS)
WITH exact_run AS MATERIALIZED (
    SELECT sync_run_id
    FROM public.wb_finance_sync_runs
    WHERE organization_id = :'organization_id'::integer
      AND marketplace_account_id = :'marketplace_account_id'::integer
      AND date_from = :'date_from'::date
      AND date_to = :'date_to'::date
      AND is_materialized
      AND is_rollup_materialized
    ORDER BY last_observed_at DESC, captured_at DESC, sync_run_id DESC
    LIMIT 1
)
SELECT
    rollup.nm_id,
    rollup.seller_article,
    rollup.operation_count,
    rollup.revenue_kopecks,
    rollup.main_revenue_kopecks,
    rollup.redemptions_revenue_kopecks,
    rollup.late_correction_revenue_kopecks,
    rollup.unknown_revenue_kopecks,
    rollup.sales_units,
    rollup.returns_units,
    rollup.net_units
FROM exact_run
JOIN public.wb_finance_sync_run_sku_rollups AS rollup
  ON rollup.organization_id = :'organization_id'::integer
 AND rollup.marketplace_account_id = :'marketplace_account_id'::integer
 AND rollup.sync_run_id = exact_run.sync_run_id;

\endif

-- Waiting sessions that currently hold or request a lock on a finance relation.
WITH finance_relations AS (
    SELECT relation.oid, relation.relname
    FROM pg_catalog.pg_class AS relation
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = relation.relnamespace
    WHERE namespace.nspname = 'public'
      AND relation.relname IN (
          'wb_finance_sync_runs',
          'wb_finance_operations',
          'wb_finance_sync_run_operations',
          'wb_finance_sync_run_sku_rollups',
          'wb_finance_sync_run_sku_pnl_rollups',
          'wb_finance_sync_run_sku_daily_pnl_rollups'
      )
)
SELECT
    activity.pid,
    activity.usename,
    activity.application_name,
    activity.state,
    clock_timestamp() - activity.xact_start AS transaction_age,
    activity.wait_event_type,
    activity.wait_event,
    finance_relations.relname AS relation_name,
    locks.mode,
    locks.granted,
    pg_catalog.pg_blocking_pids(activity.pid) AS blocking_pids
FROM pg_catalog.pg_locks AS locks
JOIN finance_relations
  ON finance_relations.oid = locks.relation
JOIN pg_catalog.pg_stat_activity AS activity
  ON activity.pid = locks.pid
WHERE activity.pid <> pg_backend_pid()
  AND (
      NOT locks.granted
      OR activity.wait_event_type = 'Lock'
      OR cardinality(pg_catalog.pg_blocking_pids(activity.pid)) > 0
  )
ORDER BY transaction_age DESC NULLS LAST, activity.pid, relation_name;

-- All open transactions touching finance relations; inspect ages against policy.
WITH finance_relations AS (
    SELECT relation.oid, relation.relname
    FROM pg_catalog.pg_class AS relation
    JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = relation.relnamespace
    WHERE namespace.nspname = 'public'
      AND relation.relname IN (
          'wb_finance_sync_runs',
          'wb_finance_operations',
          'wb_finance_sync_run_operations',
          'wb_finance_sync_run_sku_rollups',
          'wb_finance_sync_run_sku_pnl_rollups',
          'wb_finance_sync_run_sku_daily_pnl_rollups'
      )
),
locked_relations AS (
    SELECT
        locks.pid,
        array_agg(DISTINCT finance_relations.relname ORDER BY finance_relations.relname)
            AS relation_names,
        bool_or(NOT locks.granted) AS has_ungranted_lock
    FROM pg_catalog.pg_locks AS locks
    JOIN finance_relations
      ON finance_relations.oid = locks.relation
    GROUP BY locks.pid
)
SELECT
    activity.pid,
    activity.usename,
    activity.application_name,
    activity.state,
    activity.xact_start,
    clock_timestamp() - activity.xact_start AS transaction_age,
    activity.state_change,
    activity.wait_event_type,
    activity.wait_event,
    locked_relations.relation_names,
    locked_relations.has_ungranted_lock,
    pg_catalog.pg_blocking_pids(activity.pid) AS blocking_pids
FROM locked_relations
JOIN pg_catalog.pg_stat_activity AS activity
  ON activity.pid = locked_relations.pid
WHERE activity.pid <> pg_backend_pid()
  AND activity.xact_start IS NOT NULL
ORDER BY transaction_age DESC, activity.pid;

\if :owner_checks

-- owner_checks also requires expected_revision and SELECT on alembic_version.
SELECT
    count(*) AS revision_row_count,
    string_agg(version_num, ',' ORDER BY version_num) AS actual_revisions,
    :'expected_revision' AS expected_revision,
    count(*) = 1 AND bool_and(version_num = :'expected_revision')
        AS revision_matches_image
FROM public.alembic_version;

\endif

ROLLBACK;
