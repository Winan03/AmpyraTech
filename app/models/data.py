from pydantic import BaseModel
from typing import List, Optional

class DeviceInfo(BaseModel):
    """Información del dispositivo detectado"""
    type: str
    icon: str
    description: str
    color: str

class ThresholdInfo(BaseModel):
    """Información de umbral configurado"""
    corriente: float
    potencia: float

class SensorData(BaseModel):
    """Datos completos de un sensor"""
    id: str
    irms: float
    potencia: float
    is_overload: bool
    timestamp: str
    device: DeviceInfo
    threshold: ThresholdInfo

class CurrentDataResponse(BaseModel):
    """Respuesta completa de datos actuales"""
    sensors: List[SensorData]
    connected: bool
    message: str
    timestamp: str
    total_consumption: float

class HistoryRecord(BaseModel):
    """Registro histórico individual"""
    timestamp: str
    irms: float
    potencia: float
    estado: str
    device: DeviceInfo

class ThresholdUpdate(BaseModel):
    """Datos para actualizar umbral"""
    corriente: float
    potencia: float