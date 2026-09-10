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
-- Inbox discovery/list and recipient receipts only; no notification production.
GRANT SELECT ON notification_in_app_events,notification_in_app_receipts,
 review_facts,review_observations,review_sync_runs_v2 TO wb_live_api;
GRANT INSERT ON notification_in_app_receipts TO wb_live_api;
GRANT UPDATE(read_at,dismissed_at) ON notification_in_app_receipts TO wb_live_api;
-- Local Review context/manual draft/edit/approval/history only. Existing owner-
-- seeded policy/source are read, never created or published by this API role.
GRANT SELECT ON review_policy_versions,review_policy_heads,review_draft_revisions,
 review_decisions,review_workflow_heads,review_local_audit,review_local_command_receipts TO wb_live_api;
GRANT INSERT ON review_draft_revisions,review_decisions,review_workflow_heads,
 review_local_audit,review_local_command_receipts TO wb_live_api;
GRANT UPDATE(head_id,version,current_draft_id,current_draft_revision,current_decision_id,updated_at)
 ON review_workflow_heads TO wb_live_api;
-- Lock capability only: policy-head writes require separately privileged version
-- advancement; fact first_observed_at is immutable and fact writes require version
-- advancement too. Existing physical guards reject these column-only mutations.
GRANT UPDATE(updated_at) ON review_policy_heads TO wb_live_api;
GRANT UPDATE(first_observed_at) ON review_facts TO wb_live_api;
-- Explicit pure codecs only; no trigger, send, enqueue or namespace-wide EXECUTE.
GRANT EXECUTE ON FUNCTION public.review_local_integer_text(numeric,boolean),
 public.review_local_timestamp_text(timestamp with time zone),
 public.review_local_utf8_json_string(bytea),public.review_local_nonblank_utf8(bytea),
 public.review_local_string(text,boolean),public.review_local_uuid(uuid,boolean),
 public.review_local_number(numeric,boolean,boolean),public.review_local_label(text),
 public.review_local_checksum(text),public.review_local_policy_bytes(public.review_policy_versions),
 public.review_local_generation_bytes(public.review_draft_revisions),
 public.review_local_decision_binding_bytes(public.review_draft_revisions,bytea),
 public.review_local_audit_bytes(public.review_local_audit),
 public.review_local_result_bytes(public.review_local_command_receipts),
 public.review_local_request_bytes(public.review_local_command_receipts,public.review_policy_versions,
  public.review_draft_revisions,public.review_decisions,bytea),
 public.review_run_binding_bytes(integer,integer,text,text,text),
 public.review_binding_ascii_string(text) TO wb_live_api;
GRANT EXECUTE ON FUNCTION public.review_send_unicode_version(),public.review_send_uuid4(uuid),
 public.review_send_external_id(bytea),
 public.review_strict_utf8(bytea),public.review_local_integer_text(numeric,boolean),
 public.review_local_timestamp_text(timestamp with time zone),
 public.review_local_utf8_json_string(bytea),public.review_local_string(text,boolean),
 public.review_local_uuid(uuid,boolean),public.review_local_number(numeric,boolean,boolean),
 public.notification_in_app_identity_bytes(public.notification_in_app_events),
 public.notification_in_app_event_bytes(public.notification_in_app_events),
 public.notification_in_app_receipt_bytes(public.notification_in_app_receipts),
 public.notification_in_app_visible_action_bytes(integer,integer,integer,uuid[],text)
 TO wb_live_api;
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
-- Additive 0082 rights. The condition keeps the grant script usable by older
-- isolated schema fixtures; the history runtime itself requires migration 0082.
DO $$ BEGIN
 IF to_regclass('public.wb_live_history_pages') IS NOT NULL THEN
  GRANT SELECT,INSERT ON public.wb_live_history_requests TO wb_live_api;
  GRANT SELECT,INSERT ON public.wb_live_history_pages,public.wb_live_history_rows TO wb_live_worker;
  GRANT UPDATE(state,receipt,published_at) ON public.wb_live_history_pages TO wb_live_worker;
 END IF;
END $$;
-- Quota custody is infrastructure admission only, not price mutation authority.
-- A distinct future price executor uses repricer-executor-grants.sql separately.
-- Keep this after role creation and the reader privilege reset above.
DO $$ BEGIN
 IF to_regclass('public.wb_price_quota') IS NOT NULL THEN
  GRANT SELECT,INSERT ON public.wb_price_quota TO wb_live_worker;
  GRANT UPDATE(next_allowed_at,updated_at) ON public.wb_price_quota TO wb_live_worker;
 END IF;
END $$;
