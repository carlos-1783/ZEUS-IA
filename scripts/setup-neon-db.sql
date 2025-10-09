-- ===============================================
-- ZEUS-IA - Configuración inicial de base de datos Neon
-- ===============================================

-- Crear extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Crear esquema principal
CREATE SCHEMA IF NOT EXISTS zeus_ia;

-- Configurar permisos
GRANT ALL PRIVILEGES ON SCHEMA zeus_ia TO zeus_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA zeus_ia TO zeus_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA zeus_ia TO zeus_user;

-- Configurar búsqueda de texto
ALTER DATABASE zeus_ia_prod SET default_text_search_config = 'spanish';

-- Crear índices para optimización
-- Estos se crearán automáticamente con las migraciones de Alembic

-- Configurar conexiones máximas
ALTER DATABASE zeus_ia_prod SET max_connections = 100;

-- Configurar timezone
SET timezone = 'UTC';

-- Crear usuario administrador inicial (será sobrescrito por las migraciones)
-- INSERT INTO zeus_ia.users (username, email, hashed_password, is_active, is_superuser, created_at)
-- VALUES ('admin', 'admin@zeusia.app', '$2b$12$...', true, true, NOW());

COMMIT;
