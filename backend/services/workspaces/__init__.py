"""
Paquete de herramientas para workspaces de agentes.
"""

from .perseo_tools import (
    analyze_perseo_image,
    enhance_perseo_video,
    run_seo_audit,
    build_ads_blueprint,
)
from .rafael_tools import (
    read_qr_payload,
    scan_nfc_payload,
    parse_dnie_mrz,
)
from .justicia_tools import (
    sign_pdf_document,
    generate_contract_kit,
    run_gdpr_audit,
)
from .thalos_tools import (
    monitor_security_logs,
    detect_threat_events,
    revoke_credentials,
)

__all__ = [
    "analyze_perseo_image",
    "enhance_perseo_video",
    "run_seo_audit",
    "build_ads_blueprint",
    "read_qr_payload",
    "scan_nfc_payload",
    "parse_dnie_mrz",
    "sign_pdf_document",
    "generate_contract_kit",
    "run_gdpr_audit",
    "monitor_security_logs",
    "detect_threat_events",
    "revoke_credentials",
]

