# SafyraShield 🛡️

**Evaluación de la eficiencia de un sistema IoT para la detección temprana de sobrecargas eléctricas en el Colegio Interamericana Covicorti.**

Sistema IoT de monitoreo de consumo eléctrico en tiempo real que detecta sobrecargas y consumos fuera de horario en laboratorios de cómputo, enviando alertas automáticas por correo y WhatsApp. Arquitectura energéticamente eficiente con microcontroladores de bajo consumo y despliegue cloud verde.

---

## Stack Tecnológico

| Capa | Tecnología |
|---|---|
| **Sensor** | SCT-013-030 (transformador de corriente no invasivo, 30A/1V) |
| **Adquisición** | Arduino Nano (5V, muestreo analógico, filtro umbral 0.17A, heartbeat 30s) |
| **Comunicación** | ESP32 DevKit (UART → WiFi, HTTP POST con medición de latencia) |
| **Backend** | FastAPI (async/await, BackgroundTasks, ThreadPoolExecutor) |
| **Base de Datos** | Firebase Realtime DB (hot data) + Supabase PostgreSQL (cold data/auditoría) |
| **Alertas** | n8n → Correo SMTP + WhatsApp (CallMeBot) |
| **Frontend** | Jinja2 Templates + RBAC (Admin, Auditor, Operativo) |
| **Despliegue** | Coolify en Contabo VPS (100% energía verde certificada) |
| **Pruebas** | pytest (108 tests, 106 pasan) |

---

## Métricas Clave

| Métrica | Valor |
|---|---|
| **Latencia Backend** | ≤ 100 ms (procesamiento async) |
| **Latencia Alerta Completa** | ≤ 3,000 ms (E2E sensor → WhatsApp) |
| **Precisión Detección** | ≥ 90% en clasificación de estados |
| **Consumo Hardware IoT** | 0.0095 kWh/día (~S/ 2.43/año) |
| **Reducción Tráfico** | ~759 MB/mes → ~216 MB/mes (71.5% menos) |
| **Alertas Duplicadas** | Bloqueadas por Cooldown configurable (300s default) |

---

## Arquitectura

```
[SCT-013] --analog--> [Arduino Nano] --UART--> [ESP32] --HTTPS--> [FastAPI Backend]
                                                                      │
                                                    ┌─────────────────┼─────────────────┐
                                                    ▼                 ▼                 ▼
                                            [Firebase RTDB]   [Supabase PGSQL]   [n8n Webhook]
                                            (lecturas vivas)   (auditoría/tickets)  │
                                                                              ┌─────┴─────┐
                                                                              ▼           ▼
                                                                          [Correo]   [WhatsApp]
```

### Flujo de Datos
1. **Arduino Nano** lee el SCT-013 cada ~600ms. Si `promedioIrms ≥ 0.17A` envía por UART al ESP32 inmediatamente; si está inactivo, envía heartbeat cada 30s.
2. **ESP32** recibe la trama UART y la reenvía mediante HTTP POST al backend con medición de latencia.
3. **FastAPI** procesa la lectura: evalúa umbrales dinámicos, horario autorizado, y decide si dispara alerta vía webhook a n8n.
4. **n8n** envía notificaciones por correo y WhatsApp a los roles autorizados.
5. **Firebase** mantiene la telemetría viva para el dashboard; **Supabase** almacena el histórico de auditoría y tickets.

---

## Estructura del Proyecto

```
SafyraShield/
├── app/                        # Aplicación FastAPI
│   ├── main.py                 # Punto de entrada, rutas HTML
│   ├── db/                     # Conexiones a Firebase y Supabase
│   ├── models/                 # Modelos Pydantic
│   ├── routers/                # Endpoints API (data, auth, tickets, reports)
│   ├── services/               # Lógica de negocio (notificaciones, scheduler, reportes PDF)
│   ├── static/                 # CSS, JS, imágenes, sonidos
│   └── templates/              # Jinja2 HTML (dashboard, login, alerts, etc.)
├── code_microcontroladores/    # Firmware .ino (Arduino Nano + ESP32)
├── configuracion_vps/          # Guía de instalación en Contabo con Coolify
├── docs/                       # Documentación de sostenibilidad y checklist verde
├── integrations/               # Workflow de n8n (no versionado)
├── tools/                      # Scripts de simulación IoT
│   └── iot/                    # Simulador de 10 ramales, 13 escenarios
├── tests/                      # 108 pruebas pytest
│   ├── iot/                    # Pruebas de ingesta y simulador
│   └── schedule/               # Pruebas de agenda y horarios
├── README.md                   # Este archivo
├── requirements.txt            # Dependencias Python
└── .env.example                # Template de variables de entorno
```

---

## Requisitos

- Python 3.11+
- Cuenta gratuita en [Firebase](https://console.firebase.google.com) y [Supabase](https://supabase.com)
- URL de webhook n8n (opcional para alertas)

---

## Instalación Rápida

```bash
# Clonar
git clone https://github.com/tu-usuario/safyrashield.git
cd safyrashield

# Entorno virtual
python -m venv venv
.\venv\Scripts\activate   # Windows
source venv/bin/activate  # Linux

# Dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales reales (nunca versiones .env)

# Iniciar servidor de desarrollo
uvicorn app.main:app --reload

# Abrir http://localhost:8000
```

---

## Variables de Entorno

Ver `.env.example` para la lista completa. Las variables se agrupan en:

| Grupo | Variables |
|---|---|
| Firebase | `FIREBASE_DATABASE_URL`, `FIREBASE_WEB_API_KEY`, etc. |
| JWT | `JWT_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES` |
| Admin inicial | `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, etc. |
| IoT | `SAFYRA_IOT_TOKEN`, `PHYSICAL_BRANCH_ID` |
| n8n | `N8N_ALERT_WEBHOOK_URL`, `N8N_ALERT_WEBHOOK_TOKEN` |
| Laboratorio | `LAB_ROOM_ID`, `MONITORED_SENSOR_IDS` |

---

## Simulación IoT

```bash
# Escenario normal (sin alertas)
python -m tools.iot.simulator --scenario both_off

# Sobrecarga en ramal físico
python -m tools.iot.simulator --scenario branch_overload

# Consumo fuera de horario
python -m tools.iot.simulator --scenario out_of_schedule

# Demo completa con 3 escenarios
python -m tools.iot.simulator --demo --interval 8
```

---

## Pruebas

```bash
pytest -v
```

108 pruebas distribuidas en: autenticación (24), ingesta IoT (15), horarios (14), umbrales (12), datos actuales (9), simulador (9), historial (8), alertas (6), agenda (4), filtros Firebase (2).

---

## Software Verde 🌱

SafyraShield fue evaluado contra la lista de verificación de **Green Software**, cumpliendo **31 de 42** criterios. Los 11 restantes son No Aplica (GPU, certificaciones ISO, tarifas verdes corporativas).

### Prácticas implementadas
- **Transmisión condicional**: Umbral de 0.17A + heartbeat cada 30s en inactividad
- **Programación asíncrona**: FastAPI async/await, BackgroundTasks para tareas pesadas
- **Arquitectura event-driven**: Webhooks eliminan polling constante
- **Cooldown anti-spam**: Bloquea alertas duplicadas por 300s
- **Hardware de bajo consumo**: 0.0095 kWh/día (Arduino ~0.14W, ESP32 ~0.198W base)
- **Hosting verde**: Contabo VPS con 100% energía renovable certificada
- **Simulación IoT**: Reduce e-waste al evitar sensores físicos para 9 de 10 ramales

---

## Autenticación y Roles

| Rol | Acceso |
|---|---|
| **Admin** | CRUD completo, umbrales dinámicos, gestión de usuarios, 2FA obligatorio |
| **Auditor** | Solo lectura, reportes PDF, histórico, no modifica configuración |
| **Operativo** | Dashboard semáforo, exportación de bitácora, sin acceso a configuración |

---

## Licencia

Proyecto académico - Universidad Privada Antenor Orrego (UPAO)
