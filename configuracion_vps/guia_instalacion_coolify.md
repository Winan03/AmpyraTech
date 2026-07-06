# Guía de Instalación: Coolify en Contabo VPS + SafyraShield

> **VPS:** Contabo VPS 10 — IP: `75.119.145.51` — Ubuntu — 150GB SSD

---

## 1. Conexión Inicial

```bash
ssh root@75.119.145.51
# Ingresar contraseña cuando se solicite
```

---

## 2. Actualizar Sistema

```bash
apt update && apt upgrade -y
```

---

## 3. Instalar Docker

```bash
curl -fsSL https://get.docker.com | sh
```

Verificar instalación:

```bash
docker --version
docker compose version
```

---

## 4. Instalar Coolify

```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

La instalación:
- Descarga e inicia los contenedores Docker de Coolify
- Crea el directorio `/data/coolify` para persistencia
- Expone el dashboard en `http://75.119.145.51:8000`

Al finalizar, verás una URL de acceso. Anótala.

---

## 5. Configuración Inicial de Coolify

1. Abrir `http://75.119.145.51:8000` en el navegador
2. Crear cuenta de administrador (email + contraseña segura)
3. Conectar una fuente Git (GitHub, GitLab, etc.)

---

## 6. Desplegar SafyraShield

### 6.1. En Coolify

1. Ir a **Resources** → **New Resource** → **Private Repository** (o Public si el repo es público)
2. Seleccionar el repositorio de SafyraShield
3. Configurar:

| Campo | Valor |
|---|---|
| **Build Pack** | `Python` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port 80` |
| **Install Command** | `pip install -r requirements.txt` |
| **Port** | `80` |

4. Ir a la pestaña **Environment Variables** y añadir todas las variables del `.env` local
5. Hacer clic en **Deploy**

### 6.2. Variables de Entorno Requeridas

Las variables se agrupan en estas categorías (usar `.env.example` como referencia):

| Categoría | Variables clave |
|---|---|
| **Firebase DB** | `FIREBASE_DATABASE_URL`, `FIREBASE_PRIVATE_KEY_JSON_BASE64` |
| **Firebase Auth** | `FIREBASE_WEB_API_KEY`, `FIREBASE_PROJECT_ID`, etc. |
| **JWT** | `JWT_SECRET_KEY` (generar una segura) |
| **Admin inicial** | `ADMIN_USERNAME_HASH`, `ADMIN_EMAIL`, etc. |
| **IoT** | `SAFYRA_IOT_TOKEN`, `PHYSICAL_BRANCH_ID=C-01` |
| **Laboratorio** | `LAB_ROOM_ID=LAB-PC-01`, `MONITORED_SENSOR_IDS=C-01,...,C-10` |
| **Alertas n8n** | `N8N_ALERT_WEBHOOK_URL`, `N8N_ALERT_WEBHOOK_TOKEN` |

> **⚠️ Importante:** Usar los mismos valores que en el `.env` local de desarrollo.
> No versionar el `.env` real. Solo el `.env.example` va al repositorio.

---

## 7. Configurar Dominio (Opcional)

Coolify asigna automáticamente un subdominio. Para usar dominio propio:

### Opción A: DuckDNS (gratis)
```bash
# Crear cuenta en https://duckdns.org
# Obtener token y configurar dominio: safyrashield.duckdns.org
```

### Opción B: Dominio propio
1. Comprar dominio (Nic.pe, Namecheap, etc.)
2. Configurar registro A apuntando a `75.119.145.51`
3. En Coolify: **Domains** → añadir dominio
4. Coolify obtiene SSL automáticamente con Let's Encrypt

---

## 8. Desplegar n8n en el Mismo Servidor (Opcional)

Coolify tiene un template de 1 clic para n8n:

1. **Resources** → **New Resource** → **n8n**
2. Configurar variables:
   - `N8N_PORT=5678`
   - `WEBHOOK_URL=https://<tu-dominio>/webhook/`
3. Deploy
4. Importar el workflow desde `integrations/n8n/safyra_alerts_workflow.json`

---

## 9. Verificar Despliegue

```bash
curl http://localhost/api/data/connection
# Respuesta esperada: {"status": "ok", "service": "SafyraShield IoT Monitor"}

curl http://localhost/health
# Respuesta esperada: {"status": "online", "service": "SafyraShield IoT Monitor", "version": "3.0.0 - Sprint 3"}
```

---

## 10. Comandos Útiles

```bash
# Ver logs del deployment
docker logs -f coolify

# Ver contenedores activos
docker ps

# Ver logs de la aplicación desde Coolify dashboard
# Ir a Resource → SafyraShield → Logs

# Conectar por SSH (después de configurar coolify)
# Las claves SSH se configuran en Coolify > Keys
```

---

## 11. Solución de Problemas

| Problema | Causa posible | Solución |
|---|---|---|
| Coolify no inicia | Puerto 8000 ocupado | `lsof -i :8000` y matar proceso |
| Build falla | requirements.txt mal formado | Verificar sintaxis, correr `pip install -r requirements.txt` localmente |
| App no responde | Variables de entorno faltantes | Revisar que `.env` tenga TODAS las variables necesarias |
| SSL no funciona | Puerto 443 bloqueado | `ufw allow 443/tcp` o verificar firewall del VPS |

---

## 12. Seguridad

```bash
# Firewall básico
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp        # SSH
ufw allow 80/tcp        # HTTP
ufw allow 443/tcp       # HTTPS
ufw allow 8000/tcp      # Coolify dashboard
ufw enable

# Fail2Ban para SSH
apt install fail2ban -y
systemctl enable fail2ban
systemctl start fail2ban
```
