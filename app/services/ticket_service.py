import uuid
import logging
from datetime import datetime
from app.db.supabase import get_supabase_client
from app.models.supabase_models import AuditEventCreate, TicketCreate
import math

logger = logging.getLogger(__name__)

def generate_ticket_code() -> str:
    # Genera un codigo unico TCK-YYYY-XXXX
    year = datetime.now().year
    short_uuid = str(uuid.uuid4()).split('-')[0].upper()
    return f"TCK-{year}-{short_uuid}"

def create_audit_event(event_data: AuditEventCreate) -> str:
    """Guarda el evento en Supabase y devuelve su ID"""
    client = get_supabase_client()
    data = event_data.model_dump(exclude_none=True)
    response = client.table("audit_events").insert(data).execute()
    
    if response.data:
        return response.data[0]["id"]
    raise Exception("No se pudo crear el evento de auditoria")

def create_maintenance_ticket(event_id: str, event_type: str, severity: str) -> str:
    """Crea un ticket vinculado a un evento"""
    client = get_supabase_client()
    
    # Determinar prioridad basada en severidad
    priority = "Alta" if severity == "Alta" else ("Media" if severity == "Media" else "Baja")
    
    ticket_code = generate_ticket_code()
    ticket_data = TicketCreate(
        event_id=event_id,
        ticket_code=ticket_code,
        issue_type=event_type,
        priority=priority,
    )
    
    response = client.table("maintenance_tickets").insert(ticket_data.model_dump(exclude_none=True)).execute()
    if response.data:
        return response.data[0]["id"]
    raise Exception("No se pudo crear el ticket de mantenimiento")

def handle_critical_alert(event_type: str, sensor_id: str, severity: str = "Media", irms: float = None, power: float = None, branch_label: str = None):
    """Función principal que orquesta la auditoría y creación de ticket"""
    print(f"\n[TICKET] Iniciando creación de ticket para sensor={sensor_id}, tipo={event_type}, severidad={severity}")
    try:
        # Validar y limpiar NaN o nulos
        valid_irms = float(irms) if irms is not None else 0.0
        if math.isnan(valid_irms): valid_irms = 0.0
            
        valid_power = float(power) if power is not None else 0.0
        if math.isnan(valid_power): valid_power = 0.0
        
        print(f"[TICKET] Datos validados: irms={valid_irms}, power={valid_power}, branch={branch_label}")
            
        event = AuditEventCreate(
            event_type=event_type,
            sensor_id=sensor_id,
            severity=severity,
            irms=valid_irms,
            power=valid_power,
            branch_label=branch_label or "Desconocido"
        )
        print(f"[TICKET] Insertando audit_event en Supabase: {event.model_dump()}")
        event_id = create_audit_event(event)
        print(f"[TICKET] audit_event creado con ID: {event_id}")
        
        ticket_id = create_maintenance_ticket(event_id, event_type, severity)
        print(f"[TICKET] ✅ Ticket creado con ID: {ticket_id} para sensor {sensor_id}")
        logger.info(f"✅ Ticket creado: {ticket_id} (sensor={sensor_id}, tipo={event_type})")
        return ticket_id
    except Exception as e:
        import traceback
        print(f"[TICKET] ❌ ERROR creando ticket para {sensor_id}: {str(e)}")
        print(traceback.format_exc())
        logger.error(f"❌ Error al crear ticket para {sensor_id}: {str(e)}")
        return None
