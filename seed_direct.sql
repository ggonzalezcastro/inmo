-- Seed directo para Railway
-- Ejecutar con: psql "postgresql://postgres:SQunzsbimTiRZHfHzIAGdCAFbEcdkLOG@hopper.proxy.rlwy.net:48609/railway" -f seed_direct.sql

-- Insertar Brokers
INSERT INTO brokers (name, slug, contact_email, contact_phone, is_active, created_at, updated_at)
VALUES
  ('Inmobiliaria Santiago Centro', 'santiago-centro', 'contacto@santiagocentro.cl', '+56 2 2345 6789', true, NOW(), NOW()),
  ('Propiedades Las Condes', 'las-condes', 'info@lascondes.cl', '+56 2 2987 6543', true, NOW(), NOW()),
  ('Inmobiliaria Ñuñoa', 'nunoa', 'ventas@nunoa.cl', '+56 2 2111 2222', true, NOW(), NOW())
ON CONFLICT (slug) DO NOTHING;

-- Obtener IDs de los brokers
WITH broker_ids AS (
  SELECT id, slug FROM brokers WHERE slug IN ('santiago-centro', 'las-condes', 'nunoa')
)

-- Insertar Usuarios (Admin + Agentes)
INSERT INTO users (email, hashed_password, name, role, broker_id, is_active, created_at, updated_at)
SELECT
  email,
  'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', -- sha256('123')
  name,
  role,
  (SELECT id FROM broker_ids WHERE slug = broker_slug),
  true,
  NOW(),
  NOW()
FROM (
  -- Santiago Centro
  VALUES
    ('admin@santiagocentro.cl', 'Admin Santiago Centro', 'ADMIN', 'santiago-centro'),
    ('carlos@santiagocentro.cl', 'Carlos Ramírez', 'AGENT', 'santiago-centro'),
    ('valentina@santiagocentro.cl', 'Valentina Torres', 'AGENT', 'santiago-centro'),
    -- Las Condes
    ('admin@lascondes.cl', 'Admin Las Condes', 'ADMIN', 'las-condes'),
    ('andres@lascondes.cl', 'Andrés Morales', 'AGENT', 'las-condes'),
    ('catalina@lascondes.cl', 'Catalina Vega', 'AGENT', 'las-condes'),
    -- Ñuñoa
    ('admin@nunoa.cl', 'Admin Ñuñoa', 'ADMIN', 'nunoa'),
    ('felipe@nunoa.cl', 'Felipe Herrera', 'AGENT', 'nunoa'),
    ('sofia@nunoa.cl', 'Sofía Castillo', 'AGENT', 'nunoa')
) AS users_data(email, name, role, broker_slug)
WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.email = users_data.email);

-- Insertar BrokerPromptConfigs
INSERT INTO broker_prompt_configs (broker_id, agent_name, agent_role, enable_appointment_booking, created_at, updated_at)
SELECT id, 'Sofía', 'asesora inmobiliaria', true, NOW(), NOW()
FROM brokers
WHERE slug IN ('santiago-centro', 'las-condes', 'nunoa')
ON CONFLICT (broker_id) DO NOTHING;

-- Insertar BrokerLeadConfigs
INSERT INTO broker_lead_configs (broker_id, created_at, updated_at)
SELECT id, NOW(), NOW()
FROM brokers
WHERE slug IN ('santiago-centro', 'las-condes', 'nunoa')
ON CONFLICT (broker_id) DO NOTHING;

SELECT '✅ Seed completado' AS resultado;
