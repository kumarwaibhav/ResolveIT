-- Human identity comes from trusted credential provisioning, never a request body.
ALTER TABLE api_keys ADD COLUMN human_subject_id uuid;
REVOKE INSERT, UPDATE, DELETE ON api_keys FROM resolveit_app;
REVOKE UPDATE ON tenants FROM resolveit_app;
GRANT UPDATE (timezone) ON tenants TO resolveit_app;
DROP FUNCTION resolve_api_key(text);
CREATE FUNCTION resolve_api_key(p_hash text)
RETURNS TABLE (tenant_id uuid, role text, human_subject_id uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp
AS $$ SELECT k.tenant_id, k.role, k.human_subject_id FROM api_keys k
      WHERE k.key_hash=p_hash AND k.revoked_at IS NULL $$;
GRANT CREATE ON SCHEMA public TO resolveit_auth;
ALTER FUNCTION resolve_api_key(text) OWNER TO resolveit_auth;
REVOKE CREATE ON SCHEMA public FROM resolveit_auth;
REVOKE ALL ON FUNCTION resolve_api_key(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION resolve_api_key(text) TO resolveit_app;

CREATE TABLE tenant_settings (
    tenant_id uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    version integer NOT NULL DEFAULT 1,
    queue_mapping jsonb NOT NULL DEFAULT '{}'::jsonb,
    misroute_minutes double precision NOT NULL DEFAULT 240 CHECK (misroute_minutes>0),
    defer_minutes double precision NOT NULL DEFAULT 45 CHECK (defer_minutes>0)
);
CREATE TABLE review_items (
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    incident_id uuid NOT NULL,
    split text NOT NULL CHECK (split IN ('training','scaling','calibration','frozen_test')),
    status text NOT NULL DEFAULT 'unlabeled' CHECK (status IN ('unlabeled','single_label','needs_adjudication','gold','synthetic_labeled')),
    gold_label jsonb,
    adjudicator uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, incident_id),
    FOREIGN KEY (tenant_id, incident_id) REFERENCES incidents(tenant_id,id) ON DELETE CASCADE
);
CREATE TABLE connector_observation (
    tenant_id uuid PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    status text NOT NULL DEFAULT 'disabled' CHECK (status IN ('disabled','verified')),
    coverage_from timestamptz NOT NULL,
    complete_through timestamptz NOT NULL,
    CHECK (complete_through>=coverage_from)
);
CREATE TABLE review_labels (
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    incident_id uuid NOT NULL,
    annotator_id uuid NOT NULL,
    label jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,incident_id,annotator_id),
    FOREIGN KEY (tenant_id,incident_id) REFERENCES review_items(tenant_id,incident_id) ON DELETE CASCADE
);
CREATE TABLE review_exposures (
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    incident_id uuid NOT NULL,
    subject_id uuid NOT NULL,
    kind text NOT NULL CHECK (kind IN ('model','peer')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,incident_id,subject_id,kind),
    FOREIGN KEY (tenant_id,incident_id) REFERENCES review_items(tenant_id,incident_id) ON DELETE CASCADE
);
-- Legacy incidents are explicitly enrolled under tenant_tx, into training only.
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['tenant_settings','review_items','review_labels','review_exposures','connector_observation']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
        EXECUTE format('CREATE POLICY tenant_isolation ON %I '
        'USING (tenant_id=NULLIF(current_setting(''app.current_tenant_id'',true),'''')::uuid) '
        'WITH CHECK (tenant_id=NULLIF(current_setting(''app.current_tenant_id'',true),'''')::uuid)',t);
        EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON %I TO resolveit_app',t);
    END LOOP;
END $$;
-- Split assignment stays immutable to application credentials; labels may only be inserted or erased.
REVOKE UPDATE ON review_labels FROM resolveit_app;
REVOKE UPDATE ON review_exposures FROM resolveit_app;
REVOKE UPDATE ON review_items FROM resolveit_app;
GRANT UPDATE (status,gold_label,adjudicator) ON review_items TO resolveit_app;
-- Only a separately trusted connector may assert complete event observation.
REVOKE INSERT,UPDATE,DELETE ON connector_observation FROM resolveit_app;
