@echo off
REM ========================================
REM ZEUS-IA - Configuración Comercial
REM ========================================

echo.
echo ========================================
echo ZEUS-IA - Configuración para Venta
echo ========================================
echo.

echo [1] Configurando variables comerciales...
echo.
echo Variables a configurar en Railway:
echo.
echo === PAGOS (STRIPE) ===
echo STRIPE_PUBLIC_KEY=pk_live_tu_clave_publica
echo STRIPE_SECRET_KEY=sk_live_tu_clave_secreta
echo STRIPE_WEBHOOK_SECRET=whsec_tu_webhook_secret
echo.
echo === EMAIL MARKETING ===
echo SMTP_HOST=smtp.gmail.com
echo SMTP_PORT=587
echo SMTP_USER=tu-email@gmail.com
echo SMTP_PASSWORD=tu-app-password
echo EMAILS_FROM_EMAIL=noreply@zeus-ia.com
echo EMAILS_FROM_NAME=ZEUS-IA
echo.
echo === ANALYTICS ===
echo ENABLE_ANALYTICS=true
echo GOOGLE_ANALYTICS_ID=GA-XXXXXXXXX
echo.
echo === BRANDING ===
echo VITE_APP_NAME=Tu Empresa
echo VITE_COMPANY_LOGO=tu-logo.png
echo VITE_COMPANY_COLOR=#your-color
echo.

echo [2] Configurando dominio personalizado...
echo.
echo En Railway Dashboard:
echo 1. Settings → Domains
echo 2. Add Custom Domain
echo 3. Configurar DNS en tu proveedor
echo.

echo [3] Configurando SSL y seguridad...
echo.
echo Railway ya tiene SSL automático
echo Configurar CORS para tu dominio:
echo BACKEND_CORS_ORIGINS=https://tu-dominio.com,https://zeus-ia-production.up.railway.app
echo.

echo [4] Configurando monitoreo...
echo.
echo Opciones de monitoreo:
echo - Railway Metrics (incluido)
echo - Sentry (errores)
echo - Google Analytics (tráfico)
echo - Uptime Robot (disponibilidad)
echo.

echo ========================================
echo Configuración comercial completada
echo ========================================
echo.
echo Próximos pasos:
echo 1. Configurar variables en Railway
echo 2. Configurar dominio personalizado
echo 3. Configurar pagos (Stripe)
echo 4. Configurar email marketing
echo 5. Configurar analytics
echo 6. ¡Empezar a vender!
echo.

pause

