from pydantic import BaseModel

class Data(BaseModel):
    irms: float  # Corriente Irms en Amperios (A)
    power: float  # Potencia en Watts (W)