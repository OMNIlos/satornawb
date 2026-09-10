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
-- Reset only known WB custody objects, including leftover column privileges.
DO $$ DECLARE t record; a record; BEGIN
 FOR t IN SELECT oid,relname,relrowsecurity,relforcerowsecurity FROM pg_class
  WHERE relnamespace='public'::regnamespace AND relname IN ('wb_live_sync_jobs',
   'wb_live_sync_sources','wb_live_sync_requests','wb_live_products','wb_live_product_sizes',
   'wb_live_pages','wb_live_history_requests','wb_live_history_pages','wb_live_history_rows') LOOP
  IF NOT t.relrowsecurity OR NOT t.relforcerowsecurity THEN RAISE EXCEPTION 'WB_LOCAL_SCHEMA_INVALID'; END IF;
  EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC,wb_live_api,wb_live_worker,wb_live_dispatch',t.relname);
  FOR a IN SELECT attname FROM pg_attribute WHERE attrelid=t.oid AND attnum>0 AND NOT attisdropped LOOP
   EXECUTE format('REVOKE ALL (%I) ON public.%I FROM PUBLIC,wb_live_api,wb_live_worker,wb_live_dispatch',a.attname,t.relname);
  END LOOP;
 END LOOP;
END $$;
REVOKE ALL ON FUNCTION public.wb_live_due_jobs(integer) FROM PUBLIC,wb_live_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON
 lk_organizations,lk_users,lk_user_permissions,lk_user_preferences,lk_sessions,lk_integrations,lk_audit_events,
 iam_memberships,marketplace_accounts,marketplace_account_credentials TO wb_live_api;
GRANT SELECT ON wb_live_sync_jobs,wb_live_sync_sources,wb_live_sync_requests TO wb_live_api;
GRANT INSERT(organization_id,marketplace_account_id,job_id,credential_id,credential_generation,
 account_incarnation,external_account_id,credential_ref,user_id,membership_id,session_id,state,created_at,updated_at)
 ON wb_live_sync_jobs TO wb_live_api,wb_live_worker;
GRANT UPDATE(state,updated_at) ON wb_live_sync_jobs TO wb_live_api,wb_live_worker;
GRANT INSERT(organization_id,marketplace_account_id,job_id,source,run_id,state,checkpoint,processed,
 revision,attempt,lease_token,lease_expires_at,next_due_at,updated_at,error_code)
 ON wb_live_sync_sources TO wb_live_api,wb_live_worker;
GRANT UPDATE(state,attempt,error_code,lease_token,lease_expires_at,next_due_at,updated_at)
 ON wb_live_sync_sources TO wb_live_api;
GRANT INSERT(organization_id,marketplace_account_id,idempotency_key,job_id) ON wb_live_sync_requests TO wb_live_api;
GRANT SELECT ON wb_live_products,wb_live_product_sizes,wb_live_pages TO wb_live_api;
-- Historical overrides remain readable after offer unmapping; no writer rights.
GRANT SELECT ON wb_repricing_sku_override_heads,wb_repricing_sku_override_versions TO wb_live_api;
-- Saved Orders views only; snapshot publication and ingestion stay separate.
GRANT SELECT ON order_read_snapshots,order_read_snapshot_rows TO wb_live_api;
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
GRANT SELECT ON wb_live_sync_jobs,wb_live_sync_sources,wb_live_products,wb_live_product_sizes,wb_live_pages TO wb_live_worker;
GRANT UPDATE(run_id,state,checkpoint,processed,revision,attempt,lease_token,lease_expires_at,next_due_at,updated_at,error_code)
 ON wb_live_sync_sources TO wb_live_worker;
GRANT INSERT(organization_id,marketplace_account_id,nm_id,vendor_code,title,brand,subject_id,subject_name,
 photo_url,source_updated_at,content_updated_at,prices_updated_at,discount_pct,club_discount_pct)
 ON wb_live_products TO wb_live_worker;
GRANT UPDATE(vendor_code,title,brand,subject_id,subject_name,photo_url,source_updated_at,
 content_updated_at,prices_updated_at,discount_pct,club_discount_pct) ON wb_live_products TO wb_live_worker;
GRANT INSERT(organization_id,marketplace_account_id,nm_id,chrt_id,tech_size,skus,price_kopecks,
 discounted_price_kopecks,club_price_kopecks,content_updated_at,prices_updated_at) ON wb_live_product_sizes TO wb_live_worker;
GRANT UPDATE(tech_size,skus,price_kopecks,discounted_price_kopecks,club_price_kopecks,content_updated_at,prices_updated_at)
 ON wb_live_product_sizes TO wb_live_worker;
GRANT INSERT(organization_id,marketplace_account_id,job_id,source,run_id,lease_token,page_digest,checkpoint,row_count)
 ON wb_live_pages TO wb_live_worker;
GRANT USAGE,SELECT ON SEQUENCE lk_organizations_organization_id_seq,lk_user_permissions_permission_id_seq,
 lk_user_preferences_preference_id_seq,lk_integrations_integration_id_seq,lk_audit_events_event_id_seq,
 iam_memberships_membership_id_seq,marketplace_accounts_marketplace_account_id_seq TO wb_live_api;
GRANT EXECUTE ON FUNCTION public.wb_live_due_jobs(integer) TO wb_live_worker,wb_live_dispatch;
-- Additive 0082 rights. The condition keeps the grant script usable by older
-- isolated schema fixtures; the history runtime itself requires migration 0082.
DO $$ BEGIN
 IF to_regclass('public.wb_live_history_pages') IS NOT NULL THEN
  REVOKE ALL ON FUNCTION public.wb_live_history_immutable() FROM PUBLIC,wb_live_api,wb_live_worker,wb_live_dispatch;
  GRANT SELECT ON public.wb_live_history_requests TO wb_live_api;
  GRANT INSERT(organization_id,marketplace_account_id,idempotency_key,job_id,date_from) ON public.wb_live_history_requests TO wb_live_api;
  GRANT SELECT ON public.wb_live_history_pages,public.wb_live_history_rows TO wb_live_worker;
  GRANT INSERT(organization_id,marketplace_account_id,job_id,source,run_id,lease_token,page_id,
   input_date_from,request_checksum,credential_id,credential_generation,account_incarnation)
   ON public.wb_live_history_pages TO wb_live_worker;
  GRANT INSERT(organization_id,marketplace_account_id,job_id,source,page_id,ordinal,srid,nm_id,
   barcode,semantic_checksum,source_row_checksum,observation,source_revision,effective_at)
   ON public.wb_live_history_rows TO wb_live_worker;
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
