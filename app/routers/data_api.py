# app/routers/data_api.py
from fastapi import APIRouter, HTTPException, Response, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.db.firebase import (
    get_current_data, 
    get_history_data, 
    check_connection,
    update_sensor_threshold,
    export_history_csv,
    export_history_excel,
    get_alert_history # <-- ¡NUEVA IMPORTACIÓN!
)
from app.routers.auth_api import get_current_user
from app.models.data import ThresholdUpdate
import io

# ======================================================================
# CONFIGURACIÓN DEL ROUTER (¡PROTEGIDO!)
# ======================================================================
router = APIRouter(
    prefix="/data", 
    tags=["data"],
    dependencies=[Depends(get_current_user)]
)

# ======================================================================
# ENDPOINTS EXISTENTES (Ahora protegidos)
# ======================================================================

@router.get("/current")
async def read_current_data():
    """
    Endpoint para obtener datos actuales con detección de dispositivos
    (Protegido por autenticación)
    """
    result = get_current_data()
    return result

@router.get("/history/{sensor_id}")
async def read_history_data(
    sensor_id: str, 
    limit: int = 20,
    start_date: str = None, # (HU-010)
    end_date: str = None   # (HU-010)
):
    """
    Endpoint para obtener el historial con filtros de fecha (HU-010)
    (Protegido por autenticación)
    """
    history = get_history_data(sensor_id, limit, start_date, end_date)
    return {
        "sensor_id": sensor_id,
        "data": history,
        "count": len(history)
    }

# ======================================================================
# ¡NUEVO ENDPOINT DE ALERTAS!
# ======================================================================
@router.get("/alerts")
async def read_alert_history(
    start_date: str = None,
    end_date: str = None
):
    """
    Endpoint para obtener SÓLO el historial de alertas (sobrecargas)
    (Protegido por autenticación)
    """
    alerts = get_alert_history(start_date, end_date)
    return {
        "data": alerts,
        "count": len(alerts)
    }
# ======================================================================

@router.get("/connection")
async def check_connection_status():
    """
    Endpoint para verificar el estado de la conexión
    (Protegido por autenticación)
    """
    is_connected = check_connection()
    return {
        "connected": is_connected,
        "message": "Sistema operativo" if is_connected else "Sistema desconectado"
    }

@router.put("/threshold/{sensor_id}")
async def update_threshold(sensor_id: str, threshold: ThresholdUpdate):
    """
    Actualizar umbral de un sensor específico (HU-005)
    (Protegido por autenticación)
    """
    success = update_sensor_threshold(
        sensor_id, 
        threshold.corriente, 
        threshold.potencia
    )
    
    if success:
        return {
            "success": True,
            "message": f"Umbral actualizado para {sensor_id}",
            "threshold": {
                "corriente": threshold.corriente,
                "potencia": threshold.potencia
            }
        }
    else:
        raise HTTPException(status_code=500, detail="Error al actualizar umbral")

# ======================================================================
# ENDPOINTS DE EXPORTACIÓN (CSV y NUEVO EXCEL)
# ======================================================================

@router.get("/export/csv")
async def export_csv(
    sensor_id: str = None,
    start_date: str = None,
    end_date: str = None
):
    """
    Exportar datos históricos en formato CSV (HU-011)
    (Protegido por autenticación)
    """
    csv_content = export_history_csv(sensor_id, start_date, end_date)
    
    if not csv_content:
        raise HTTPException(status_code=404, detail="No hay datos para exportar")
    
    filename = f"safyrashield_export_{sensor_id or 'all'}.csv"
    
    return StreamingResponse(
        io.BytesIO(csv_content.encode('utf-8')),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )

@router.get("/export/excel")
async def export_excel(
    sensor_id: str = None,
    start_date: str = None,
    end_date: str = None
):
    """
    NUEVO: Exportar datos históricos en formato Excel con estilos (HU-011)
    (Protegido por autenticación)
    """
    excel_content_bytes = export_history_excel(sensor_id, start_date, end_date)
    
    if not excel_content_bytes:
        raise HTTPException(status_code=404, detail="No hay datos para exportar")
    
    filename = f"safyrashield_export_{sensor_id or 'all'}.xlsx"
    
    return Response(
        content=excel_content_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )

@router.get("/statistics")
async def get_statistics():
    """
    Obtener estadísticas generales del sistema
    (Protegido por autenticación)
    """
    current_data = get_current_data()
    
    # ... (lógica de estadísticas existente) ...
    active_sensors = sum(1 for s in current_data["sensors"] if s["irms"] > 0)
    overload_count = sum(1 for s in current_data["sensors"] if s["is_overload"])
    
    device_types = {}
    for sensor in current_data["sensors"]:
        device_type = sensor["device"]["type"]
        device_types[device_type] = device_types.get(device_type, 0) + 1
    
    return {
        "total_sensors": len(current_data["sensors"]),
        "active_sensors": active_sensors,
        "overload_count": overload_count,
        "total_consumption": current_data["total_consumption"],
        "device_distribution": device_types,
        "timestamp": current_data["timestamp"]
    }