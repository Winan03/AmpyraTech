from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def generate_weekly_report_job():
    logger.info("Iniciando generacion de reporte semanal por Cron...")
    # Aqui importaremos y llamaremos a la logica de report_service
    # Para evitar circular imports, se importa dentro de la funcion o se estructura despues
    from app.services.report_service import generate_and_save_report
    try:
        await generate_and_save_report(days=7)
        logger.info("Reporte semanal generado y enviado con exito.")
    except Exception as e:
        logger.error(f"Error generando reporte semanal: {e}")

def start_scheduler():
    # Ejecutar todos los viernes (day_of_week=4, 0 es lunes) a las 18:00 (6:00 PM)
    scheduler.add_job(
        generate_weekly_report_job,
        trigger=CronTrigger(day_of_week=4, hour=18, minute=0),
        id="weekly_report_job",
        replace_existing=True
    )
    scheduler.start()
    logger.info("APScheduler iniciado. Reportes configurados para Viernes 18:00.")

def shutdown_scheduler():
    scheduler.shutdown()
