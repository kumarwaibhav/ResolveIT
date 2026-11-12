-- ResolveIT schema 0001. Run as resolveit_migrator (table owner).
-- Roles are created by infra/dev/bootstrap_roles.sql (needs a superuser, once per cluster).

CREATE TABLE tenants (
    id            uuid PRIMARY KEY,
    name          text NOT NULL,
    timezone      text NOT NULL DEFAULT 'Asia/Kolkata',
    is_synthetic  boolean NOT NULL DEFAULT false,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE api_keys (
    id          uuid PRIMARY KEY,
    tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    key_hash    text NOT NULL UNIQUE,
    role        text NOT NULL CHECK (role IN ('admin', 'reviewer', 'viewer', 'agent')),
    created_at  timestamptz NOT NULL DEFAULT now(),
    revoked_at  timestamptz
);

CREATE TABLE incidents (
    id               uuid PRIMARY KEY,
    tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    state            text NOT NULL CHECK (state IN
                       ('PENDING_CLARIFICATION', 'ROUTED', 'DEFERRED', 'BOUNCED', 'RESOLVED', 'ERASED')),
    version          integer NOT NULL DEFAULT 1,
    channel          text NOT NULL CHECK (channel IN ('web', 'email', 'chat', 'itsm', 'agent')),
    locale           text NOT NULL DEFAULT 'en',
    parent_id        uuid REFERENCES incidents(id),
    segment_idx      integer NOT NULL DEFAULT 0,
    sla_started_at   timestamptz NOT NULL,
    clarify_deadline timestamptz,
    audit_selected   boolean NOT NULL,
    no_ask_holdout   boolean NOT NULL,
    security_trigger boolean NOT NULL DEFAULT false,
    routed_team      text,
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX incidents_pending_idx ON incidents (clarify_deadline) WHERE state = 'PENDING_CLARIFICATION';

CREATE TABLE incident_keys (
    incident_id  uuid PRIMARY KEY REFERENCES incidents(id) ON DELETE CASCADE,
    tenant_id    uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    wrapped_key  bytea NOT NULL
);

CREATE TABLE incident_text (
    incident_id     uuid PRIMARY KEY REFERENCES incidents(id) ON DELETE CASCADE,
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    masked_text     text,
    raw_ciphertext  bytea,
    raw_nonce       bytea,
    tombstoned_at   timestamptz
);

CREATE TABLE subject_index (
    tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    identifier_hmac  bytea NOT NULL,
    incident_id      uuid NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    PRIMARY KEY (tenant_id, identifier_hmac, incident_id)
);

CREATE TABLE frames (
    incident_id  uuid NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    tenant_id    uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    version      integer NOT NULL,
    slots        jsonb NOT NULL,
    PRIMARY KEY (incident_id, version)
);

CREATE TABLE decisions (
    id           uuid PRIMARY KEY,
    incident_id  uuid NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    tenant_id    uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    stage        text NOT NULL CHECK (stage IN ('initial', 'final')),
    bundle_id    text NOT NULL,
    payload      jsonb NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE questions (
    incident_id   uuid PRIMARY KEY REFERENCES incidents(id) ON DELETE CASCADE,
    tenant_id     uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    slot          text NOT NULL,
    template_id   text NOT NULL,
    channel       text NOT NULL,
    outcome       text NOT NULL DEFAULT 'pending'
                    CHECK (outcome IN ('pending', 'answered', 'skipped', 'timeout')),
    answer        text,
    answer_source text,
    asked_at      timestamptz NOT NULL DEFAULT now(),
    closed_at     timestamptz
);

CREATE TABLE channel_stats (
    tenant_id  uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    channel    text NOT NULL,
    asks       integer NOT NULL DEFAULT 0,
    answers    integer NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, channel)
);

CREATE TABLE erasure_requests (
    id               uuid PRIMARY KEY,
    tenant_id        uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    identifier_hmac  bytea NOT NULL,
    incidents_erased integer NOT NULL,
    requested_at     timestamptz NOT NULL DEFAULT now()
);

-- Row-level security: enabled AND forced on every tenant table. An unset
-- tenant makes the comparison NULL, so reads return nothing and writes fail.
DO $$
DECLARE
    t text;
    col text;
BEGIN
    FOREACH t IN ARRAY ARRAY['tenants', 'api_keys', 'incidents', 'incident_keys', 'incident_text',
                             'subject_index', 'frames', 'decisions', 'questions', 'channel_stats',
                             'erasure_requests']
    LOOP
        col := CASE WHEN t = 'tenants' THEN 'id' ELSE 'tenant_id' END;
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I '
            'USING (%I = NULLIF(current_setting(''app.current_tenant_id'', true), '''')::uuid) '
            'WITH CHECK (%I = NULLIF(current_setting(''app.current_tenant_id'', true), '''')::uuid)',
            t, col, col);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON %I TO resolveit_app', t);
    END LOOP;
END $$;

-- The only path that reads across tenants: resolve an API key hash to its
-- tenant before any tenant context exists. Owned by resolveit_auth, the one
-- role with BYPASSRLS, which can read api_keys and nothing else.
GRANT SELECT ON api_keys TO resolveit_auth;

CREATE FUNCTION resolve_api_key(p_hash text)
RETURNS TABLE (tenant_id uuid, role text)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT k.tenant_id, k.role FROM api_keys k WHERE k.key_hash = p_hash AND k.revoked_at IS NULL
$$;
-- A new owner needs CREATE on the schema at the moment of transfer only.
GRANT CREATE ON SCHEMA public TO resolveit_auth;
ALTER FUNCTION resolve_api_key(text) OWNER TO resolveit_auth;
REVOKE CREATE ON SCHEMA public FROM resolveit_auth;
REVOKE ALL ON FUNCTION resolve_api_key(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION resolve_api_key(text) TO resolveit_app;
