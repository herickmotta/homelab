-- Managed by herickmotta.homelab.data_platform.
-- ops_ledger domain only. Do not create finance or media_catalog here.

\set ON_ERROR_STOP on

CREATE SCHEMA IF NOT EXISTS ops_ledger AUTHORIZATION ops_ledger_owner;
REVOKE ALL ON SCHEMA ops_ledger FROM PUBLIC;
GRANT USAGE ON SCHEMA ops_ledger TO ops_ledger_migrator;
GRANT USAGE ON SCHEMA ops_ledger TO ops_ledger_hermes;
GRANT USAGE ON SCHEMA ops_ledger TO ops_ledger_readonly;
GRANT ALL ON SCHEMA ops_ledger TO ops_ledger_owner;

ALTER DEFAULT PRIVILEGES FOR ROLE ops_ledger_owner IN SCHEMA ops_ledger
  GRANT SELECT ON TABLES TO ops_ledger_readonly;
ALTER DEFAULT PRIVILEGES FOR ROLE ops_ledger_owner IN SCHEMA ops_ledger
  GRANT SELECT ON TABLES TO ops_ledger_hermes;

CREATE TABLE IF NOT EXISTS ops_ledger.incidents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  status text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT incidents_status_check
    CHECK (status IN ('open', 'investigating', 'resolved', 'closed'))
);

CREATE TABLE IF NOT EXISTS ops_ledger.events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id uuid NOT NULL REFERENCES ops_ledger.incidents (id),
  kind text NOT NULL,
  body jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ops_ledger.feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  incident_id uuid NOT NULL REFERENCES ops_ledger.incidents (id),
  body text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS events_incident_id_idx
  ON ops_ledger.events (incident_id, created_at);
CREATE INDEX IF NOT EXISTS feedback_incident_id_idx
  ON ops_ledger.feedback (incident_id, created_at);

ALTER TABLE ops_ledger.incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE ops_ledger.events ENABLE ROW LEVEL SECURITY;
ALTER TABLE ops_ledger.feedback ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS incidents_read ON ops_ledger.incidents;
CREATE POLICY incidents_read ON ops_ledger.incidents
  FOR SELECT TO ops_ledger_hermes, ops_ledger_readonly
  USING (true);

DROP POLICY IF EXISTS events_read ON ops_ledger.events;
CREATE POLICY events_read ON ops_ledger.events
  FOR SELECT TO ops_ledger_hermes, ops_ledger_readonly
  USING (true);

DROP POLICY IF EXISTS feedback_read ON ops_ledger.feedback;
CREATE POLICY feedback_read ON ops_ledger.feedback
  FOR SELECT TO ops_ledger_hermes, ops_ledger_readonly
  USING (true);

CREATE OR REPLACE FUNCTION ops_ledger.append_event(
  p_title text,
  p_kind text,
  p_body jsonb DEFAULT '{}'::jsonb,
  p_incident_id uuid DEFAULT NULL
) RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ops_ledger, pg_temp
AS $$
DECLARE
  v_id uuid;
  v_status text;
  v_next text;
BEGIN
  IF p_title IS NULL OR length(btrim(p_title)) = 0 THEN
    RAISE EXCEPTION 'title is required';
  END IF;
  IF p_kind IS NULL OR length(btrim(p_kind)) = 0 THEN
    RAISE EXCEPTION 'kind is required';
  END IF;

  IF p_incident_id IS NULL THEN
    INSERT INTO ops_ledger.incidents (title, status)
    VALUES (btrim(p_title), 'open')
    RETURNING id INTO v_id;
  ELSE
    SELECT id, status INTO v_id, v_status
    FROM ops_ledger.incidents
    WHERE id = p_incident_id
    FOR UPDATE;
    IF NOT FOUND THEN
      RAISE EXCEPTION 'incident not found';
    END IF;
  END IF;

  v_next := CASE p_kind
    WHEN 'opened' THEN 'open'
    WHEN 'investigating' THEN 'investigating'
    WHEN 'resolved' THEN 'resolved'
    WHEN 'closed' THEN 'closed'
    ELSE NULL
  END;

  IF v_next IS NOT NULL THEN
    IF v_status IS NOT NULL
       AND v_status = 'closed'
       AND v_next <> 'closed' THEN
      RAISE EXCEPTION 'closed incidents do not reopen in this increment';
    END IF;
    UPDATE ops_ledger.incidents
    SET status = v_next, updated_at = now()
    WHERE id = v_id;
  ELSE
    UPDATE ops_ledger.incidents
    SET updated_at = now()
    WHERE id = v_id;
  END IF;

  INSERT INTO ops_ledger.events (incident_id, kind, body)
  VALUES (v_id, btrim(p_kind), COALESCE(p_body, '{}'::jsonb));

  RETURN v_id;
END;
$$;

CREATE OR REPLACE FUNCTION ops_ledger.add_feedback(
  p_incident_id uuid,
  p_body text
) RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ops_ledger, pg_temp
AS $$
DECLARE
  v_id uuid;
BEGIN
  IF p_body IS NULL OR length(btrim(p_body)) = 0 THEN
    RAISE EXCEPTION 'feedback body is required';
  END IF;
  PERFORM 1 FROM ops_ledger.incidents WHERE id = p_incident_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'incident not found';
  END IF;
  INSERT INTO ops_ledger.feedback (incident_id, body)
  VALUES (p_incident_id, btrim(p_body))
  RETURNING id INTO v_id;
  UPDATE ops_ledger.incidents SET updated_at = now() WHERE id = p_incident_id;
  RETURN v_id;
END;
$$;

REVOKE ALL ON FUNCTION ops_ledger.append_event(text, text, jsonb, uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION ops_ledger.add_feedback(uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ops_ledger.append_event(text, text, jsonb, uuid)
  TO ops_ledger_hermes;
GRANT EXECUTE ON FUNCTION ops_ledger.add_feedback(uuid, text)
  TO ops_ledger_hermes;

GRANT SELECT ON ops_ledger.incidents TO ops_ledger_hermes, ops_ledger_readonly;
GRANT SELECT ON ops_ledger.events TO ops_ledger_hermes, ops_ledger_readonly;
GRANT SELECT ON ops_ledger.feedback TO ops_ledger_hermes, ops_ledger_readonly;

REVOKE INSERT, UPDATE, DELETE ON ops_ledger.incidents FROM ops_ledger_hermes;
REVOKE INSERT, UPDATE, DELETE ON ops_ledger.events FROM ops_ledger_hermes;
REVOKE INSERT, UPDATE, DELETE ON ops_ledger.feedback FROM ops_ledger_hermes;

NOTIFY pgrst, 'reload schema';
