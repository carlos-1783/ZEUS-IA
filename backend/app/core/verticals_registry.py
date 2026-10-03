"""Registro único de verticales/módulos de negocio (fuente de verdad).

Antes de este registro, NO existía ningún control de acceso a verticales en
el backend (confirmado por grep de `require_module` en todo `backend/`: cero
resultados). El único "gating" era un filtro de menú en el frontend que ni
siquiera cubría la vertical Seguros -> cualquier empresa (restaurante,
tienda, oficina, lo que fuera) podía ver y usar el menú de Seguros, crear
pólizas y siniestros, aunque no lo hubiese contratado. El filtrado por
`company_id` dentro de `insurance.py` sí era correcto (sin fuga de datos
entre empresas que SÍ entraban), pero no había ninguna comprobación de SI
una empresa debía entrar siquiera.

Este módulo centraliza, por vertical, qué `Company.company_type` tiene
acceso. Se consume desde:
  - Backend: `app.core.module_access.require_module(...)` (dependencia
    FastAPI real, devuelve 403 si no hay acceso).
  - Frontend: vía el endpoint/espejo que expone esta misma información
    (ver `frontend/src/utils/companyModules.ts`), para ocultar el menú Y
    bloquear la ruta -- pero el backend es la autoridad real; el frontend
    es solo UX.

Reglas de esta estructura:
  - Clave = nombre de módulo/vertical tal y como se usa en
    `require_module("<modulo>")` y en el prefijo de su router
    (p. ej. "insurance" -> `/api/v1/insurance`).
  - Valor = lista de `company_type` (ver `app.models.company.Company.company_type`)
    que tienen acceso a ese módulo SIN ser superusuario.
  - Lista vacía ([]) significa: módulo cerrado por defecto, SOLO accesible
    para `User.is_superuser=True` (ver `module_access.require_module`).
    Esto es intencional, no un olvido -- se documenta módulo por módulo.
"""

from __future__ import annotations

from typing import Dict, List

# NOTA IMPORTANTE sobre "insurance":
# Deliberadamente vacío de company_types. Carlos (producto) tiene pendiente
# confirmar qué tipo(s) de empresa (aseguradora / correduría / agencia, etc.)
# tendrán acceso real a esta vertical -- hoy esos `company_type` ni siquiera
# existen en `Company.company_type` (solo existen "bar_restaurant" y
# "office"). Hasta que se confirme, Seguros queda SOLO accesible para
# superusuario. Esto es estrictamente más seguro que el estado anterior
# (visible/accesible para cualquier empresa) y no requiere inventar tipos
# de empresa que no están decididos.
#
# Cuando Carlos confirme los tipos, añadir aquí la lista, p. ej.:
#   "insurance": ["insurance_broker", "insurance_agency"],
VERTICAL_MODULE_COMPANY_TYPES: Dict[str, List[str]] = {
    "insurance": [],
}

# Prefijo real (bajo `settings.API_V1_STR`) del router de cada vertical, tal
# y como se registra en `app/api/v1/__init__.py` vía `include_router(...,
# prefix=...)`. Se usa en `tests/test_verticals_module_access.py` como
# "fuente de verdad" para comprobar, de forma automática, que todo módulo
# aquí registrado tiene un router real con `require_module` aplicado -- y
# que no queda ningún router de vertical sin su entrada correspondiente en
# `VERTICAL_MODULE_COMPANY_TYPES`.
VERTICAL_MODULE_ROUTE_PREFIXES: Dict[str, str] = {
    "insurance": "/insurance",
}


def allowed_company_types_for_module(module: str) -> List[str]:
    """Devuelve los `company_type` con acceso a `module`.

    Lista vacía (incluido el caso de módulo desconocido) significa:
    cerrado salvo superusuario. Un módulo no registrado aquí se trata como
    cerrado por defecto (fail-closed), nunca como abierto por defecto.
    """
    return list(VERTICAL_MODULE_COMPANY_TYPES.get(module, []))


def is_known_module(module: str) -> bool:
    return module in VERTICAL_MODULE_COMPANY_TYPES
