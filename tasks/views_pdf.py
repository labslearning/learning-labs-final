# tasks/views_pdf.py
import markdown
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from weasyprint import HTML, CSS # Importamos WeasyPrint

# Importamos tu orquestador
from .ai.orchestrator import ai_orchestrator
from .ai.constants import ACCION_ANALISIS_GLOBAL_BIENESTAR

@login_required
def generar_pdf_bienestar(request):
    """
    Genera el PDF Profesional usando WeasyPrint + Stratos AI.
    """
    
    # 1. LLAMADA A STRATOS AI (Tu cerebro existente)
    # Usamos el prompt "EXTENSO Y PROFESIONAL" que configuramos en el paso anterior
    respuesta_ia = ai_orchestrator.process_request(
        user=request.user,
        action_type=ACCION_ANALISIS_GLOBAL_BIENESTAR,
        user_query="",
        params={}
    )

    if not respuesta_ia.get('success'):
        return HttpResponse(f"Error generando reporte IA: {respuesta_ia.get('content')}", status=500)

    # 2. PROCESAMIENTO MARKDOWN
    # Convertimos el texto de la IA en HTML limpio para inyectarlo en el reporte
    texto_markdown = respuesta_ia.get('content', '')
    contenido_html_cuerpo = markdown.markdown(
        texto_markdown,
        extensions=['extra', 'nl2br', 'sane_lists']
    )

    # 3. CONTEXTO PARA EL TEMPLATE
    contexto = {
        'contenido_html': contenido_html_cuerpo,
        'objetivo': request.user, # Institucional
        'solicitante': request.user,
        'tipo_reporte': 'AUDITORÍA ESTRATÉGICA DE BIENESTAR',
        'fecha_impresion': timezone.now(),
        'query_original': 'Diagnóstico de Clima Escolar y Rutas de Mejora'
    }

    # 4. RENDERIZADO CON WEASYPRINT
    # Renderizamos el HTML como string usando tu template "tasks/templates/pdf/ai_report_template.html"
    html_string = render_to_string('pdf/ai_report_template.html', contexto, request=request)

    # Configuración de respuesta HTTP como PDF
    response = HttpResponse(content_type='application/pdf')
    filename = f"Informe_Stratos_Bienestar_{timezone.now().strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # Generación del PDF
    # base_url es importante para que cargue imágenes locales si las tuvieras
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
    
    return response