-- ResolveIT schema 0002: MCP idempotency and the worker's cross-tenant due list.

CREATE TABLE mcp_calls (
    tenant_id    uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    idem_key     text NOT NULL,
    incident_id  uuid NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, idem_key)
);
ALTER TABLE mcp_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_calls FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON mcp_calls
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
GRANT SELECT, INSERT, UPDATE, DELETE ON mcp_calls TO resolveit_app;

-- The worker must find overdue clarifications in every tenant. It gets IDs only,
-- through one function; all further work happens inside that tenant's transaction.
GRANT SELECT (id, tenant_id, state, clarify_deadline) ON incidents TO resolveit_auth;

CREATE FUNCTION due_clarifications(p_limit integer)
RETURNS TABLE (tenant_id uuid, incident_id uuid)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT i.tenant_id, i.id FROM incidents i
    WHERE i.state = 'PENDING_CLARIFICATION' AND i.clarify_deadline <= now()
    ORDER BY i.clarify_deadline LIMIT p_limit
$$;
GRANT CREATE ON SCHEMA public TO resolveit_auth;
ALTER FUNCTION due_clarifications(integer) OWNER TO resolveit_auth;
REVOKE CREATE ON SCHEMA public FROM resolveit_auth;
REVOKE ALL ON FUNCTION due_clarifications(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION due_clarifications(integer) TO resolveit_app;
