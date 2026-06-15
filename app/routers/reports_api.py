from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from app.db.supabase import get_supabase_client
from app.services.report_service import generate_pdf_from_summary

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.get("/")
async def get_reports():
    """Lista todos los reportes historicos"""
    client = get_supabase_client()
    res = client.table("reports").select("id, report_code, period_start, period_end, total_alerts, total_tickets, peak_current, generated_at").order("generated_at", desc=True).execute()
    return {"data": res.data}

@router.get("/{report_id}/download")
async def download_report_pdf(report_id: str):
    """Renderiza on-the-fly el PDF desde el JSON almacenado"""
    client = get_supabase_client()
    res = client.table("reports").select("*").eq("id", report_id).execute()
    
    if not res.data:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
        
    report = res.data[0]
    summary_data = report.get("summary_data")
    
    if not summary_data:
        raise HTTPException(status_code=500, detail="Data del reporte corrupta")
        
    pdf_bytes = generate_pdf_from_summary(summary_data)
    
    filename = f"{report['report_code']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.post("/generate")
async def generate_manual_report(days: int = 30):
    """Endpoint para forzar la generacion del reporte (ej. por Admin)"""
    from app.services.report_service import generate_and_save_report
    await generate_and_save_report(days=days)
    return {"success": True, "message": "Reporte generado exitosamente"}
