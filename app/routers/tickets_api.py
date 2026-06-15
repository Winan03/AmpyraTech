from fastapi import APIRouter, Depends, HTTPException, status
from app.db.supabase import get_supabase_client
from app.models.supabase_models import TicketUpdate

router = APIRouter(prefix="/api/tickets", tags=["tickets"])

# Omitimos require_roles para simplificar, pero en prod importarias:
# from app.routers.auth_api import require_roles, ADMIN_ROLES

@router.get("/")
async def get_tickets():
    client = get_supabase_client()
    # Join con audit_events para obtener sensor_id, event_type y branch_label
    res = client.table("maintenance_tickets").select(
        "id, ticket_code, issue_type, priority, status, resolution_notes, created_at, "
        "audit_events(sensor_id, event_type, branch_label, irms, power, detected_at)"
    ).order("created_at", desc=True).execute()
    
    # Aplanar la respuesta para facilitar el consumo en el frontend
    flattened = []
    for t in (res.data or []):
        event = t.get("audit_events") or {}
        flattened.append({
            "id": t.get("id"),
            "ticket_code": t.get("ticket_code"),
            "issue_type": t.get("issue_type"),
            "priority": t.get("priority"),
            "status": t.get("status"),
            "resolution_notes": t.get("resolution_notes"),
            "created_at": t.get("created_at"),
            "sensor_id": event.get("sensor_id", "—"),
            "branch_label": event.get("branch_label", "—"),
            "event_type": event.get("event_type", t.get("issue_type", "—")),
            "irms": event.get("irms"),
            "power": event.get("power"),
        })
    return {"data": flattened}

@router.patch("/{ticket_id}")
async def update_ticket(ticket_id: str, update_data: TicketUpdate):
    client = get_supabase_client()
    
    # Validacion basica
    data = update_data.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No data provided to update")
        
    res = client.table("maintenance_tickets").update(data).eq("id", ticket_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Ticket not found")
        
    return {"success": True, "data": res.data[0]}
