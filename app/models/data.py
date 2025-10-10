
from pydantic import BaseModel
from typing import List, Optional

class Data(BaseModel):
    irms: float  # Corriente Irms en Amperios (A)
    power: float  # Potencia en Watts (W)

class SensorData(BaseModel):
    id: str
    irms: float
    potencia: float
    is_overload: bool
    timestamp: str