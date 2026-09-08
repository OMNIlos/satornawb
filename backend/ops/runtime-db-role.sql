\set ON_ERROR_STOP on

DO $$
DECLARE
    insecure_tables text;
BEGIN
    SELECT string_agg(required.table_name, ', ' ORDER BY required.table_name)
    INTO insecure_tables
    FROM (
        VALUES
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
