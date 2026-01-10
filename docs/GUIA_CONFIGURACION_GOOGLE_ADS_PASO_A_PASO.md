# 🔐 Guía Paso a Paso: Configurar Google Ads API para PERSEO

## 🎯 Objetivo
Configurar PERSEO para que pueda gestionar automáticamente campañas de Google Ads mediante la API, sin necesidad de añadir usuarios adicionales a tu cuenta de Google Ads.

---

## 📋 Prerrequisitos

- ✅ Cuenta de Google Ads activa: **129-046-8001 Marketing Digital PER-SEO**
- ✅ Email administrador: `marketingdigitalper.seo@gmail.com`
- ✅ Cuenta de Google Cloud (puede ser la misma cuenta de Google)

---

## 🚀 PARTE 1: Obtener Developer Token de Google Ads

### Paso 1.1: Acceder a Google Ads API Center

1. **Abre tu navegador** y ve a:
   ```
   https://ads.google.com/aw/apicenter
   ```

2. **Inicia sesión** con:
   - Email: `marketingdigitalper.seo@gmail.com`
   - (Tu contraseña habitual de Google)

3. **Verifica que estás en la cuenta correcta**:
   - Deberías ver: **129-046-8001 Marketing Digital PER-SEO**

### Paso 1.2: Solicitar Developer Token

1. En la página del API Center, busca la sección **"Developer Tokens"** o **"Tokens de Desarrollador"**

2. Si no tienes un token, verás un botón como:
   - **"Request Access"** o **"Solicitar Acceso"**
   - **"Create Developer Token"** o **"Crear Token de Desarrollador"**

3. **Haz clic** en ese botón

### Paso 1.3: Completar el Formulario de Solicitud

Cuando Google te pida información, usa **EXACTAMENTE** estos datos:

#### **Nombre de la Aplicación:**
```
ZEUS IA - Sistema de Automatización de Marketing con IA
```

#### **Descripción de la Aplicación:**
```
ZEUS IA es una plataforma SaaS de automatización empresarial que utiliza inteligencia artificial para gestionar campañas de marketing digital, incluyendo Google Ads. El sistema permite crear, optimizar y gestionar campañas publicitarias de forma automatizada mediante agentes de IA especializados (PERSEO - Growth Strategist).

La aplicación está diseñada para empresas que necesitan automatizar su marketing digital y gestionar múltiples campañas de forma eficiente sin conocimientos técnicos avanzados.
```

#### **Tipo de Aplicación:**
```
Aplicación Web / API Backend
```

#### **URL de la Aplicación (Producción):**
```
https://zeus-ia-production-16d8.up.railway.app
```

#### **URL de la Aplicación (Desarrollo):**
```
http://localhost:8000
```

#### **Propósito del Uso:**
```
Gestión automatizada de campañas de Google Ads para clientes empresariales mediante plataforma SaaS. La aplicación permite:

- Crear campañas publicitarias automatizadas para múltiples clientes
- Optimizar campañas existentes mediante IA (agente PERSEO)
- Generar reportes de rendimiento automáticos
- Gestionar presupuestos y pujas de forma automatizada
- Proporcionar a los clientes una interfaz sencilla para automatizar su marketing sin conocimientos técnicos
```

#### **Tipo de Organización:**
```
Agencia de Publicidad / Plataforma SaaS de Automatización de Marketing
- Gestionamos Google Ads para múltiples clientes
- Automatizamos la creación y optimización de campañas mediante IA
- Los clientes utilizan nuestra plataforma para simplificar su marketing digital
```

#### **Casos de Uso Específicos:**
```
1. Creación automática de campañas basadas en objetivos de marketing definidos por el cliente
2. Optimización de palabras clave y pujas mediante análisis de IA en tiempo real
3. Generación automática de reportes de rendimiento y ROI
4. Gestión centralizada de múltiples cuentas de Google Ads desde una única plataforma
5. Ajuste automático de presupuestos basado en rendimiento y objetivos
```

4. **Envía el formulario** y espera la aprobación

### Paso 1.4: Esperar Aprobación

- ⏳ **Tiempo estimado**: 1-5 días hábiles
- 📧 Google te enviará un email cuando el token sea aprobado
- ✅ Una vez aprobado, verás el **Developer Token** en la página del API Center

### Paso 1.5: Copiar el Developer Token

1. Una vez aprobado, ve a: `https://ads.google.com/aw/apicenter`
2. Encuentra tu token (verás algo como: `xxxx-xxxx-xxxx-xxxx`)
3. **Copia el token completo** (guárdalo en un lugar seguro, lo necesitarás después)

---

## 🔑 PARTE 2: Crear Credenciales OAuth2 en Google Cloud

### Paso 2.1: Acceder a Google Cloud Console

1. Ve a:
   ```
   https://console.cloud.google.com/
   ```

2. **Inicia sesión** con `marketingdigitalper.seo@gmail.com`

3. Si es tu primera vez, acepta los términos de servicio

### Paso 2.2: Crear o Seleccionar un Proyecto

1. En la parte superior, haz clic en el **selector de proyectos** (junto al logo de Google Cloud)

2. Opciones:
   - **Si ya tienes un proyecto**: Selecciónalo
   - **Si necesitas crear uno**:
     - Haz clic en **"NUEVO PROYECTO"** o **"NEW PROJECT"**
     - **Nombre del proyecto**: `ZEUS-IA`
     - Haz clic en **"CREAR"** o **"CREATE"**
     - Espera a que se cree (1-2 minutos)

3. **Asegúrate de que el proyecto correcto esté seleccionado**

### Paso 2.3: Habilitar la API de Google Ads

1. Ve a la **Biblioteca de APIs**:
   ```
   https://console.cloud.google.com/apis/library
   ```

2. En el buscador, escribe: **"Google Ads API"**

3. Haz clic en **"Google Ads API"** de los resultados

4. Haz clic en el botón **"HABILITAR"** o **"ENABLE"**

5. Espera a que se habilite (30 segundos - 1 minuto)

### Paso 2.4: Configurar Pantalla de Consentimiento OAuth

1. Ve a:
   ```
   https://console.cloud.google.com/apis/credentials/consent
   ```

2. Selecciona **"Externo"** (External) si no tienes Google Workspace

3. Completa el formulario:
   - **Nombre de la aplicación**: `ZEUS IA`
   - **Email de soporte**: `marketingdigitalper.seo@gmail.com`
   - **Dominio autorizado**: `zeus-ia-production-16d8.up.railway.app`
   - **Email del desarrollador**: `marketingdigitalper.seo@gmail.com`

4. En **"Ámbitos"** (Scopes), haz clic en **"AÑADIR O QUITAR ÁMBITOS"**

5. Busca y selecciona:
   - ✅ `https://www.googleapis.com/auth/adwords` (Google Ads API)

6. Haz clic en **"GUARDAR Y CONTINUAR"**

7. En **"Usuarios de prueba"** (si aparece):
   - Haz clic en **"AÑADIR USUARIOS"**
   - Añade: `marketingdigitalper.seo@gmail.com`
   - Haz clic en **"GUARDAR Y CONTINUAR"**

8. Revisa y **"VOLVER AL PANEL"**

### Paso 2.5: Crear Credenciales OAuth 2.0

1. Ve a:
   ```
   https://console.cloud.google.com/apis/credentials
   ```

2. Haz clic en **"+ CREAR CREDENCIALES"** o **"+ CREATE CREDENTIALS"**

3. Selecciona **"ID de cliente de OAuth"** o **"OAuth client ID"**

4. Si es la primera vez, selecciona **"Aplicación de escritorio"** o **"Desktop app"**

5. O si ya tienes configurada la pantalla de consentimiento, selecciona:
   - **Tipo de aplicación**: **"Aplicación web"** o **"Web application"**
   - **Nombre**: `ZEUS IA Backend`

6. En **"URIs de redirección autorizados"**, añade:
   ```
   http://localhost:8000
   https://zeus-ia-production-16d8.up.railway.app
   ```

7. Haz clic en **"CREAR"** o **"CREATE"**

8. **⚠️ IMPORTANTE**: Se abrirá un popup con:
   - **ID de cliente** (Client ID) - Copia esto
   - **Secreto de cliente** (Client Secret) - Copia esto

   **Guarda ambos valores**, los necesitarás en Railway.

### Paso 2.6: Generar Refresh Token (Opcional pero Recomendado)

Para que PERSEO pueda acceder sin re-autenticación constante:

1. **Instala la biblioteca de Google Ads** (si no la tienes):
   ```bash
   pip install google-ads
   ```

2. **Ejecuta este script** (crea un archivo `generate_refresh_token.py`):

```python
from google_auth_oauthlib.flow import InstalledAppFlow
import json

# Descarga el JSON de credenciales desde Google Cloud Console
# Guárdalo como 'credentials.json' en el mismo directorio

SCOPES = ['https://www.googleapis.com/auth/adwords']

def generate_refresh_token():
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    
    # Guarda las credenciales
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
    
    print(f"Refresh Token: {creds.refresh_token}")
    return creds.refresh_token

if __name__ == '__main__':
    refresh_token = generate_refresh_token()
    print(f"\n✅ Refresh Token generado: {refresh_token}")
    print("\n⚠️ Añade este valor a Railway como: GOOGLE_ADS_REFRESH_TOKEN")
```

3. **Ejecuta el script**:
   ```bash
   python generate_refresh_token.py
   ```

4. Se abrirá un navegador, inicia sesión con `marketingdigitalper.seo@gmail.com`

5. **Copia el Refresh Token** que se muestra en la consola

---

## 🚂 PARTE 3: Configurar en Railway

### Paso 3.1: Acceder a Railway

1. Ve a: https://railway.app
2. Inicia sesión
3. Selecciona tu proyecto **ZEUS-IA**
4. Selecciona el servicio **backend**

### Paso 3.2: Añadir Variables de Entorno

1. Ve a la pestaña **"Variables"** o **"Variables"**

2. Haz clic en **"+ New Variable"** o **"+ Nueva Variable"**

3. **Añade las siguientes variables** (una por una):

#### Variable 1: Developer Token
```
Nombre: GOOGLE_ADS_DEVELOPER_TOKEN
Valor: [Pega el Developer Token que copiaste del Paso 1.5]
```

#### Variable 2: Client ID
```
Nombre: GOOGLE_ADS_CLIENT_ID
Valor: [Pega el Client ID del Paso 2.5]
```

#### Variable 3: Client Secret
```
Nombre: GOOGLE_ADS_CLIENT_SECRET
Valor: [Pega el Client Secret del Paso 2.5]
```

#### Variable 4: Customer ID
```
Nombre: GOOGLE_ADS_CUSTOMER_ID
Valor: 129-046-8001
```

#### Variable 5: Refresh Token (Opcional pero recomendado)
```
Nombre: GOOGLE_ADS_REFRESH_TOKEN
Valor: [Pega el Refresh Token del Paso 2.6 si lo generaste]
```

#### Variable 6: Modo (Para desarrollo)
```
Nombre: GOOGLE_ADS_MODE
Valor: PRODUCTION
```
(Puedes usar `SANDBOX` para pruebas, pero cambia a `PRODUCTION` cuando esté listo)

4. **Guarda cada variable** haciendo clic en **"Add"** o **"Añadir"**

5. Railway **reiniciará automáticamente** el servicio backend

---

## ✅ PARTE 4: Verificar que Funciona

### Paso 4.1: Verificar en el Sistema

1. Espera 2-3 minutos a que Railway reinicie

2. Ve a tu panel de admin:
   ```
   https://zeus-ia-production-16d8.up.railway.app/admin
   ```

3. O verifica directamente el endpoint:
   ```
   https://zeus-ia-production-16d8.up.railway.app/api/v1/system/pending-authorizations
   ```

4. **Deberías ver** que `GOOGLE_ADS_DEVELOPER_TOKEN` ya **NO** aparece en la lista de pendientes

### Paso 4.2: Verificar Estado de Marketing

1. Haz una petición a:
   ```
   GET https://zeus-ia-production-16d8.up.railway.app/api/v1/marketing/status
   ```

2. **Respuesta esperada**:
   ```json
   {
     "google_ads": {
       "configured": true,
       "status": "active"
     }
   }
   ```

### Paso 4.3: Probar Creación de Campaña (Opcional)

Si quieres probar que PERSEO puede crear campañas:

1. Usa el endpoint:
   ```
   POST https://zeus-ia-production-16d8.up.railway.app/api/v1/marketing/google-ads/campaign
   ```

2. Con un token JWT válido y un cuerpo como:
   ```json
   {
     "name": "Campaña de Prueba ZEUS",
     "budget_amount": 10,
     "target_locations": ["España"],
     "keywords": ["marketing digital"],
     "ad_text": {
       "headline": "Prueba ZEUS IA",
       "description": "Campaña generada automáticamente"
     }
   }
   ```

---

## ⚠️ Problemas Comunes y Soluciones

### Problema 1: "Token pendiente de aprobación"
**Solución**: Espera 1-5 días. Google revisa manualmente las solicitudes de Developer Token.

### Problema 2: "Credenciales OAuth inválidas"
**Solución**: Verifica que:
- El Client ID y Client Secret sean correctos
- La API de Google Ads esté habilitada
- Los URIs de redirección incluyan tu dominio de producción

### Problema 3: "Cuenta no verificada"
**Solución**: Completa la verificación del anunciante en Google Ads antes de usar la API.

### Problema 4: "Refresh Token expirado"
**Solución**: Regenera el Refresh Token usando el script del Paso 2.6.

---

## 📝 Checklist Final

Antes de considerar la configuración completa, verifica:

- [ ] Developer Token solicitado en Google Ads API Center
- [ ] Developer Token aprobado por Google
- [ ] Proyecto creado en Google Cloud Console
- [ ] API de Google Ads habilitada en el proyecto
- [ ] Pantalla de consentimiento OAuth configurada
- [ ] Credenciales OAuth 2.0 creadas (Client ID y Secret)
- [ ] Refresh Token generado (opcional pero recomendado)
- [ ] Todas las variables añadidas en Railway
- [ ] Backend reiniciado en Railway
- [ ] `/api/v1/system/pending-authorizations` ya NO muestra `GOOGLE_ADS_DEVELOPER_TOKEN`
- [ ] `/api/v1/marketing/status` muestra `google_ads: configured: true`

---

## 🎯 Resumen

1. ✅ **Obtener Developer Token** desde Google Ads API Center
2. ✅ **Crear credenciales OAuth2** en Google Cloud Console
3. ✅ **Configurar variables** en Railway
4. ✅ **Verificar** que todo funciona

**Tiempo estimado total**: 30-45 minutos (más tiempo de espera para aprobación del Developer Token)

---

**¿Necesitas ayuda?** Revisa los logs de Railway o los endpoints de estado del sistema para más información de depuración.

**Última actualización**: 2025-01-13
**Mantenido por**: ZEUS IA DevOps Team

