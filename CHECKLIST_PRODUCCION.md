# ✅ Checklist pre-lanzamiento ZEUS-IA

## Correcciones de auditoría aplicadas

- [x] **auth.py**: `OperationalError` y `DisconnectionError` importados desde `sqlalchemy.exc`
- [x] **CORS**: Sin `*`. Orígenes, métodos y cabeceras explícitos en:
  - `backend/app/main.py` (producción)
  - `backend/main.py`
  - `backend/app/minimal_main.py`
- [x] **TPV**: `imageFile` / `imagePreview` / `iconOptions` definidos; `imageUrl` en `saveProduct` con upload y fallback
- [x] **Auditoría**: `AUDITORIA_COMPLETA_PRODUCCION.md` actualizado

## Antes de desplegar

1. **Variables de entorno (Railway / .env)**  
   - `DATABASE_URL`, `SECRET_KEY`, `REFRESH_TOKEN_SECRET`  
   - Evitar valores por defecto de desarrollo en producción.

2. **Frontend**  
   - `npm run build` sin errores.  
   - Servir `dist/` (o equivalente) desde `backend/static` si usas deploy unificado.

3. **Backend**  
   - `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (Railway usa `app.main:app`).

4. **Smoke test**  
   - Login → Dashboard → TPV → Añadir producto (con/sin imagen) → Añadir al carrito → Pagar.

## Post-lanzamiento (opcional)

- Sustituir `alert()` por toasts/notificaciones en TPV.
- Revisar TODOs críticos en el código.
- Activar rate limiting en endpoints públicos si se requiere.
