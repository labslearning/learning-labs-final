import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q

# Importaciones Locales
from .models import ImportBatch
from .services.importer import ImportService
from .services.rollback import RollbackService

# Configuración de Logger para traza de errores en servidor
logger = logging.getLogger(__name__)

# --- CONTROL DE ACCESO ---
def is_staff_or_superuser(user):
    return user.is_staff or user.is_superuser

# ========================================================
#  1. VISTAS DE INGESTA (WIZARD PASO 1 y 2)
# ========================================================

@login_required
@user_passes_test(is_staff_or_superuser)
def import_upload_view(request):
    """
    PASO 1: SUBIDA DE ARCHIVO (Upload & Analyze)
    Recibe el Excel, detecta metadatos y crea el lote en estado 'MAPPING'.
    """
    if request.method == 'POST' and request.FILES.get('archivo'):
        archivo = request.FILES['archivo']
        service = ImportService()
        
        try:
            # Ejecutamos Fase 1: Análisis y Staging
            batch, suggestions = service.create_batch(
                file_obj=archivo, 
                user=request.user, 
                model_target='HistorialAcademico'
            )
            
            # Guardamos estado en sesión para persistencia entre pasos
            request.session['import_batch_id'] = str(batch.id)
            # Nota: 'suggestions' puede ser grande, en sistemas muy masivos usaríamos Redis/DB
            # pero para archivos administrativos estándar (<10MB), la sesión está bien.
            request.session['import_suggestions'] = suggestions
            
            logger.info(f"Usuario {request.user} subió lote {batch.id} con {batch.total_filas} filas.")
            messages.success(request, f"✅ Archivo analizado correctamente: {batch.total_filas} filas detectadas.")
            
            return redirect('import_mapping')
            
        except ValueError as e:
            logger.warning(f"Error de validación en subida: {str(e)}")
            messages.warning(request, f"⚠️ Atención: {str(e)}")
        except Exception as e:
            logger.error(f"Error crítico en subida: {str(e)}", exc_info=True)
            messages.error(request, f"⛔ Error del sistema: {str(e)}")
            
    return render(request, 'admin/import/upload.html')

@login_required
@user_passes_test(is_staff_or_superuser)
def import_mapping_view(request):
    """
    PASO 2: MAPEO INTELIGENTE (Mapping & Execution)
    Interfaz visual donde el usuario conecta columnas Excel -> BD.
    """
    batch_id = request.session.get('import_batch_id')
    suggestions = request.session.get('import_suggestions')
    
    # Protección de flujo: Si no hay ID en sesión, volver al inicio
    if not batch_id:
        messages.warning(request, "La sesión de importación ha expirado. Por favor sube el archivo nuevamente.")
        return redirect('import_upload')

    batch = get_object_or_404(ImportBatch, id=batch_id)
    
    # Procesamiento del Formulario de Mapeo
    if request.method == 'POST':
        mapping_json = request.POST.get('mapping_data')
        if not mapping_json:
            messages.error(request, "No se recibieron datos de mapeo.")
            return redirect('import_mapping')

        try:
            mapping_dict = json.loads(mapping_json)
            service = ImportService()
            
            # Ejecutamos Fase 2: Escritura en Base de Datos
            count = service.execute_import(batch_id, mapping_dict)
            
            # Limpieza de sesión post-éxito
            if 'import_batch_id' in request.session: del request.session['import_batch_id']
            if 'import_suggestions' in request.session: del request.session['import_suggestions']
            
            messages.success(request, f"🚀 ¡Proceso completado! Se han creado/actualizado {count} historiales académicos.")
            
            # Redirigimos al Historial para que vea el resultado final y tenga opción de Rollback
            return redirect('import_history') 
            
        except Exception as e:
            logger.error(f"Error importando lote {batch_id}: {str(e)}", exc_info=True)
            messages.error(request, f"❌ Error durante la importación: {str(e)}")
            # No redirigimos para permitir reintento sin resubir

    # Datos para el Template
    sample_row = batch.filas_staging.first()
    preview_data = sample_row.data_original if sample_row else {}

    # Materias Estándar (Idealmente vendrían de un modelo Materia.objects.all())
    materias_comunes = [
        'Matemáticas', 'Español', 'Inglés', 'Ciencias Naturales', 'Ciencias Sociales', 
        'Física', 'Química', 'Filosofía', 'Educación Física', 'Artes', 'Informática', 
        'Ética', 'Religión', 'Economía', 'Política'
    ]

    context = {
        'batch': batch,
        'suggestions': suggestions or {}, 
        'preview': preview_data,
        'materias': materias_comunes
    }
    return render(request, 'admin/import/mapping.html', context)

# ========================================================
#  2. VISTAS DE AUDITORÍA Y SEGURIDAD (History & Rollback)
# ========================================================

@login_required
@user_passes_test(is_staff_or_superuser)
def import_history_view(request):
    """
    DASHBOARD DE AUDITORÍA:
    Muestra bitácora de operaciones con paginación y optimización de consultas.
    """
    # Optimización: select_related trae los datos del usuario en la misma query (evita N+1 problem)
    queryset = ImportBatch.objects.select_related('usuario').all().order_by('-creado_en')
    
    # Paginación (15 registros por página)
    paginator = Paginator(queryset, 15) 
    page_number = request.GET.get('page')
    lotes = paginator.get_page(page_number)

    return render(request, 'admin/import/history.html', {'lotes': lotes})

@login_required
@user_passes_test(is_staff_or_superuser)
def import_rollback_view(request, batch_id):
    """
    ACCIÓN CRÍTICA: ROLLBACK
    Ejecuta la reversión de un lote a través del RollbackService.
    """
    if request.method == "POST":
        service = RollbackService()
        try:
            # Ejecutar reversión
            stats = service.revert_batch(batch_id)
            
            # Mensaje detallado HTML safe
            msg = (
                f"✅ <strong>Operación Exitosa:</strong> Reversión completada en {stats.get('duration_ms', 0)}ms.<br>"
                f"🗑️ Eliminados: {stats['deleted']} registros.<br>"
                f"♻️ Restaurados: {stats['restored']} versiones previas."
            )
            messages.success(request, msg)
            logger.info(f"Admin {request.user} revirtió lote {batch_id}: {stats}")
            
        except ValueError as e:
            messages.warning(request, f"⚠️ No se pudo ejecutar: {str(e)}")
        except Exception as e:
            logger.error(f"Fallo crítico en rollback {batch_id}: {str(e)}", exc_info=True)
            messages.error(request, f"⛔ Error Crítico: {str(e)}")
            
    return redirect('import_history')