-- Se aplica al arrancar; cada sentencia se puede repetir sin romper nada.

CREATE TABLE IF NOT EXISTS usuarios (
  id serial PRIMARY KEY,
  email text NOT NULL UNIQUE,
  nombre text NOT NULL DEFAULT '',
  rol text NOT NULL DEFAULT 'USUARIO' CHECK (rol IN ('ADMIN', 'USUARIO')),
  activo boolean NOT NULL DEFAULT true,
  creado_por integer REFERENCES usuarios(id),
  creado_at timestamptz NOT NULL DEFAULT now(),
  ultimo_ingreso timestamptz
);

CREATE TABLE IF NOT EXISTS codigos (
  id serial PRIMARY KEY,
  email text NOT NULL,
  codigo_hash text NOT NULL,
  expira timestamptz NOT NULL,
  intentos integer NOT NULL DEFAULT 0,
  usado boolean NOT NULL DEFAULT false,
  creado_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS codigos_email ON codigos (email, creado_at DESC);

-- Una base subida y todo lo que se hizo con ella
CREATE TABLE IF NOT EXISTS trabajos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre text NOT NULL,
  archivo text NOT NULL,
  creado_por integer NOT NULL REFERENCES usuarios(id),
  creado_at timestamptz NOT NULL DEFAULT now(),
  actualizado_at timestamptz NOT NULL DEFAULT now(),
  -- CARGADO → BUSCANDO_RUC → REVISAR_RUC → CONSULTANDO → REVISION (y ERROR)
  estado text NOT NULL DEFAULT 'CARGADO',
  progreso integer NOT NULL DEFAULT 0,
  total integer NOT NULL DEFAULT 0,
  mensaje text,
  columnas_extra jsonb NOT NULL DEFAULT '[]',
  endpoints jsonb NOT NULL DEFAULT '[]',
  descargas integer NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS filas (
  id serial PRIMARY KEY,
  trabajo_id uuid NOT NULL REFERENCES trabajos(id) ON DELETE CASCADE,
  n integer NOT NULL,                      -- fila en el Excel original
  original jsonb NOT NULL DEFAULT '{}',    -- lo que vino en el archivo (campos reconocidos)
  extra jsonb NOT NULL DEFAULT '{}',       -- las demás columnas del archivo
  ruc text,
  -- DEL_ARCHIVO, EXACTO, PROBABLE, VARIOS, NO_ENCONTRADO, INVALIDO, ELEGIDO, DESCARTADA
  ruc_estado text,
  opciones jsonb NOT NULL DEFAULT '[]',    -- candidatos del padrón
  padron jsonb,                            -- razón social, estado, condición, ubigeo y dirección del padrón
  sunat jsonb,                             -- respuestas de apiconsulta ya resumidas
  datos jsonb NOT NULL DEFAULT '{}',       -- lo que se revisó a mano (gana sobre lo demás)
  consultada boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS filas_trabajo ON filas (trabajo_id, n);

-- Cada consulta a apiconsulta (las de caché no gastan del plan)
CREATE TABLE IF NOT EXISTS consultas (
  id bigserial PRIMARY KEY,
  ruc text NOT NULL,
  endpoint text NOT NULL,
  ok boolean NOT NULL,
  respuesta jsonb,
  desde_cache boolean NOT NULL DEFAULT false,
  usuario_id integer REFERENCES usuarios(id),
  trabajo_id uuid REFERENCES trabajos(id) ON DELETE SET NULL,
  creado_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS consultas_cache ON consultas (ruc, endpoint, creado_at DESC) WHERE ok AND NOT desde_cache;
CREATE INDEX IF NOT EXISTS consultas_mes ON consultas (creado_at) WHERE NOT desde_cache;

-- Quién hizo qué (accesos, cargas, consultas, descargas)
CREATE TABLE IF NOT EXISTS actividad (
  id bigserial PRIMARY KEY,
  usuario_id integer REFERENCES usuarios(id),
  accion text NOT NULL,
  detalle jsonb,
  creado_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ajustes (
  clave text PRIMARY KEY,
  valor jsonb NOT NULL,
  actualizado_at timestamptz NOT NULL DEFAULT now()
);
