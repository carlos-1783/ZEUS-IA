"""
📅 Google Workspace Endpoints
Endpoints para Google Calendar, Gmail, Drive, Sheets
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime

# Importar servicio
from services.google_service import google_service

router = APIRouter()

# ============================================================================
# MODELS
# ============================================================================

class CalendarEvent(BaseModel):
    summary: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    attendees: Optional[List[str]] = None
    location: Optional[str] = None

class GmailMessage(BaseModel):
    to_email: EmailStr
    subject: str
    body: str
    attachments: Optional[List[str]] = None

class DriveUpload(BaseModel):
    file_path: str
    folder_id: Optional[str] = None
    file_name: Optional[str] = None

class SpreadsheetCreate(BaseModel):
    title: str
    sheets: Optional[List[str]] = None

class SpreadsheetWrite(BaseModel):
    spreadsheet_id: str
    range_name: str  # ej: "Sheet1!A1:C10"
    values: List[List[Any]]
    value_input_option: str = "USER_ENTERED"

class SpreadsheetRead(BaseModel):
    spreadsheet_id: str
    range_name: str

# ============================================================================
# GOOGLE CALENDAR ENDPOINTS
# ============================================================================

@router.post("/calendar/event")
async def create_calendar_event(event: CalendarEvent):
    """Crear evento en Google Calendar"""
    result = await google_service.create_calendar_event(
        summary=event.summary,
        start_time=event.start_time,
        end_time=event.end_time,
        description=event.description,
        attendees=event.attendees,
        location=event.location
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

@router.get("/calendar/events")
async def list_calendar_events(
    start_date: datetime,
    end_date: datetime,
    max_results: int = 10
):
    """Listar eventos de calendario"""
    result = await google_service.list_calendar_events(
        start_date=start_date,
        end_date=end_date,
        max_results=max_results
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

# ============================================================================
# GMAIL ENDPOINTS
# ============================================================================

@router.post("/gmail/send")
async def send_gmail(message: GmailMessage):
    """Enviar email vía Gmail API"""
    result = await google_service.send_gmail(
        to_email=message.to_email,
        subject=message.subject,
        body=message.body,
        attachments=message.attachments
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

@router.get("/gmail/inbox")
async def read_gmail_inbox(
    max_results: int = 10,
    query: Optional[str] = None
):
    """Leer bandeja de entrada de Gmail"""
    result = await google_service.read_gmail_inbox(
        max_results=max_results,
        query=query
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

# ============================================================================
# GOOGLE DRIVE ENDPOINTS
# ============================================================================

@router.post("/drive/upload")
async def upload_to_drive(upload: DriveUpload):
    """Subir archivo a Google Drive"""
    result = await google_service.upload_to_drive(
        file_path=upload.file_path,
        folder_id=upload.folder_id,
        file_name=upload.file_name
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

@router.get("/drive/files")
async def list_drive_files(
    folder_id: Optional[str] = None,
    max_results: int = 10
):
    """Listar archivos de Drive"""
    result = await google_service.list_drive_files(
        folder_id=folder_id,
        max_results=max_results
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

# ============================================================================
# GOOGLE SHEETS ENDPOINTS
# ============================================================================

@router.post("/sheets/create")
async def create_spreadsheet(spreadsheet: SpreadsheetCreate):
    """Crear nueva hoja de cálculo"""
    result = await google_service.create_spreadsheet(
        title=spreadsheet.title,
        sheets=spreadsheet.sheets
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

@router.post("/sheets/write")
async def write_to_sheet(data: SpreadsheetWrite):
    """Escribir datos en hoja de cálculo"""
    result = await google_service.write_to_sheet(
        spreadsheet_id=data.spreadsheet_id,
        range_name=data.range_name,
        values=data.values,
        value_input_option=data.value_input_option
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

@router.post("/sheets/read")
async def read_from_sheet(data: SpreadsheetRead):
    """Leer datos de hoja de cálculo"""
    result = await google_service.read_from_sheet(
        spreadsheet_id=data.spreadsheet_id,
        range_name=data.range_name
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result

# ============================================================================
# STATUS
# ============================================================================

@router.get("/status")
async def google_status():
    """Obtener estado de las integraciones Google"""
    return google_service.get_status()

