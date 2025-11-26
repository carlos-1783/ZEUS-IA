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
    generate_fiscal_forms,
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
from .afrodita_tools import (
    record_face_check_in,
    handle_qr_check_in,
    build_employee_schedule,
    create_rrhh_contract,
)

__all__ = [
    "analyze_perseo_image",
    "enhance_perseo_video",
    "run_seo_audit",
    "build_ads_blueprint",
    "read_qr_payload",
    "scan_nfc_payload",
    "parse_dnie_mrz",
    "generate_fiscal_forms",
    "sign_pdf_document",
    "generate_contract_kit",
    "run_gdpr_audit",
    "monitor_security_logs",
    "detect_threat_events",
    "revoke_credentials",
    "record_face_check_in",
    "handle_qr_check_in",
    "build_employee_schedule",
    "create_rrhh_contract",
]

