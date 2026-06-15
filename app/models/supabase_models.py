from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class AuditEventCreate(BaseModel):
    event_type: str
    sensor_id: str
    branch_label: Optional[str] = None
    irms: Optional[float] = None
    power: Optional[float] = None
    severity: Optional[str] = "Media"
    source: Optional[str] = "Firebase"

class TicketCreate(BaseModel):
    event_id: str  # UUID as string
    ticket_code: str
    issue_type: str
    priority: str
    assigned_to: Optional[str] = None

class TicketUpdate(BaseModel):
    status: Optional[str] = None
    resolution_notes: Optional[str] = None
    reviewed_by: Optional[str] = None

class ReportCreate(BaseModel):
    report_code: str
    period_start: datetime
    period_end: datetime
    total_alerts: int
    total_tickets: int
    peak_current: Optional[float] = None
    affected_branches: Optional[List[str]] = []
    summary_data: Dict[str, Any]  # The JSON used for rendering the PDF
