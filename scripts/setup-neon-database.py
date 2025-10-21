#!/usr/bin/env python3
"""
🚀 Script para configurar Neon Database automáticamente
Configura las tablas necesarias para ZEUS-IA en Neon PostgreSQL
"""

import os
import sys
import asyncio
import asyncpg
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def setup_neon_database():
    """Configurar base de datos Neon con tablas necesarias"""
    
    # Obtener DATABASE_URL de variables de entorno
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL no encontrada en variables de entorno")
        return False
    
    logger.info("🚀 Iniciando configuración de Neon Database...")
    logger.info(f"🔗 Conectando a: {database_url[:50]}...")
    
    try:
        # Crear conexión asíncrona
        engine = create_async_engine(database_url)
        
        async with engine.begin() as conn:
            # Crear tablas necesarias para ZEUS-IA
            await create_zeus_tables(conn)
            await create_agent_logs_table(conn)
            await create_command_history_table(conn)
            await create_system_metrics_table(conn)
            
        logger.info("✅ Neon Database configurado correctamente")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error configurando Neon Database: {e}")
        return False

async def create_zeus_tables(conn):
    """Crear tablas principales de ZEUS-IA"""
    
    # Tabla de usuarios (si no existe)
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            hashed_password VARCHAR(255) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            is_superuser BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    # Tabla de tokens de refresh
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            token VARCHAR(255) UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    logger.info("✅ Tablas principales creadas")

async def create_agent_logs_table(conn):
    """Crear tabla de logs de agentes ZEUS"""
    
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS agent_logs (
            id SERIAL PRIMARY KEY,
            agent_name VARCHAR(50) NOT NULL,
            command VARCHAR(100) NOT NULL,
            status VARCHAR(20) NOT NULL,
            response TEXT,
            execution_time_ms INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER REFERENCES users(id),
            metadata JSONB
        )
    """))
    
    # Índices para optimizar consultas
    await conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_agent_logs_agent_name 
        ON agent_logs(agent_name)
    """))
    
    await conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_agent_logs_timestamp 
        ON agent_logs(timestamp)
    """))
    
    logger.info("✅ Tabla de logs de agentes creada")

async def create_command_history_table(conn):
    """Crear tabla de historial de comandos"""
    
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS command_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            command VARCHAR(100) NOT NULL,
            input_data JSONB,
            output_data JSONB,
            success BOOLEAN NOT NULL,
            error_message TEXT,
            execution_time_ms INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    await conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_command_history_user_id 
        ON command_history(user_id)
    """))
    
    logger.info("✅ Tabla de historial de comandos creada")

async def create_system_metrics_table(conn):
    """Crear tabla de métricas del sistema"""
    
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS system_metrics (
            id SERIAL PRIMARY KEY,
            metric_name VARCHAR(100) NOT NULL,
            metric_value DECIMAL(10,4) NOT NULL,
            metric_unit VARCHAR(20),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB
        )
    """))
    
    await conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_system_metrics_name 
        ON system_metrics(metric_name)
    """))
    
    logger.info("✅ Tabla de métricas del sistema creada")

async def test_connection():
    """Probar conexión a Neon Database"""
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("❌ DATABASE_URL no encontrada")
        return False
    
    try:
        # Probar conexión simple
        conn = await asyncpg.connect(database_url)
        result = await conn.fetchval("SELECT version()")
        logger.info(f"✅ Conexión exitosa a PostgreSQL: {result[:50]}...")
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error conectando a Neon: {e}")
        return False

if __name__ == "__main__":
    async def main():
        logger.info("🚀 Configurando Neon Database para ZEUS-IA...")
        
        # Probar conexión primero
        if await test_connection():
            # Configurar base de datos
            success = await setup_neon_database()
            if success:
                logger.info("🎉 Neon Database configurado exitosamente!")
                sys.exit(0)
            else:
                logger.error("❌ Error configurando Neon Database")
                sys.exit(1)
        else:
            logger.error("❌ No se pudo conectar a Neon Database")
            sys.exit(1)
    
    asyncio.run(main())
