# Firmware de Microcontroladores - SafyraShield

Esta carpeta contiene el firmware para los microcontroladores del sistema IoT.

## Estructura

| Archivo | Microcontrolador | Función |
|---|---|---|
| `codigo_arduino_nano_version_2.ino` | Arduino Nano | Lectura del sensor SCT-013, filtro de umbral (0.17A), heartbeat (30s), envío UART |
| `Codigo_esp_32_version_2.ino` | ESP32 | Recepción UART, conexión WiFi, envío HTTP POST al backend |

## Archivos Reales vs. Ejemplo

Los archivos `.ino` reales contienen credenciales WiFi, URL del backend y token de autenticación específicos del despliegue. Por seguridad:

- Los archivos `.ino` reales **no se incluyen en el repositorio** (están en `.gitignore`)
- En su lugar, se proveen archivos `.ino.example` con valores placeholder

Para compilar y cargar el firmware:

1. Copiar `Codigo_esp_32.ino.example` → `Codigo_esp_32.ino`
2. Copiar `codigo_arduino_nano.ino.example` → `codigo_arduino_nano.ino`
3. Reemplazar los valores placeholder con las credenciales reales
4. Abrir en Arduino IDE y cargar al microcontrolador

## Conexión entre Microcontroladores

```
Arduino Nano (TX) --UART 9600 baud--> ESP32 (RX2 pin 16)
                      GND compartido
```

El Arduino Nano siempre mide corriente (~600ms por ciclo). Si `promedioIrms ≥ 0.17A`, envía datos inmediatamente. Si está inactivo, envía un heartbeat cada 30 segundos.
