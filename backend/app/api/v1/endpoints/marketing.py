"""
📊 Marketing Automation Endpoints
Endpoints para Google Ads, Meta Ads, Analytics
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.marketing_integrations import MarketingIntegrationsIn, MarketingIntegrationsOut
from services import marketing_integrations_service as mi_svc
from services.marketing_service import marketing_service

router = APIRouter()

# ============================================================================
# MODELS
# ============================================================================

class GoogleAdsCampaign(BaseModel):
    campaign_name: str
    budget_amount: float
    target_locations: List[str]
    keywords: List[str]
    ad_text: Dict[str, str]  # headlines, descriptions

class MetaAdsCampaign(BaseModel):
    campaign_name: str
    objective: str  # CONVERSIONS, TRAFFIC, BRAND_AWARENESS
    budget_amount: float
    target_audience: Dict[str, Any]
    creative: Dict[str, Any]

class CampaignOptimization(BaseModel):
    campaign_id: str
    optimization_goal: str = "conversions"  # conversions, clicks, impressions

class AnalyticsQuery(BaseModel):
    start_date: datetime
    end_date: datetime
    metrics: List[str]
    dimensions: Optional[List[str]] = None

# ============================================================================
# GOOGLE ADS ENDPOINTS
# ============================================================================

@router.post("/google-ads/campaign")
async def create_google_ads_campaign(campaign: GoogleAdsCampaign):
    """Crear campaña en Google Ads"""
    result = await marketing_service.create_google_ads_campaign(
        campaign_name=campaign.campaign_name,
        budget_amount=campaign.budget_amount,
        target_locations=campaign.target_locations,
        keywords=campaign.keywords,
        ad_text=campaign.ad_text
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

@router.get("/google-ads/performance")
async def get_google_ads_performance(
    campaign_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    """Obtener métricas de rendimiento de Google Ads"""
    result = await marketing_service.get_google_ads_performance(
        campaign_id=campaign_id,
        start_date=start_date,
        end_date=end_date
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

@router.post("/google-ads/optimize")
async def optimize_google_ads_campaign(optimization: CampaignOptimization):
    """Optimizar campaña usando IA de PERSEO"""
    result = await marketing_service.optimize_google_ads_campaign(
        campaign_id=optimization.campaign_id,
        optimization_goal=optimization.optimization_goal
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

# ============================================================================
# META ADS ENDPOINTS
# ============================================================================

@router.post("/meta-ads/campaign")
async def create_meta_ads_campaign(campaign: MetaAdsCampaign):
    """Crear campaña en Meta Ads (Facebook/Instagram)"""
    result = await marketing_service.create_meta_ads_campaign(
        campaign_name=campaign.campaign_name,
        objective=campaign.objective,
        budget_amount=campaign.budget_amount,
        target_audience=campaign.target_audience,
        creative=campaign.creative
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

@router.get("/meta-ads/insights")
async def get_meta_ads_insights(
    campaign_id: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    """Obtener insights de Meta Ads"""
    result = await marketing_service.get_meta_ads_insights(
        campaign_id=campaign_id,
        start_date=start_date,
        end_date=end_date
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

# ============================================================================
# GOOGLE ANALYTICS ENDPOINTS
# ============================================================================

@router.post("/analytics/data")
async def get_analytics_data(query: AnalyticsQuery):
    """Obtener datos de Google Analytics"""
    result = await marketing_service.get_analytics_data(
        start_date=query.start_date,
        end_date=query.end_date,
        metrics=query.metrics,
        dimensions=query.dimensions
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

# ============================================================================
# MARKETING REPORTS
# ============================================================================

@router.get("/report")
async def generate_marketing_report(period_days: int = 30):
    """
    Generar reporte completo de marketing con análisis de PERSEO
    
    Args:
        period_days: Días del período a analizar (default: 30)
    """
    result = await marketing_service.generate_marketing_report(
        period_days=period_days
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

# ============================================================================
# STATUS
# ============================================================================

@router.get("/status")
async def marketing_status():
    """Obtener estado del servicio de marketing"""
    return marketing_service.get_status()


# ============================================================================
# MARKETING INTEGRATIONS V1
# ============================================================================


@router.get("/integrations", response_model=MarketingIntegrationsOut)
def get_marketing_integrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Integraciones sociales y ads por empresa (company_id obligatorio)."""
    data = mi_svc.get_integrations(db, current_user)
    return MarketingIntegrationsOut(**data)


@router.put("/integrations", response_model=MarketingIntegrationsOut)
def save_marketing_integrations(
    body: MarketingIntegrationsIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    on_save: validate_inputs → store_integrations → log_activity:marketing_connected
    """
    payload = body.model_dump()
    data = mi_svc.store_integrations(db, current_user, payload)
    return MarketingIntegrationsOut(**data)


@router.get("/integrations/metrics")
def get_marketing_integration_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Métricas agregadas (ad_spend, leads, CPL, engagement)."""
    return {"success": True, "data": mi_svc.collect_metrics_snapshot(db, current_user)}

