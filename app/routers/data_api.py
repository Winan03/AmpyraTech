from fastapi import APIRouter
from app.db.firebase import get_current_data, get_history_data, check_connection

router = APIRouter(prefix="/data", tags=["data"])

@router.get("/current")
async def read_current_data():
    """
    Endpoint para obtener datos actuales de los 3 sensores
    """
    result = get_current_data()
    return result

@router.get("/history/{sensor_id}")
async def read_history_data(sensor_id: str, limit: int = 20):
    """
    Endpoint para obtener el historial de un sensor específico
    """
    history = get_history_data(sensor_id, limit)
    return {
        "sensor_id": sensor_id,
        "data": history
    }

@router.get("/connection")
async def check_connection_status():
    """
    Endpoint para verificar solo el estado de la conexión
    """
    is_connected = check_connection()
    return {
        "connected": is_connected,
        "message": "Conectado" if is_connected else "Desconectado"
    }