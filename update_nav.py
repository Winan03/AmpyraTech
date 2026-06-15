import os
import glob

html_dir = r"d:\9 ciclo\2025-2\Taller integrador\Sprint 1\Avance 2\SafyraShield\app\templates"
files = glob.glob(os.path.join(html_dir, "*.html"))

new_links = """                <a class="sidebar-link" href="/tickets" data-roles="admin,auditor">
                    <span class="sidebar-icon" aria-hidden="true">TI</span>
                    <span class="sidebar-copy">
                        <strong>Tickets</strong>
                        <small>Mantenimiento</small>
                    </span>
                </a>
                <a class="sidebar-link" href="/reports" data-roles="admin,auditor">
                    <span class="sidebar-icon" aria-hidden="true">RE</span>
                    <span class="sidebar-copy">
                        <strong>Reportes</strong>
                        <small>Resumen ejecutivo</small>
                    </span>
                </a>"""

for file in files:
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()

    # Skip files without sidebar
    if '<nav class="sidebar-nav"' not in content:
        continue

    # 1. Hide Alerts from auditor
    content = content.replace('<a class="sidebar-link" href="/alerts">', '<a class="sidebar-link" href="/alerts" data-roles="admin">')
    content = content.replace('<a class="sidebar-link active" href="/alerts">', '<a class="sidebar-link active" href="/alerts" data-roles="admin">')
    
    # 2. Hide History from auditor
    content = content.replace('<a class="sidebar-link" href="/history" data-roles="admin,auditor">', '<a class="sidebar-link" href="/history" data-roles="admin">')
    content = content.replace('<a class="sidebar-link active" href="/history" data-roles="admin,auditor">', '<a class="sidebar-link active" href="/history" data-roles="admin">')
    
    # 3. Add Tickets and Reports before Schedule if they don't exist
    if 'href="/tickets"' not in content:
        # We find schedule link and insert before it
        schedule_idx = content.find('<a class="sidebar-link" href="/schedule"')
        if schedule_idx == -1:
            schedule_idx = content.find('<a class="sidebar-link active" href="/schedule"')
            
        if schedule_idx != -1:
            content = content[:schedule_idx] + new_links + "\n" + content[schedule_idx:]

    with open(file, "w", encoding="utf-8") as f:
        f.write(content)

print("HTML files updated.")
