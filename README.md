# ⚡ AmpyraTech

**AmpyraTech** es una plataforma IoT diseñada para la **detección temprana de sobrecargas eléctricas** en laboratorios de cómputo.  
El sistema mide el consumo eléctrico mediante sensores de corriente, procesa los datos con un ESP32 y los envía a **Firebase**, desde donde son visualizados en un **dashboard web en tiempo real**.

---

## ✨ Características principales
- 📊 **Monitoreo en tiempo real** del consumo eléctrico.  
- ⚠️ **Alertas automáticas** cuando se detecta una sobrecarga.  
- 🛠️ **Umbrales configurables** por el encargado del laboratorio.  
- 📂 **Historial de registros** accesible y exportable a CSV.  
- 🔒 **Acceso seguro** mediante inicio de sesión.  

---

## 🛠️ Tecnologías utilizadas
- **Hardware:** ESP32, sensor SCT-013-030, acondicionamiento de señal con OpAmp.  
- **Conexión:** WiFi → Firebase.  
- **Frontend:** HTML, CSS, JavaScript + Chart.js.  
- **Base de datos:** Firebase Realtime Database / Firestore.  

---

## 📐 Arquitectura general
```mermaid
flowchart TD
    Sensor[SCT-013-030] --> ESP32[ESP32 - Procesamiento de señal]
    ESP32 -->|WiFi| Firebase[(Firebase DB)]
    Firebase --> Web[Dashboard Web - AmpyraTech]
    Web --> Usuario[Encargado de Laboratorio]
