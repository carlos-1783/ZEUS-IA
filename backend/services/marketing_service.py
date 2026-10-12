"""
Marketing de plataforma: Google Ads, Meta Ads (Facebook/Instagram), Google Analytics.

Fase 2 / Step 2 (sin simulacion): antes todas las operaciones devolvian success=True con
IDs de campana inventados ("campaignId=simulated") y metricas fijas (12500 impresiones,
325 clics...). Ahora:
- Meta Ads: llamadas REALES a la Graph API (crear campana, leer insights).
- Google Ads y Google Analytics: no hay cliente real integrado (ni libreria ni OAuth):
  responden 501 explicando que falta, o 503 si ni siquiera hay credenciales.
Nunca se devuelve un exito que no haya ocurrido.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from fastapi import HTTPException

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.facebook.com/v21.0"
# Objetivos clasicos -> objetivos ODAX vigentes de la Marketing API.
_META_OBJECTIVES = {
    "CONVERSIONS": "OUTCOME_SALES",
    "TRAFFIC": "OUTCOME_TRAFFIC",
    "BRAND_AWARENESS": "OUTCOME_AWARENESS",
    "LEADS": "OUTCOME_LEADS",
    "ENGAGEMENT": "OUTCOME_ENGAGEMENT",
}
_INSIGHT_FIELDS = "impressions,clicks,spend,ctr,cpc,reach"


def _not_implemented(platform: str, what: str, missing: str) -> HTTPException:
    return HTTPException(
        status_code=501,
        detail={
            "error": f"{platform}_not_implemented",
            "message": f"{what} no esta implementado: {missing}. No se ha hecho nada.",
        },
    )


def _not_configured(platform: str, variables: List[str]) -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"error": f"{platform}_not_configured", "missing": variables},
    )


class MarketingService:
    """Operaciones de marketing con cuentas de PLATAFORMA (solo superusuario, ver endpoint)."""

    # -------------------------------------------------------------- configuracion

    @staticmethod
    def _meta_token() -> Optional[str]:
        return os.getenv("FACEBOOK_ACCESS_TOKEN") or os.getenv("META_ACCESS_TOKEN")

    @staticmethod
    def _meta_account() -> Optional[str]:
        acc = os.getenv("FACEBOOK_AD_ACCOUNT_ID") or os.getenv("META_AD_ACCOUNT_ID")
        if not acc:
            return None
        return acc if acc.startswith("act_") else f"act_{acc}"

    def is_configured(self, platform: Optional[str] = None) -> bool:
        flags = {
            "google_ads": bool(os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN") and os.getenv("GOOGLE_ADS_CUSTOMER_ID")),
            "meta_ads": bool(self._meta_token() and self._meta_account()),
            "google_analytics": bool(os.getenv("GA_PROPERTY_ID") and os.getenv("GA_CREDENTIALS")),
        }
        if platform:
            return flags.get(platform, False)
        return any(flags.values())

    # -------------------------------------------------------------- Google Ads

    def _require_google_ads(self, what: str) -> None:
        if not self.is_configured("google_ads"):
            raise _not_configured("google_ads", ["GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CUSTOMER_ID"])
        raise _not_implemented(
            "google_ads", what, "falta el cliente real de la Google Ads API (libreria google-ads + OAuth)"
        )

    async def create_google_ads_campaign(self, **_: Any) -> Dict[str, Any]:
        from services.perseo_ads_engine_v2 import create_google_campaign

        # Misma implementacion que PERSEO: 503 sin credenciales, 501 sin cliente real.
        return create_google_campaign(name="-")

    async def get_google_ads_performance(self, **_: Any) -> Dict[str, Any]:
        self._require_google_ads("Leer el rendimiento de Google Ads")
        return {}

    async def optimize_google_ads_campaign(self, **_: Any) -> Dict[str, Any]:
        # Optimizar exige leer el rendimiento real primero.
        self._require_google_ads("Optimizar campanas de Google Ads")
        return {}

    # -------------------------------------------------------------- Meta Ads

    async def create_meta_ads_campaign(
        self,
        campaign_name: str,
        objective: str,
        budget_amount: float,
        target_audience: Optional[Dict[str, Any]] = None,
        creative: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Crea la CAMPANA real en Meta (en pausa). El conjunto de anuncios (audiencia) y
        el anuncio (creatividad) no se crean aqui: se informa explicitamente."""
        from services.perseo_ads_engine_v2 import create_meta_campaign

        if budget_amount is None or budget_amount <= 0:
            raise HTTPException(status_code=422, detail="El presupuesto diario debe ser mayor que 0.")
        result = create_meta_campaign(
            name=campaign_name,
            objective=_META_OBJECTIVES.get((objective or "").upper(), objective or "OUTCOME_TRAFFIC"),
            daily_budget_cents=int(round(budget_amount * 100)),
            status="PAUSED",
        )
        result["status"] = "PAUSED"
        result["not_created"] = [
            k for k, v in (("ad_set (target_audience)", target_audience), ("ad (creative)", creative)) if v
        ]
        result["message"] = (
            "Campana creada en Meta en estado PAUSED. Conjunto de anuncios y creatividades "
            "no se crean desde este endpoint."
        )
        logger.info("Meta Ads: campana real creada id=%s", result.get("campaign_id"))
        return result

    async def get_meta_ads_insights(
        self,
        campaign_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        token, account = self._meta_token(), self._meta_account()
        if not token or not account:
            raise _not_configured("meta_ads", ["FACEBOOK_ACCESS_TOKEN", "FACEBOOK_AD_ACCOUNT_ID"])
        target = campaign_id or account
        params: Dict[str, Any] = {"access_token": token, "fields": _INSIGHT_FIELDS}
        if start_date and end_date:
            params["time_range"] = json.dumps(
                {"since": start_date.strftime("%Y-%m-%d"), "until": end_date.strftime("%Y-%m-%d")}
            )
        else:
            params["date_preset"] = "last_30d"
        try:
            r = requests.get(f"{GRAPH_API}/{target}/insights", params=params, timeout=30)
            body = r.json()
        except (requests.RequestException, ValueError) as exc:
            raise HTTPException(status_code=502, detail={"error": "meta_ads_api_unreachable"}) from exc
        if r.status_code >= 400 or "error" in body:
            raise HTTPException(
                status_code=502,
                detail={"error": "meta_ads_api_failed", "response": body.get("error", body)},
            )
        return {
            "success": True,
            "platform": "meta_ads",
            "target": target,
            "data": body.get("data", []),
            "source": "graph_api",
        }

    # -------------------------------------------------------------- Google Analytics

    async def get_analytics_data(self, **_: Any) -> Dict[str, Any]:
        if not self.is_configured("google_analytics"):
            raise _not_configured("google_analytics", ["GA_PROPERTY_ID", "GA_CREDENTIALS"])
        raise _not_implemented(
            "google_analytics", "Leer Google Analytics", "falta el cliente real de la GA4 Data API"
        )

    # -------------------------------------------------------------- informe

    async def generate_marketing_report(self, period_days: int = 30) -> Dict[str, Any]:
        """Informe SOLO con datos reales. Cada plataforma sin integracion real aparece como
        no disponible con su motivo; nunca con cifras de relleno."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=max(1, int(period_days)))
        platforms: Dict[str, Any] = {}
        unavailable: Dict[str, str] = {}
        if self.is_configured("meta_ads"):
            try:
                platforms["meta_ads"] = (
                    await self.get_meta_ads_insights(start_date=start_date, end_date=end_date)
                )["data"]
            except HTTPException as exc:
                unavailable["meta_ads"] = json.dumps(exc.detail, default=str)[:300]
        else:
            unavailable["meta_ads"] = "no configurado"
        unavailable["google_ads"] = "cliente real no implementado"
        unavailable["google_analytics"] = "cliente real no implementado"
        if not platforms:
            raise HTTPException(
                status_code=503,
                detail={"error": "no_real_marketing_data", "unavailable": unavailable},
            )
        return {
            "success": True,
            "period": {"start": start_date.date().isoformat(), "end": end_date.date().isoformat()},
            "generated_at": datetime.utcnow().isoformat(),
            "platforms": platforms,
            "unavailable": unavailable,
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "platforms": {
                "google_ads": {"configured": self.is_configured("google_ads"), "implemented": False},
                "meta_ads": {"configured": self.is_configured("meta_ads"), "implemented": True},
                "google_analytics": {"configured": self.is_configured("google_analytics"), "implemented": False},
            },
        }


marketing_service = MarketingService()
