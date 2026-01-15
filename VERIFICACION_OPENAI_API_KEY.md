# 🔑 Verificación y Sincronización de OpenAI API Key

## 📋 Estado Actual

### En OpenAI Platform
- ✅ **Proyecto**: "Zeus IA / ZEUS-IA-Producción"
- ✅ **Nombre de la clave**: "ZEUS-IA-Producción"
- ✅ **Estado**: Activo
- ✅ **Permisos**: Todo (All permissions)
- ✅ **Último uso**: 5 ENE 2026
- ✅ **Creada**: 27 oct 2025

### En Railway (Variables de Entorno)
- ✅ **Variable**: `OPENAI_API_KEY`
- ⚠️ **Estado**: Visible (sin máscara)
- ⚠️ **Problema**: Clave expuesta en la interfaz

## 🔍 Verificación de la Configuración

### 1. Cómo se Carga la API Key en el Código

El sistema carga la API key desde variables de entorno:

```python
# backend/services/openai_service.py (implícito)
api_key = os.getenv("OPENAI_API_KEY")

# backend/agents/base_agent.py
from services.openai_service import chat_completion

# backend/app/api/v1/endpoints/system_status.py
"OPENAI_API_KEY": {
    "service": "OpenAI",
    "required_for": "Todos los agentes - Decisiones IA",
    "link": "https://platform.openai.com/api-keys"
}
```

### 2. Cómo Verificar que la Key Está Correctamente Configurada

#### Opción A: Verificar desde Railway
1. Ve a Railway Dashboard → Variables
2. Busca `OPENAI_API_KEY`
3. Verifica que el valor completo coincida con la key en OpenAI
4. La key debe comenzar con `sk-proj-` o `sk-`

#### Opción B: Verificar desde el Sistema
El sistema tiene un endpoint para verificar el estado:

```
GET /api/v1/system/status
```

Este endpoint verifica si `OPENAI_API_KEY` está configurada.

### 3. Pasos para Sincronizar la Key

#### Paso 1: Obtener la Key Completa de OpenAI
1. Ve a https://platform.openai.com/api-keys
2. Busca la key "ZEUS-IA-Producción"
3. Haz clic en el ícono de copiar o en "Reveal key"
4. **IMPORTANTE**: Copia la key completa (debe empezar con `sk-proj-` y terminar con los últimos caracteres)

#### Paso 2: Actualizar en Railway
1. Ve a Railway Dashboard → Tu proyecto → Variables
2. Busca `OPENAI_API_KEY`
3. Haz clic en "Edit" o el ícono de lápiz
4. Pega la key completa que copiaste de OpenAI
5. Haz clic en "Save" o "Update"
6. **IMPORTANTE**: Marca la variable como "Secret" si es posible para ocultarla

#### Paso 3: Verificar que Railway Reinicie el Servicio
- Railway debería reiniciar automáticamente después de cambiar variables
- Verifica que el servicio esté "En linea" después de guardar

#### Paso 4: Probar que Funciona
1. Ve al sistema ZEUS-IA
2. Intenta usar PERSEO u otro agente
3. Verifica que no aparezca el error de permisos

## ⚠️ Problemas Comunes y Soluciones

### Error: "API key no tiene permisos suficientes"
**Causa**: La key en Railway no coincide con la de OpenAI o tiene permisos insuficientes.

**Solución**:
1. Verifica que la key en Railway sea exactamente la misma que en OpenAI
2. Verifica en OpenAI que los permisos sean "Todo" (All)
3. Si el problema persiste, crea una nueva key en OpenAI y actualízala en Railway

### Error: "API key no encontrada"
**Causa**: La variable `OPENAI_API_KEY` no está configurada en Railway.

**Solución**:
1. Crea la variable `OPENAI_API_KEY` en Railway
2. Pega el valor completo de la key de OpenAI
3. Guarda y espera a que Railway reinicie

### La Key está Visible en Railway
**Problema**: Seguridad - la key debería estar oculta.

**Solución**:
- Railway automáticamente debería ocultar valores largos después de guardarlos
- Si no se oculta, verifica que el valor esté correcto y guarda de nuevo
- Considera usar Railway Secrets para mayor seguridad

## 🔐 Buenas Prácticas de Seguridad

1. **Nunca expongas la key en el código**
   - ✅ Usa variables de entorno
   - ❌ No la hardcodees

2. **Marca la variable como secreta si es posible**
   - En Railway, las variables de entorno se ocultan automáticamente después de guardarlas

3. **Rota las keys periódicamente**
   - Crea nuevas keys en OpenAI cada 3-6 meses
   - Actualiza Railway con la nueva key

4. **Monitorea el uso**
   - Revisa el uso de la API key en OpenAI Dashboard
   - Configura límites de costo si es necesario

## 📝 Verificación Final

Después de sincronizar, verifica:

- [ ] La key en Railway coincide exactamente con la de OpenAI
- [ ] El servicio en Railway está "En linea"
- [ ] No hay errores de permisos al usar los agentes
- [ ] La variable `OPENAI_API_KEY` está oculta/marcada como secreta
- [ ] El endpoint `/api/v1/system/status` muestra que la key está configurada

## 🆘 Soporte

Si el problema persiste después de seguir estos pasos:

1. Verifica los logs de Railway para ver errores específicos
2. Verifica el último uso de la key en OpenAI (debe ser reciente)
3. Prueba crear una nueva key en OpenAI y usarla
4. Verifica que el proyecto en OpenAI sea el correcto ("Zeus IA / ZEUS-IA-Producción")

---

**Última actualización**: 2024-12-19
**Versión**: 1.0
