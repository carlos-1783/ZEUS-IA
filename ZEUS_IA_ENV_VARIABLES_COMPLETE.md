# 🔐 ZEUS-IA - Variables de Entorno Completas
## Listado completo de todas las variables del ecosistema ZEUS-IA

**Última actualización:** 2024
**Modo:** Read-only (solo listado, no modifica existentes)

---

## 📋 Índice de Módulos

1. [ZEUS_CORE](#zeus_core)
2. [PERSEO](#perseo)
3. [RAFAEL](#rafael)
4. [JUSTICIA](#justicia)
5. [THALOS](#thalos)
6. [AFRODITA](#afrodita)
7. [FIREWALL_LEGAL_FISCAL](#firewall_legal_fiscal)
8. [TPV_UNIVERSAL](#tpv_universal)
9. [CORE_APPLICATION](#core_application)
10. [DATABASE](#database)
11. [SECURITY_JWT](#security_jwt)
12. [CORS_NETWORK](#cors_network)
13. [OPENAI_AI](#openai_ai)
14. [STRIPE_PAYMENTS](#stripe_payments)
15. [EMAIL_SENDGRID](#email_sendgrid)
16. [WHATSAPP_TWILIO](#whatsapp_twilio)
17. [MARKETING_GOOGLE](#marketing_google)
18. [MARKETING_META](#marketing_meta)
19. [MARKETING_LINKEDIN](#marketing_linkedin)
20. [MARKETING_TIKTOK](#marketing_tiktok)
21. [AEAT_HACIENDA](#aeat_hacienda)
22. [GOOGLE_WORKSPACE](#google_workspace)
23. [LOGGING_AUDIT](#logging_audit)
24. [FRONTEND_VITE](#frontend_vite)
25. [INFRASTRUCTURE](#infrastructure)

---

## ZEUS_CORE

Variables para el orquestador principal del sistema.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `ZEUS_AGENT_ENABLED` | Habilitar agente ZEUS CORE | boolean | No | `"true"` |
| `TEAMFLOW_ENGINE` | Habilitar motor TeamFlow | boolean | No | `"true"` |
| `AGENT_ORCHESTRATION` | Habilitar orquestación multiagente | boolean | No | `"true"` |
| `CONTEXT_SHARED_MEMORY` | Habilitar memoria compartida entre agentes | boolean | No | `"true"` |
| `AUTO_ROUTER` | Habilitar enrutamiento automático de solicitudes | boolean | No | `"true"` |
| `FAILSAFE_MODE` | Modo de seguridad fallback | boolean | No | `"true"` |
| `GLOBAL_LOGS_PATH` | Ruta global para logs del sistema | string | No | `"backend/logs"` |
| `ZEUS_ADDITIONAL_CORS_ORIGINS` | Orígenes CORS adicionales (separados por coma) | string | No | `""` |

---

## PERSEO

Variables para el agente de Marketing y SEO.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `PERSEO_AGENT_ENABLED` | Habilitar agente PERSEO | boolean | No | `"true"` |
| `PERSEO_IMAGES_ENABLED` | Habilitar procesamiento de imágenes | boolean | No | `"true"` |
| `PERSEO_IMAGE_UPLOAD_DIR` | Directorio para subida de imágenes | string | No | `"static/uploads/perseo"` |
| `PERSEO_IMAGE_MAX_BYTES` | Tamaño máximo de imagen en bytes | integer | No | `5242880` (5MB) |
| `PERSEO_IMAGE_ENGINE` | Motor de procesamiento de imágenes | string | No | `"pillow"` |
| `PERSEO_VIDEO_ENGINE` | Motor de procesamiento de videos | string | No | `"ffmpeg"` |
| `PERSEO_SEO_ENGINE` | Motor de análisis SEO | string | No | `"custom"` |
| `PERSEO_ADS_ENGINE` | Motor de gestión de anuncios | string | No | `"google_ads"` |
| `PERSEO_MEDIA_TEMP_PATH` | Ruta temporal para archivos multimedia | string | No | `"storage/temp/perseo"` |
| `VITE_PERSEO_IMAGES_ENABLED` | Habilitar imágenes PERSEO en frontend | boolean | No | `"true"` |

---

## RAFAEL

Variables para el agente Fiscal y Contable.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `RAFAEL_AGENT_ENABLED` | Habilitar agente RAFAEL | boolean | No | `"true"` |
| `RAFAEL_QR_ENABLED` | Habilitar lectura de códigos QR | boolean | No | `"true"` |
| `RAFAEL_NFC_ENABLED` | Habilitar lectura de etiquetas NFC | boolean | No | `"true"` |
| `RAFAEL_DNIE_OCR_ENABLED` | Habilitar OCR para DNIe | boolean | No | `"true"` |
| `RAFAEL_SUPERUSER_MODE` | Modo superusuario para operaciones avanzadas | boolean | No | `"false"` |
| `RAFAEL_PRELAUNCH_MODE` | Modo pre-lanzamiento para datos incompletos | boolean | No | `"false"` |
| `RAFAEL_FISCAL_MODEL_PATH` | Ruta para modelos fiscales (303, 390, etc.) | string | No | `"storage/fiscal/models"` |
| `RAFAEL_INCOME_LEDGER_PATH` | Ruta para libro de ingresos | string | No | `"storage/fiscal/income"` |
| `RAFAEL_EXPENSE_LEDGER_PATH` | Ruta para libro de gastos | string | No | `"storage/fiscal/expenses"` |
| `RAFAEL_BANK_MATCH_ENABLED` | Habilitar conciliación bancaria automática | boolean | No | `"true"` |
| `BANK_WEBHOOK_PAYMENTS` | URL webhook para recibir pagos bancarios | string | No | `""` |
| `BANK_WEBHOOK_SECRET` | Secreto para validar webhooks bancarios | string | No | `""` |
| `BANK_MATCH_TOLERANCE` | Tolerancia en euros para matching bancario | float | No | `0.01` |

---

## JUSTICIA

Variables para el agente Legal y GDPR.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `JUSTICIA_AGENT_ENABLED` | Habilitar agente JUSTICIA | boolean | No | `"true"` |
| `LEGAL_PDF_SIGNER` | Habilitar firma digital de PDFs | boolean | No | `"true"` |
| `LEGAL_CONTRACT_GENERATOR` | Habilitar generador de contratos | boolean | No | `"true"` |
| `GDPR_AUDIT_ENGINE` | Habilitar motor de auditoría GDPR | boolean | No | `"true"` |
| `LEGAL_FIREWALL_ENABLED` | Habilitar firewall legal (ver sección dedicada) | boolean | No | `"true"` |
| `ABOGADO_EMAIL` | Email del asesor legal (deprecated, usar FIREWALL) | string | No | `""` |
| `FIREWALL_LOGS_ENABLED` | Habilitar logs del firewall legal | boolean | No | `"true"` |

---

## THALOS

Variables para el agente de Seguridad Cibernética.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `THALOS_AGENT_ENABLED` | Habilitar agente THALOS | boolean | No | `"true"` |
| `THALOS_ENABLED` | Habilitar sistema THALOS | boolean | No | `"true"` |
| `THALOS_THREAT_DETECTOR` | Habilitar detector de amenazas | boolean | No | `"true"` |
| `THALOS_LOG_MONITOR` | Habilitar monitor de logs | boolean | No | `"true"` |
| `THALOS_THREAT_THRESHOLD` | Umbral de amenaza (0.0-1.0) | float | No | `0.90` |
| `THALOS_AUTO_ISOLATION` | Habilitar aislamiento automático | boolean | No | `"true"` |
| `THALOS_LOG_LEVEL` | Nivel de logging | string | No | `"INFO"` |
| `THALOS_LOG_RETENTION_DAYS` | Días de retención de logs | integer | No | `30` |
| `THALOS_ALERT_WEBHOOK` | Webhook para alertas de seguridad | string | No | `""` |
| `CREDENTIAL_REVOCATION` | Habilitar revocación automática de credenciales | boolean | No | `"true"` |
| `API_GATEWAY_PROTECTION` | Habilitar protección del API Gateway | boolean | No | `"true"` |
| `ENDPOINT_ISOLATION` | Habilitar aislamiento de endpoints | boolean | No | `"true"` |

---

## AFRODITA

Variables para el agente de RRHH y Logística.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `AFRODITA_RH_AGENT_ENABLED` | Habilitar agente AFRODITA | boolean | No | `"true"` |
| `RRHH_CHECK_IN_FACE` | Habilitar fichaje por reconocimiento facial | boolean | No | `"true"` |
| `RRHH_CHECK_IN_QR` | Habilitar fichaje por código QR | boolean | No | `"true"` |
| `RRHH_EMPLOYEE_MANAGER` | Habilitar gestor de empleados | boolean | No | `"true"` |
| `RRHH_CONTRACT_CREATOR` | Habilitar creador de contratos RRHH | boolean | No | `"true"` |
| `RRHH_SCHEDULE_ENGINE` | Habilitar motor de gestión de horarios | boolean | No | `"true"` |

---

## FIREWALL_LEGAL_FISCAL

Variables para el Firewall Legal-Fiscal (protección RAFAEL y JUSTICIA).

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `FIREWALL_LEGAL_ENABLED` | Habilitar firewall legal-fiscal | boolean | No | `"true"` |
| `FIREWALL_REQUIRE_APPROVAL` | Requerir aprobación del cliente siempre | boolean | No | `"true"` |
| `GESTOR_FISCAL_EMAIL` | Email del gestor fiscal (onboarding) | string | **Sí** | `""` |
| `ABOGADO_EMAIL` | Email del abogado (onboarding) | string | **Sí** | `""` |
| `FIREWALL_LOGS_ENABLED` | Habilitar logs de auditoría del firewall | boolean | No | `"true"` |
| `SEND_TO_TAX_ADVISOR` | Habilitar envío automático a asesor fiscal | boolean | No | `"true"` |
| `SEND_TO_LEGAL_ADVISOR` | Habilitar envío automático a asesor legal | boolean | No | `"true"` |
| `FIREWALL_AUDIT_RETENTION_DAYS` | Días de retención de logs de auditoría | integer | No | `365` |

**Nota:** `GESTOR_FISCAL_EMAIL` y `ABOGADO_EMAIL` se configuran durante el onboarding del usuario. Si no están configurados, el sistema marca las tareas como pendientes.

---

## TPV_UNIVERSAL

Variables para el módulo TPV Universal Enterprise.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `TPV_ENABLED` | Habilitar módulo TPV | boolean | No | `"true"` |
| `TPV_SUPPORTED_METHODS` | Métodos de pago soportados (separados por coma) | string | No | `"efectivo,tarjeta,bizum,transferencia"` |
| `TPV_DEFAULT_BUSINESS_TYPE` | Tipo de negocio por defecto | string | No | `"otros"` |
| `TPV_PRODUCT_STORAGE_PATH` | Ruta para almacenar productos | string | No | `"storage/tpv/products"` |
| `TPV_SALES_STORAGE_PATH` | Ruta para almacenar ventas | string | No | `"storage/tpv/sales"` |
| `TPV_INVOICE_FULL_ENABLED` | Habilitar factura completa (vs ticket) | boolean | No | `"true"` |
| `TPV_CLOSURE_SCHEDULE_CRON` | Cron para cierre automático de caja | string | No | `"0 2 * * *"` (2 AM diario) |
| `TPV_CLOSURE_ARCHIVE_PATH` | Ruta para archivar cierres de caja | string | No | `"storage/tpv/closures"` |
| `TPV_AUDIT_LOGS_ENABLED` | Habilitar logs de auditoría TPV | boolean | No | `"true"` |
| `TPV_NOTIFY_ON_MISMATCH` | Notificar en caso de desajuste de caja | boolean | No | `"true"` |
| `TPV_REQUIRE_HUMAN_GATEKEEPER_ON_HIGH_RISK` | Requerir aprobación humana en operaciones de alto riesgo | boolean | No | `"true"` |
| `TPV_PRINTER_SUPPORT` | Habilitar soporte de impresoras | boolean | No | `"true"` |
| `TPV_TABLES_ENABLED` | Habilitar gestión de mesas (restaurantes) | boolean | No | `"false"` |
| `TPV_WAITER_ACCOUNTS` | Habilitar cuentas de camarero | boolean | No | `"false"` |
| `TPV_MULTI_SEDE_ENABLED` | Habilitar múltiples sedes | boolean | No | `"false"` |

---

## CORE_APPLICATION

Variables básicas de la aplicación.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `PROJECT_NAME` | Nombre del proyecto | string | No | `"ZEUS-IA"` |
| `VERSION` | Versión de la aplicación | string | No | `"1.0.6"` |
| `ENVIRONMENT` | Entorno (development/staging/production) | string | No | `"production"` |
| `RAILWAY_ENVIRONMENT` | Entorno Railway (si aplica) | string | No | `""` |
| `APP_ENV` | Entorno de aplicación | string | No | `"production"` |
| `DEBUG` | Modo debug | boolean | No | `"false"` |
| `HOST` | Host del servidor | string | No | `"0.0.0.0"` |
| `PORT` | Puerto del servidor | integer | No | `8000` |
| `TZ` | Zona horaria | string | No | `"UTC"` |
| `API_V1_STR` | Prefijo de API v1 | string | No | `"/api/v1"` |

---

## DATABASE

Variables de configuración de base de datos.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `DATABASE_URL` | URL de conexión a la base de datos | string | **Sí** | `""` |
| `DATABASE_PUBLIC_URL` | URL pública de la base de datos (Railway) | string | No | `""` |

---

## SECURITY_JWT

Variables de seguridad y autenticación JWT.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `SECRET_KEY` | Clave secreta para JWT (64+ caracteres) | string | **Sí** | `""` |
| `ALGORITHM` | Algoritmo JWT | string | No | `"HS256"` |
| `JWT_ALGORITHM` | Algoritmo JWT (alias) | string | No | `"HS256"` |
| `JWT_SECRET_KEY` | Clave secreta JWT (alias) | string | No | `""` |
| `JWT_ISSUER` | Emisor del token JWT | string | No | `"zeus-ia-backend"` |
| `JWT_AUDIENCE` | Audiencia del token JWT (separado por coma) | string | No | `"zeus-ia:auth,zeus-ia:access,zeus-ia:websocket"` |
| `JWT_ACCESS_TOKEN_TYPE` | Tipo de token de acceso | string | No | `"access"` |
| `JWT_WEBSOCKET_TOKEN_TYPE` | Tipo de token WebSocket | string | No | `"websocket"` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Minutos de expiración del token de acceso | integer | No | `30` |
| `REFRESH_TOKEN_SECRET` | Secreto para tokens de refresco | string | **Sí** | `""` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Días de expiración del token de refresco | integer | No | `7` |

---

## CORS_NETWORK

Variables de configuración CORS y red.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `ALLOWED_ORIGINS` | Orígenes permitidos (separados por coma) | string | No | `"http://localhost:5173,http://localhost:3000"` |
| `BACKEND_CORS_ORIGINS` | Orígenes CORS del backend (separados por coma) | string | No | `"http://localhost:5173,http://localhost:8000"` |
| `BACKEND_BASE_URL` | URL base del backend | string | No | `"https://zeus-ia-production-16d8.up.railway.app"` |
| `PUBLIC_APP_URL` | URL pública de la aplicación | string | No | `"https://zeus-ia-production-16d8.up.railway.app"` |
| `WEBSOCKET_PUBLIC_URL` | URL pública del WebSocket | string | No | `"wss://zeus-ia-production-16d8.up.railway.app/ws"` |

---

## OPENAI_AI

Variables para la integración con OpenAI.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `OPENAI_API_KEY` | Clave API de OpenAI | string | **Sí** | `""` |
| `OPENAI_MODEL` | Modelo de OpenAI a usar | string | No | `"gpt-4"` |
| `OPENAI_MAX_TOKENS` | Máximo de tokens por solicitud | integer | No | `2000` |
| `OPENAI_TEMPERATURE` | Temperatura del modelo (0.0-1.0) | float | No | `0.7` |
| `MAX_OPENAI_COST_PER_DAY` | Costo máximo diario de OpenAI (USD) | float | No | `50.0` |

---

## STRIPE_PAYMENTS

Variables para integración con Stripe.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `STRIPE_API_KEY` | Clave API de Stripe (secret key) | string | **Sí** | `""` |
| `STRIPE_SECRET_KEY` | Clave secreta de Stripe (alias) | string | No | `""` |
| `STRIPE_PUBLISHABLE_KEY` | Clave pública de Stripe | string | No | `""` |
| `STRIPE_WEBHOOK_SECRET` | Secreto para validar webhooks de Stripe | string | No | `""` |
| `STRIPE_CURRENCY` | Moneda por defecto | string | No | `"eur"` |
| `STRIPE_MODE` | Modo de Stripe (test/live/auto) | string | No | `"live"` |

### Stripe - Productos y Precios (Planes STARTUP/GROWTH/BUSINESS/ENTERPRISE)

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `ZEUS_STARTUP_PRODUCT_ID` | ID del producto STARTUP | string | No | `""` |
| `ZEUS_STARTUP_SETUP_PRICE_ID` | ID del precio de setup STARTUP | string | No | `""` |
| `ZEUS_STARTUP_MONTHLY_PRICE_ID` | ID del precio mensual STARTUP | string | No | `""` |
| `ZEUS_GROWTH_PRODUCT_ID` | ID del producto GROWTH | string | No | `""` |
| `ZEUS_GROWTH_SETUP_PRICE_ID` | ID del precio de setup GROWTH | string | No | `""` |
| `ZEUS_GROWTH_MONTHLY_PRICE_ID` | ID del precio mensual GROWTH | string | No | `""` |
| `ZEUS_BUSINESS_PRODUCT_ID` | ID del producto BUSINESS | string | No | `""` |
| `ZEUS_BUSINESS_SETUP_PRICE_ID` | ID del precio de setup BUSINESS | string | No | `""` |
| `ZEUS_BUSINESS_MONTHLY_PRICE_ID` | ID del precio mensual BUSINESS | string | No | `""` |
| `ZEUS_ENTERPRISE_PRODUCT_ID` | ID del producto ENTERPRISE | string | No | `""` |
| `ZEUS_ENTERPRISE_SETUP_PRICE_ID` | ID del precio de setup ENTERPRISE | string | No | `""` |
| `ZEUS_ENTERPRISE_MONTHLY_PRICE_ID` | ID del precio mensual ENTERPRISE | string | No | `""` |

---

## EMAIL_SENDGRID

Variables para integración con SendGrid (email).

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `SENDGRID_API_KEY` | Clave API de SendGrid | string | **Sí** | `""` |
| `SENDGRID_FROM_EMAIL` | Email remitente por defecto | string | No | `"noreply@zeus-ia.com"` |
| `SENDGRID_FROM_NAME` | Nombre remitente por defecto | string | No | `"ZEUS-IA"` |

---

## WHATSAPP_TWILIO

Variables para integración con Twilio (WhatsApp).

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `TWILIO_ACCOUNT_SID` | SID de cuenta de Twilio | string | **Sí** | `""` |
| `TWILIO_AUTH_TOKEN` | Token de autenticación de Twilio | string | **Sí** | `""` |
| `TWILIO_API_KEY` | Clave API de Twilio | string | No | `""` |
| `TWILIO_WHATSAPP_NUMBER` | Número de WhatsApp de Twilio | string | No | `"whatsapp:+14155238886"` |

---

## MARKETING_GOOGLE

Variables para integración con Google Ads y Analytics.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Token de desarrollador de Google Ads | string | No | `""` |
| `GOOGLE_ADS_CLIENT_ID` | ID de cliente de Google Ads | string | No | `""` |
| `GOOGLE_ADS_CLIENT_SECRET` | Secreto de cliente de Google Ads | string | No | `""` |
| `GOOGLE_ADS_REFRESH_TOKEN` | Token de refresco de Google Ads | string | No | `""` |
| `GOOGLE_ADS_ACCESS_TOKEN` | Token de acceso de Google Ads | string | No | `""` |
| `GOOGLE_ADS_CUSTOMER_ID` | ID de cliente de Google Ads | string | No | `""` |
| `GOOGLE_ADS_MODE` | Modo de Google Ads (SANDBOX/PRODUCTION) | string | No | `"SANDBOX"` |
| `GA_PROPERTY_ID` | ID de propiedad de Google Analytics | string | No | `""` |
| `GA_CREDENTIALS` | Credenciales de Google Analytics (JSON) | string | No | `""` |

---

## MARKETING_META

Variables para integración con Meta/Facebook Ads.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `FACEBOOK_ACCESS_TOKEN` | Token de acceso de Facebook | string | No | `""` |
| `FACEBOOK_APP_ID` | ID de aplicación de Facebook | string | No | `""` |
| `FACEBOOK_APP_SECRET` | Secreto de aplicación de Facebook | string | No | `""` |
| `FACEBOOK_AD_ACCOUNT_ID` | ID de cuenta de anuncios de Facebook | string | No | `""` |
| `META_ACCESS_TOKEN` | Token de acceso de Meta (alias) | string | No | `""` |
| `META_APP_ID` | ID de aplicación de Meta (alias) | string | No | `""` |
| `META_APP_SECRET` | Secreto de aplicación de Meta (alias) | string | No | `""` |
| `META_AD_ACCOUNT_ID` | ID de cuenta de anuncios de Meta (alias) | string | No | `""` |

---

## MARKETING_LINKEDIN

Variables para integración con LinkedIn.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `LINKEDIN_CLIENT_ID` | ID de cliente de LinkedIn | string | No | `"77uirs6c1jyvhe"` |
| `LINKEDIN_CLIENT_SECRET` | Secreto de cliente de LinkedIn | string | No | `""` |
| `LINKEDIN_ACCESS_TOKEN` | Token de acceso de LinkedIn | string | No | `""` |

---

## MARKETING_TIKTOK

Variables para integración con TikTok.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `TIKTOK_ENABLED` | Habilitar integración con TikTok | boolean | No | `"true"` |
| `TIKTOK_APP_ID` | ID de aplicación de TikTok | string | No | `"aw6uqljw50xrjbls"` |
| `TIKTOK_APP_SECRET` | Secreto de aplicación de TikTok | string | No | `""` |
| `TIKTOK_ACCESS_TOKEN` | Token de acceso de TikTok | string | No | `""` |

---

## AEAT_HACIENDA

Variables para integración con AEAT/Hacienda española.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `AEAT_ENVIRONMENT` | Entorno de AEAT (test/production) | string | No | `"test"` |
| `AEAT_NIF` | NIF para autenticación en AEAT | string | No | `""` |
| `AEAT_PASSWORD` | Contraseña para autenticación en AEAT | string | No | `""` |

---

## GOOGLE_WORKSPACE

Variables para integración con Google Workspace.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `GOOGLE_CLIENT_ID` | ID de cliente de Google OAuth | string | No | `""` |
| `GOOGLE_CLIENT_SECRET` | Secreto de cliente de Google OAuth | string | No | `""` |
| `GOOGLE_CREDENTIALS_JSON` | Credenciales JSON de Google (genérico) | string | No | `""` |
| `GOOGLE_CALENDAR_CREDENTIALS` | Credenciales de Google Calendar | string | No | `""` |
| `GOOGLE_GMAIL_CREDENTIALS` | Credenciales de Gmail | string | No | `""` |
| `GOOGLE_DRIVE_CREDENTIALS` | Credenciales de Google Drive | string | No | `""` |
| `GOOGLE_SHEETS_CREDENTIALS` | Credenciales de Google Sheets | string | No | `""` |

---

## LOGGING_AUDIT

Variables para logging y auditoría.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `LOG_LEVEL` | Nivel de logging (DEBUG/INFO/WARNING/ERROR) | string | No | `"INFO"` |
| `LOG_FORMAT` | Formato de logs (json/text) | string | No | `"json"` |
| `AUDIT_LOGS_ENABLED` | Habilitar logs de auditoría | boolean | No | `"true"` |
| `HITL_ENABLED` | Habilitar Human-In-The-Loop | boolean | No | `"true"` |
| `ROLLBACK_ENABLED` | Habilitar rollback de operaciones | boolean | No | `"true"` |
| `SHADOW_MODE` | Modo shadow (solo logs, sin ejecución) | boolean | No | `"false"` |
| `AGENT_AUTOMATION_ENABLED` | Habilitar automatización de agentes | boolean | No | `"true"` |
| `AGENT_AUTOMATION_INTERVAL` | Intervalo de automatización en segundos | integer | No | `600` |
| `AGENT_AUTOMATION_LOG_DIR` | Directorio de logs de automatización | string | No | `"backend/logs/automation"` |
| `AGENT_BACKUP_DIR` | Directorio de backups de agentes | string | No | `"storage/backups"` |
| `AGENT_OUTPUT_DIR` | Directorio de salida de agentes | string | No | `"storage/outputs"` |
| `MAX_REQUESTS_PER_MINUTE` | Máximo de solicitudes por minuto | integer | No | `100` |

---

## FRONTEND_VITE

Variables para el frontend (Vite).

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `VITE_APP_NAME` | Nombre de la aplicación | string | No | `"ZEUS-IA"` |
| `VITE_APP_VERSION` | Versión de la aplicación | string | No | `"1.0.6"` |
| `VITE_APP_ENV` | Entorno de la aplicación | string | No | `"production"` |
| `VITE_APP_URL` | URL de la aplicación frontend | string | No | `"https://zeus-ia-frontend-production.up.railway.app"` |
| `VITE_API_URL` | URL de la API | string | No | `"https://zeus-ia-production-16d8.up.railway.app/api/v1"` |
| `VITE_API_BASE_URL` | URL base de la API (alias) | string | No | `"https://zeus-ia-production-16d8.up.railway.app/api/v1"` |
| `VITE_WS_URL` | URL del WebSocket | string | No | `"wss://zeus-ia-production-16d8.up.railway.app/ws"` |
| `VITE_ENABLE_ANALYTICS` | Habilitar analytics | boolean | No | `"true"` |
| `VITE_ENABLE_SENTRY` | Habilitar Sentry (error tracking) | boolean | No | `"false"` |
| `VITE_SUPPORTED_LANGUAGES` | Idiomas soportados (separados por coma) | string | No | `"es,en"` |
| `VITE_DEFAULT_LANGUAGE` | Idioma por defecto | string | No | `"es"` |
| `VITE_PERSEO_IMAGES_ENABLED` | Habilitar imágenes PERSEO en frontend | boolean | No | `"true"` |

---

## INFRASTRUCTURE

Variables de infraestructura y servicios opcionales.

| Variable | Descripción | Tipo | Requerido | Valor por Defecto |
|----------|-------------|------|-----------|-------------------|
| `REDIS_URL` | URL de conexión a Redis (opcional) | string | No | `""` |
| `SENTRY_DSN` | DSN de Sentry para error tracking | string | No | `""` |
| `SLACK_WEBHOOK_URL` | URL de webhook de Slack para notificaciones | string | No | `""` |
| `ADMIN_EMAIL` | Email del administrador | string | No | `"admin@zeus-ia.com"` |
| `FIRST_SUPERUSER_EMAIL` | Email del primer superusuario | string | No | `"admin@zeus-ia.com"` |
| `FIRST_SUPERUSER_PASSWORD` | Contraseña del primer superusuario | string | No | `""` |
| `IMAGE_STORAGE` | Tipo de almacenamiento de imágenes (local/s3) | string | No | `"local"` |
| `NIXPACKS_PYTHON_VERSION` | Versión de Python para Nixpacks | string | No | `"3.11"` |
| `PIP_DISABLE_PIP_VERSION_CHECK` | Deshabilitar verificación de versión de pip | string | No | `"1"` |
| `PYTHONUNBUFFERED` | Deshabilitar buffer de Python | string | No | `"1"` |

---

## 📝 Notas Importantes

### Variables Requeridas (Críticas)

Las siguientes variables **DEBEN** estar configuradas en producción:

1. `DATABASE_URL` - Sin esto, la aplicación no puede conectarse a la base de datos
2. `SECRET_KEY` - Sin esto, JWT no funcionará
3. `REFRESH_TOKEN_SECRET` - Sin esto, los tokens de refresco no funcionarán
4. `OPENAI_API_KEY` - Sin esto, los agentes IA no funcionarán
5. `STRIPE_API_KEY` - Si se usa Stripe para pagos
6. `SENDGRID_API_KEY` - Si se envían emails
7. `TWILIO_ACCOUNT_SID` y `TWILIO_AUTH_TOKEN` - Si se usa WhatsApp

### Variables Nuevas Añadidas

Las siguientes variables son **nuevas** y no existían en el sistema original:

#### RAFAEL:
- `RAFAEL_QR_ENABLED`
- `RAFAEL_NFC_ENABLED`
- `RAFAEL_DNIE_OCR_ENABLED`
- `RAFAEL_BANK_MATCH_ENABLED`
- `BANK_WEBHOOK_PAYMENTS`
- `BANK_WEBHOOK_SECRET`
- `BANK_MATCH_TOLERANCE`

#### FIREWALL_LEGAL_FISCAL:
- `FIREWALL_LEGAL_ENABLED`
- `FIREWALL_REQUIRE_APPROVAL`
- `GESTOR_FISCAL_EMAIL`
- `SEND_TO_TAX_ADVISOR`
- `SEND_TO_LEGAL_ADVISOR`
- `FIREWALL_AUDIT_RETENTION_DAYS`

#### TPV_UNIVERSAL:
- `TPV_ENABLED`
- `TPV_SUPPORTED_METHODS`
- `TPV_DEFAULT_BUSINESS_TYPE`
- `TPV_PRODUCT_STORAGE_PATH`
- `TPV_SALES_STORAGE_PATH`
- `TPV_INVOICE_FULL_ENABLED`
- `TPV_CLOSURE_SCHEDULE_CRON`
- `TPV_CLOSURE_ARCHIVE_PATH`
- `TPV_AUDIT_LOGS_ENABLED`
- `TPV_NOTIFY_ON_MISMATCH`
- `TPV_REQUIRE_HUMAN_GATEKEEPER_ON_HIGH_RISK`
- `TPV_PRINTER_SUPPORT`
- `TPV_TABLES_ENABLED`
- `TPV_WAITER_ACCOUNTS`
- `TPV_MULTI_SEDE_ENABLED`

### Formato para Railway Raw Editor

Para usar estas variables en Railway Raw Editor, usa el formato:

```
VARIABLE_NAME="value"
```

Sin espacios alrededor del `=` y con comillas alrededor del valor si contiene caracteres especiales.

---

## 🔄 Actualizaciones Futuras

Este documento se actualizará cuando se añadan nuevos módulos o variables al sistema ZEUS-IA.

**Versión del documento:** 1.0.0
**Última revisión:** 2024

