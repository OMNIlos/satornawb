\set ON_ERROR_STOP on

-- Run this script as a standalone psql input, not inside an outer transaction
-- or with --single-transaction. Runtime must never see the broad grant interval.
BEGIN;

DO $$
DECLARE
    insecure_tables text;
BEGIN
    SELECT string_agg(required.table_name, ', ' ORDER BY required.table_name)
    INTO insecure_tables
    FROM (
        VALUES
            ('review_sync_runs_v2'),
            ('review_facts'),
            ('review_observations'),
            ('review_sync_run_items'),
            ('order_sync_runs'),
            ('marketplace_orders'),
            ('marketplace_order_items'),
            ('order_observations'),
            ('order_status_observations'),
            ('order_lifecycle_events'),
            ('order_deadlines'),
            ('order_sync_coverage'),
            ('order_sync_memberships'),
            ('order_read_snapshots'),
            ('order_read_snapshot_rows'),
            ('production_work_items'),
            ('production_assignment_receipts'),
            ('production_assignment_history'),
            ('wb_repricing_sku_override_versions'),
            ('wb_repricing_sku_override_heads'),
            ('wb_repricing_sku_override_audit'),
            ('catalog_cost_versions'),
            ('catalog_economics_override_versions'),
            ('catalog_skus'),
            ('iam_memberships'),
            ('marketplace_accounts'),
            ('marketplace_account_credentials'),
            ('marketplace_account_ingestion_tokens'),
            ('marketplace_offers'),
            ('marketplace_products'),
            ('organization_economics_versions'),
            ('wb_finance_operations'),
            ('wb_finance_sync_run_operations'),
            ('wb_finance_sync_run_sku_daily_pnl_rollups'),
            ('wb_finance_sync_run_sku_pnl_rollups'),
            ('wb_finance_sync_run_sku_rollups'),
            ('wb_finance_sync_runs')
    ) AS required(table_name)
    LEFT JOIN pg_class AS relation
        ON relation.relname = required.table_name
        AND relation.relnamespace = 'public'::regnamespace
    WHERE relation.oid IS NULL
        OR NOT relation.relrowsecurity
        OR NOT relation.relforcerowsecurity;

    IF insecure_tables IS NOT NULL THEN
        RAISE EXCEPTION 'canonical tables without forced RLS: %', insecure_tables;
    END IF;
END
$$;

SELECT format('CREATE ROLE %I', :'runtime_role')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'runtime_role')
\gexec

SELECT format(
    'ALTER ROLE %I WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS',
    :'runtime_role',
    :'runtime_password'
)
\gexec

GRANT CONNECT, TEMPORARY ON DATABASE :"runtime_database" TO :"runtime_role";
REVOKE CREATE ON DATABASE :"runtime_database" FROM :"runtime_role";
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM :"runtime_role";
GRANT USAGE ON SCHEMA public TO :"runtime_role";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO :"runtime_role";
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO :"runtime_role";

ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_role" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :"runtime_role";
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner_role" IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO :"runtime_role";

REVOKE ALL ON TABLE public.alembic_version FROM :"runtime_role";

-- Orders overrides must follow every broad runtime grant above.
REVOKE ALL ON TABLE public.order_sync_runs, public.marketplace_orders,
    public.marketplace_order_items, public.order_observations,
    public.order_status_observations, public.order_lifecycle_events,
    public.order_deadlines, public.order_sync_coverage, public.order_sync_memberships,
    public.order_read_snapshots, public.order_read_snapshot_rows FROM :"runtime_role";
GRANT SELECT, INSERT ON TABLE public.order_sync_runs, public.marketplace_orders,
    public.marketplace_order_items, public.order_observations,
    public.order_status_observations, public.order_lifecycle_events,
    public.order_deadlines, public.order_sync_coverage, public.order_sync_memberships,
    public.order_read_snapshots, public.order_read_snapshot_rows TO :"runtime_role";
GRANT UPDATE ON TABLE public.order_sync_runs, public.marketplace_orders,
    public.marketplace_order_items TO :"runtime_role";

-- Immutable Orders binding: only pure CHECK/codec helpers are callable.
REVOKE ALL ON FUNCTION public.orders_run_binding_insert_guard(),
    public.orders_run_binding_update_guard() FROM PUBLIC, :"runtime_role";
REVOKE ALL ON FUNCTION public.orders_binding_text(text,integer),
    public.orders_binding_ascii_string(text),
    public.orders_run_binding_bytes(integer,integer,text,text,text)
    FROM PUBLIC, :"runtime_role";
GRANT EXECUTE ON FUNCTION public.orders_binding_text(text,integer),
    public.orders_binding_ascii_string(text),
    public.orders_run_binding_bytes(integer,integer,text,text,text) TO :"runtime_role";

-- Only the identity sequences belonging to these Orders tables are narrowed.
SELECT format('REVOKE ALL ON SEQUENCE %s FROM %I; GRANT USAGE ON SEQUENCE %s TO %I',
    pg_get_serial_sequence(format('public.%I', c.relname), a.attname), :'runtime_role',
    pg_get_serial_sequence(format('public.%I', c.relname), a.attname), :'runtime_role')
FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid AND a.attidentity<>''
WHERE c.relnamespace='public'::regnamespace AND c.relname IN (
    'order_sync_runs','marketplace_orders','marketplace_order_items','order_observations',
    'order_status_observations','order_lifecycle_events','order_deadlines','order_sync_coverage',
    'order_sync_memberships','order_read_snapshots','order_read_snapshot_rows')
\gexec

-- Review Facts overrides also follow all broad grants within this transaction.
REVOKE ALL ON TABLE public.review_sync_runs_v2, public.review_facts,
    public.review_observations, public.review_sync_run_items FROM :"runtime_role";
-- Explicitly clear column rights before reinstating the INSERT allowlist.
SELECT format('REVOKE ALL (%I) ON TABLE public.review_sync_runs_v2 FROM %I',
    a.attname, :'runtime_role')
FROM pg_attribute a WHERE a.attrelid='public.review_sync_runs_v2'::regclass
    AND a.attnum>0 AND NOT a.attisdropped
\gexec
GRANT SELECT, UPDATE ON TABLE public.review_sync_runs_v2 TO :"runtime_role";
GRANT INSERT (sync_run_id, organization_id, marketplace_account_id, marketplace,
    source_run_id, request_checksum, status, completeness, started_at, completed_at,
    observed_count, manifest_checksum, coverage, error_code, source_run_id_utf8, coverage_utf8,
    account_binding_schema_version, account_binding_external_account_id,
    account_binding_credential_ref, account_binding_payload, account_binding_checksum)
    ON public.review_sync_runs_v2 TO :"runtime_role";
GRANT SELECT, INSERT, UPDATE ON TABLE public.review_facts TO :"runtime_role";
GRANT SELECT, INSERT ON TABLE public.review_observations, public.review_sync_run_items
    TO :"runtime_role";
GRANT EXECUTE ON FUNCTION public.review_strict_utf8(bytea),
    public.review_coverage_json_object_utf8(bytea) TO :"runtime_role";
-- Review binding adds only pure descriptor/CHECK evaluation authority.
GRANT EXECUTE ON FUNCTION public.review_binding_ascii_string(text),
    public.review_run_binding_bytes(integer,integer,text,text,text) TO :"runtime_role";
SELECT format('REVOKE ALL ON SEQUENCE %s FROM %I; GRANT USAGE ON SEQUENCE %s TO %I',
    pg_get_serial_sequence('public.review_sync_runs_v2','run_sequence'), :'runtime_role',
    pg_get_serial_sequence('public.review_sync_runs_v2','run_sequence'), :'runtime_role')
\gexec

-- Repricer overrides follow all broad grants inside the same atomic transaction.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM (VALUES ('wb_repricer_price_approvals'),
        ('wb_repricer_price_apply_attempts'),('wb_repricer_price_approval_audit')) t(name)
        LEFT JOIN pg_class c ON c.oid=to_regclass('public.'||t.name)
        WHERE c.oid IS NULL OR NOT c.relrowsecurity OR NOT c.relforcerowsecurity)
    THEN RAISE EXCEPTION 'repricer_forced_rls_required'; END IF;
END $$;
REVOKE ALL ON TABLE public.wb_repricer_price_approvals,
    public.wb_repricer_price_apply_attempts, public.wb_repricer_price_approval_audit
    FROM PUBLIC, :"runtime_role";
SELECT format('REVOKE ALL (%I) ON TABLE public.%I FROM PUBLIC, %I',
    a.attname,c.relname,:'runtime_role')
FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid
WHERE c.relnamespace='public'::regnamespace AND c.relname IN
    ('wb_repricer_price_approvals','wb_repricer_price_apply_attempts','wb_repricer_price_approval_audit')
    AND a.attnum>0 AND NOT a.attisdropped
\gexec
GRANT SELECT, INSERT, UPDATE ON TABLE public.wb_repricer_price_approvals,
    public.wb_repricer_price_apply_attempts TO :"runtime_role";
GRANT SELECT, INSERT ON TABLE public.wb_repricer_price_approval_audit TO :"runtime_role";
REVOKE ALL ON FUNCTION public.repricer_account_lock(), public.repricer_row_guard(),
    public.repricer_validate() FROM PUBLIC, :"runtime_role";
REVOKE ALL ON FUNCTION public.repricer_exact_text(text),
    public.repricer_integral_finite(numeric), public.repricer_safe_code(text),
    public.repricer_ascii_json_string(text), public.repricer_integer_decimal(numeric),
    public.repricer_request_bytes(integer,integer,text,integer,numeric,text,numeric,smallint,numeric,numeric),
    public.repricer_action_key(integer,integer,text,text),
    public.repricer_dispatch_key(integer,integer,text,text,uuid), public.repricer_context_id(text)
    FROM PUBLIC, :"runtime_role";
GRANT EXECUTE ON FUNCTION public.repricer_exact_text(text),
    public.repricer_integral_finite(numeric), public.repricer_safe_code(text),
    public.repricer_ascii_json_string(text), public.repricer_integer_decimal(numeric),
    public.repricer_request_bytes(integer,integer,text,integer,numeric,text,numeric,smallint,numeric,numeric),
    public.repricer_action_key(integer,integer,text,text),
    public.repricer_dispatch_key(integer,integer,text,text,uuid), public.repricer_context_id(text)
    TO :"runtime_role";

-- Dormant Production assignment overrides, after every broad grant.
REVOKE ALL ON TABLE public.production_work_items,
    public.production_assignment_receipts, public.production_assignment_history
    FROM PUBLIC, :"runtime_role";
SELECT format('REVOKE ALL (%I) ON TABLE public.%I FROM PUBLIC, %I',
    a.attname,c.relname,:'runtime_role')
FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid
WHERE c.relnamespace='public'::regnamespace AND c.relname IN
    ('production_work_items','production_assignment_receipts','production_assignment_history')
    AND a.attnum>0 AND NOT a.attisdropped
\gexec
GRANT SELECT, INSERT, UPDATE ON TABLE public.production_work_items TO :"runtime_role";
GRANT SELECT, INSERT ON TABLE public.production_assignment_receipts,
    public.production_assignment_history TO :"runtime_role";
SELECT format('REVOKE ALL ON SEQUENCE %s FROM PUBLIC, %I; GRANT USAGE ON SEQUENCE %s TO %I',
    pg_get_serial_sequence(format('public.%I',c.relname),a.attname), :'runtime_role',
    pg_get_serial_sequence(format('public.%I',c.relname),a.attname), :'runtime_role')
FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid AND a.attidentity<>''
WHERE c.relnamespace='public'::regnamespace AND c.relname IN
    ('production_work_items','production_assignment_receipts','production_assignment_history')
\gexec
REVOKE ALL ON FUNCTION public.production_account_lock(), public.production_row_guard(),
    public.production_validate() FROM PUBLIC, :"runtime_role";
REVOKE ALL ON FUNCTION public.production_exact_text(text),
    public.production_ascii_json_string(text),
    public.production_assignment_bytes(bigint,bigint,integer,text,text)
    FROM PUBLIC, :"runtime_role";
GRANT EXECUTE ON FUNCTION public.production_exact_text(text),
    public.production_ascii_json_string(text),
    public.production_assignment_bytes(bigint,bigint,integer,text,text) TO :"runtime_role";

-- Account-scoped SKU override rights, after the atomic broad-grant interval.
REVOKE ALL ON TABLE public.wb_repricing_sku_override_versions,
    public.wb_repricing_sku_override_heads, public.wb_repricing_sku_override_audit
    FROM PUBLIC, :"runtime_role";
SELECT format('REVOKE ALL (%I) ON TABLE public.%I FROM PUBLIC, %I',
    a.attname,c.relname,:'runtime_role')
FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid
WHERE c.relnamespace='public'::regnamespace AND c.relname IN
    ('wb_repricing_sku_override_versions','wb_repricing_sku_override_heads','wb_repricing_sku_override_audit')
    AND a.attnum>0 AND NOT a.attisdropped
\gexec
GRANT SELECT, INSERT ON TABLE public.wb_repricing_sku_override_versions,
    public.wb_repricing_sku_override_audit TO :"runtime_role";
GRANT SELECT, INSERT, UPDATE ON TABLE public.wb_repricing_sku_override_heads TO :"runtime_role";
REVOKE ALL ON FUNCTION public.wb_sku_override_account_lock(), public.wb_sku_override_row_guard(),
    public.wb_sku_override_validate() FROM PUBLIC, :"runtime_role";
REVOKE ALL ON FUNCTION public.wb_sku_override_decimal(numeric),
    public.wb_sku_override_integral(numeric),
    public.wb_sku_override_bytes(integer,integer,integer,integer,uuid,numeric,jsonb)
    FROM PUBLIC, :"runtime_role";
GRANT EXECUTE ON FUNCTION public.wb_sku_override_decimal(numeric),
    public.wb_sku_override_integral(numeric),
    public.wb_sku_override_bytes(integer,integer,integer,integer,uuid,numeric,jsonb)
    TO :"runtime_role";

COMMIT;
