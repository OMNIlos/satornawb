\set ON_ERROR_STOP on
-- Applies only inside the launcher's dedicated owned database/cluster.
DO $$ BEGIN
 IF current_database() <> 'satorna_wb_live' OR session_user <> 'wb_live_owner' THEN
   RAISE EXCEPTION 'WB_LOCAL_WRONG_DATABASE';
 END IF;
END $$;
DO $$ DECLARE r text; BEGIN
 FOREACH r IN ARRAY ARRAY['wb_live_api','wb_live_worker','wb_live_dispatch'] LOOP
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname=r) THEN
   EXECUTE format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS',r);
  END IF;
  EXECUTE format('GRANT CONNECT ON DATABASE satorna_wb_live TO %I',r);
  EXECUTE format('GRANT USAGE ON SCHEMA public TO %I',r);
 END LOOP;
END $$;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM wb_live_worker,wb_live_dispatch;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM wb_live_worker,wb_live_dispatch;
GRANT SELECT, INSERT, UPDATE, DELETE ON
 lk_organizations,lk_users,lk_user_permissions,lk_user_preferences,lk_sessions,lk_integrations,lk_audit_events,
 iam_memberships,marketplace_accounts,marketplace_account_credentials TO wb_live_api;
GRANT SELECT,INSERT,UPDATE ON wb_live_sync_jobs,wb_live_sync_sources,wb_live_sync_requests TO wb_live_api;
GRANT SELECT ON wb_live_products,wb_live_product_sizes,wb_live_pages TO wb_live_api;
GRANT SELECT(user_id,organization_id,is_active,updated_at) ON lk_users TO wb_live_worker;
GRANT SELECT ON iam_memberships,marketplace_accounts,marketplace_account_credentials TO wb_live_worker;
-- PostgreSQL requires UPDATE on at least one column for SELECT FOR SHARE/UPDATE.
-- Timestamp-only privileges support the existing guard's locks without granting
-- changes to identities, roles, permissions, sessions, binding, status or secrets.
GRANT UPDATE(updated_at) ON lk_users,iam_memberships,marketplace_accounts,marketplace_account_credentials TO wb_live_worker;
GRANT SELECT,INSERT,UPDATE ON wb_live_sync_jobs,wb_live_sync_sources,wb_live_products,wb_live_product_sizes TO wb_live_worker;
GRANT SELECT,INSERT ON wb_live_pages TO wb_live_worker;
GRANT USAGE,SELECT ON SEQUENCE lk_organizations_organization_id_seq,lk_user_permissions_permission_id_seq,
 lk_user_preferences_preference_id_seq,lk_integrations_integration_id_seq,lk_audit_events_event_id_seq,
 iam_memberships_membership_id_seq,marketplace_accounts_marketplace_account_id_seq TO wb_live_api;
GRANT EXECUTE ON FUNCTION public.wb_live_due_jobs(integer) TO wb_live_worker,wb_live_dispatch;
