-- ===============================================
-- ZEUS-IA - Script de Inicialización de Base de Datos
-- ===============================================

-- Crear extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Crear esquema si no existe
CREATE SCHEMA IF NOT EXISTS zeus_ia;

-- Configurar búsqueda de texto
CREATE TEXT SEARCH CONFIGURATION IF NOT EXISTS spanish (COPY = spanish);

-- Crear índices para optimización
-- (Estos se crearán automáticamente por SQLAlchemy, pero es bueno tenerlos aquí como referencia)

-- Configurar timezone
SET timezone = 'UTC';

-- Crear usuario de aplicación si no existe
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'zeus_app') THEN
        CREATE ROLE zeus_app WITH LOGIN PASSWORD 'zeus_app_password_2024';
    END IF;
END
$$;

-- Otorgar permisos
GRANT CONNECT ON DATABASE zeus_ia_prod TO zeus_app;
GRANT USAGE ON SCHEMA public TO zeus_app;
GRANT CREATE ON SCHEMA public TO zeus_app;

-- Configurar políticas de seguridad
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO zeus_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO zeus_app;

-- Comentarios para documentación
COMMENT ON DATABASE zeus_ia_prod IS 'Base de datos de producción para ZEUS-IA';
COMMENT ON SCHEMA public IS 'Esquema principal de la aplicación ZEUS-IA';
