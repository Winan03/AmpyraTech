from datetime import datetime, timedelta, timezone
import json
import logging
from fpdf import FPDF
from app.db.supabase import get_supabase_client
from app.services.notifications import queue_alert_notification
from typing import Dict, Any
import os

logger = logging.getLogger(__name__)

INCIDENT_TRANSLATIONS = {
    "overload": "Sobrecarga",
    "out_of_schedule_consumption": "Consumo fuera de horario"
}

def get_period_data(days: int = 7) -> Dict[str, Any]:
    client = get_supabase_client()
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=days)
    
    start_str = period_start.isoformat()
    end_str = now.isoformat()
    
    # Tickets creados en el periodo
    tickets_res = client.table("maintenance_tickets") \
        .select("id, ticket_code, issue_type, priority, status, created_at") \
        .gte("created_at", start_str) \
        .lte("created_at", end_str) \
        .execute()
    tickets = tickets_res.data or []
    
    # Audit events del periodo (usa detected_at que es la columna de la tabla)
    events_res = client.table("audit_events") \
        .select("id, irms, branch_label, event_type, sensor_id, detected_at") \
        .gte("detected_at", start_str) \
        .lte("detected_at", end_str) \
        .execute()
    events = events_res.data or []
    
    total_tickets = len(tickets)
    total_alerts = len(events)
    
    peak_current = 0.0
    affected_branches = set()
    alerts_by_type: Dict[str, int] = {}
    
    for ev in events:
        irms_val = ev.get("irms") or 0
        try:
            irms_float = float(irms_val)
            if irms_float > peak_current:
                peak_current = irms_float
        except (TypeError, ValueError):
            pass
        label = ev.get("branch_label") or ev.get("sensor_id") or "Desconocido"
        affected_branches.add(label)
        etype = ev.get("event_type") or "desconocido"
        alerts_by_type[etype] = alerts_by_type.get(etype, 0) + 1
            
    summary_data = {
        "period_start": start_str,
        "period_end": end_str,
        "total_alerts": total_alerts,
        "total_tickets": total_tickets,
        "peak_current": round(peak_current, 3),
        "affected_branches": sorted(list(affected_branches)),
        "alerts_by_type": alerts_by_type,
        "tickets_list": tickets
    }
    
    return summary_data

class PremiumPDF(FPDF):
    def header(self):
        # Fondo oscuro para el header (color ink #0d2440)
        self.set_fill_color(13, 36, 64)
        self.rect(0, 0, 210, 35, 'F')
        
        # Titulo principal
        self.set_font("Arial", 'B', 24)
        self.set_text_color(255, 255, 255)
        self.set_y(8)
        self.set_x(15)
        self.cell(0, 10, "SafyraShield IoT", ln=1, align='L')
        
        # Subtitulo
        self.set_font("Arial", '', 12)
        self.set_text_color(0, 245, 255) # accent cyan
        self.set_x(15)
        self.cell(0, 8, "Reporte Ejecutivo de Mantenimiento", ln=1, align='L')
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", 'I', 9)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Generado automaticamente - Pagina {self.page_no()}", 0, 0, 'C')

def generate_pdf_from_summary(summary_data: dict) -> bytes:
    """Genera un PDF en memoria a partir de los datos JSON con diseño premium"""
    pdf = PremiumPDF()
    pdf.add_page()
    
    start_date = summary_data['period_start'][:10]
    end_date = summary_data['period_end'][:10]
    
    # Calcular si es mensual o semanal basado en la diferencia de dias
    try:
        d1 = datetime.strptime(start_date, "%Y-%m-%d")
        d2 = datetime.strptime(end_date, "%Y-%m-%d")
        days_diff = (d2 - d1).days
        tipo_reporte = "Mensual" if days_diff > 20 else "Semanal"
    except:
        tipo_reporte = "Ejecutivo"

    # Tarjeta de Periodo
    pdf.set_fill_color(240, 244, 248) # Fondo gris muy claro
    pdf.set_draw_color(200, 210, 220)
    pdf.set_xy(15, 45)
    pdf.cell(180, 12, "", border=1, fill=True, align='C')
    pdf.set_xy(15, 46)
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(23, 93, 182) # Color primary blue
    pdf.cell(180, 10, txt=f"Resumen {tipo_reporte} ({start_date} al {end_date})", align='C')
    
    pdf.ln(20)
    
    # Metricas en recuadros
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(50, 60, 70)
    pdf.set_x(15)
    pdf.cell(0, 8, txt="Metricas Generales:", ln=1)
    
    # Dibujar metricas
    pdf.set_fill_color(255, 255, 255)
    pdf.set_font("Arial", '', 11)
    
    metrics = [
        ("Total de Alertas", str(summary_data['total_alerts'])),
        ("Total de Tickets", str(summary_data['total_tickets'])),
        ("Pico Max. Corriente", f"{summary_data['peak_current']} A"),
    ]
    
    x_start = 15
    y_start = pdf.get_y() + 2
    for title, val in metrics:
        pdf.set_xy(x_start, y_start)
        pdf.set_fill_color(248, 250, 252)
        pdf.rect(x_start, y_start, 55, 20, 'DF')
        
        pdf.set_xy(x_start, y_start + 3)
        pdf.set_font("Arial", '', 9)
        pdf.set_text_color(100, 110, 120)
        pdf.cell(55, 5, txt=title, align='C')
        
        pdf.set_xy(x_start, y_start + 9)
        pdf.set_font("Arial", 'B', 14)
        pdf.set_text_color(15, 111, 209)
        pdf.cell(55, 8, txt=val, align='C')
        x_start += 60
        
    pdf.set_y(y_start + 25)
    
    branches = ", ".join(summary_data['affected_branches']) if summary_data['affected_branches'] else "Ninguno"
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(50, 60, 70)
    pdf.set_x(15)
    pdf.cell(0, 8, txt="Ramales Afectados:", ln=0)
    pdf.set_font("Arial", '', 11)
    pdf.set_text_color(100, 110, 120)
    pdf.set_x(55)
    pdf.cell(0, 8, txt=branches, ln=1)
    
    pdf.ln(10)
    
    # Tabla de Tickets
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(23, 93, 182)
    pdf.set_x(15)
    pdf.cell(0, 10, txt="Detalle de Tickets Creados", ln=1)
    pdf.ln(2)
    
    # Cabecera tabla
    pdf.set_fill_color(13, 36, 64)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 10)
    pdf.set_x(15)
    pdf.cell(40, 10, "Ticket", 1, 0, 'C', 1)
    pdf.cell(60, 10, "Incidente", 1, 0, 'C', 1)
    pdf.cell(40, 10, "Prioridad", 1, 0, 'C', 1)
    pdf.cell(40, 10, "Estado", 1, 1, 'C', 1)
    
    # Filas
    pdf.set_font("Arial", '', 9)
    pdf.set_text_color(50, 50, 50)
    pdf.set_fill_color(248, 250, 252)
    fill = False
    
    if not summary_data['tickets_list']:
        pdf.set_x(15)
        pdf.cell(180, 10, "No se registraron tickets en este periodo.", 1, 1, 'C')
    else:
        for t in summary_data['tickets_list']:
            pdf.set_x(15)
            issue_type = t.get('issue_type', '')
            issue_type_es = INCIDENT_TRANSLATIONS.get(issue_type, issue_type.capitalize().replace('_', ' '))
            pdf.cell(40, 10, t['ticket_code'], 1, 0, 'C', fill)
            pdf.cell(60, 10, issue_type_es, 1, 0, 'C', fill)
            pdf.cell(40, 10, t['priority'], 1, 0, 'C', fill)
            pdf.cell(40, 10, t['status'], 1, 1, 'C', fill)
            fill = not fill
        
    out = pdf.output(dest='S')
    if isinstance(out, str):
        return out.encode('latin1')
    return bytes(out)

async def generate_and_save_report(days: int = 7):
    """Llamado por el cron job o manualmente para procesar el periodo, guardar en BD y enviar a n8n"""
    summary = get_period_data(days=days)
    
    year = datetime.now().year
    month = datetime.now().month
    week = datetime.now().isocalendar()[1]
    
    report_code = f"REP-{year}-M{month}" if days >= 28 else f"REP-{year}-W{week}"
    
    # Guardar solo el JSON en Supabase (Zero-Storage para PDFs)
    client = get_supabase_client()
    report_row = {
        "report_code": report_code,
        "period_start": summary["period_start"],
        "period_end": summary["period_end"],
        "total_alerts": summary["total_alerts"],
        "total_tickets": summary["total_tickets"],
        "peak_current": summary["peak_current"],
        "affected_branches": summary["affected_branches"],
        "summary_data": summary,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        response = client.table("reports").upsert(report_row, on_conflict="report_code").execute()
        if response.data:
            report_id = response.data[0]["id"]
            logger.info(f"Reporte {report_code} guardado en BD con ID {report_id}")
            
            # Enviar la notificacion via n8n
            backend_url = os.getenv("SAFYRA_BACKEND_URL", "http://127.0.0.1:8000")
            download_url = f"{backend_url}/api/reports/{report_id}/download"
            
            # Formato requerido por el nodo Code de n8n para correos
            payload = {
                "email_recipients": [{"email": "direccion@colegio.edu.pe"}],
                "notification": {
                    "email_subject": f"[SafyraShield] Reporte Semanal {report_code}",
                    "email_html": f"<h1>Reporte Semanal Generado</h1>"
                                  f"<p>El reporte semanal <b>{report_code}</b> se ha generado con exito.</p>"
                                  f"<p>Total de incidentes esta semana: <b>{summary['total_tickets']}</b></p>"
                                  f"<br><a href='{download_url}' style='padding: 10px 15px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;'>Descargar Reporte en PDF</a>"
                                  f"<br><br><small>Nota: Requiere iniciar sesion en el sistema SafyraShield.</small>"
                }
            }
            queue_alert_notification(payload)
    except Exception as e:
        logger.error(f"Fallo al guardar o enviar el reporte: {str(e)}")
