# tasks/views_shadow.py

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from .models import (
    Nota, NotaDetallada, Observacion, Asistencia, 
    ActaInstitucional, Seguimiento
)

User = get_user_model()

# --- CONFIGURACIÓN BI (Business Intelligence) ---
VALOR_PENSIÓN_MENSUAL = 450000 
MESES_PERDIDA_PROMEDIO = 6      
COSTO_LITIGIO_BASE = 5000000    

@login_required
def shadow_tenant_dashboard(request):
    """
    🛡️ COMMAND CENTER: TORRE DE CONTROL DE RIESGO
    Muestra: Dinero en Juego, Riesgo Legal y Operación Diaria.
    """
    # 1. 🔍 MOTOR DE RIESGO (CRUCE DE DATOS OPTIMIZADO)
    
    # A. Riesgo Académico: Unificamos lógica de detección
    # Estudiantes con promedio < 3.2 en CUALQUIER sistema
    umbral_academico = 3.2
    
    ids_academico = set(
        Nota.objects.values('estudiante').annotate(p=Avg('valor')).filter(p__lt=umbral_academico).values_list('estudiante', flat=True)
    ) | set(
        NotaDetallada.objects.values('estudiante').annotate(p=Avg('valor')).filter(p__lt=umbral_academico).values_list('estudiante', flat=True)
    )
    
    # B. Riesgo Legal: Faltas Graves o Tipo 'Convivencia'
    ids_legal = set(Observacion.objects.filter(tipo__in=['CONVIVENCIA', '2', '3']).values_list('estudiante', flat=True))
    
    # C. Riesgo Ausentismo: > 5 Fallas
    ids_ausentismo = set(Asistencia.objects.filter(estado='FALLA').values('estudiante').annotate(c=Count('id')).filter(c__gte=5).values_list('estudiante', flat=True))

    # 2. 🧠 FILTRO INTELIGENTE: ¿QUIÉN YA ESTÁ SIENDO ATENDIDO?
    # Excluimos estudiantes con seguimiento en los últimos 15 días (Riesgo Mitigado)
    fecha_limite = timezone.now() - timedelta(days=15)
    ids_atendidos = set(Seguimiento.objects.filter(fecha__gte=fecha_limite).values_list('estudiante', flat=True))
    
    # Riesgo BRUTO (Todos) vs Riesgo NETO (Sin atender)
    total_riesgo_ids = ids_academico | ids_legal | ids_ausentismo
    riesgo_neto_ids = total_riesgo_ids - ids_atendidos
    
    count_riesgo_bruto = len(total_riesgo_ids)
    count_riesgo_neto = len(riesgo_neto_ids) # Este es el número que debe bajar a 0

    # 3. 💰 CÁLCULO DE IMPACTO (BI)
    # KPIs Financieros sobre el Riesgo NETO (Lo que realmente se puede perder hoy)
    kpi_dinero = count_riesgo_neto * VALOR_PENSIÓN_MENSUAL * MESES_PERDIDA_PROMEDIO
    
    # Estimación legal conservadora
    kpi_legal = (len(ids_legal - ids_atendidos) * 0.20) * COSTO_LITIGIO_BASE 

    # 4. 📊 CONTEXTO GLOBAL
    total_alumnos = User.objects.filter(perfil__rol='ESTUDIANTE').count() or 1
    tasa_riesgo = round((count_riesgo_neto / total_alumnos) * 100, 1)

    # 5. 🚨 OPERACIÓN: CASOS PRIORITARIOS
    ultimos_casos = ActaInstitucional.objects.select_related('implicado').order_by('-fecha')[:8]

    context = {
        "kpis": {
            "dinero": kpi_dinero,
            "legal": kpi_legal,
            "total_riesgo": count_riesgo_neto, # Mostramos el Neto para impulsar acción
            "riesgo_mitigado": count_riesgo_bruto - count_riesgo_neto,
            "tasa_riesgo": tasa_riesgo
        },
        "conteos": {
            "academico": len(ids_academico),
            "legal": len(ids_legal),
            "ausentismo": len(ids_ausentismo)
        },
        "ultimos_casos": ultimos_casos,
        "config": {"pension": VALOR_PENSIÓN_MENSUAL, "meses": MESES_PERDIDA_PROMEDIO},
        "fecha": timezone.now()
    }
    return render(request, 'admin/shadow_dashboard.html', context)

@login_required
def shadow_case_detail(request, acta_id):
    """
    📂 DOSSIER FORENSE 360° (EXPEDIENTE DIGITAL UNIFICADO)
    Integra: Acta Actual + Historial Legal + Bitácora Psicológica + Notas.
    """
    acta = get_object_or_404(ActaInstitucional, id=acta_id)
    estudiante = acta.implicado

    # 1. INTEGRACIÓN DE FUENTES (DATA FUSION)
    seguimientos = Seguimiento.objects.filter(estudiante=estudiante).order_by('-fecha')
    otras_actas = ActaInstitucional.objects.filter(implicado=estudiante).exclude(id=acta.id).order_by('-fecha')
    observaciones = Observacion.objects.filter(estudiante=estudiante).order_by('-fecha_creacion')

    # 2. SCORING EN TIEMPO REAL (Unificado)
    notas_legacy = Nota.objects.filter(estudiante=estudiante)
    notas_new = NotaDetallada.objects.filter(estudiante=estudiante)
    
    # Promedio ponderado inteligente
    p1 = notas_legacy.aggregate(Avg('valor'))['valor__avg']
    p2 = notas_new.aggregate(Avg('valor'))['valor__avg']
    promedio = p2 if p2 else (p1 if p1 else 0)
    
    perdidas = notas_legacy.filter(valor__lt=3.5).count() + notas_new.filter(valor__lt=3.5).count()
    graves = observaciones.filter(tipo__in=['CONVIVENCIA', '2', '3']).count()
    fallas = Asistencia.objects.filter(estudiante=estudiante, estado='FALLA').count()

    # 3. MOTOR DE RECOMENDACIÓN (IA SIMULADA)
    if perdidas >= 3 or graves >= 1 or fallas >= 8:
        nivel, color, accion = "CRÍTICO", "danger", "⚠️ ACTIVAR RUTA DE PERMANENCIA (RIESGO DESERCIÓN)."
    elif perdidas >= 1 or fallas >= 3:
        nivel, color, accion = "ALERTA", "warning", "Compromiso académico y citación a acudiente."
    else:
        nivel, color, accion = "BAJO", "success", "Continuar monitoreo preventivo."

    context = {
        "acta": acta,
        "estudiante": estudiante,
        "dossier": {
            "seguimientos": seguimientos,
            "otras_actas": otras_actas,
            "observaciones_recent": observaciones[:5],
            "total_observaciones": observaciones.count()
        },
        "metrics": {
            "promedio": round(promedio, 2),
            "perdidas": perdidas,
            "graves": graves,
            "fallas": fallas
        },
        "estado": {"nivel": nivel, "color": color, "accion": accion}
    }
    return render(request, 'admin/shadow_case_detail.html', context)