"""J9a: tabla UNICA de enrutado dominio -> agente (sustituye ZeusCore._route_to_agent).

Palabras completas (texto sin acentos, tokens alfanumericos), nunca subcadenas: "ip" no casa en
"equipo", "log" no casa en "catalogo", "ley" no casa en "Leyre". Sin default silencioso: sin dominio claro
o con empate devuelve agent=None y ZEUS responde con su propia personalidad (o pregunta).
THALOS (seguridad) solo se elige si el solicitante es superusuario (como J4); en otro caso, ZEUS.
El vocabulario de campanas/ofertas se comparte con el parser (`intent_parser._OFFER_RE`)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from services import intent_parser as ip

# dominio -> (task_type de ZeusCore, agente)
DOMAIN_AGENT: Dict[str, Tuple[str, str]] = {
    "marketing": ("marketing", "PERSEO"),
    "fiscal": ("fiscal", "RAFAEL"),
    "legal": ("legal", "JUSTICIA"),
    "rrhh": ("rrhh", "AFRODITA"),
    "security": ("security", "THALOS"),
}

# Terminos (ya sin acentos, minusculas). Los de varias palabras casan como secuencia de tokens.
DOMAIN_TERMS: Dict[str, Tuple[str, ...]] = {
    "marketing": (
        "marketing", "campana", "campanas", "anuncio", "anuncios", "seo", "sem", "lead", "leads",
        "conversion", "trafico", "contenido", "contenidos", "redes sociales", "instagram", "facebook",
        "google ads", "publicidad", "newsletter", "embudo", "funnel", "ventas",
    ),
    "fiscal": (
        "factura", "facturas", "facturacion", "impuesto", "impuestos", "iva", "irpf", "hacienda",
        "contable", "contabilidad", "gasto", "gastos", "ingreso", "ingresos", "deducible", "deducibles",
        "declaracion", "fiscal", "tributario", "aeat", "modelo 303", "modelo 130", "modelo 111",
        "modelo 115", "modelo 390",
    ),
    "legal": (
        "legal", "legales", "contrato", "contratos", "gdpr", "rgpd", "lopd", "privacidad",
        "datos personales", "consentimiento", "politica de privacidad", "terminos", "condiciones",
        "ley", "leyes", "abogado", "clausula", "clausulas", "normativa", "cookies", "juridico",
    ),
    "rrhh": (
        "nomina", "nominas", "turno", "turnos", "fichaje", "fichajes", "fichar", "vacaciones", "horario",
        "horarios", "empleado", "empleados", "plantilla", "rrhh", "recursos humanos", "ausencia",
        "ausencias", "control horario", "baja laboral",
    ),
    "security": (
        "seguridad", "ataque", "ataques", "amenaza", "amenazas", "vulnerabilidad", "vulnerabilidades",
        "hackeo", "ip", "firewall", "log", "logs", "incidente", "incidentes", "malware", "ransomware",
        "intrusion",
    ),
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> Tuple[str, ...]:
    return tuple(_TOKEN_RE.findall(ip.fold(text or "")))


def _has_term(tokens: Tuple[str, ...], term: str) -> bool:
    parts = tuple(term.split())
    n = len(parts)
    return any(tokens[i : i + n] == parts for i in range(len(tokens) - n + 1))


def domain_scores(message: str) -> Dict[str, int]:
    toks = _tokens(message)
    scores = {d: sum(1 for t in terms if _has_term(toks, t)) for d, terms in DOMAIN_TERMS.items()}
    if ip._OFFER_RE.search(ip.fold(message or "")):  # ofertas/descuentos/promos: vocabulario del parser
        scores["marketing"] += 1
    return scores


@dataclass
class RouteDecision:
    agent: Optional[str]  # None => ZEUS responde directamente
    task_type: Optional[str]
    domain: Optional[str]
    reason: str  # matched | no_domain | ambiguous | thalos_requires_superuser
    scores: Dict[str, int] = field(default_factory=dict)


def route_message(message: str, *, is_superuser: bool = False) -> RouteDecision:
    scores = domain_scores(message)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_domain, top = ranked[0]
    if top == 0:
        return RouteDecision(None, None, None, "no_domain", scores)
    if len(ranked) > 1 and ranked[1][1] == top:
        return RouteDecision(None, None, None, "ambiguous", scores)
    task_type, agent = DOMAIN_AGENT[top_domain]
    if agent == "THALOS" and not is_superuser:
        return RouteDecision(None, None, top_domain, "thalos_requires_superuser", scores)
    return RouteDecision(agent, task_type, top_domain, "matched", scores)


def task_type_to_agent(task_type: Optional[str]) -> Optional[str]:
    for tt, agent in DOMAIN_AGENT.values():
        if tt == task_type:
            return agent
    return None
