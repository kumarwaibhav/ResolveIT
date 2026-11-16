-- Tenant-consistent references: RLS alone does not constrain a foreign key's tenant.
ALTER TABLE mcp_calls ADD COLUMN request_digest text;
ALTER TABLE incidents ADD CONSTRAINT incidents_tenant_identity UNIQUE (tenant_id, id);
ALTER TABLE incidents ADD CONSTRAINT incidents_tenant_parent_fk
    FOREIGN KEY (tenant_id, parent_id) REFERENCES incidents (tenant_id, id);
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['incident_keys', 'incident_text', 'subject_index', 'frames',
                             'decisions', 'questions', 'mcp_calls']
    LOOP
        EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I FOREIGN KEY (tenant_id, incident_id) '
                       'REFERENCES incidents (tenant_id, id) ON DELETE CASCADE', t, t || '_tenant_incident_fk');
    END LOOP;
END $$;

CREATE TABLE inbox (
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    source text NOT NULL,
    event_id text NOT NULL,
    body_hash text NOT NULL,
    disposition text NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, source, event_id),
    UNIQUE (tenant_id, source, body_hash)
);

CREATE TABLE outbox (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    incident_id uuid NOT NULL,
    incident_version integer NOT NULL,
    topic text NOT NULL CHECK (topic = 'incident.route'),
    payload jsonb NOT NULL,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'leased', 'delivered', 'dead')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    lease_token uuid,
    lease_until timestamptz,
    available_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    delivered_at timestamptz,
    UNIQUE (tenant_id, incident_id, incident_version, topic),
    FOREIGN KEY (tenant_id, incident_id) REFERENCES incidents(tenant_id, id) ON DELETE CASCADE
);
CREATE INDEX outbox_due_idx ON outbox (available_at) WHERE status IN ('pending', 'leased');

CREATE TABLE billing_ledger (
    tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    sequence bigint NOT NULL,
    incident_id uuid NOT NULL,
    event_kind text NOT NULL CHECK (event_kind IN ('routed', 'bounced', 'zero_bounce_72h', 'credit')),
    occurred_at timestamptz NOT NULL,
    previous_hash text NOT NULL,
    entry_hash text NOT NULL,
    PRIMARY KEY (tenant_id, sequence),
    UNIQUE (tenant_id, incident_id, event_kind),
    FOREIGN KEY (tenant_id, incident_id) REFERENCES incidents(tenant_id, id) ON DELETE CASCADE
);

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['inbox', 'outbox', 'billing_ledger']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY tenant_isolation ON %I '
                       'USING (tenant_id = NULLIF(current_setting(''app.current_tenant_id'', true), '''')::uuid) '
                       'WITH CHECK (tenant_id = NULLIF(current_setting(''app.current_tenant_id'', true), '''')::uuid)', t);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO resolveit_app', t);
    END LOOP;
END $$;
-- Append-only through application role. A database administrator can still rewrite history;
-- production must export signed chain heads to independent immutable storage.
REVOKE UPDATE, DELETE ON billing_ledger FROM resolveit_app;
REVOKE DELETE ON tenants, incidents FROM resolveit_app;

GRANT SELECT (id, tenant_id, status, available_at, lease_until) ON outbox TO resolveit_auth;
CREATE FUNCTION due_outbox(p_limit integer)
RETURNS TABLE (tenant_id uuid, event_id uuid)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp
AS $$
    SELECT o.tenant_id, o.id FROM outbox o
    WHERE (o.status = 'pending' AND o.available_at <= now())
       OR (o.status = 'leased' AND o.lease_until <= now())
    ORDER BY o.available_at LIMIT LEAST(GREATEST(p_limit, 0), 1000)
$$;
GRANT CREATE ON SCHEMA public TO resolveit_auth;
ALTER FUNCTION due_outbox(integer) OWNER TO resolveit_auth;
REVOKE CREATE ON SCHEMA public FROM resolveit_auth;
REVOKE ALL ON FUNCTION due_outbox(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION due_outbox(integer) TO resolveit_app;
