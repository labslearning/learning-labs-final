# -*- coding: utf-8 -*-
from django.db.models import Avg, Count, Q, Min, Max
import json
from .models import Observacion, Institucion # <--- Importante importar Observacion
from .models import Seguimiento # Asegúrate que importas tus modelos correctamente
from django.core.serializers.json import DjangoJSONEncoder
# --- AGREGA ESTO AL PRINCIPIO DE tasks/views.py ---
from django.template.loader import get_template  # <--- FALTABA ESTO
from django.template import TemplateDoesNotExist # <--- FALTABA ESTO
from django.conf import settings                 # <--- FALTABA ESTO
import os
from django.views.decorators.csrf import csrf_exempt
#agregando los cambios de deepseek
from openai import OpenAI    # pip install openai
from pypdf import PdfReader #pdf


from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
#Aqui importaciones para hacer el pdf con el reporte de la AI 
import markdown # <--- NECESARIO
from django.utils.html import mark_safe
#Hasta aqui

from .ai.orchestrator import ai_orchestrator
#from .ai.constants import ACCION_MEJORAS_ESTUDIANTE
from tasks.ai.constants import (
    ACCION_CHAT_SOCRATICO,
    ACCION_ANALISIS_CONVIVENCIA,
    ACCION_CUMPLIMIENTO_PEI,
    ACCION_MEJORAS_DOCENTE,
    ACCION_MEJORAS_ESTUDIANTE,      # <--- Fíjate que aquí ya la incluimos
    ACCION_APOYO_ACUDIENTE,
    ACCION_ANALISIS_GLOBAL_BIENESTAR, 
    ACCION_MEJORA_STAFF_ACADEMICO   # Agrego esta por seguridad si la usas
)


from tasks.ai.context_builder import context_builder  # <--- ESTO ES LO QUE FALTA
# 1. IMPORTACIONES AÑADIDAS
from django.contrib.auth import login, logout, authenticate, get_user_model, update_session_auth_hash
from django.db import IntegrityError, transaction
# --- INICIO DE CIRUGÍA 1: Importar Avg (Sin cambios) ---
from django.db.models import Q, Avg
# --- FIN DE CIRUGÍA 1 ---
from django.http import JsonResponse, HttpResponseNotAllowed
# --- INICIO DE MODIFICACIÓN 1: Añadir Importaciones ---
from django.http import HttpResponse, Http404
from django.template.loader import render_to_string
# --- FIN DE MODIFICACIÓN 1 ---
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta, date  # 🩺 CIRUGÍA: Se aseguró 'date'
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
from decimal import Decimal, ROUND_HALF_UP
import json
import csv
import io
import decimal
import logging
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from operator import itemgetter
from django.urls import reverse
from django.core.paginator import Paginator # Añadido en paso anterior
from django.db.models import Q, Count # Necesitas Count para ordenar por número de miembros
from .forms import UserEditForm, EditarPerfilForm

# --- Modelos: Se añade Acudiente y Observacion ---
from .models import (
    Question, Answer, Perfil, Curso, Nota, Materia,
    Periodo, AsignacionMateria, Matricula, ComentarioDocente,
    ActividadSemanal, LogroPeriodo, Convivencia, GRADOS_CHOICES,
    Post, Comment, AuditLog,Report, Acudiente, Institucion, 
    Observacion, # <--- 🩺 CIRUGÍA: Modelo añadido previamente
    Asistencia, MensajeInterno, Notificacion, Reaction, Follow, UserLogro, SocialGroup # <--- 🩺 FASE 4: NUEVOS MODELOS AÑADIDOS
)
from django.contrib.contenttypes.models import ContentType
# ===================================================================
# 🩺 INICIO DE CIRUGÍA: Importaciones añadidas para el Plan
# (Añadidas en pasos anteriores )
# ===================================================================
from .models import BoletinArchivado
from django.core.files.base import ContentFile
# ===================================================================
# 🩺 FIN DE CIRUGÍA
# ===================================================================

# --- Formularios: Se añaden los nuevos formularios ---
from .forms import (
    BulkCSVForm, PasswordChangeFirstLoginForm, ProfileSearchForm, 
    QuestionForm, AnswerForm,
    ObservacionForm, # <--- 🩺 CIRUGÍA: Form añadido previamente
    MensajeForm, 
    Post, 
    PostForm,
    Comment,
    CommentForm,
    SocialGroupForm, 
     
     # <--- 🩺 FASE 4: FORMULARIO CHAT AÑADIDO
)

# --- Utilidades: Se añaden las nuevas funciones de ayuda ---
from .utils import (
    generar_username_unico, generar_contrasena_temporal, asignar_curso_por_grado,
    crear_notificacion, notificar_acudientes # <--- 🩺 FASE 4: UTILIDADES NOTIFICACION AÑADIDAS
)

# --- Decoradores: Se añade el nuevo decorador ---
from .decorators import role_required

# --- INICIO DE MODIFICACIÓN 1 (continuación): Añadir Importaciones ---
from .services import get_student_report_context # Usamos el nuevo servicio
# --- FIN DE MODIFICACIÓN 1 ---

####Seguridad 

from django.contrib.auth.decorators import login_required
from .utils import Sentinel # Tu motor de seguridad


# Obtener el modelo de usuario de forma segura
User = get_user_model()

# Configuración de logging
logger = logging.getLogger(__name__)

# --- INICIO DE MODIFICACIÓN 1 (continuación): Importar WeasyPrint ---

# --- FIN DE MODIFICACIÓN 1 ---


# Historial Matricula puede que aún no esté en tu models.py; lo usamos si existe
try:
    from .models import HistorialMatricula
    _HISTORIAL_MATRICULA_DISPONIBLE = True
except ImportError:
    _HISTORIAL_MATRICULA_DISPONIBLE = False

# Valor por defecto para la capacidad de los cursos
CAPACIDAD_POR_DEFECTO = getattr(settings, 'CAPACIDAD_CURSOS_DEFAULT', 40)

# ########################################################################## #
# ############# INICIO DEL CAMBIO DE CONTRASEÑA ############################ #
# ########################################################################## #

# Contraseña temporal unificada para todos los nuevos usuarios.
DEFAULT_TEMP_PASSWORD = getattr(settings, 'DEFAULT_TEMP_PASSWORD', '123456')

# ########################################################################## #
# ############### FIN DEL CAMBIO DE CONTRASEÑA ############################# #
# ########################################################################## #

# Constantes de negocio centralizadas
PESOS_NOTAS = {1: Decimal('0.20'), 2: Decimal('0.30'), 3: Decimal('0.30'), 4: Decimal('0.20')}
ESCALA_MIN = Decimal('0.0')
ESCALA_MAX = Decimal('5.0')
NOTA_APROBACION = Decimal('3.5')
NUM_NOTAS = (1, 2, 3, 4)
TWO_PLACES = Decimal('0.01')

# --- Normalización de grados para registro masivo
_GRADOS_VALIDOS = set(dict(GRADOS_CHOICES).keys())
_NOMBRE_A_CLAVE = {v.upper(): k for k, v in GRADOS_CHOICES}
def _normalizar_grado(g):
    """
    Acepta clave válida (p.ej. '5') o nombre (p.ej. 'QUINTO').
    Devuelve la clave aceptada por el modelo o None si no coincide.
    """
    if g in _GRADOS_VALIDOS:
        return g
    g_up = (g or "").strip().upper()
    return _NOMBRE_A_CLAVE.get(g_up)

# Helpers de negocio
def _anio_escolar_actual():
    """
    Devuelve un string tipo '2025-2026' según fecha actual (jul-dic→ y-(y+1), ene-jun → (y-1)-y).
    Ajusta a tu calendario si usas otra regla.
    """
    hoy = timezone.now().date()
    y = hoy.year
    if hoy.month >= 7:
        return f"{y}-{y + 1}"
    else:
        return f"{y - 1}-{y}"

def _secciones_disponibles(anio_escolar=None):
    qs = Curso.objects.exclude(seccion__isnull=True).exclude(seccion__exact='')
    if anio_escolar:
        qs = qs.filter(anio_escolar=anio_escolar)
    return sorted(list(set(qs.values_list('seccion', flat=True))))

def _siguiente_letra(secciones_existentes):
    """
    Dada una lista/set de secciones existentes ['A','B', 'C'], devuelve la siguiente ('D').
    Si se acaban, genera 'X#'.
    """
    letras = [chr(i) for i in range(ord('A'), ord('Z') + 1)]
    existing = set([s for s in secciones_existentes if s])
    for letra in letras:
        if letra not in existing:
            return letra
    return f"X{len(existing) + 1}"

def _capacidad_curso(curso):
    """
    Obtiene capacidad_maxima si existe; por defecto CAPACIDAD_POR_DEFECTO.
    """
    return getattr(curso, 'capacidad_maxima', CAPACIDAD_POR_DEFECTO) or CAPACIDAD_POR_DEFECTO

def _curso_esta_completo(curso):
    """
    Si el modelo tiene método esta_completo(), úsalo; si no, calcula por matrículas activas.
    """
    if hasattr(curso, 'esta_completo') and callable(getattr(curso, 'esta_completo')):
        try:
            return curso.esta_completo()
        except Exception as e:
            logger.exception("Error en curso.esta_completo (%s): %s", getattr(curso, 'id', 's/n'), e)
    ocupacion = Matricula.objects.filter(curso=curso, activo=True).count()
    return ocupacion >= _capacidad_curso(curso)

def _obtener_o_crear_curso_libre(grado, anio_escolar):
    """
    Busca curso del grado/año con cupo; si no existe o están llenos, crea nueva sección.
    """
    cursos = list(Curso.objects.filter(grado=grado, anio_escolar=anio_escolar).order_by('seccion'))
    for c in cursos:
        if not _curso_esta_completo(c):
            return c
    # Intentar crear un nuevo curso de forma segura
    with transaction.atomic():
        secciones = [c.seccion for c in cursos]
        nueva = _siguiente_letra(secciones)
        try:
            return Curso.objects.create(
                nombre=f"{dict(GRADOS_CHOICES).get(grado, str(grado))} {nueva}",
                grado=grado, seccion=nueva, anio_escolar=anio_escolar,
                capacidad_maxima=CAPACIDAD_POR_DEFECTO, activo=True
            )
        except IntegrityError:
            # Si otro proceso creó el curso en paralelo, lo recuperamos
            return Curso.objects.get(grado=grado, seccion=nueva, anio_escolar=anio_escolar)

def _obtener_grados_por_nivel():
    """
    Función que define los grados para cada nivel.
    Esto permite una configuración más limpia y centralizada.
    """
    return {
        'preescolar': ['PREKINDER', 'KINDER', 'JARDIN', 'TRANSICION'],
        'primaria': ['1', '2', '3', '4', '5'],
        'bachillerato': ['6', '7', '8', '9', '10', '11']
    }


# Vistas públicas
def home(request):
    categories = [
        {'icon': 'fa-language', 'title': 'Inglés', 'desc': 'Aprende inglés con nuestro método acelerado'},
        {'icon': 'fa-calculator', 'title': 'Matemáticas', 'desc': 'Domina las matemáticas desde cero'},
        {'icon': 'fa-flask', 'title': 'Física y Química', 'desc': 'Aprende con experimentos prácticos'},
        {'icon': 'fa-gamepad', 'title': 'Desarrollo de Videojuegos', 'desc': 'Crea tus propios juegos'},
        {'icon': 'fa-code', 'title': 'Programación', 'desc': 'Aprende los lenguajes más demandados'},
        {'icon': 'fa-robot', 'title': 'Inteligencia Artificial', 'desc': 'Domina las tecnologías del futuro'},
        {'icon': 'fa-school', 'title': 'ICFES', 'desc': 'Prepárate para tus pruebas con éxito'}
    ]
    return render(request, "home.html", {'categories': categories})

def signup(request):
    if request.method == 'GET':
        return render(request, "signup.html", {'form': UserCreationForm()})
    form = UserCreationForm(request.POST)
    if form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
                Perfil.objects.create(user=user, rol='ESTUDIANTE')
                login(request, user)
                messages.success(request, '¡Cuenta creada exitosamente!')
                return redirect('dashboard_estudiante')
        except IntegrityError:
            messages.error(request, 'El nombre de usuario ya existe.')
            return render(request, 'signup.html', {'form': form})
    messages.error(request, 'Hubo un error con tu registro. Verifica los campos.')
    return render(request, 'signup.html', {'form': form})

def tasks(request):
    return render(request, 'tasks.html')

def signout(request):
    logout(request)
    messages.success(request, 'Sesión cerrada correctamente')
    return redirect('home')

##aqui 

@csrf_protect
def signin(request):
    # --- GET ---
    if request.method == 'GET':
        return render(request, "signin.html", {
            'form': AuthenticationForm(request)
        })

    # --- POST ---
    form = AuthenticationForm(request, data=request.POST)

    if not form.is_valid():
        # Log detallado para producción
        for error in form.non_field_errors():
            logger.warning(f"Fallo de autenticación: {error}")

        messages.error(request, 'Usuario o contraseña incorrectos.')
        return render(request, 'signin.html', {'form': form})

    # 🔒 VALIDACIÓN CRÍTICA
    user = form.get_user()

    if user is None:
        logger.error("AuthenticationForm válido pero user=None")
        messages.error(request, 'Error interno de autenticación.')
        return render(request, 'signin.html', {'form': form})

    # Login seguro
    login(request, user)

    # --- CAMBIO DE CLAVE FORZADO ---
    if hasattr(user, 'perfil') and getattr(user.perfil, 'requiere_cambio_clave', False):
        messages.info(request, 'Por seguridad, debes cambiar tu contraseña.')
        return redirect('cambiar_clave')

    # --- REDIRECCIÓN NEXT SEGURA ---
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure()
    ):
        return redirect(next_url)

    # --- REDIRECCIÓN POR ROL (LÓGICA CORREGIDA) ---
    try:
        perfil = user.perfil
        rol = perfil.rol

        # 1. PRIORIDAD ALTA: ADMINISTRADOR
        # Se pone primero para que 'es_director' no intercepte al admin.
        if rol == 'ADMINISTRADOR':
            return redirect('admin_dashboard')

        # 2. Staff de Bienestar
        elif rol in ['PSICOLOGO', 'COORD_CONVIVENCIA', 'COORD_ACADEMICO']:
            return redirect('dashboard_bienestar')

        # 3. Estudiantes y Acudientes
        elif rol == 'ESTUDIANTE':
            return redirect('dashboard_estudiante')
        elif rol == 'ACUDIENTE':
            return redirect('dashboard_acudiente')

        # 4. Docentes y Directores de Curso
        # Se deja de último. Si eres admin y director, entrarás por el 'if' de arriba.
        # Si solo eres docente/director, entrarás aquí.
        elif rol == 'DOCENTE' or getattr(perfil, 'es_director', False):
            return redirect('dashboard_docente')

    except Exception as e:
        logger.exception(f"Error redireccionando por rol: {e}")
        messages.warning(request, 'Error en el perfil del usuario.')

    # --- FALLBACK FINAL ---
    return redirect('home')



def english(request): return render(request, 'english.html')
def english2(request): return render(request, 'english2.html')
def english3(request): return render(request, 'english3.html')
def english4(request): return render(request, 'english4.html')
def ai(request): return render(request, 'ai.html')

# Foro
def forum(request):
    questions = Question.objects.all().order_by('-created_at')
    return render(request, 'forum.html', {'questions': questions})

@login_required
def ask_question(request):
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.user = request.user
            question.save()
            messages.success(request, 'Pregunta publicada correctamente')
            return redirect('forum')
    else:
        form = QuestionForm()
    return render(request, 'ask_question.html', {'form': form})

def question_detail(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    answers = question.answers.all()
    return render(request, 'question_detail.html', {'question': question, 'answers': answers})

@login_required
def answer_question(request, question_id):
    question = get_object_or_404(Question, pk=question_id)
    if request.method == 'POST':
        form = AnswerForm(request.POST)
        if form.is_valid():
            answer = form.save(commit=False)
            answer.question = question
            answer.user = request.user
            answer.save()
            messages.success(request, 'Respuesta publicada correctamente')
            return redirect('question_detail', question_id=question.id)
    else:
        form = AnswerForm()
    return render(request, 'answer_question.html', {'form': form, 'question': question})

# Dashboards
##DEsde aqui
# ===================================================================
# 🎓 VISTA DASHBOARD ESTUDIANTE: PREMIUM (ANALÍTICA + ASISTENCIA)
# ===================================================================

@login_required
@role_required('ESTUDIANTE')
def dashboard_estudiante(request):
    """
    Panel del Estudiante con Estadísticas Avanzadas, Asistencia y Directorio.
    """
    estudiante = request.user
    perfil_estudiante = get_object_or_404(Perfil, user=estudiante)

    # Intenta obtener la matrícula activa más reciente
    matricula = Matricula.objects.filter(estudiante=estudiante, activo=True).select_related('curso').first()
    curso = matricula.curso if matricula else None

    # Inicializar colecciones
    materias_con_notas = {}
    comentarios_docente = {}
    actividades_semanales = {}
    convivencia_notas = {}
    logros_por_materia_por_periodo = {}
    periodos_disponibles = []
    
    # --- VARIABLES PARA ESTADÍSTICAS (NUEVO) ---
    stats_materias_labels = []    
    stats_materias_promedios = [] 
    stats_periodos_labels = []    
    stats_periodos_data = []      
    conteo_ganadas = 0
    conteo_perdidas = 0
    promedio_general_acumulado = 0.0
    
    # Variables de asistencia
    porcentaje_asistencia = 100.0
    total_fallas = 0
    fallas_detalladas = []

    # Directorio Docente
    docentes_directorio = []

    if curso:
        # Obtener periodos
        periodos_disponibles = list(Periodo.objects.filter(curso=curso, activo=True).order_by('id'))

        # Obtener asignaciones (Optimizada para traer datos del docente)
        asignaciones = AsignacionMateria.objects.filter(curso=curso, activo=True).select_related('materia', 'docente')
        materias = [a.materia for a in asignaciones]

        # --- LÓGICA DIRECTORIO DE DOCENTES ---
        docentes_vistos = set()
        for asig in asignaciones:
            if asig.docente_id and asig.docente_id not in docentes_vistos:
                docente = asig.docente
                # Foto segura
                foto_url = None
                try:
                    if hasattr(docente, 'perfil') and docente.perfil.foto:
                        foto_url = docente.perfil.foto.url
                except Exception: pass

                docentes_directorio.append({
                    'id': docente.id,
                    'nombre': docente.get_full_name() or docente.username,
                    'materia_principal': asig.materia.nombre,
                    'foto_url': foto_url
                })
                docentes_vistos.add(docente.id)

        # -----------------------------------------------------------
        # 1. CÁLCULO DE ESTADÍSTICAS ACADÉMICAS
        # -----------------------------------------------------------
        notas_definitivas_qs = Nota.objects.filter(
            estudiante=estudiante, 
            materia__in=materias,
            numero_nota=5
        )

        # A. Estadísticas por Materia
        for materia in materias:
            notas_mat = [n.valor for n in notas_definitivas_qs if n.materia_id == materia.id]
            promedio_materia = 0.0

            if notas_mat:
                promedio_materia = float(sum(notas_mat)) / len(notas_mat)
                if promedio_materia >= 3.5: 
                    conteo_ganadas += 1
                else:
                    conteo_perdidas += 1
            
            stats_materias_labels.append(materia.nombre)
            stats_materias_promedios.append(round(promedio_materia, 2))

        # B. Estadísticas por Periodo
        for periodo in periodos_disponibles:
            stats_periodos_labels.append(periodo.nombre)
            notas_per = [n.valor for n in notas_definitivas_qs if n.periodo_id == periodo.id]
            
            if notas_per:
                prom_per = float(sum(notas_per)) / len(notas_per)
                stats_periodos_data.append(round(prom_per, 2))
            else:
                stats_periodos_data.append(0)

        # C. Promedio General
        if stats_materias_promedios:
            promedios_validos = [p for p in stats_materias_promedios if p > 0]
            if promedios_validos:
                promedio_general_acumulado = sum(promedios_validos) / len(promedios_validos)

        # -----------------------------------------------------------
        # 2. CÁLCULO DE ASISTENCIA DETALLADA
        # -----------------------------------------------------------
        try:
            from .models import Asistencia 
            total_clases = Asistencia.objects.filter(estudiante=estudiante, curso=curso).count()
            fallas_qs = Asistencia.objects.filter(estudiante=estudiante, curso=curso, estado='FALLA').select_related('materia').order_by('-fecha')
            total_fallas = fallas_qs.count()
            fallas_detalladas = list(fallas_qs)

            if total_clases > 0:
                porcentaje_asistencia = ((total_clases - total_fallas) / total_clases) * 100
            
            porcentaje_asistencia = round(porcentaje_asistencia, 1)
        except ImportError: pass

        # -----------------------------------------------------------
        # 3. DATOS DETALLADOS (LÓGICA ORIGINAL)
        # -----------------------------------------------------------
        for materia in materias:
            # Notas
            notes = Nota.objects.filter(estudiante=estudiante, materia=materia).select_related('periodo').order_by('periodo__id', 'numero_nota')
            notas_por_periodo = {}
            for nota in notes:
                notas_por_periodo.setdefault(nota.periodo.id, {})[nota.numero_nota] = nota

            if notas_por_periodo:
                materias_con_notas[materia] = notas_por_periodo

            # Comentarios
            comentarios = ComentarioDocente.objects.filter(estudiante=estudiante, materia=materia).order_by('-fecha_creacion')
            if comentarios.exists():
                comentarios_docente[materia.id] = comentarios

            # Actividades
            actividades = ActividadSemanal.objects.filter(curso=curso, materia=materia).order_by('-fecha_creacion')
            if actividades.exists():
                actividades_semanales[materia.id] = actividades

            # Logros
            logros_de_la_materia = LogroPeriodo.objects.filter(curso=curso, materia=materia).order_by('periodo__id', '-fecha_creacion')
            if logros_de_la_materia.exists():
                logros_por_periodo_temp = {}
                for logro in logros_de_la_materia:
                    logros_por_periodo_temp.setdefault(logro.periodo.id, []).append(logro)
                logros_por_materia_por_periodo[materia] = logros_por_periodo_temp

        # Convivencia
        convivencia_existente = Convivencia.objects.filter(estudiante=estudiante, curso=curso).select_related('periodo')
        for convivencia in convivencia_existente:
            convivencia_notas[convivencia.periodo.id] = {'valor': convivencia.valor, 'comentario': convivencia.comentario}

    # Empaquetar Estadísticas
    stats = {
        'materias_labels': json.dumps(stats_materias_labels),
        'materias_data': json.dumps(stats_materias_promedios),
        'periodos_labels': json.dumps(stats_periodos_labels),
        'periodos_data': json.dumps(stats_periodos_data),
        'ganadas': conteo_ganadas,
        'perdidas': conteo_perdidas,
        'promedio_general': round(promedio_general_acumulado, 2),
        'distribucion_data': json.dumps([conteo_ganadas, conteo_perdidas]),
        'asistencia_pct': porcentaje_asistencia,
        'total_fallas': total_fallas,
        'detalle_fallas': fallas_detalladas
    }

    context = {
        'estudiante': estudiante,
        'perfil': perfil_estudiante,
        'curso': curso,
        'matricula': matricula,
        'periodos_disponibles': periodos_disponibles,
        'materias_con_notas': materias_con_notas,
        'comentarios_docente': comentarios_docente,
        'actividades_semanales': actividades_semanales,
        'logros_por_materia_por_periodo': logros_por_materia_por_periodo,
        'convivencia_notas': convivencia_notas,
        # NUEVOS CONTEXTOS
        'stats': stats,
        'docentes': docentes_directorio
    }

    return render(request, 'dashboard_estudiante.html', context)


##Hasta aqui 
# ===================================================================
# --- INICIO DE CIRUGÍA 2: FUNCIÓN dashboard_docente MODIFICADA ---
# ===================================================================
#desde aqui 
# ===================================================================
# 👨‍🏫 VISTA DASHBOARD DOCENTE: GESTIÓN + INTELIGENCIA ACADÉMICA
# ===================================================================

@role_required('DOCENTE')
def dashboard_docente(request):
    docente = request.user
    
    # 1. Obtener asignaciones base ordenadas
    asignaciones = AsignacionMateria.objects.filter(docente=docente, activo=True)\
        .select_related('materia', 'curso').order_by('materia__nombre', 'curso__grado', 'curso__seccion')
    
    # --- ESTRUCTURAS DE DATOS ---
    materias_por_curso = {}
    total_estudiantes_unicos = set()
    estadisticas_por_materia = {} # Pestaña 2
    
    # --- VARIABLES PARA ESTADÍSTICAS AVANZADAS ---
    analisis_estudiantes = {} 
    conteo_reprobados_global = 0 
    conteo_total_fallas = 0      

    # --- INICIO DEL BUCLE PRINCIPAL ---
    for asignacion in asignaciones:
        curso = asignacion.curso
        materia_actual = asignacion.materia
        
        if not curso: continue
            
        curso_key = f"{curso.get_grado_display()} {curso.seccion}"
        
        # -------------------------------------------------------
        # BLOQUE 1: GESTIÓN DE MATERIAS (Tab 1)
        # -------------------------------------------------------
        if curso_key not in materias_por_curso:
            qs_estudiantes = Matricula.objects.filter(curso=curso, activo=True).select_related('estudiante', 'estudiante__perfil')
            
            materias_por_curso[curso_key] = {
                'curso_obj': curso,
                'materias': [], 
                'es_director': (getattr(curso, 'director', None) == docente),
                'estudiantes': qs_estudiantes,
            }
            
            for mat in qs_estudiantes:
                est = mat.estudiante
                total_estudiantes_unicos.add(est.id)
                if est.id not in analisis_estudiantes:
                    analisis_estudiantes[est.id] = {
                        'obj': est,
                        'curso_texto': curso_key,
                        'suma_notas': 0.0,
                        'num_notas': 0,
                        'fallas': 0,
                        'historial_temp': [] # Placeholder
                    }

        if materia_actual not in materias_por_curso[curso_key]['materias']:
            materias_por_curso[curso_key]['materias'].append(materia_actual)
        
        # -------------------------------------------------------
        # BLOQUE 2: ESTADÍSTICAS POR MATERIA (Tab 2)
        # -------------------------------------------------------
        if materia_actual.id not in estadisticas_por_materia:
            estadisticas_por_materia[materia_actual.id] = {
                'materia_obj': materia_actual,
                'cursos': {}
            }
        
        if curso.id not in estadisticas_por_materia[materia_actual.id]['cursos']:
            estudiantes_del_curso_ids = [m.estudiante.id for m in materias_por_curso[curso_key]['estudiantes']]
            periodos_curso = Periodo.objects.filter(curso=curso, activo=True).order_by('id')
            
            estadisticas_por_materia[materia_actual.id]['cursos'][curso.id] = {
                'curso_obj': curso,
                'periodos': {}
            }

            for periodo in periodos_curso:
                notas_qs = Nota.objects.filter(
                    estudiante_id__in=estudiantes_del_curso_ids,
                    materia=materia_actual,
                    periodo=periodo,
                    numero_nota=5 
                )
                
                promedio_materia_periodo = notas_qs.aggregate(promedio=Avg('valor'))['promedio']

                for nota in notas_qs:
                    if nota.estudiante_id in analisis_estudiantes:
                        analisis_estudiantes[nota.estudiante_id]['suma_notas'] += float(nota.valor)
                        analisis_estudiantes[nota.estudiante_id]['num_notas'] += 1

                logros_periodo = LogroPeriodo.objects.filter(
                    curso=curso, docente=docente, materia=materia_actual, periodo=periodo
                ).order_by('-fecha_creacion')

                if promedio_materia_periodo is not None or logros_periodo.exists():
                    estadisticas_por_materia[materia_actual.id]['cursos'][curso.id]['periodos'][periodo.id] = {
                        'periodo_obj': periodo,
                        'promedio': promedio_materia_periodo,
                        'logros': logros_periodo
                    }

    # -------------------------------------------------------
    # BLOQUE 3: PROCESAMIENTO FINAL DE ANALÍTICA (Tab 3)
    # -------------------------------------------------------
    
    # 1. Calcular Ausentismo (Fallas Y Retardos - Conteo Global)
    mis_materias_ids = [a.materia.id for a in asignaciones] # IDs de las materias de este profe
    try:
        from .models import Asistencia
        
        # Filtramos fallas y retardos
        fallas_agrupadas = Asistencia.objects.filter(
            materia_id__in=mis_materias_ids,
            estado__in=['FALLA', 'TARDE'] 
        ).values('estudiante_id').annotate(total=Count('id'))
        
        for f in fallas_agrupadas:
            eid = f['estudiante_id']
            if eid in analisis_estudiantes:
                analisis_estudiantes[eid]['fallas'] = f['total']
                conteo_total_fallas += f['total']
                
    except ImportError:
        pass 

    # 2. Convertir diccionario a lista plana para ordenar
    lista_final_estudiantes = []
    
    for eid, data in analisis_estudiantes.items():
        promedio_final = 0.0
        if data['num_notas'] > 0:
            promedio_final = data['suma_notas'] / data['num_notas']
        
        if promedio_final > 0 and promedio_final < 3.0:
            conteo_reprobados_global += 1

        lista_final_estudiantes.append({
            'estudiante': data['obj'],
            'curso': data['curso_texto'],
            'promedio': round(promedio_final, 2),
            'fallas': data['fallas'],
            'historial': [] # Inicializamos la lista vacía para llenarla luego
        })

    # 3. Generar los TOPS
    top_mejores = sorted(lista_final_estudiantes, key=lambda x: x['promedio'], reverse=True)[:5]
    
    estudiantes_con_notas = [x for x in lista_final_estudiantes if x['promedio'] > 0]
    top_riesgo = sorted(estudiantes_con_notas, key=lambda x: x['promedio'])[:5]
    
    con_fallas = [x for x in lista_final_estudiantes if x['fallas'] > 0]
    top_ausentismo = sorted(con_fallas, key=lambda x: x['fallas'], reverse=True)[:5]

    # ==============================================================================
    # 🔥 CORRECCIÓN CRÍTICA: CARGAR EL HISTORIAL DETALLADO DE FALLAS
    # Sin este bloque, el modal en el HTML nunca tendrá datos para mostrar.
    # ==============================================================================
    try:
        from .models import Asistencia
        
        # Recorremos SOLO a los estudiantes que están en el Top de Ausentismo
        for item in top_ausentismo:
            estudiante_obj = item['estudiante']
            
            # Buscamos cada registro individual (Día, Fecha, Hora, Materia)
            # Solo de las materias de este profesor (mis_materias_ids)
            detalle_fallas = Asistencia.objects.filter(
                estudiante=estudiante_obj,
                materia_id__in=mis_materias_ids,
                estado__in=['FALLA', 'TARDE']
            ).select_related('materia').order_by('-fecha', '-id') # Orden descendente
            
            # Guardamos la consulta en el diccionario del estudiante
            item['historial'] = list(detalle_fallas)

    except Exception as e:
        print(f"Error cargando historial de fallas: {e}")
    # ==============================================================================

    context = {
        'docente': docente,
        'materias_por_curso': materias_por_curso,
        'estadisticas_por_materia': estadisticas_por_materia,
        'total_cursos': len(materias_por_curso),
        'total_materias': len(estadisticas_por_materia),
        'total_estudiantes': len(total_estudiantes_unicos),
        'top_mejores': top_mejores,
        'top_riesgo': top_riesgo,
        'top_ausentismo': top_ausentismo, # Ahora incluye 'historial' con fechas y horas
        'kpi_reprobados': conteo_reprobados_global,
        'kpi_fallas': conteo_total_fallas
    }
    return render(request, 'dashboard_docente.html', context)

def get_description_nota(numero_nota):
    return {
        1: 'Quiz (20%)',
        2: 'Examen (30%)',
        3: 'Proyecto (30%)',
        4: 'Sustentación (20%)',
        5: 'Promedio ponderado'
    }.get(numero_nota, f'Nota {numero_nota}')

# ===================================================================
# INICIO DE LA FUNCIÓN CORREGIDA
# ===================================================================
#desde aqui 
@role_required('DOCENTE')
def subir_notas(request, materia_id):
    asignacion = get_object_or_404(AsignacionMateria, materia_id=materia_id, docente=request.user, activo=True)
    materia = asignacion.materia
    curso = asignacion.curso
    estudiantes_matriculados = Matricula.objects.filter(curso=curso, activo=True).select_related('estudiante')
    periodos = Periodo.objects.filter(curso=curso, activo=True).order_by('id')

    if not periodos.exists():
        nombres = ['Primer Periodo', 'Segundo Periodo', 'Tercer Periodo', 'Cuarto Periodo']
        for nombre in nombres:
            Periodo.objects.create(
                nombre=nombre, curso=curso,
                fecha_inicio=timezone.now(),
                fecha_fin=timezone.now() + timedelta(days=90),
                activo=True
            )
        periodos = Periodo.objects.filter(curso=curso, activo=True).order_by('id')
        messages.info(request, f'Se crearon {len(periodos)} periodos automaticamente para el curso.')

    if request.method == 'POST':
        with transaction.atomic():
            # --- ACTIVIDADES Y TAREAS ---
            actividad_ids_a_mantener = [int(i) for i in request.POST.getlist('actividad_id[]') if i and i.isdigit()]
            ActividadSemanal.objects.filter(curso=curso, materia=materia, docente=request.user)\
                .exclude(id__in=actividad_ids_a_mantener).delete()
            
            titulos = request.POST.getlist('titulo_actividad[]')
            descripciones = request.POST.getlist('descripcion_actividad[]')
            fechas_inicio = request.POST.getlist('fecha_inicio_actividad[]')
            fechas_fin = request.POST.getlist('fecha_fin_actividad[]')
            actividad_ids = request.POST.getlist('actividad_id[]')
            
            for i in range(len(titulos)):
                titulo = (titulos[i] or "").strip()
                descripcion = (descripciones[i] or "").strip()
                fi_str = (fechas_inicio[i] or "").strip()
                ff_str = (fechas_fin[i] or "").strip()
                actividad_id = (actividad_ids[i] or "").strip()
                
                if (titulo or descripcion):
                    try:
                        fecha_inicio = datetime.strptime(fi_str, '%Y-%m-%d').date() if fi_str else None
                        fecha_fin = datetime.strptime(ff_str, '%Y-%m-%d').date() if ff_str else None
                    except ValueError:
                        messages.error(request, 'Formato de fecha inválido. Usa AAAA-MM-DD.')
                        return redirect('subir_notas', materia_id=materia.id)
                    
                    if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
                        messages.error(request, 'La fecha de inicio no puede ser posterior a la fecha de finalización.')
                        return redirect('subir_notas', materia_id=materia.id)
                    
                    if actividad_id:
                        ActividadSemanal.objects.filter(id=actividad_id, docente=request.user).update(
                            titulo=titulo if titulo else 'Actividad de la Semana',
                            descripcion=descripcion,
                            fecha_inicio=fecha_inicio,
                            fecha_fin=fecha_fin,
                        )
                    else:
                        # Crear nueva actividad y notificar
                        ActividadSemanal.objects.create(
                            curso=curso, materia=materia, docente=request.user,
                            titulo=titulo if titulo else 'Actividad de la Semana',
                            descripcion=descripcion,
                            fecha_inicio=fecha_inicio,
                            fecha_fin=fecha_fin,
                        )
                        # 🔔 Notificación de Tarea
                        from .utils import notificar_acudientes, crear_notificacion
                        for m in estudiantes_matriculados:
                            crear_notificacion(m.estudiante, "Nueva Tarea", f"{materia.nombre}: {titulo}", "ACTIVIDAD", "/dashboard/estudiante/")
                            notificar_acudientes(m.estudiante, "Nueva Tarea Asignada", f"En {materia.nombre}: {titulo}", "ACTIVIDAD", "/dashboard/acudiente/")

            # --- LOGROS ---
            logros_json_data = request.POST.get('logros_json_data', '')
            if logros_json_data:
                try:
                    logros_por_periodo = json.loads(logros_json_data)
                    ids_a_mantener = []
                    for periodo_id, logros_list in logros_por_periodo.items():
                        for logro in logros_list:
                            if logro.get('id', 0) > 0:
                                ids_a_mantener.append(logro['id'])
                    LogroPeriodo.objects.filter(curso=curso, materia=materia, docente=request.user).exclude(id__in=ids_a_mantener).delete()
                    for periodo_id, logros_list in logros_por_periodo.items():
                        periodo_obj = get_object_or_404(Periodo, id=periodo_id, curso=curso)
                        for logro in logros_list:
                            lid = logro.get('id', 0)
                            desc = (logro.get('descripcion', "") or "").strip()
                            if desc:
                                if lid > 0:
                                    LogroPeriodo.objects.filter(id=lid, docente=request.user).update(descripcion=desc)
                                else:
                                    LogroPeriodo.objects.create(
                                        curso=curso, periodo=periodo_obj, docente=request.user,
                                        materia=materia, descripcion=desc
                                    )
                except json.JSONDecodeError as e:
                    logger.exception("JSONDecodeError: %s", e)

            # --- NOTAS Y PROMEDIOS ---
            usuario_sistema, _ = User.objects.get_or_create(username='sistema', defaults={'is_active': False})
            
            for m in estudiantes_matriculados:
                estudiante = m.estudiante
                for periodo in periodos:
                    # 1. Guardar notas parciales (1-4)
                    for i in NUM_NOTAS:
                        nota_key = f'nota_{estudiante.id}_{periodo.id}_{i}'
                        valor_nota = request.POST.get(nota_key)
                        if valor_nota and valor_nota.strip():
                            try:
                                nota_valor = Decimal(valor_nota)
                                if ESCALA_MIN <= nota_valor <= ESCALA_MAX:
                                    Nota.objects.update_or_create(
                                        estudiante=estudiante, materia=materia, periodo=periodo, numero_nota=i,
                                        defaults={'valor': nota_valor.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
                                                  'descripcion': get_description_nota(i), 'registrado_por': request.user}
                                    )
                            except: pass

                    # 2. Calcular y Guardar Promedio (Nota 5) - ESTO ES LO VITAL PARA EL DASHBOARD
                    notas_db = Nota.objects.filter(
                        estudiante=estudiante, materia=materia, periodo=periodo,
                        numero_nota__in=NUM_NOTAS
                    ).values('numero_nota', 'valor')
                    
                    promedio = Decimal('0.0')
                    for n in notas_db:
                        promedio += n['valor'] * PESOS_NOTAS.get(n['numero_nota'], Decimal('0.0'))
                    
                    # Solo guardamos promedio si hay notas parciales
                    if notas_db:
                        Nota.objects.update_or_create(
                            estudiante=estudiante, materia=materia, periodo=periodo, numero_nota=5,
                            defaults={
                                'valor': promedio.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
                                'descripcion': 'Promedio ponderado',
                                'registrado_por': usuario_sistema
                            }
                        )

                    # 3. Comentarios
                    comentario_key = f'comentario_{estudiante.id}_{periodo.id}'
                    texto = request.POST.get(comentario_key)
                    if texto and texto.strip():
                        ComentarioDocente.objects.update_or_create(
                            docente=request.user, estudiante=estudiante, materia=materia, periodo=periodo,
                            defaults={'comentario': texto.strip()}
                        )
                    elif not (texto or "").strip():
                        ComentarioDocente.objects.filter(docente=request.user, estudiante=estudiante, materia=materia, periodo=periodo).delete()

            messages.success(request, 'Notas guardadas correctamente.')
            return redirect('subir_notas', materia_id=materia.id)

    # --- GET ---
    estudiante_ids = [m.estudiante_id for m in estudiantes_matriculados]
    periodo_ids = [p.id for p in periodos]

    notas_qs = Nota.objects.filter(
        estudiante_id__in=estudiante_ids, materia=materia, periodo_id__in=periodo_ids
    ).values('estudiante_id', 'periodo_id', 'numero_nota', 'valor')

    notas_data = {m.estudiante.id: {'estudiante': m.estudiante, 'periodos': {p.id: {} for p in periodos}} for m in estudiantes_matriculados}
    for n in notas_qs:
        if n['estudiante_id'] in notas_data and n['periodo_id'] in notas_data[n['estudiante_id']]['periodos']:
            notas_data[n['estudiante_id']]['periodos'][n['periodo_id']][n['numero_nota']] = n['valor']

    comentarios_qs = ComentarioDocente.objects.filter(docente=request.user, materia=materia, estudiante_id__in=estudiante_ids).select_related('periodo')
    comentarios_data = {m.estudiante.id: {p.id: "" for p in periodos} for m in estudiantes_matriculados}
    for c in comentarios_qs:
        if c.estudiante_id in comentarios_data and c.periodo_id in comentarios_data[c.estudiante_id]:
            comentarios_data[c.estudiante_id][c.periodo.id] = c.comentario

    actividades = ActividadSemanal.objects.filter(curso=curso, materia=materia).order_by('-fecha_creacion')
    logros = LogroPeriodo.objects.filter(curso=curso, docente=request.user, materia=materia).order_by('periodo__id', '-fecha_creacion')
    logros_por_periodo = {}
    for l in logros:
        logros_por_periodo.setdefault(l.periodo.id, []).append({'id': l.id, 'descripcion': l.descripcion, 'periodo_id': l.periodo.id})

    context = {
        'materia': materia, 'curso': curso, 'estudiantes_matriculados': estudiantes_matriculados,
        'periodos': periodos, 'notas_data': notas_data, 'comentarios_data': comentarios_data,
        'actividades_semanales': actividades, 'logros_por_periodo': json.dumps(logros_por_periodo),
        'rango_notas': NUM_NOTAS, 'escala_min': ESCALA_MIN, 'escala_max': ESCALA_MAX, 'nota_aprobacion': NOTA_APROBACION,
        'grados': GRADOS_CHOICES, 'secciones': _secciones_disponibles()
    }
    return render(request, 'subir_notas.html', context)

@role_required('ADMINISTRADOR')
def admin_dashboard(request):
    total_estudiantes = Perfil.objects.filter(rol='ESTUDIANTE').count()
    # CORRECCIÓN: Se cambió 'Q(perfil__es_director=True)' a 'Q(es_director=True)' ya que la consulta es directamente sobre el modelo Perfil.
    total_docentes = Perfil.objects.filter(Q(rol='DOCENTE') | Q(es_director=True)).distinct().count()
    total_cursos = Curso.objects.filter(activo=True).count()
    total_materias = Materia.objects.count()
    cursos_sin_director = Curso.objects.filter(director__isnull=True, activo=True).count()
    cursos_activos = Curso.objects.filter(activo=True).only('id', 'capacidad_maxima')
    cursos_completos = [curso for curso in cursos_activos if _curso_esta_completo(curso)]
    context = {
        'total_estudiantes': total_estudiantes,
        'total_docentes': total_docentes,
        'total_cursos': total_cursos,
        'total_materias': total_materias,
        'cursos_sin_director': cursos_sin_director,
        'cursos_completos': len(cursos_completos),
    }
    return render(request, 'admin_dashboard.html', context)

@role_required('ADMINISTRADOR')
def gestion_academica(request):
    context = {
        'grados': GRADOS_CHOICES,
        'secciones': _secciones_disponibles(),
        'anio_escolar': _anio_escolar_actual(),
    }
    return render(request, 'gestion_academica.html', context)

@role_required('ADMINISTRADOR')
def gestionar_cursos(request):
    profesores = User.objects.filter(
        Q(perfil__rol='DOCENTE') | Q(perfil__es_director=True)
    ).select_related('perfil').order_by('first_name', 'last_name').distinct()

    if request.method == 'POST':
        if 'crear_curso' in request.POST:
            grado = request.POST.get('grado')
            seccion = request.POST.get('seccion', '').upper()
            anio_escolar = request.POST.get('anio_escolar') or _anio_escolar_actual()
            capacidad = int(request.POST.get('capacidad_maxima', CAPACIDAD_POR_DEFECTO))
            descripcion = request.POST.get('descripcion', "")
            try:
                nombre_curso = f"{dict(GRADOS_CHOICES).get(grado, grado)} {seccion}"
                if len(nombre_curso) > 255:
                    messages.error(request, 'El nombre del curso es demasiado largo.')
                    return redirect('gestionar_cursos')

                Curso.objects.create(
                    nombre=nombre_curso,
                    grado=grado, seccion=seccion, anio_escolar=anio_escolar,
                    capacidad_maxima=capacidad, descripcion=descripcion,
                    activo=True
                )
                messages.success(request, f'Curso {nombre_curso} creado exitosamente.')
            except IntegrityError:
                messages.error(request, 'El curso ya existe para este año escolar.')
            except Exception as e:
                messages.error(request, f'Ocurrió un error: {e}')
            return redirect('gestionar_cursos')

        elif 'crear_cursos_personalizados' in request.POST:
            anio_escolar = request.POST.get('anio_escolar_personalizado') or _anio_escolar_actual()
            cursos_creados = 0
            cursos_ya_existentes = 0
            errores_creacion = []

            try:
                num_preescolar = int(request.POST.get('num_preescolar', 0))
                num_primaria = int(request.POST.get('num_primaria', 0))
                num_bachillerato = int(request.POST.get('num_bachillerato', 0))
            except (ValueError, TypeError):
                messages.error(request, 'Los valores para la cantidad de cursos deben ser números enteros.')
                return redirect('gestionar_cursos')

            cursos_a_crear = {
                'preescolar': num_preescolar,
                'primaria': num_primaria,
                'bachillerato': num_bachillerato
            }
            grados_por_nivel = _obtener_grados_por_nivel()

            for nivel, num_cursos_deseados in cursos_a_crear.items():
                if num_cursos_deseados > 0:
                    grados_del_nivel = grados_por_nivel.get(nivel, [])
                    for grado in grados_del_nivel:
                        secciones_existentes = list(Curso.objects.filter(
                            grado=grado,
                            anio_escolar=anio_escolar
                        ).values_list('seccion', flat=True))

                        for i in range(num_cursos_deseados):
                            next_section_char = _siguiente_letra(secciones_existentes)
                            if len(next_section_char) > 2: # Límite arbitrario para evitar secciones largas
                                messages.warning(request, f'Se agotaron las letras para crear secciones en el grado {dict(GRADOS_CHOICES).get(grado, grado)}.')
                                break

                            nombre_curso = f"{dict(GRADOS_CHOICES).get(grado, grado)} {next_section_char}"
                            try:
                                Curso.objects.create(
                                    nombre=nombre_curso, grado=grado, seccion=next_section_char,
                                    anio_escolar=anio_escolar, capacidad_maxima=CAPACIDAD_POR_DEFECTO, activo=True
                                )
                                cursos_creados += 1
                                secciones_existentes.append(next_section_char)
                            except IntegrityError:
                                cursos_ya_existentes += 1
                                continue
                            except Exception as e:
                                error_msg = f'Error inesperado al crear el curso {nombre_curso}: {e}'
                                messages.error(request, error_msg)
                                logger.exception(error_msg)
                                errores_creacion.append(error_msg)

            if cursos_creados > 0 or cursos_ya_existentes > 0:
                resumen = f"Operación finalizada: Creados: {cursos_creados}, Ya existentes (omitidos): {cursos_ya_existentes}."
                messages.success(request, resumen)
            else:
                messages.info(request, 'No se crearon cursos. Asegúrate de ingresar un número mayor a cero.')

            return redirect('gestionar_cursos')

        elif 'asignar_director' in request.POST:
            curso_id = request.POST.get('curso_id')
            docente_id = request.POST.get('docente_id')
            curso = get_object_or_404(Curso, id=curso_id)
            try:
                with transaction.atomic():
                    old_director = curso.director
                    if old_director:
                        # Verificar si el director saliente dirige otros cursos
                        if not Curso.objects.filter(director=old_director).exclude(id=curso.id).exists():
                            old_perfil = Perfil.objects.get(user=old_director)
                            old_perfil.es_director = False
                            old_perfil.save()

                    if docente_id:
                        new_director = get_object_or_404(User, id=docente_id)
                        new_perfil = get_object_or_404(Perfil, user=new_director)
                        if new_perfil.rol not in ['DOCENTE', 'ADMINISTRADOR']:
                            messages.error(request, 'El usuario no es un docente válido.')
                            return redirect('gestionar_cursos')
                        curso.director = new_director
                        new_perfil.es_director = True
                        new_perfil.save()
                        messages.success(request, f'Director {new_director.get_full_name()} asignado a: {curso}.')
                    else:
                        curso.director = None
                        messages.success(request, f'Director removido del curso: {curso}.')
                    curso.save()
            except Exception as e:
                msg = str(e) if settings.DEBUG else "Ocurrió un error al asignar el director."
                messages.error(request, msg)
            return redirect('gestionar_cursos')

    cursos_queryset = Curso.objects.all().select_related('director').order_by('grado', 'seccion')
    grados_por_nivel = _obtener_grados_por_nivel()
    orden_preescolar = grados_por_nivel['preescolar']
    orden_bachillerato = grados_por_nivel['bachillerato']

    cursos_list = list(cursos_queryset)
    cursos_por_nivel = {
        'preescolar': sorted([c for c in cursos_list if c.grado in orden_preescolar], key=lambda x: (orden_preescolar.index(x.grado), x.seccion)),
        'primaria': sorted([c for c in cursos_list if c.grado in grados_por_nivel['primaria']], key=lambda x: (int(x.grado), x.seccion)),
        'bachillerato': sorted([c for c in cursos_list if c.grado in orden_bachillerato], key=lambda x: (orden_bachillerato.index(x.grado), x.seccion)),
    }

    context = {
        'profesores': profesores,
        'grados': GRADOS_CHOICES,
        'secciones': _secciones_disponibles(),
        'anio_escolar': _anio_escolar_actual(),
        'cursos_por_nivel': cursos_por_nivel,
    }
    return render(request, 'gestionar_cursos.html', context)

@role_required('DIRECTOR_CURSO')
def dashboard_director(request):
    messages.info(request, "Redirigiendo a tu panel de docente/director.")
    return redirect('dashboard_docente')

@role_required('DIRECTOR_CURSO')
def panel_director_curso(request, curso_id):
    director = request.user
    curso = get_object_or_404(Curso, id=curso_id, director=director, activo=True)
    estudiantes = User.objects.filter(
        matriculas__curso=curso, matriculas__activo=True, perfil__rol='ESTUDIANTE'
    ).select_related('perfil').order_by('last_name', 'first_name').distinct()
    materias = Materia.objects.filter(asignaciones__curso=curso).distinct().order_by('nombre')
    periodos = Periodo.objects.filter(curso=curso, activo=True).order_by('id')
    notas_finales_data = {}
    convivencias_data = {}
    estudiante_ids = [e.id for e in estudiantes]
    materia_ids = [m.id for m in materias]
    periodo_ids = [p.id for p in periodos]
    notas_qs = Nota.objects.filter(
        estudiante_id__in=estudiante_ids,
        materia_id__in=materia_ids,
        periodo_id__in=periodo_ids,
        numero_nota=5
    ).values('estudiante_id', 'materia_id', 'periodo_id', 'valor')
    convivencia_qs = Convivencia.objects.filter(
        estudiante_id__in=estudiante_ids,
        curso=curso,
        periodo_id__in=periodo_ids
    ).values('estudiante_id', 'periodo_id', 'valor', 'comentario')
    for estudiante in estudiantes:
        notas_finales_data[estudiante.id] = {m.id: {} for m in materias}
        convivencias_data[estudiante.id] = {p.id: {'valor': None, 'comentario': ""} for p in periodos}
    for nota in notas_qs:
        if nota['estudiante_id'] in notas_finales_data and nota['materia_id'] in notas_finales_data[nota['estudiante_id']]:
            notas_finales_data[nota['estudiante_id']][nota['materia_id']][nota['periodo_id']] = nota['valor']
    for conv in convivencia_qs:
        if conv['estudiante_id'] in convivencias_data and conv['periodo_id'] in convivencias_data[conv['estudiante_id']]:
            convivencias_data[conv['estudiante_id']][conv['periodo_id']] = {'valor': conv['valor'], 'comentario': conv['comentario']}
    context = {
        'curso': curso, 'estudiantes': estudiantes, 'materias': materias, 'periodos': periodos,
        'notas_finales_data': notas_finales_data, 'convivencias_data': convivencias_data,
    }
    return render(request, 'director/panel_director_curso.html', context)

@role_required('DIRECTOR_CURSO')
@require_POST
@csrf_protect
def guardar_convivencia(request, curso_id):
    director = request.user
    curso = get_object_or_404(Curso, id=curso_id, director=director, activo=True)
    try:
        with transaction.atomic():
            for key, value in request.POST.items():
                if key.startswith('convivencia_'):
                    parts = key.split('_')
                    if len(parts) == 3:
                        periodo_id = int(parts[1])
                        estudiante_id = int(parts[2])
                        estudiante = get_object_or_404(User, id=estudiante_id)
                        periodo = get_object_or_404(Periodo, id=periodo_id)
                        valor_str = (value or "").strip()
                        comentario = request.POST.get(f'comentario_convivencia_{periodo_id}_{estudiante_id}', "").strip()
                        if valor_str:
                            valor = Decimal(valor_str)
                            if ESCALA_MIN <= valor <= ESCALA_MAX:
                                Convivencia.objects.update_or_create(
                                    estudiante=estudiante, curso=curso, periodo=periodo,
                                    defaults={'valor': valor.quantize(TWO_PLACES, rounding=ROUND_HALF_UP), 'comentario': comentario, 'registrado_por': director}
                                )
                            else:
                                messages.error(request, f'El valor de convivencia para {estudiante.get_full_name()} debe estar entre 0.0 y 5.0.')
                        else:
                            Convivencia.objects.filter(estudiante=estudiante, curso=curso, periodo=periodo).delete()
        messages.success(request, 'Notas de convivencia guardadas correctamente.')
    except Exception as e:
        msg = str(e) if settings.DEBUG else "Ocurrió un error al guardar."
        messages.error(request, msg)
        logger.exception("Error en guardar_convivencia: %s", e)
    return redirect('panel_director_curso', curso_id=curso.id)

@role_required('DIRECTOR_CURSO')
def generar_boletin(request, curso_id):
    curso = get_object_or_404(Curso, id=curso_id, director=request.user)
    estudiantes = User.objects.filter(
        matriculas__curso=curso, matriculas__activo=True, perfil__rol='ESTUDIANTE'
    ).select_related('perfil').prefetch_related('notas', 'matriculas').distinct()
    periodos = Periodo.objects.filter(curso=curso, activo=True).order_by('id')
    materias = Materia.objects.filter(asignaciones__curso=curso, asignaciones__activo=True).distinct().order_by('nombre')
    notas_data = {}
    for estudiante in estudiantes:
        notas_data[estudiante.id] = {}
        for materia in materias:
            notas_data[estudiante.id][materia.id] = {}
            for periodo in periodos:
                notas_periodo = Nota.objects.filter(estudiante=estudiante, materia=materia, periodo=periodo).order_by('numero_nota')
                notas_dict = {i: None for i in range(1, 6)}
                for nota in notas_periodo:
                    notas_dict[nota.numero_nota] = nota.valor
                notas_data[estudiante.id][materia.id][periodo.id] = notas_dict
    if request.method == 'POST':
        messages.success(request, 'Boletín generado correctamente.')
        return redirect('generar_boletin', curso_id=curso_id)
    context = {'curso': curso, 'estudiantes': estudiantes, 'periodos': periodos, 'materias': materias, 'notas_data': notas_data}
    return render(request, 'generar_boletin.html', context)

#Aqui empece con el registro de los profesores
@role_required('ADMINISTRADOR')
def asignar_materia_docente(request):
    """
    Vista Maestra de Gestión Académica.
    Maneja 3 procesos en una sola pantalla:
    1. Registrar Nuevo Docente (Forma B - Rápida).
    2. Crear Materias.
    3. Asignar Carga Académica.
    """
    
    # 1. CARGA DE DATOS PARA LOS SELECTORES (Contexto)
    docentes = User.objects.filter(
        Q(perfil__rol='DOCENTE') | Q(perfil__es_director=True)
    ).select_related('perfil').order_by('first_name', 'last_name').distinct()
    
    cursos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')
    
    # Ordenamos materias por nombre y curso para facilitar la búsqueda visual
    materias = Materia.objects.all().select_related('curso').order_by('nombre')
    
    # Tabla de resumen de lo que ya existe
    asignaciones = AsignacionMateria.objects.filter(activo=True).select_related(
        'materia', 'curso', 'docente'
    ).order_by('curso__grado', 'curso__seccion', 'materia__nombre')

    # 2. PROCESAMIENTO DE FORMULARIOS (POST)
    if request.method == 'POST':
        
        # ---------------------------------------------------------
        # CASO A: REGISTRAR NUEVO DOCENTE (Forma B)
        # ---------------------------------------------------------
        if 'crear_profesor' in request.POST:
            # Captura de datos
            username = request.POST.get('username', '').strip().lower()
            first_name = request.POST.get('first_name', '').strip().title()
            last_name = request.POST.get('last_name', '').strip().title()
            email = request.POST.get('email', '').strip().lower()

            # Validación preventiva
            if User.objects.filter(username=username).exists():
                messages.error(request, f"Error: El usuario '{username}' ya existe.")
                return redirect('asignar_materia_docente')

            try:
                with transaction.atomic():
                    # 1. Crear Usuario (Sin pedir clave, usa la default)
                    user = User.objects.create_user(
                        username=username, 
                        first_name=first_name, 
                        last_name=last_name,
                        email=email, 
                        password=DEFAULT_TEMP_PASSWORD
                    )
                    
                    # 2. Crear Perfil y activar CERROJO DE SEGURIDAD
                    Perfil.objects.create(
                        user=user, 
                        rol='DOCENTE', 
                        requiere_cambio_clave=True # Obligatorio cambio al entrar
                    )
                    
                    messages.success(request, f'Docente "{first_name} {last_name}" registrado. Usuario: {username}')
            
            except IntegrityError:
                messages.error(request, "El correo electrónico ya está en uso por otro usuario.")
            except Exception as e:
                messages.error(request, f"Error crítico al crear docente: {e}")
                
            return redirect('asignar_materia_docente')

        # ---------------------------------------------------------
        # CASO B: CREAR MATERIA
        # ---------------------------------------------------------
        elif 'crear_materia' in request.POST:
            nombre = request.POST.get('nombre')
            curso_id = request.POST.get('curso_id')
            
            if nombre and curso_id:
                try:
                    curso_obj = get_object_or_404(Curso, id=curso_id)
                    Materia.objects.get_or_create(
                        nombre=nombre.strip().title(),
                        curso=curso_obj
                    )
                    messages.success(request, f'Materia "{nombre}" creada correctamente.')
                except Exception as e:
                    messages.error(request, f'Error al crear materia: {e}')
            return redirect('asignar_materia_docente')

        # ---------------------------------------------------------
        # CASO C: ASIGNAR DOCENTE A MATERIA
        # ---------------------------------------------------------
        elif 'asignar_docente' in request.POST:
            materia_id = request.POST.get('materia_id')
            docente_id = request.POST.get('docente_id')
            
            try:
                materia_obj = get_object_or_404(Materia, id=materia_id)
                docente_obj = get_object_or_404(User, id=docente_id)
                
                # El curso lo sacamos de la materia para evitar inconsistencias
                curso_obj = materia_obj.curso
                
                AsignacionMateria.objects.update_or_create(
                    materia=materia_obj,
                    curso=curso_obj,
                    defaults={'docente': docente_obj, 'activo': True}
                )
                messages.success(request, f'Asignado: {docente_obj.get_full_name()} -> {materia_obj.nombre}.')
            except Exception as e:
                messages.error(request, f'Error en la asignación: {e}')
                
            return redirect('asignar_materia_docente')

    # 3. RENDERIZADO
    context = {
        'docentes': docentes,
        'cursos': cursos,
        'materias': materias,
        'asignaciones': asignaciones
    }
    
    return render(request, 'admin/asignar_materia_docente.html', context)



@role_required('ADMINISTRADOR')
def registrar_alumnos_masivo_form(request):
    """
    Muestra el formulario para subir el CSV de alumnos.
    """
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])
    form = BulkCSVForm()
    context = {
        'form': form,
        'grados': GRADOS_CHOICES,
        'secciones': _secciones_disponibles(),
        'anio_escolar': _anio_escolar_actual(),
    }
    return render(request, 'admin/registrar_alumnos.html', context)


# --- VISTA DE CARGA MASIVA COMPLETAMENTE CORREGIDA ---
@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def registrar_alumnos_masivo(request):
    """
    Procesa el registro masivo de estudiantes y acudientes desde un archivo CSV.
    Se corrige el error de autenticación para acudientes existentes y el error de sintaxis/indentación.
    """
    form = BulkCSVForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Error en el formulario. Por favor, sube un archivo CSV válido.")
        return redirect('registrar_alumnos_masivo_form')

    archivo_csv = form.cleaned_data['csv_file']
    anio_escolar = form.cleaned_data['anio_escolar'] or _anio_escolar_actual()

    creados_est, creados_acu = 0, 0
    actualizados_est, actualizados_acu = 0, 0
    matriculados, vinculados = 0, 0
    errores = []

    try:
        decoded_file = archivo_csv.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(decoded_file))

        # 1. CORRECCIÓN: Se elimina 'acudiente_cedula' de las columnas obligatorias.
        columnas_obligatorias = {
            'first_name', 'last_name', 'email', 'grado',
            'acudiente_first_name', 'acudiente_last_name', 'acudiente_email'
        }

        reader.fieldnames = [h.strip().lower().replace(' ', '_') for h in reader.fieldnames or []]

        if not columnas_obligatorias.issubset(reader.fieldnames):
            faltantes = ", ".join(columnas_obligatorias - set(reader.fieldnames))
            messages.error(request, f"El CSV es inválido. Faltan las columnas: {faltantes}")
            return redirect('registrar_alumnos_masivo_form')

        for i, row in enumerate(reader, start=2):
            try:
                with transaction.atomic():
                    # --- Datos del Acudiente ---
                    acu_email = (row.get('acudiente_email') or "").strip().lower()
                    acu_first = (row.get('acudiente_first_name') or "").strip().title()
                    acu_last = (row.get('acudiente_last_name') or "").strip().title()

                    if not all([acu_email, acu_first, acu_last]):
                        raise ValueError("Faltan datos obligatorios del acudiente (email, nombre, apellido).")

                    validate_email(acu_email)

                    acudiente_user, created_acu_user = User.objects.get_or_create(
                        email=acu_email,
                        defaults={ 'username': generar_username_unico(acu_first, acu_last), 'first_name': acu_first, 'last_name': acu_last }
                    )

                    # 🔑 CORRECCIÓN CLAVE: Aplica la contraseña temporal y el flag de cambio
                    perfil_acudiente, created_perfil_acu = Perfil.objects.get_or_create(
                        user=acudiente_user, defaults={'rol': 'ACUDIENTE'}
                    )

                    if created_acu_user or created_perfil_acu or not perfil_acudiente.requiere_cambio_clave:
                        acudiente_user.set_password(DEFAULT_TEMP_PASSWORD)
                        acudiente_user.save()
                        perfil_acudiente.rol = 'ACUDIENTE'
                        perfil_acudiente.requiere_cambio_clave = True
                        perfil_acudiente.save(update_fields=['rol', 'requiere_cambio_clave'])
                        if created_acu_user:
                            creados_acu += 1
                        else:
                            actualizados_acu += 1
                    else:
                        perfil_acudiente.rol = 'ACUDIENTE'
                        perfil_acudiente.save(update_fields=['rol'])
                        if not created_acu_user:
                            actualizados_acu += 1

                    # --- Datos del Estudiante ---
                    est_email = (row.get('email') or "").strip().lower()
                    est_first = (row.get('first_name') or "").strip().title()
                    est_last = (row.get('last_name') or "").strip().title()
                    grado_str = (row.get('grado') or "").strip()
                    grado_norm = _normalizar_grado(grado_str)

                    if not all([est_email, est_first, est_last, grado_norm]):
                        raise ValueError(f"Faltan datos del estudiante o el grado '{grado_str}' es inválido.")

                    validate_email(est_email)

                    estudiante_user, created_est_user = User.objects.get_or_create(
                        email=est_email,
                        defaults={ 'username': generar_username_unico(est_first, est_last), 'first_name': est_first, 'last_name': est_last }
                    )

                    perfil_estudiante, created_perfil_est = Perfil.objects.get_or_create(
                        user=estudiante_user, defaults={'rol': 'ESTUDIANTE'}
                    )

                    if created_est_user:
                        estudiante_user.set_password(DEFAULT_TEMP_PASSWORD)
                        estudiante_user.save()
                        creados_est += 1
                        perfil_estudiante.requiere_cambio_clave = True
                        perfil_estudiante.save(update_fields=['requiere_cambio_clave'])
                    elif created_perfil_est:
                        perfil_estudiante.rol = 'ESTUDIANTE'
                        perfil_estudiante.requiere_cambio_clave = True
                        perfil_estudiante.save(update_fields=['rol', 'requiere_cambio_clave'])
                        actualizados_est += 1
                    else:
                        actualizados_est += 1

                    # 3. CORRECCIÓN: Se crea el vínculo Acudiente-Estudiante de forma segura.
                    Acudiente.objects.update_or_create(
                        acudiente=acudiente_user,
                        estudiante=estudiante_user,
                        defaults={}
                    )
                    vinculados += 1

                    # --- Matrícula del Estudiante ---
                    curso_destino = asignar_curso_por_grado(grado_norm, anio_escolar=anio_escolar) # Pasar anio_escolar
                    if curso_destino:
                        Matricula.objects.update_or_create(
                            estudiante=estudiante_user, anio_escolar=anio_escolar,
                            defaults={'curso': curso_destino, 'activo': True}
                        )
                        matriculados += 1
                    else:
                        raise ValueError(f"No se encontraron cupos disponibles para el grado {grado_str} en el año {anio_escolar}.")

            except (ValidationError, ValueError, IntegrityError) as e:
                errores.append(f"Fila {i}: {e} | Datos: {row.get('first_name')} {row.get('last_name')}")

    # Este 'except' final maneja errores de lectura del archivo CSV (ej. encoding)
    except Exception as e:
        messages.error(request, f"No se pudo leer el archivo CSV. Error: {e}")
        logger.exception("Error procesando CSV de alumnos")
        return redirect('registrar_alumnos_masivo_form')

    # ################################################################## #
    # ############# INICIO DE LA MEJORA EN MENSAJES #################### #
    # ################################################################## #

    # 🚨 CORRECCIÓN DE SINTAXIS: Se asegura el uso del objeto 'request' para los mensajes y la indentación correcta.

    # Si no se creó/actualizó ningún estudiante y hubo errores, muestra un mensaje de error principal.
    if creados_est == 0 and actualizados_est == 0 and errores:
        messages.error(request, f"La carga masiva falló. No se procesó ningún estudiante. Causa probable: No existen cursos creados para los grados en el archivo CSV para el año {anio_escolar}.")
    # De lo contrario, muestra el resumen normal.
    else:
        messages.success(request, f"Proceso finalizado. Estudiantes creados: {creados_est}. Acudientes creados: {creados_acu}. Matriculados: {matriculados}.")
        if creados_est > 0 or creados_acu > 0:
            messages.info(request, f"La contraseña temporal para todos los usuarios nuevos es: '{DEFAULT_TEMP_PASSWORD}'")


    # Si hubo errores en filas específicas, muéstralos.
    if errores:
        # Se cambia el mensaje para mayor claridad.
        messages.warning(request, f"Se encontraron {len(errores)} filas con errores que no se pudieron procesar (mostrando los primeros 5):")
        for error in errores[:5]:
            messages.error(request, error)

    # ################################################################## #
    # ############### FIN DE LA MEJORA EN MENSAJES ##################### #
    # ################################################################## #

    return redirect('admin_dashboard')


# ===================================================================
# ===================================================================
#
# 🩺 INICIO DE LA CIRUGÍA: registrar_alumno_individual
#
# ===================================================================
# ===================================================================

@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def registrar_alumno_individual(request):
    """
    Procesa el registro individual de un estudiante Y su acudiente,
    replicando la lógica de seguridad y vinculación del registro masivo.
    """

    # --- 1. Obtención de Datos del Formulario ---
    # Datos del Estudiante
    est_username = (request.POST.get('username') or "").strip()
    est_email = (request.POST.get('email') or "").strip().lower()
    est_first = (request.POST.get('first_name') or "").strip().title()
    est_last = (request.POST.get('last_name') or "").strip().title()
    curso_id = request.POST.get('curso_id')

    # Datos del Acudiente (Nuevos - del formulario actualizado)
    acu_email = (request.POST.get('acudiente_email') or "").strip().lower()
    acu_first = (request.POST.get('acudiente_first_name') or "").strip().title()
    acu_last = (request.POST.get('acudiente_last_name') or "").strip().title()

    # --- 2. Validación Rigurosa ---
    try:
        # Validar que todos los campos nuevos y viejos estén presentes
        if not all([est_username, est_email, est_first, est_last, curso_id, acu_email, acu_first, acu_last]):
            raise ValueError('Todos los campos (Estudiante y Acudiente) son obligatorios.')
        
        # Validar ambos emails
        validate_email(est_email)
        validate_email(acu_email)
        
        if est_email == acu_email:
            raise ValueError("El email del estudiante y del acudiente no pueden ser el mismo.")

        # Validar curso y obtener el año escolar desde el curso (más seguro)
        curso = get_object_or_404(Curso, id=curso_id, activo=True)
        anio_escolar = curso.anio_escolar

        if _curso_esta_completo(curso):
            raise ValueError(f'El curso {curso.nombre} está lleno.')

    except (ValidationError, ValueError) as e:
        messages.error(request, f'Error de validación: {e}')
        return redirect('mostrar_registro_individual')
    except Http404:
        messages.error(request, 'El curso seleccionado no es válido o no está activo.')
        return redirect('mostrar_registro_individual')

    # --- 3. Cirugía: Transacción Atómica (Como en el registro masivo) ---
    try:
        with transaction.atomic():
            
            # --- A. Procesar Acudiente (Lógica de registro masivo) ---
            # Usamos el email como identificador único para el acudiente
            acudiente_user, created_acu_user = User.objects.get_or_create(
                email=acu_email,
                defaults={
                    'username': generar_username_unico(acu_first, acu_last), # de utils.py
                    'first_name': acu_first,
                    'last_name': acu_last
                }
            )
            
            perfil_acudiente, created_perfil_acu = Perfil.objects.get_or_create(
                user=acudiente_user, defaults={'rol': 'ACUDIENTE'}
            )

            # Asignar contraseña temporal y flag de cambio (Igual que en registro masivo)
            if created_acu_user or created_perfil_acu or not perfil_acudiente.requiere_cambio_clave:
                acudiente_user.set_password(DEFAULT_TEMP_PASSWORD)
                acudiente_user.save()
                perfil_acudiente.rol = 'ACUDIENTE'
                perfil_acudiente.requiere_cambio_clave = True
                perfil_acudiente.save(update_fields=['rol', 'requiere_cambio_clave'])
                if created_acu_user:
                    # ✅ Retroalimentación para el admin
                    messages.info(request, f'Nuevo acudiente creado: {acudiente_user.username}. Contraseña: {DEFAULT_TEMP_PASSWORD}')
            else:
                perfil_acudiente.rol = 'ACUDIENTE'
                perfil_acudiente.save(update_fields=['rol'])
                # ✅ Retroalimentación para el admin
                messages.info(request, f'Acudiente existente vinculado: {acudiente_user.username}.')


            # --- B. Procesar Estudiante (Lógica de registro individual) ---
            # Usamos el username (del formulario) como identificador único
            estudiante_user, created_est_user = User.objects.get_or_create(
                username=est_username,
                defaults={
                    'email': est_email,
                    'first_name': est_first,
                    'last_name': est_last,
                }
            )
            
            if created_est_user:
                estudiante_user.set_password(DEFAULT_TEMP_PASSWORD)
                estudiante_user.save()
                Perfil.objects.create(user=estudiante_user, rol='ESTUDIANTE', requiere_cambio_clave=True)
                # ✅ Retroalimentación para el admin
                messages.success(request, f'Estudiante creado: {est_username}. Contraseña: {DEFAULT_TEMP_PASSWORD}')
            else:
                # Si ya existía, actualizamos datos y perfil
                estudiante_user.email = est_email
                estudiante_user.first_name = est_first
                estudiante_user.last_name = est_last
                estudiante_user.save(update_fields=['email', 'first_name', 'last_name'])
                
                perfil_est, p_created = Perfil.objects.get_or_create(user=estudiante_user, defaults={'rol': 'ESTUDIANTE'})
                if not p_created and perfil_est.rol != 'ESTUDIANTE':
                    perfil_est.rol = 'ESTUDIANTE'
                    perfil_est.save(update_fields=['rol'])
                messages.info(request, f'Estudiante {est_username} ya existía. Sus datos han sido actualizados.')

            # --- C. Vincular Acudiente y Estudiante (Lógica de registro masivo) ---
            Acudiente.objects.update_or_create(
                acudiente=acudiente_user,
                estudiante=estudiante_user,
                defaults={}
            )

            # --- D. Matricular Estudiante (Lógica de registro individual) ---
            Matricula.objects.update_or_create(
                estudiante=estudiante_user,
                anio_escolar=anio_escolar, # Usar el año del curso seleccionado
                defaults={'curso': curso, 'activo': True}
            )
            messages.success(request, f'Estudiante matriculado en {curso.nombre}.')

            # ¡Éxito! Redirigir al dashboard de admin.
            return redirect('admin_dashboard')

    # --- 4. Manejo de Errores (Como en el registro masivo) ---
    except IntegrityError as e:
        if 'username' in str(e) and est_username in str(e):
            messages.error(request, f'El nombre de usuario del estudiante "{est_username}" ya está en uso. Elige otro.')
        elif 'email' in str(e):
                if est_email in str(e):
                    messages.error(request, f'El email de estudiante "{est_email}" ya está en uso.')
                elif acu_email in str(e):
                    messages.error(request, f'El email de acudiente "{acu_email}" ya está en uso y vinculado a otro usuario.')
                else:
                    messages.error(request, f'Error de email duplicado: {e}')
        else:
            messages.error(request, f'Error de integridad en la base de datos: {e}')
        return redirect('mostrar_registro_individual')
        
    except Exception as e:
        logger.exception(f"Error inesperado en registro individual: {e}")
        messages.error(request, f'Ocurrió un error inesperado: {e}')
        return redirect('mostrar_registro_individual')

# ===================================================================
# ===================================================================
#
# 🩺 FIN DE LA CIRUGÍA: registrar_alumno_individual
#
# ===================================================================
# ===================================================================


@role_required('ADMINISTRADOR')
def mostrar_registro_individual(request):
    anio_escolar = _anio_escolar_actual()
    cursos = Curso.objects.filter(activo=True, anio_escolar=anio_escolar).order_by('grado', 'seccion')
    return render(request, 'admin/registrar_alumno_individual.html', {
        'cursos': cursos, 'anio_escolar': anio_escolar
    })

# ########################################################################## #
# ############# INICIO DEL BLOQUE DE CÓDIGO CORREGIDO ###################### #
# ########################################################################## #

@role_required('ADMINISTRADOR')
def asignar_curso_estudiante(request):
    cursos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')

    if request.method == 'POST':
        # 🩺 CIRUGÍA B (admin_eliminar_estudiante) se ejecutará si se presiona el botón 'Eliminar'
        # Esta parte maneja la asignación de curso (botón 'Asignar')
        if 'estudiante' in request.POST and 'curso' in request.POST:
            estudiante_id = request.POST.get('estudiante')
            curso_id = request.POST.get('curso')

            if not estudiante_id or not curso_id:
                messages.error(request, 'Debes seleccionar tanto un estudiante como un curso.')
                return redirect('asignar_curso_estudiante')

            try:
                estudiante = get_object_or_404(User, id=estudiante_id, perfil__rol='ESTUDIANTE')
                curso = get_object_or_404(Curso, id=curso_id, activo=True)

                if _curso_esta_completo(curso):
                    messages.error(request, f'El curso {curso} está lleno.')
                else:
                    Matricula.objects.update_or_create(
                        estudiante=estudiante, anio_escolar=curso.anio_escolar,
                        defaults={'curso': curso, 'activo': True}
                    )
                    messages.success(request, f'{estudiante.get_full_name() or estudiante.username} fue asignado a {curso}.')
            except Exception as e:
                messages.error(request, f"Ocurrió un error al procesar la asignación: {e}")

        return redirect('asignar_curso_estudiante')

    # --- LÓGICA MEJORADA PARA OBTENER Y ORDENAR DATOS ---

    # 1. Obtenemos todas las matrículas activas, ordenadas por curso y luego por apellido del estudiante.
    matriculas_ordenadas = Matricula.objects.filter(activo=True).select_related(
        'estudiante__perfil', 'curso'
    ).order_by('curso__grado', 'curso__seccion', 'estudiante__last_name')

    # 2. Preparamos una lista de IDs de estudiantes para buscar sus acudientes de forma eficiente.
    student_ids = [m.estudiante_id for m in matriculas_ordenadas]

    # 3. Buscamos todos los acudientes en una sola consulta para evitar sobrecargar la base de datos.
    vinculos_acudientes = Acudiente.objects.filter(estudiante_id__in=student_ids).select_related('acudiente')
    acudiente_map = {vinculo.estudiante_id: vinculo.acudiente for vinculo in vinculos_acudientes}

    # 4. Construimos la lista final con toda la información.
    estudiantes_con_curso = []
    for matricula in matriculas_ordenadas:
        estudiante = matricula.estudiante
        acudiente = acudiente_map.get(estudiante.id)

        # ===================================================================
        # 🩺 INICIO DE CIRUGÍA: Añadir 'acudiente_username' al contexto
        # ===================================================================
        estudiantes_con_curso.append({
            'user': estudiante,
            'curso': matricula.curso,
            'rol': 'Estudiante',
            'acudiente_nombre': acudiente.get_full_name() if acudiente else "Sin asignar",
            'acudiente_username': acudiente.username if acudiente else "-", # 👈 LÍNEA AÑADIDA
            'matricula': matricula
        })
        # ===================================================================
        # 🩺 FIN DE CIRUGÍA
        # ===================================================================

    # Para el menú desplegable, obtenemos todos los estudiantes ACTIVOS sin importar si tienen matrícula
    todos_los_estudiantes = User.objects.filter(perfil__rol='ESTUDIANTE', is_active=True).order_by('last_name')

    context = {
        'todos_los_estudiantes': todos_los_estudiantes, # Para el menú desplegable de asignación
        'estudiantes_con_curso': estudiantes_con_curso, # Para la tabla ordenada
        'cursos': cursos,
        'anio_escolar': _anio_escolar_actual()
    }
    return render(request, 'admin/asignar_curso_estudiante.html', context)

# ########################################################################## #
# ############### FIN DEL BLOQUE DE CÓDIGO CORREGIDO ######################### #
# ########################################################################## #


# ===================================================================
# 🩺 INICIO DE CIRUGÍA B: Vista de "Retiro" Profesional (AÑADIDA)
# (Plan )
# ===================================================================
#Desde aqui 

@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def admin_eliminar_estudiante(request):
    """
    "Retira" a un estudiante (Soft Delete) y archiva sus boletines.
    1. Genera un boletín por CADA AÑO (matrícula) cursado.
    2. [NUEVO] Genera y archiva el Observador del Alumno.
    3. Guarda los PDFs en BoletinArchivado y ObservadorArchivado.
    4. Desactiva al Estudiante (User.is_active = False).
    5. Desactiva al Acudiente (si queda huérfano).
    """
    # Imports necesarios para la generación del PDF dentro de la vista
    from .models import ObservadorArchivado, Observacion, Institucion

    estudiante_id = request.POST.get('estudiante_id')
    if not estudiante_id:
        messages.error(request, "No se proporcionó un ID de estudiante.")
        return redirect('asignar_curso_estudiante')

    try:
        estudiante_a_retirar = get_object_or_404(User, id=estudiante_id, perfil__rol='ESTUDIANTE', is_active=True)
        estudiante_nombre = estudiante_a_retirar.get_full_name() or estudiante_a_retirar.username

        # 2. Encontrar TODAS sus matrículas (pasadas y presente)
        todas_las_matriculas = Matricula.objects.filter(
            estudiante=estudiante_a_retirar
        ).select_related('curso').order_by('anio_escolar')

        if not todas_las_matriculas.exists():
            messages.warning(request, f"El estudiante {estudiante_nombre} no tiene matrículas. Se procederá a desactivar.")

        boletines_generados = 0
        boletines_fallidos = 0
        observador_archivado = False # Bandera para controlar el mensaje final

        # Usamos una transacción para todo el proceso de retiro
        with transaction.atomic():

            # --- 3. Generación de Boletines Históricos ---
            for matricula in todas_las_matriculas:
                try:
                    # Usamos el service refactorizado para obtener el contexto de CADA matrícula
                    contexto_historico = get_student_report_context(matricula.id)

                    if not contexto_historico:
                        logger.warning(f"No se pudo obtener contexto para {estudiante_nombre} en {matricula.anio_escolar}. Omitiendo boletín.")
                        boletines_fallidos += 1
                        continue

                    # (Re-usamos la lógica de _generar_boletin_pdf_logica pero sin la respuesta HTTP)
                    contexto_historico['request'] = request
                    html_string = render_to_string('pdf/boletin_template.html', contexto_historico)
                    base_url = request.build_absolute_uri('/')
                    pdf_content = HTML(string=html_string, base_url=base_url).write_pdf()

                    # ===================================================================
                    # 🩺 INICIO DE LA CIRUGÍA: Corregir discrepancia de nombres
                    # ===================================================================
                    
                    # 1. Usamos el username (ej: 'rmorales')
                    student_username = estudiante_a_retirar.username
                    
                    # 2. Reemplazamos el guion '-' del año por '_'
                    anio_con_guion = matricula.anio_escolar # (ej: "2025-2026")
                    anio_con_guion_bajo = anio_con_guion.replace('-', '_') # (ej: "2025_2026")
                    
                    # 3. Creamos el nombre de archivo sincronizado
                    nombre_archivo_sincronizado = f"boletin_{student_username}_{anio_con_guion_bajo}.pdf"
                    
                    # 4. Usamos el nombre corregido en el ContentFile
                    pdf_file = ContentFile(pdf_content, name=nombre_archivo_sincronizado)
                    
                    # ===================================================================
                    # 🩺 FIN DE LA CIRUGÍA
                    # ===================================================================

                    curso_obj = contexto_historico.get('curso')

                    # Guardar en el modelo BoletinArchivado
                    BoletinArchivado.objects.create(
                        nombre_estudiante=estudiante_nombre,
                        username_estudiante=estudiante_a_retirar.username,
                        grado_archivado=curso_obj.grado,
                        seccion_archivada=curso_obj.seccion,
                        anio_lectivo_archivado=curso_obj.anio_escolar,
                        eliminado_por=request.user,
                        archivo_pdf=pdf_file # pdf_file ahora tiene el nombre sincronizado
                    )
                    boletines_generados += 1

                except Exception as e:
                    logger.exception(f"Fallo al generar boletín histórico para {estudiante_nombre} (Año: {matricula.anio_escolar}): {e}")
                    boletines_fallidos += 1

            # ===================================================================
            # 🩺 CIRUGÍA NUEVA: GENERAR Y ARCHIVAR OBSERVADOR
            # ===================================================================
            try:
                # 1. Obtener datos para el observador
                observaciones = Observacion.objects.filter(estudiante=estudiante_a_retirar).order_by('fecha_creacion')
                institucion = Institucion.objects.first()
                # Tomamos el último curso conocido para el encabezado
                ultimo_curso = todas_las_matriculas.last().curso if todas_las_matriculas.exists() else None

                # 2. Preparar contexto (mismo usado en ver_observador)
                ctx_observador = {
                    'estudiante': estudiante_a_retirar,
                    'observaciones': observaciones,
                    'institucion': institucion,
                    'curso': ultimo_curso,
                    'fecha_impresion': timezone.now(),
                    'generado_por': request.user.get_full_name(),
                    'es_oficial': True,
                    'es_archivo_retiro': True, # Marca para indicar que es el archivo final
                    'request': request
                }

                # 3. Generar PDF del Observador
                html_obs = render_to_string('pdf/observador_template.html', ctx_observador)
                base_url_obs = request.build_absolute_uri('/')
                pdf_content_obs = HTML(string=html_obs, base_url=base_url_obs).write_pdf()

                # 4. Crear archivo en memoria
                nombre_archivo_obs = f"OBSERVADOR_FINAL_{estudiante_a_retirar.username}.pdf"
                pdf_file_obs = ContentFile(pdf_content_obs, name=nombre_archivo_obs)

                # 5. Guardar en el modelo ObservadorArchivado
                ObservadorArchivado.objects.create(
                    estudiante_nombre=estudiante_nombre,
                    estudiante_username=estudiante_a_retirar.username,
                    eliminado_por=request.user,
                    archivo_pdf=pdf_file_obs
                )
                observador_archivado = True
            
            except Exception as e:
                # Logueamos el error pero NO detenemos el retiro, para asegurar que el alumno se vaya
                logger.error(f"Error generando Observador Archivado para {estudiante_nombre}: {e}")
            
            # ===================================================================
            # 🩺 FIN CIRUGÍA OBSERVADOR
            # ===================================================================


            # --- 4. Desactivación (Retiro) ---

            # Desactivar todas las matrículas
            todas_las_matriculas.update(activo=False)

            # Desactivar el usuario Estudiante (Soft Delete)
            estudiante_a_retirar.is_active = False
            estudiante_a_retirar.save(update_fields=['is_active'])

            # Desactivar Acudiente (si queda huérfano)
            acudientes_retirados_nombres = []
            vinculos = Acudiente.objects.filter(estudiante=estudiante_a_retirar).select_related('acudiente')
            acudiente_users_a_revisar = [v.acudiente for v in vinculos]

            for acudiente_user in acudiente_users_a_revisar:
                # Revisar si el acudiente tiene OTROS estudiantes *ACTIVOS*
                if not Matricula.objects.filter(
                    estudiante__acudientes_asignados__acudiente=acudiente_user,
                    activo=True
                ).exists():
                    # Si no tiene más estudiantes ACTIVOS, desactivamos al acudiente
                    acudiente_nombre = acudiente_user.get_full_name() or acudiente_user.username
                    acudiente_user.is_active = False
                    acudiente_user.save(update_fields=['is_active'])
                    acudientes_retirados_nombres.append(acudiente_nombre)

            # 5. Mensajes de Éxito
            messages.success(request, f"Estudiante '{estudiante_nombre}' retirado y movido a 'Ex Alumnos' exitosamente.")
            
            if boletines_generados > 0:
                messages.info(request, f"Se generaron y archivaron {boletines_generados} boletines de respaldo.")
            
            if observador_archivado:
                messages.info(request, "✅ Observador del Alumno generado y archivado correctamente.")
            else:
                messages.warning(request, "⚠️ No se pudo archivar el Observador (verificar logs).")

            if boletines_fallidos > 0:
                messages.warning(request, f"Falló la generación de {boletines_fallidos} boletines históricos (revisar logs).")
            
            if acudientes_retirados_nombres:
                messages.info(request, f"Acudientes retirados (por no tener más estudiantes activos): {', '.join(acudientes_retirados_nombres)}")

    except Http404:
        messages.error(request, "El estudiante seleccionado no existe o ya no está activo.")
    except Exception as e:
        logger.exception(f"Error al retirar estudiante {estudiante_id}: {e}")
        messages.error(request, f"Ocurrió un error inesperado al retirar al estudiante: {e}")

    return redirect('asignar_curso_estudiante')

#Hasta aqui 
# ===================================================================
# 🩺 FIN DE CIRUGÍA B
# ===================================================================


@role_required('ADMINISTRADOR')
def asignar_materia_docente(request):
    # 1. CARGAR DOCENTES (Filtramos por rol DOCENTE o Director)
    docentes = User.objects.filter(
        Q(perfil__rol='DOCENTE') | Q(perfil__es_director=True)
    ).select_related('perfil').order_by('first_name', 'last_name').distinct()
    
    cursos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')
    materias = Materia.objects.all().select_related('curso').order_by('nombre')
    
    asignaciones = AsignacionMateria.objects.filter(activo=True).select_related(
        'materia', 'curso', 'docente'
    ).order_by('curso__grado', 'curso__seccion', 'materia__nombre')

    if request.method == 'POST':
        
        # 🟢 ACCIÓN 1: CREAR NUEVO DOCENTE (Lógica Blindada)
        if 'crear_profesor' in request.POST:
            username = request.POST.get('username', '').strip().lower()
            first_name = request.POST.get('first_name', '').strip().title()
            last_name = request.POST.get('last_name', '').strip().title()
            email = request.POST.get('email', '').strip().lower()

            if User.objects.filter(username=username).exists():
                messages.error(request, f"El usuario '{username}' ya existe.")
                return redirect('asignar_materia_docente')

            try:
                with transaction.atomic():
                    # 1. Crear Usuario
                    user = User.objects.create_user(
                        username=username, 
                        first_name=first_name, 
                        last_name=last_name,
                        email=email, 
                        password=DEFAULT_TEMP_PASSWORD
                    )
                    
                    # 2. Gestionar Perfil (FORZANDO EL ROL)
                    # Intentamos obtener el perfil (por si una señal lo creó) o crearlo
                    perfil, created = Perfil.objects.get_or_create(user=user)
                    
                    # Forzamos los valores SÍ o SÍ, y guardamos explícitamente
                    perfil.rol = 'DOCENTE'
                    perfil.requiere_cambio_clave = True
                    perfil.save() # Guardado explícito para asegurar el cambio
                    
                    messages.success(request, f'Docente "{first_name} {last_name}" registrado correctamente. (Usuario: {username})')
            
            except IntegrityError:
                messages.error(request, "Error: El correo electrónico ya está en uso.")
            except Exception as e:
                messages.error(request, f"Error interno: {e}")
                
            return redirect('asignar_materia_docente')

        # 🔵 ACCIÓN 2: CREAR MATERIA
        elif 'crear_materia' in request.POST:
            nombre = request.POST.get('nombre')
            curso_id = request.POST.get('curso_id')
            
            if nombre and curso_id:
                try:
                    curso_obj = get_object_or_404(Curso, id=curso_id)
                    Materia.objects.get_or_create(
                        nombre=nombre.strip().title(),
                        curso=curso_obj
                    )
                    messages.success(request, f'Materia "{nombre}" creada.')
                except Exception as e:
                    messages.error(request, f'Error: {e}')
            return redirect('asignar_materia_docente')

        # 🟠 ACCIÓN 3: ASIGNAR DOCENTE
        elif 'asignar_docente' in request.POST:
            materia_id = request.POST.get('materia_id')
            docente_id = request.POST.get('docente_id')
            
            try:
                materia_obj = get_object_or_404(Materia, id=materia_id)
                docente_obj = get_object_or_404(User, id=docente_id)
                curso_obj = materia_obj.curso
                
                AsignacionMateria.objects.update_or_create(
                    materia=materia_obj,
                    curso=curso_obj,
                    defaults={'docente': docente_obj, 'activo': True}
                )
                messages.success(request, f'Asignado: {docente_obj.get_full_name()}.')
            except Exception as e:
                messages.error(request, f'Error: {e}')
                
            return redirect('asignar_materia_docente')

    context = {
        'docentes': docentes,
        'cursos': cursos,
        'materias': materias,
        'asignaciones': asignaciones
    }
    
    return render(request, 'admin/asignar_materia_docente.html', context)


@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def api_crear_curso(request):
    try:
        data = json.loads(request.body)
        grado = data.get('grado')
        seccion = data.get('seccion')
        anio_escolar = data.get('anio_escolar') or _anio_escolar_actual()
        capacidad = int(data.get('capacidad_maxima', CAPACIDAD_POR_DEFECTO))
        descripcion = data.get('descripcion', "")
        if grado not in dict(GRADOS_CHOICES):
            return JsonResponse({'error': 'Grado no válido'}, status=400)
        curso, created = Curso.objects.get_or_create(
            grado=grado, seccion=seccion, anio_escolar=anio_escolar,
            defaults={
                'nombre': f"{dict(GRADOS_CHOICES)[grado]} {seccion}",
                'capacidad_maxima': capacidad, 'descripcion': descripcion, 'activo': True
            }
        )
        if not created:
            return JsonResponse({'error': 'El curso ya existe.'}, status=400)
        return JsonResponse({'success': True, 'message': f'Curso {curso} creado exitosamente.', 'curso_id': curso.id}, status=201)
    except Exception as e:
        msg = str(e) if settings.DEBUG else "Error interno"
        return JsonResponse({'error': msg}, status=400)

@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def api_asignar_director(request):
    try:
        data = json.loads(request.body)
        curso_id = data.get('curso_id')
        docente_id = data.get('docente_id')
        curso = get_object_or_404(Curso, id=curso_id)
        with transaction.atomic():
            if curso.director:
                old = curso.director
                if not Curso.objects.filter(director=old).exclude(id=curso.id).exists():
                    old_perfil = get_object_or_404(Perfil, user=old)
                    old_perfil.es_director = False
                    old_perfil.save()
            if docente_id:
                new_director = get_object_or_404(User, id=docente_id)
                new_perfil = get_object_or_404(Perfil, user=new_director)
                if new_perfil.rol not in ['DOCENTE', 'ADMINISTRADOR']:
                    return JsonResponse({'success': False, 'error': 'El usuario no es un docente válido.'}, status=400)
                curso.director = new_director
                new_perfil.es_director = True
                new_perfil.save()
                curso.save()
                return JsonResponse({'success': True, 'message': f'Director asignado a: {curso}.', 'director_nombre': new_director.get_full_name() or new_director.username, 'curso_id': curso.id})
            else:
                curso.director = None
                curso.save()
                return JsonResponse({'success': True, 'message': f'Director removido de {curso}.', 'director_nombre': "", 'curso_id': curso.id})
    except Exception as e:
        msg = str(e) if settings.DEBUG else "Error interno"
        return JsonResponse({'success': False, 'error': msg}, status=400)

@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def matricular_estudiante(request):
    try:
        data = json.loads(request.body)
        estudiante_id = data.get('estudiante_id')
        curso_id = data.get('curso_id')
        estudiante = get_object_or_404(User, id=estudiante_id)
        curso = get_object_or_404(Curso, id=curso_id)
        if not hasattr(estudiante, 'perfil') or estudiante.perfil.rol != 'ESTUDIANTE':
            return JsonResponse({'error': 'El usuario no es un estudiante.'}, status=400)
        if _curso_esta_completo(curso):
            return JsonResponse({'error': 'El curso ha alcanzado su capacidad máxima.'}, status=400)
        matricula, created = Matricula.objects.update_or_create(
            estudiante=estudiante, anio_escolar=curso.anio_escolar,
            defaults={'curso': curso, 'activo': True}
        )
        return JsonResponse({'success': True, 'created': created, 'message': f'Estudiante matriculado en {curso}.', 'matricula_id': matricula.id})
    except Exception as e:
        msg = str(e) if settings.DEBUG else "Error interno"
        return JsonResponse({'error': msg}, status=400)

@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def api_mover_estudiante(request):
    try:
        data = json.loads(request.body)
        estudiante_id = data.get('estudiante_id')
        curso_destino_id = data.get('curso_destino_id')
        motivo = data.get('motivo', 'CAMBIO')
        observacion = data.get('observacion', "")
        with transaction.atomic():
            alumno = get_object_or_404(User, id=estudiante_id)
            curso_destino = get_object_or_404(Curso, id=curso_destino_id, activo=True)
            if _curso_esta_completo(curso_destino):
                return JsonResponse({'error': 'El curso destino está lleno.'}, status=400)

            mat_actual = Matricula.objects.filter(estudiante=alumno, activo=True).order_by('-id').first()
            curso_origen = mat_actual.curso if mat_actual else None

            if mat_actual:
                mat_actual.activo = False
                mat_actual.save()

            Matricula.objects.update_or_create(
                estudiante=alumno, anio_escolar=curso_destino.anio_escolar,
                defaults={'curso': curso_destino, 'activo': True}
            )
            if _HISTORIAL_MATRICULA_DISPONIBLE:
                HistorialMatricula.objects.create(
                    alumno=alumno, curso_origen=curso_origen, curso_destino=curso_destino,
                    motivo=motivo, observacion=observacion, movido_por=request.user
                )
            return JsonResponse({'success': True, 'message': 'Alumno movido de curso correctamente.'})
    except Exception as e:
        msg = str(e) if settings.DEBUG else "Error interno"
        return JsonResponse({'error': msg}, status=400)

@role_required('ADMINISTRADOR')
def api_get_students_by_course(request, curso_id):
    if request.method == 'GET':
        try:
            estudiantes_matriculados = Matricula.objects.filter(
                curso_id=curso_id, activo=True
            ).select_related('estudiante').order_by('estudiante__last_name', 'estudiante__first_name')

            estudiante_lista = [
                {'id': m.estudiante.id, 'name': m.estudiante.get_full_name() or m.estudiante.username}
                for m in estudiantes_matriculados
            ]
            return JsonResponse({'success': True, 'students': estudiante_lista})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Método de solicitud no válido'}, status=405)


# --- VISTAS DE ACUDIENTE Y GESTIÓN DE CUENTAS ---
# Desde Aqui 
# ===================================================================
# 🩺 VISTA DASHBOARD ACUDIENTE: CORREGIDA Y BLINDADA
# ===================================================================

@login_required
@role_required('ACUDIENTE')
def dashboard_acudiente(request):
    """
    Panel de control para el acudiente.
    CORRECCIÓN: Se asegura de cargar los docentes aunque no tengan perfil completo.
    """
    acudiente_user = request.user

    # Obtener vínculos (optimizada)
    vinculados = Acudiente.objects.filter(acudiente=acudiente_user).select_related('estudiante', 'estudiante__perfil')

    if not vinculados.exists():
        messages.error(request, "No tienes estudiantes vinculados. Por favor, contacta a la administración.")
        return render(request, 'dashboard_acudiente.html', {'estudiantes_data': []})

    estudiantes_data = []

    for vinculo in vinculados:
        estudiante = vinculo.estudiante
        perfil_estudiante = getattr(estudiante, 'perfil', None)

        # Matrícula y curso
        matricula = Matricula.objects.filter(estudiante=estudiante, activo=True).select_related('curso').first()
        curso = matricula.curso if matricula else None

        # Colecciones de datos
        materias_con_notas = {}
        comentarios_docente = {}
        actividades_semanales = {}
        convivencia_notas = {}
        logros_por_materia_por_periodo = {}
        periodos_disponibles = []
        
        # Variables estadísticas
        stats_materias_labels = []    
        stats_materias_promedios = [] 
        stats_periodos_labels = []    
        stats_periodos_data = []      
        conteo_ganadas = 0
        conteo_perdidas = 0
        promedio_general_acumulado = 0.0
        
        # Variables de asistencia
        porcentaje_asistencia = 100.0
        total_fallas = 0
        fallas_detalladas = []

        # Variable para Directorio Docente
        docentes_directorio = []

        if curso:
            # Obtener periodos
            periodos_disponibles = list(Periodo.objects.filter(curso=curso, activo=True).order_by('id'))
            
            # -----------------------------------------------------------
            # CORRECCIÓN CRÍTICA AQUÍ: 
            # Quitamos 'docente__perfil' del select_related para evitar que
            # Django oculte profesores que no tienen perfil configurado.
            # -----------------------------------------------------------
            asignaciones = AsignacionMateria.objects.filter(curso=curso, activo=True).select_related('materia', 'docente')
            materias = [a.materia for a in asignaciones]

            # --- LÓGICA DIRECTORIO DE DOCENTES (BLINDADA) ---
            docentes_vistos = set()
            for asig in asignaciones:
                # Verificamos que la asignación tenga un docente real (ID válido)
                if asig.docente_id and asig.docente_id not in docentes_vistos:
                    docente = asig.docente
                    
                    # Obtener foto de forma segura (sin romper si no hay perfil)
                    foto_url = None
                    try:
                        if hasattr(docente, 'perfil') and docente.perfil.foto:
                            foto_url = docente.perfil.foto.url
                    except Exception:
                        foto_url = None # Si falla algo con la foto, ponemos None y mostramos la inicial

                    docentes_directorio.append({
                        'id': docente.id,
                        'nombre': docente.get_full_name() or docente.username,
                        'materia_principal': asig.materia.nombre,
                        'foto_url': foto_url
                    })
                    docentes_vistos.add(docente.id)

            # -----------------------------------------------------------
            # 1. CÁLCULO DE ESTADÍSTICAS ACADÉMICAS
            # -----------------------------------------------------------
            notas_definitivas_qs = Nota.objects.filter(
                estudiante=estudiante, 
                materia__in=materias,
                numero_nota=5
            )

            # A. Estadísticas por Materia
            for materia in materias:
                notas_mat = [n.valor for n in notas_definitivas_qs if n.materia_id == materia.id]
                promedio_materia = 0.0

                if notas_mat:
                    promedio_materia = float(sum(notas_mat)) / len(notas_mat)
                    if promedio_materia >= 3.5: 
                        conteo_ganadas += 1
                    else:
                        conteo_perdidas += 1
                
                stats_materias_labels.append(materia.nombre)
                stats_materias_promedios.append(round(promedio_materia, 2))

            # B. Estadísticas por Periodo
            for periodo in periodos_disponibles:
                stats_periodos_labels.append(periodo.nombre)
                notas_per = [n.valor for n in notas_definitivas_qs if n.periodo_id == periodo.id]
                
                if notas_per:
                    prom_per = float(sum(notas_per)) / len(notas_per)
                    stats_periodos_data.append(round(prom_per, 2))
                else:
                    stats_periodos_data.append(0)

            # C. Promedio General
            if stats_materias_promedios:
                promedios_validos = [p for p in stats_materias_promedios if p > 0]
                if promedios_validos:
                    promedio_general_acumulado = sum(promedios_validos) / len(promedios_validos)

            # -----------------------------------------------------------
            # 2. CÁLCULO DE ASISTENCIA DETALLADA
            # -----------------------------------------------------------
            try:
                from .models import Asistencia 
                
                total_clases = Asistencia.objects.filter(estudiante=estudiante, curso=curso).count()
                
                fallas_qs = Asistencia.objects.filter(
                    estudiante=estudiante, 
                    curso=curso, 
                    estado='FALLA'
                ).select_related('materia').order_by('-fecha')
                
                total_fallas = fallas_qs.count()
                fallas_detalladas = list(fallas_qs)

                if total_clases > 0:
                    porcentaje_asistencia = ((total_clases - total_fallas) / total_clases) * 100
                
                porcentaje_asistencia = round(porcentaje_asistencia, 1)

            except ImportError:
                pass 

            # -----------------------------------------------------------
            # 3. CARGA DE DATOS PARA TABLAS (DETALLE)
            # -----------------------------------------------------------
            notas_qs = Nota.objects.filter(
                estudiante=estudiante, materia__in=materias
            ).select_related('periodo', 'materia').order_by('periodo__id', 'numero_nota')

            for nota in notas_qs:
                materias_con_notas.setdefault(nota.materia, {}).setdefault(nota.periodo.id, {})[nota.numero_nota] = nota

            # Comentarios
            comentarios_qs = ComentarioDocente.objects.filter(estudiante=estudiante, materia__in=materias).select_related('materia')
            for c in comentarios_qs:
                comentarios_docente.setdefault(c.materia.id, []).append(c)

            # Actividades
            actividades_qs = ActividadSemanal.objects.filter(curso=curso, materia__in=materias).order_by('-fecha_creacion').select_related('materia')
            for act in actividades_qs:
                actividades_semanales.setdefault(act.materia.id, []).append(act)

            # Logros
            logros_qs = LogroPeriodo.objects.filter(curso=curso, materia__in=materias).select_related('periodo', 'materia')
            for logro in logros_qs:
                logros_por_materia_por_periodo.setdefault(logro.materia, {}).setdefault(logro.periodo.id, []).append(logro)

            # Convivencia
            convivencia_qs = Convivencia.objects.filter(estudiante=estudiante, curso=curso).select_related('periodo')
            for conv in convivencia_qs:
                convivencia_notas[conv.periodo.id] = {'valor': conv.valor, 'comentario': conv.comentario}

        # Empaquetado final
        estudiantes_data.append({
            'estudiante': estudiante,
            'perfil': perfil_estudiante,
            'curso': curso,
            'matricula': matricula,
            'periodos_disponibles': periodos_disponibles,
            'materias_con_notas': materias_con_notas,
            'comentarios_docente': comentarios_docente,
            'actividades_semanales': actividades_semanales,
            'logros_por_materia_por_periodo': logros_por_materia_por_periodo,
            'convivencia_notas': convivencia_notas,
            # ESTADÍSTICAS
            'stats': {
                'materias_labels': json.dumps(stats_materias_labels),
                'materias_data': json.dumps(stats_materias_promedios),
                'periodos_labels': json.dumps(stats_periodos_labels),
                'periodos_data': json.dumps(stats_periodos_data),
                'ganadas': conteo_ganadas,
                'perdidas': conteo_perdidas,
                'promedio_general': round(promedio_general_acumulado, 2),
                'distribucion_data': json.dumps([conteo_ganadas, conteo_perdidas]),
                'asistencia_pct': porcentaje_asistencia,
                'total_fallas': total_fallas,
                'detalle_fallas': fallas_detalladas
            },
            # DIRECTORIO DOCENTE (Ahora sí cargará siempre)
            'docentes': docentes_directorio
        })

    context = {
        'acudiente': acudiente_user,
        'estudiantes_data': estudiantes_data
    }
    return render(request, 'dashboard_acudiente.html', context)
# Hasta Aqui

@login_required
def cambiar_clave(request):
    """
    Permite a los usuarios cambiar su contraseña.
    Al terminar, los redirige automáticamente a su Dashboard correspondiente.
    """
    if request.method == 'POST':
        form = PasswordChangeFirstLoginForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            # Esto mantiene la sesión iniciada tras el cambio de clave
            update_session_auth_hash(request, user)

            if hasattr(user, 'perfil'):
                # 1. Quitamos el "cepo" de seguridad
                user.perfil.requiere_cambio_clave = False
                user.perfil.save(update_fields=['requiere_cambio_clave'])

                # 2. Redirección Inteligente según el Rol
                rol = user.perfil.rol
                
                # --- STAFF DE BIENESTAR (Psicólogos y Coords) ---
                if rol in ['PSICOLOGO', 'COORD_CONVIVENCIA', 'COORD_ACADEMICO']:
                    return redirect('dashboard_bienestar')
                
                # --- OTROS ROLES ---
                elif rol == 'ESTUDIANTE':
                    return redirect('dashboard_estudiante')
                elif rol == 'ACUDIENTE':
                    return redirect('dashboard_acudiente')
                elif rol == 'DOCENTE' or user.perfil.es_director:
                    return redirect('dashboard_docente')
                elif rol == 'ADMINISTRADOR':
                    return redirect('admin_dashboard')

            messages.success(request, '¡Tu contraseña ha sido actualizada correctamente!')
            return redirect('home') # Fallback por si no tiene rol
        else:
            messages.error(request, 'Por favor corrige los errores a continuación.')
    else:
        form = PasswordChangeFirstLoginForm(user=request.user)

    return render(request, 'account/cambiar_clave.html', {'form': form})


@role_required('ADMINISTRADOR')
def gestion_perfiles(request):
    """
    Panel de administrador para buscar, filtrar y gestionar perfiles de usuario.
    """
    # Consulta optimizada para obtener usuarios (students/acudientes/teachers) y su perfil en una sola query
    perfiles_qs = Perfil.objects.select_related('user').order_by('user__last_name', 'user__first_name')
    form = ProfileSearchForm(request.GET or None)

    if form.is_valid():
        query = form.cleaned_data.get('query')
        rol = form.cleaned_data.get('rol')

        if query:
            perfiles_qs = perfiles_qs.filter(
                Q(user__username__icontains=query) |
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query) |
                Q(user__email__icontains=query)
            )
        if rol:
            perfiles_qs = perfiles_qs.filter(rol=rol)

    # Se pasa el QuerySet directo de objetos Perfil, que es la forma idiomática de filtrar por un objeto relacionado.
    users = User.objects.filter(perfil__in=perfiles_qs).select_related('perfil').order_by('last_name', 'first_name')


    context = {
        'form': form,
        'users': users
    }
    return render(request, 'admin/gestion_perfiles.html', context)


@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def admin_reset_password(request):
    """
    Manejador para el botón de resetear contraseña desde la gestión de perfiles.
    CORREGIDO: Usa DEFAULT_TEMP_PASSWORD en lugar de generar una aleatoria.
    """
    username = request.POST.get('username')
    try:
        user_to_reset = User.objects.select_related('perfil').get(username=username)

        # --- CORRECCIÓN AQUÍ ---
        # Usar la contraseña temporal predeterminada
        nueva_contrasena = DEFAULT_TEMP_PASSWORD
        # --- FIN CORRECCIÓN ---

        user_to_reset.set_password(nueva_contrasena)
        user_to_reset.save()

        if hasattr(user_to_reset, 'perfil'):
            user_to_reset.perfil.requiere_cambio_clave = True
            user_to_reset.perfil.save(update_fields=['requiere_cambio_clave'])

        # --- Mensaje de éxito actualizado (Opción A: Sin mostrar la contraseña) ---
        messages.success(request, f"Contraseña para '{user_to_reset.username}' restablecida a la predeterminada. El usuario deberá cambiarla al iniciar sesión.")
        # --- Fin mensaje actualizado ---

    except User.DoesNotExist:
        messages.error(request, f"El usuario '{username}' no existe.")
    except Exception as e:
        messages.error(request, f"Ocurrió un error inesperado: {e}")

    # Redirigir a la vista de gestión con los filtros actuales
    return redirect(f"{reverse('gestion_perfiles')}?{request.META.get('QUERY_STRING', '')}")


@role_required('ADMINISTRADOR')
def admin_db_visual(request):
    """
    Prepara y ordena los datos de estudiantes/acudientes por curso.
    """
    # 1. ESTUDIANTES E ACUDIENTES (AGRUPADOS POR CURSO)
    # Consulta para cursos activos, ordenados por jerarquía académica.
    cursos_activos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')

    data_visual = []

    for curso in cursos_activos:
        # Consulta de matrículas, optimizada para traer estudiante y perfil
        matriculas = Matricula.objects.filter(curso=curso, activo=True).select_related('estudiante__perfil')

        # Si el curso no tiene estudiantes, se salta.
        if not matriculas.exists():
            continue

        # Optimizamos la búsqueda de acudientes para todos los estudiantes de este curso.
        estudiante_ids = [m.estudiante_id for m in matriculas]
        vinculos_acudientes = Acudiente.objects.filter(estudiante_id__in=estudiante_ids).select_related('acudiente__perfil')
        acudiente_map = {vinculo.estudiante_id: vinculo.acudiente for vinculo in vinculos_acudientes}

        grupo_estudiantes = []
        for matricula in matriculas:
            estudiante = matricula.estudiante
            acudiente = acudiente_map.get(estudiante.id)

            # Lógica para mostrar la Contraseña Temporal del ESTUDIANTE
            estudiante_password_status = 'Cambiada o Desconocida'
            if hasattr(estudiante, 'perfil') and estudiante.perfil.requiere_cambio_clave:
                estudiante_password_status = DEFAULT_TEMP_PASSWORD

            # Lógica para mostrar la Contraseña Temporal del ACUDIENTE
            acudiente_password_status = 'N/A'
            if acudiente:
                if hasattr(acudiente, 'perfil') and acudiente.perfil.requiere_cambio_clave:
                    acudiente_password_status = DEFAULT_TEMP_PASSWORD
                else:
                    acudiente_password_status = 'Cambiada o Desconocida'

            grupo_estudiantes.append({
                'estudiante': estudiante,
                'estudiante_nombre_completo': estudiante.get_full_name() or estudiante.username,
                'estudiante_usuario': estudiante.username,
                'estudiante_password_temp': estudiante_password_status,
                'acudiente': acudiente,
                'acudiente_nombre_completo': acudiente.get_full_name() if acudiente else "Sin asignar",
                'acudiente_usuario': acudiente.username if acudiente else "Sin usuario",
                'acudiente_password_temp': acudiente_password_status,
            })

        # Agregamos los datos del curso con los estudiantes (ordenados por nombre del estudiante)
        data_visual.append({
            'curso': f"{curso.get_grado_display()} {curso.seccion} ({curso.anio_escolar})",
            'count': len(grupo_estudiantes),
            'grupo': sorted(grupo_estudiantes, key=itemgetter('estudiante_nombre_completo'))
        })

    # 2. PROFESORES Y DIRECTORES
    # Obtener todos los profesores y directores con su perfil, ordenados por nombre.
    profesores_qs = User.objects.filter(
        Q(perfil__rol='DOCENTE') | Q(perfil__es_director=True)
    ).select_related('perfil').order_by('last_name', 'first_name').distinct()

    # Mapear datos para mostrar el perfil y la contraseña temporal.
    profesores_data = [{
        'nombre_completo': p.get_full_name() or p.username,
        'usuario': p.username,
        'email': p.email,
        # La contraseña temporal sólo se muestra si requiere cambio de clave
        'password_temp': DEFAULT_TEMP_PASSWORD if hasattr(p, 'perfil') and p.perfil.requiere_cambio_clave else 'Cambiada o Desconocida',
        'rol': p.perfil.get_rol_display() if hasattr(p, 'perfil') else 'Sin perfil',
        'cambio_requerido': p.perfil.requiere_cambio_clave if hasattr(p, 'perfil') else False
    } for p in profesores_qs]

    context = {
        # La lista principal de cursos ya está ordenada por 'grado' y 'seccion' (gracias a la consulta inicial)
        'data': data_visual,
        'profesores': profesores_data,
        'default_temp_password': DEFAULT_TEMP_PASSWORD
    }

    return render(request, 'admin/db_visual.html', context)


# ===================================================================
# INICIO FASE 3: VISTAS DE GENERACIÓN DE BOLETINES (AÑADIDAS)
# ===================================================================

# ===================================================================
# 🩺 CIRUGÍA A: (REEMPLAZO) LÓGICA DE PDF REFACTORIZADA 
# ===================================================================


# ===================================================================
# 🩺 FIN DE CIRUGÍA A
# ===================================================================


def _generar_boletin_pdf_logica(request, matricula_id: int):
    """
    FASE 10: Lógica de renderizado de PDF con INTEGRACIÓN DE IA.
    Genera el boletín incluyendo el análisis de rendimiento automático.
    """
    if HTML is None:
        raise Exception("El módulo de generación de PDF (WeasyPrint) no está instalado.")

    # 1. Obtener los datos académicos base del estudiante
    context = get_student_report_context(matricula_id)
    if not context:
        raise Http404(f"No se encontró contexto para la matrícula_id: {matricula_id}")

    # 2. INTEGRACIÓN DE IA: Generar análisis pedagógico en tiempo real
    # Obtenemos el objeto estudiante desde el contexto ya cargado
    estudiante = context.get('estudiante')
    
    if estudiante:
        # Llamamos al orquestador para obtener las recomendaciones constructivistas
        # El orquestador ya sabe usar el ContextBuilder para ver las notas de la DB
        resultado_ia = ai_orchestrator.process_request(
            user=request.user, 
            action_type=ACCION_MEJORAS_ESTUDIANTE,
            target_user=estudiante
        )
        
        # Inyectamos el contenido de la IA en el contexto del template
        if resultado_ia.get('success'):
            context['analisis_ia'] = resultado_ia.get('content')
            context['ia_meta'] = resultado_ia.get('meta') # Por si quieres mostrar la fecha del análisis
        else:
            context['analisis_ia'] = "El análisis pedagógico automático no está disponible en este momento."

    # 3. Preparar el renderizado
    context['request'] = request
    html_string = render_to_string('pdf/boletin_template.html', context)

    # 4. Generar el archivo PDF con WeasyPrint
    base_url = request.build_absolute_uri('/')
    pdf = HTML(string=html_string, base_url=base_url).write_pdf()

    # 5. Configurar la respuesta de descarga/visualización
    filename = f"boletin_{estudiante.username}_{context['curso'].anio_escolar}.pdf"
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    
    return response

# ===================================================================
# 🩺 INICIO DE CIRUGÍA C: (REEMPLAZO) Vistas de PDF actualizadas 
# ===================================================================

@login_required
@role_required('ADMINISTRADOR')
def generar_boletin_pdf_admin(request, estudiante_id):
    """
    Vista para que el Administrador genere un boletín en PDF.
    (Versión modificada que usa la matrícula ACTIVA)
    """
    try:
        # Encontrar la matrícula ACTIVA de este estudiante
        matricula = get_object_or_404(Matricula, estudiante_id=estudiante_id, activo=True)
        return _generar_boletin_pdf_logica(request, matricula.id) # 👈 Pasa el matricula_id

    except Exception as e:
        logger.exception(f"Error al generar boletín PDF (Admin) para estudiante {estudiante_id}: {e}")
        messages.error(request, f"No se pudo generar el boletín. Error: {e}")
        return redirect('admin_dashboard') # Redirige a un lugar seguro


@login_required
@role_required('ACUDIENTE')
def generar_boletin_pdf_acudiente(request, estudiante_id):
    """
    Vista para que el Acudiente genere un boletín.
    Verifica el permiso en la matrícula.
    (Versión modificada que usa la matrícula ACTIVA)
    """
    
    # 1. Verificar que el acudiente tiene permiso sobre este estudiante
    try:
        vinculo = Acudiente.objects.get(acudiente=request.user, estudiante_id=estudiante_id)
    except Acudiente.DoesNotExist:
        messages.error(request, "No tienes permisos para ver el boletín de este estudiante.")
        return redirect('dashboard_acudiente')

    # 2. Verificar si la matrícula existe y tiene el permiso activado
    matricula = Matricula.objects.filter(estudiante=vinculo.estudiante, activo=True).first()
    
    if not matricula:
        messages.error(request, "El estudiante no tiene una matrícula activa.")
        return redirect('dashboard_acudiente')

    if not matricula.puede_generar_boletin:
        messages.warning(request, "La generación del boletín no está habilitada. Por favor, contacta a la administración.")
        return redirect('dashboard_acudiente')

    # 3. Si todo es correcto, llama a la LÓGICA INTERNA
    try:
        return _generar_boletin_pdf_logica(request, matricula.id) # 👈 Pasa el matricula_id
        
    except Exception as e:
        # 4. Si falla, registra el error y redirige al dashboard de ACUDIENTE
        logger.exception(f"Error al generar boletín PDF (Acudiente) para estudiante {estudiante_id}: {e}")
        messages.error(request, f"No se pudo generar el boletín. Error: {e}")
        return redirect('dashboard_acudiente')
# ===================================================================
# 🩺 FIN DE CIRUGÍA C
# ===================================================================


@login_required
@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def toggle_boletin_permiso(request):
    """
    Vista API (JSON) para activar/desactivar el permiso de boletín
    desde el panel de administración.
    """
    try:
        # Leemos el JSON enviado por Fetch
        data = json.loads(request.body)
        estudiante_id = data.get('estudiante_id')
        nuevo_estado = bool(data.get('estado'))
        
        matricula = Matricula.objects.filter(estudiante_id=estudiante_id, activo=True).first()
        
        if not matricula:
            return JsonResponse({'status': 'error', 'message': 'Matrícula no encontrada'}, status=404)
            
        matricula.puede_generar_boletin = nuevo_estado
        matricula.save(update_fields=['puede_generar_boletin'])
        
        return JsonResponse({
            'status': 'ok', 
            'nuevo_estado_texto': 'Disponible' if nuevo_estado else 'Bloqueado'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Solicitud inválida (JSON)'}, status=400)
    except Exception as e:
        # Usamos logger para registrar el error real en el servidor
        logger.exception(f"Error en toggle_boletin_permiso: {e}")
        # Enviamos un mensaje genérico al cliente
        return JsonResponse({'status': 'error', 'message': 'Error interno del servidor'}, status=500)
# ===================================================================
# FIN FASE 3
# ===================================================================

# ===================================================================
# 🩺 INICIO DE CIRUGÍA: PASO 3 (Plan 6 Pasos) 
# (Añadido en el paso anterior )
# ===================================================================

@login_required
@role_required('ADMINISTRADOR')
def admin_ex_estudiantes(request):
    """
    Vista para que el Administrador vea, filtre y descargue
    los boletines de los estudiantes retirados (Exalumnos).
    """
    
    # 1. Obtener todos los boletines, optimizados con 'select_related'
    #    para traer los datos del admin que eliminó 
    boletines_list = BoletinArchivado.objects.select_related('eliminado_por').all()

    # 2. Aplicar filtros de búsqueda (GET params) 
    query = request.GET.get('q', '').strip()
    grado_filtro = request.GET.get('grado', '').strip()
    anio_filtro = request.GET.get('anio', '').strip()

    if query:
        # Búsqueda por nombre o username
        boletines_list = boletines_list.filter(
            Q(nombre_estudiante__icontains=query) |
            Q(username_estudiante__icontains=query)
        )
    
    if grado_filtro:
        boletines_list = boletines_list.filter(grado_archivado=grado_filtro)
        
    if anio_filtro:
        boletines_list = boletines_list.filter(anio_lectivo_archivado=anio_filtro)

    # 3. Obtener los valores únicos para los menús desplegables de filtro
    #    Optimizamos esto para que solo consulte los valores distintos
    anios_disponibles = BoletinArchivado.objects.order_by('-anio_lectivo_archivado') \
                                                    .values_list('anio_lectivo_archivado', flat=True).distinct()
    
    # Usamos los GRADOS_CHOICES para los grados
    grados_disponibles = GRADOS_CHOICES

    # 4. Paginación (Escalabilidad) 
    #    Mostramos 25 resultados por página
    paginator = Paginator(boletines_list, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'total_boletines': paginator.count,
        
        # Valores para los filtros
        'anios_disponibles': anios_disponibles,
        'grados_disponibles': grados_disponibles,
        
        # Valores actuales para mantenerlos en el formulario
        'current_q': query,
        'current_grado': grado_filtro,
        'current_anio': anio_filtro,
    }
    
    # Usaremos una nueva plantilla que crearemos en el Paso 5
    return render(request, 'admin/ex_estudiantes.html', context)

# ===================================================================
# 🩺 FIN DE CIRUGÍA: PASO 3
# ===================================================================

# ===================================================================
# 🩺 INICIO DE CIRUGÍA: MÓDULO DE BIENESTAR Y CONVIVENCIA (VIEWS)
# ===================================================================

# Roles permitidos para el módulo de bienestar
STAFF_ROLES = ['PSICOLOGO', 'COORD_CONVIVENCIA', 'COORD_ACADEMICO', 'ADMINISTRADOR']

##desde aqui 


@role_required(STAFF_ROLES)
def ver_observador(request, estudiante_id):
    """
    Observation history for a specific student.
    """
    estudiante = get_object_or_404(User, id=estudiante_id)
    
    if not hasattr(estudiante, 'perfil') or estudiante.perfil.rol != 'ESTUDIANTE':
        messages.error(request, "El usuario seleccionado no es un estudiante.")
        return redirect('dashboard_bienestar')

    # Obtener observaciones ordenadas por fecha
    observaciones = Observacion.objects.filter(estudiante=estudiante).select_related('autor', 'periodo').order_by('-fecha_creacion')

    return render(request, 'bienestar/ver_observador.html', {
        'estudiante': estudiante,
        'observaciones': observaciones
    })

@role_required(STAFF_ROLES)
def crear_observacion(request, estudiante_id):
    """
    Formulario para crear una nueva observación.
    """
    estudiante = get_object_or_404(User, id=estudiante_id)

    if request.method == 'POST':
        # Pasamos el usuario al form para validaciones si fuera necesario
        form = ObservacionForm(request.POST, user=request.user, estudiante=estudiante)
        if form.is_valid():
            observacion = form.save(commit=False)
            observacion.estudiante = estudiante
            observacion.autor = request.user
            observacion.save()
            messages.success(request, "Observación registrada correctamente.")
            return redirect('ver_observador', estudiante_id=estudiante.id)
    else:
        form = ObservacionForm(user=request.user, estudiante=estudiante)

    return render(request, 'bienestar/form_observacion.html', {
        'form': form, 
        'estudiante': estudiante, 
        'titulo': 'Nueva Observación'
    })

@role_required(STAFF_ROLES)
def editar_observacion(request, observacion_id):
    """
    Edit an existing observation (with 24h validation).
    """
    observacion = get_object_or_404(Observacion, id=observacion_id)

    # Security validation: Only author or admin can edit
    es_admin = request.user.perfil.rol == 'ADMINISTRADOR'
    es_autor = observacion.autor == request.user

    if not es_admin and not es_autor:
        messages.error(request, "No tienes permiso para editar esta observación.")
        return redirect('ver_observador', estudiante_id=observacion.estudiante.id)

    # Time validation (24h)
    if not observacion.es_editable and not es_admin:
        messages.error(request, "El tiempo de edición (24h) ha expirado.")
        return redirect('ver_observador', estudiante_id=observacion.estudiante.id)

    if request.method == 'POST':
        # Pass instance to update, user and student for context
        form = ObservacionForm(request.POST, instance=observacion, user=request.user, estudiante=observacion.estudiante)
        if form.is_valid():
            form.save()
            messages.success(request, "Observación actualizada.")
            return redirect('ver_observador', estudiante_id=observacion.estudiante.id)
    else:
        form = ObservacionForm(instance=observacion, user=request.user, estudiante=observacion.estudiante)

    return render(request, 'bienestar/form_observacion.html', {
        'form': form, 
        'estudiante': observacion.estudiante, 
        'titulo': 'Editar Observación'
    })

# --- VIEW FOR MANAGING STAFF (ADMIN) ---
@role_required('ADMINISTRADOR')
def gestionar_staff(request):
    """
    Crea usuarios Psicológos, Coordinadores, etc. y maneja la subida del PEI.
    """
    staff_roles = [
        ('PSICOLOGO', 'Psicólogo'),
        ('COORD_CONVIVENCIA', 'Coord. Convivencia'),
        ('COORD_ACADEMICO', 'Coord. Académico')
    ]

    institucion = Institucion.objects.first()
    if not institucion:
        institucion = Institucion.objects.create(nombre="Institución Educativa")

    # --- Lógica de Procesamiento POST ---
    if request.method == 'POST':
        # 1. Manejar Subida de PEI (si el archivo está presente)
        if 'pei_file' in request.FILES:
            if request.user.perfil.rol in ['COORD_ACADEMICO', 'ADMINISTRADOR']:
                file = request.FILES['pei_file']
                if file.name.lower().endswith('.pdf'):
                    institucion.archivo_pei = file
                    institucion.save()
                    messages.success(request, "El Documento PEI se ha cargado correctamente.")
                else:
                    messages.error(request, "Error: El archivo debe ser un PDF.")
            else:
                messages.error(request, "No tienes permisos para modificar el PEI.")
            return redirect('gestionar_staff')

        # 2. Manejar Creación de Staff (si los campos de staff están presentes)
        elif 'username' in request.POST:
            username = request.POST.get('username')
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            email = request.POST.get('email')
            rol = request.POST.get('rol')

            try:
                with transaction.atomic():
                    if rol not in [r[0] for r in staff_roles]:
                        raise ValueError("Rol inválido")

                    user = User.objects.create_user(
                        username=username, first_name=first_name, last_name=last_name,
                        email=email, password=settings.DEFAULT_TEMP_PASSWORD
                    )
                    Perfil.objects.create(user=user, rol=rol, requiere_cambio_clave=True)
                    messages.success(request, f"Usuario {username} creado como {rol}. Clave: {settings.DEFAULT_TEMP_PASSWORD}")
            except Exception as e:
                messages.error(request, f"Error al crear staff: {e}")

        return redirect('gestionar_staff')

    # --- Lógica GET ---
    staff_users = User.objects.filter(
        perfil__rol__in=[r[0] for r in staff_roles],
        is_active=True
    ).select_related('perfil')

    return render(request, 'admin/gestionar_staff.html', {
        'staff_users': staff_users,
        'roles': staff_roles,
        'institucion': institucion # Pasamos el objeto institución
    })


# --- NEW FUNCTION: DEACTIVATE STAFF (SOFT DELETE) ---
@role_required('ADMINISTRADOR')
def desactivar_staff(request, user_id):
    """
    Deactivates (Soft Delete) a staff member.
    """
    usuario = get_object_or_404(User, id=user_id)
    
    # Protection 1: Do not deactivate superusers or self
    if usuario.is_superuser or usuario == request.user:
        messages.error(request, "No puedes desactivar a este usuario.")
        return redirect('gestionar_staff')

    # Protection 2: Verify it is wellness staff
    if not hasattr(usuario, 'perfil') or usuario.perfil.rol not in ['PSICOLOGO', 'COORD_CONVIVENCIA', 'COORD_ACADEMICO']:
        messages.error(request, "Este usuario no pertenece al staff de bienestar o no tiene perfil.")
        return redirect('gestionar_staff')

    # Proceed to deactivate
    usuario.is_active = False
    usuario.save()
    
    messages.success(request, f"El usuario {usuario.get_full_name() or usuario.username} ha sido retirado del equipo correctamente.")
    return redirect('gestionar_staff')

# --- API TO TOGGLE OBSERVER ACCESS (ADMIN) ---
@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def toggle_observador_permiso(request):
    try:
        data = json.loads(request.body)
        estudiante_id = data.get('estudiante_id')
        nuevo_estado = bool(data.get('estado'))

        # Find active enrollment
        matricula = Matricula.objects.filter(estudiante_id=estudiante_id, activo=True).first()
        if not matricula:
            return JsonResponse({'status': 'error', 'message': 'Matrícula no encontrada'}, status=404)

        matricula.puede_ver_observador = nuevo_estado
        matricula.save(update_fields=['puede_ver_observador'])

        return JsonResponse({'status': 'ok', 'nuevo_estado_texto': 'Visible' if nuevo_estado else 'Bloqueado'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def generar_observador_pdf(request, estudiante_id):
    """
    Generates the observer PDF for a student.
    """
    # 1. Validate Permissions
    es_staff = request.user.perfil.rol in STAFF_ROLES
    es_acudiente = request.user.perfil.rol == 'ACUDIENTE'

    estudiante = get_object_or_404(User, id=estudiante_id)
    matricula = Matricula.objects.filter(estudiante=estudiante, activo=True).first()

    if es_acudiente:
        # Verify link
        vinculo = Acudiente.objects.filter(acudiente=request.user, estudiante=estudiante).exists()
        if not vinculo:
            messages.error(request, "No tienes permiso.")
            return redirect('dashboard_acudiente')
        # Verify admin block
        if matricula and not matricula.puede_ver_observador:
            messages.error(request, "La visualización del observador está bloqueada temporalmente.")
            return redirect('dashboard_acudiente')
    elif not es_staff:
        messages.error(request, "Acceso denegado.")
        return redirect('home')

    # 2. Get data
    observaciones = Observacion.objects.filter(estudiante=estudiante).select_related('autor__perfil', 'periodo').order_by('periodo__id', 'fecha_creacion')
    institucion = Institucion.objects.first()

    # 3. Render PDF
    if HTML is None:
        return HttpResponse("Error: WeasyPrint no instalado.", status=500)

    html_string = render_to_string('pdf/observador_template.html', {
        'estudiante': estudiante,
        'observaciones': observaciones,
        'institucion': institucion,
        'curso': matricula.curso if matricula else None,
        'fecha_impresion': date.today()
    })

    base_url = request.build_absolute_uri('/')
    pdf = HTML(string=html_string, base_url=base_url).write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="observador_{estudiante.username}.pdf"'
    return response

# ===================================================================
# 🩺 FASE 4: FUNCIONES DE CHAT Y ASISTENCIA (NUEVAS AL FINAL)
# ===================================================================
#aqui 
@role_required('DOCENTE')
@require_POST
@csrf_protect
def api_tomar_asistencia(request):
    """
    Registra la asistencia de un estudiante vía AJAX.
    Envía notificación automática al Acudiente y al Coordinador de Convivencia si hay Falla o Retardo.
    """
    try:
        data = json.loads(request.body)
        estudiante_id = data.get('estudiante_id')
        materia_id = data.get('materia_id')
        estado = data.get('estado') 
        fecha = data.get('fecha', str(date.today()))

        estudiante = get_object_or_404(User, id=estudiante_id)
        materia = get_object_or_404(Materia, id=materia_id)
        
        # Validar matrícula activa para asegurar que el estudiante pertenece al curso
        matricula = Matricula.objects.filter(estudiante=estudiante, activo=True).first()
        if not matricula:
            return JsonResponse({'success': False, 'error': 'Estudiante no matriculado'})

        # Guardar o actualizar el registro de asistencia en la base de datos
        Asistencia.objects.update_or_create(
            estudiante=estudiante, materia=materia, fecha=fecha,
            defaults={
                'curso': matricula.curso, 
                'estado': estado, 
                'registrado_por': request.user
            }
        )

        # 🔔 SISTEMA DE NOTIFICACIONES AUTOMÁTICAS
        # Solo se activa si el estado es 'FALLA' o 'TARDE'
        if estado in ['FALLA', 'TARDE']:
            tipo_txt = "Falla de asistencia" if estado == 'FALLA' else "Llegada tarde"
            
            # Importación local para evitar errores de referencia circular
            from .utils import notificar_acudientes, crear_notificacion

            # 1. Notificar al Acudiente (Familia)
            # Esta función busca automáticamente a los acudientes del estudiante
            notificar_acudientes(
                estudiante, 
                "Alerta de Asistencia", 
                f"En la clase de {materia.nombre}: {tipo_txt} (Fecha: {fecha}).", 
                "ASISTENCIA"
            )
            
            # 2. Notificar al Coordinador de Convivencia (Staff)
            # Buscamos a todos los usuarios activos con el rol de Coordinador de Convivencia
            coordinadores = User.objects.filter(perfil__rol='COORD_CONVIVENCIA', is_active=True)
            
            for coord in coordinadores:
                crear_notificacion(
                    usuario_destino=coord,
                    titulo=f"Reporte: {tipo_txt}",
                    mensaje=f"Estudiante: {estudiante.get_full_name()} ({matricula.curso.nombre}). Materia: {materia.nombre}. Fecha: {fecha}.",
                    tipo="ASISTENCIA",
                    link=f"/bienestar/alumno/{estudiante.id}/" # Enlace directo al perfil/observador del alumno
                )

        return JsonResponse({'success': True})
    except Exception as e:
        # Captura cualquier error inesperado y lo devuelve como JSON
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def buzon_mensajes(request):
    """
    Bandeja de entrada y salida de mensajes.
    Agrupa los mensajes enviados para colapsar los envíos masivos en una sola fila.
    """
    tipo_bandeja = request.GET.get('tipo', 'recibidos') # Por defecto 'recibidos'
    
    mensajes_no_leidos_count = 0
    titulo_bandeja = ""
    # Mantenemos la inicialización
    mensajes = [] 

    if tipo_bandeja == 'enviados':
        titulo_bandeja = "Mensajes Enviados"
        
        # 1. Definir la QuerySet para AGRUPAR
        mensajes_agrupados = MensajeInterno.objects.filter(remitente=request.user).values(
            'asunto', 'cuerpo', 'fecha_envio'
        ).annotate(
            destinatarios_count=Count('destinatario', distinct=True), 
            referencia_id=Min('id'),
            ultimo_destinatario_id=Max('destinatario_id') 
        ).order_by('-fecha_envio')
        
        mensajes = list(mensajes_agrupados) 

        
    else:
        titulo_bandeja = "Buzón de Entrada"
        # Mensajes recibidos
        mensajes_recibidos_qs = MensajeInterno.objects.filter(destinatario=request.user).select_related('remitente__perfil').order_by('-fecha_envio')
        
        mensajes_no_leidos_count = mensajes_recibidos_qs.filter(leido=False).count()
        mensajes = mensajes_recibidos_qs


    # 2. Adjuntar el objeto User completo para la QuerySet de Enviados (Optimización)
    if tipo_bandeja == 'enviados':
        destinatario_ids = [m['ultimo_destinatario_id'] for m in mensajes if m['ultimo_destinatario_id']]
        
        usuarios_qs = User.objects.filter(id__in=destinatario_ids).select_related('perfil') 
        ultimo_destinatario_map = {user_obj.id: user_obj for user_obj in usuarios_qs}
            
        for m in mensajes:
            m['ultimo_destinatario_obj'] = ultimo_destinatario_map.get(m['ultimo_destinatario_id'])


    # 3. Renderizar el template final
    # Usamos 'chat/buzon.html'
    return render(request, 'chat/buzon.html', { 
        'mensajes': mensajes,
        'tipo_bandeja': tipo_bandeja,
        'titulo_bandeja': titulo_bandeja,
        'mensajes_no_leidos_count': mensajes_no_leidos_count
    })

#Aqui 
@login_required
def enviar_mensaje(request):
    """
    Formulario para enviar mensajes (Individuales o Masivos).
    Maneja la lógica de 'Responder', propagación masiva y FILTRO DE SEGURIDAD (Sentinel).
    """
    
    # 1. Capturar parámetros de la URL (Vienen del botón Responder)
    destinatario_id_get = request.GET.get('destinatario')
    asunto_previo = request.GET.get('asunto')
    mensaje_original_id = request.GET.get('reply_to')
    
    # 2. Pre-llenar el formulario
    initial_data = {}
    if destinatario_id_get:
        initial_data['destinatario'] = destinatario_id_get
    if asunto_previo:
        if not asunto_previo.startswith("Re:"):
            initial_data['asunto'] = f"Re: {asunto_previo}"
        else:
            initial_data['asunto'] = asunto_previo

    # 3. Buscar el mensaje original para mostrar el contexto (cuadro gris)
    mensaje_original = None
    if mensaje_original_id:
        try:
            mensaje_posible = MensajeInterno.objects.get(id=mensaje_original_id)
            if request.user in [mensaje_posible.destinatario, mensaje_posible.remitente]:
                mensaje_original = mensaje_posible
        except MensajeInterno.DoesNotExist:
            pass

    # 4. Procesar el envío
    if request.method == 'POST':
        # IMPORTANTE: request.FILES es necesario para subir archivos adjuntos
        form = MensajeForm(request.user, request.POST, request.FILES)
        
        if form.is_valid():
            
            # ==================================================================
            # 🛡️ INICIO: FILTRO DE SEGURIDAD (EL CENTINELA)
            # ==================================================================
            asunto_texto = form.cleaned_data.get('asunto', '')
            cuerpo_texto = form.cleaned_data.get('cuerpo', '')
            texto_completo = f"{asunto_texto} {cuerpo_texto}" # Analizamos todo

            es_toxico, motivo = Sentinel.is_toxic(texto_completo)

            if es_toxico:
                # A. Feedback al Usuario (Alerta)
                messages.error(request, '🚫 Mensaje bloqueado. Se ha detectado contenido inapropiado que infringe las normas de convivencia escolar.')
                
                # B. Registro Forense (Evidencia)
                try:
                    SecurityLog.objects.create(
                        usuario=request.user,
                        contenido_intentado=texto_completo,
                        razon_bloqueo=motivo or "Lenguaje ofensivo en Mensaje Interno"
                    )
                except Exception as e:
                    print(f"Error guardando log: {e}") # En producción usar logger

                # C. Interrupción: Devolvemos al usuario al formulario SIN enviar nada
                return render(request, 'chat/enviar.html', {
                    'form': form,
                    'mensaje_original': mensaje_original 
                })
            # ==================================================================
            # 🛡️ FIN DEL FILTRO (Si pasa, continúa con el envío)
            # ==================================================================

            # --- Extracción de Destinos (Individual o Masivo) ---
            
            # CRÍTICO: ModelChoiceField devuelve el objeto User (o None si es masivo/vacío)
            destinatario_obj = form.cleaned_data.get('destinatario')
            rol_masivo = form.cleaned_data.get('destinatario_rol_masivo')
            curso_masivo_id = form.cleaned_data.get('destinatario_curso_masivo')
            
            destinos_finales_ids = []
            
            if destinatario_obj:
                # 4.1. Caso Individual
                destinos_finales_ids = [destinatario_obj.id]
                
            else:
                # 4.2. Caso Masivo: Construir QuerySet de destinatarios
                
                # Obtener la QuerySet base de todos los usuarios, excluyendo al remitente
                qs = User.objects.exclude(id=request.user.id)
                
                if rol_masivo:
                    # Lógica para filtrar por rol
                    if rol_masivo == 'ALL_DOCENTES':
                        qs = qs.filter(perfil__rol='DOCENTE')
                    elif rol_masivo == 'ALL_ESTUDIANTES':
                        qs = qs.filter(perfil__rol='ESTUDIANTE')
                    elif rol_masivo == 'ALL_ACUDIENTES':
                        qs = qs.filter(perfil__rol='ACUDIENTE')
                    elif rol_masivo == 'ALL_STAFF':
                        qs = qs.filter(perfil__rol__in=['ADMINISTRADOR', 'COORD_ACADEMICO', 'COORD_CONVIVENCIA', 'PSICOLOGO'])
                    
                    # Lógica de Docente (Mis estudiantes/acudientes)
                    elif request.user.perfil.rol == 'DOCENTE':
                        if rol_masivo in ['MIS_ESTUDIANTES', 'MIS_ACUDIENTES']:
                            cursos_ids = AsignacionMateria.objects.filter(docente=request.user).values_list('curso_id', flat=True)
                            estudiantes_ids = Matricula.objects.filter(curso_id__in=cursos_ids).values_list('estudiante_id', flat=True)
                            
                            if rol_masivo == 'MIS_ESTUDIANTES':
                                qs = qs.filter(id__in=estudiantes_ids)
                            elif rol_masivo == 'MIS_ACUDIENTES':
                                acudientes_ids = Acudiente.objects.filter(estudiante_id__in=estudiantes_ids).values_list('acudiente_id', flat=True)
                                qs = qs.filter(id__in=acudientes_ids)

                    # Obtener las IDs finales de la queryset filtrada
                    destinos_finales_ids = list(qs.values_list('id', flat=True).distinct())


                elif curso_masivo_id:
                    # Lógica para filtrar por curso
                    try:
                        curso_id_int = int(curso_masivo_id) 
                    except ValueError:
                         messages.error(request, "Error: ID de curso inválida.")
                         return redirect('buzon_mensajes')
                    
                    estudiantes_curso_ids = Matricula.objects.filter(curso_id=curso_id_int).values_list('estudiante_id', flat=True)
                    acudientes_curso_ids = Acudiente.objects.filter(estudiante_id__in=estudiantes_curso_ids).values_list('acudiente_id', flat=True)
                    
                    all_ids = list(estudiantes_curso_ids) + list(acudientes_curso_ids)
                    
                    destinos_finales_ids = list(User.objects.filter(id__in=all_ids).exclude(id=request.user.id).values_list('id', flat=True).distinct())

            # 5. Guardar el Mensaje (Individual o Masivo)
            if destinos_finales_ids:
                
                try:
                    with transaction.atomic():
                        # 5.1. Guardar el primer mensaje (para tener el archivo subido)
                        mensaje_principal = form.save(commit=False)
                        mensaje_principal.remitente = request.user
                        mensaje_principal.destinatario_id = destinos_finales_ids[0]
                        mensaje_principal.save()
                        
                        # 5.2. Crear el resto de mensajes usando bulk_create (Clonación eficiente)
                        mensajes_adicionales = []
                        for user_id in destinos_finales_ids[1:]:
                            clone = MensajeInterno(
                                remitente=request.user,
                                destinatario_id=user_id,
                                asunto=mensaje_principal.asunto,
                                cuerpo=mensaje_principal.cuerpo,
                                archivo=mensaje_principal.archivo, 
                            )
                            mensajes_adicionales.append(clone)
                        
                        if mensajes_adicionales:
                            MensajeInterno.objects.bulk_create(mensajes_adicionales)

                    messages.success(request, f"Mensaje enviado exitosamente a {len(destinos_finales_ids)} destinatario(s).")
                    return redirect('buzon_mensajes')

                except Exception as e:
                    messages.error(request, f"Error al enviar el mensaje: {e}")
            else:
                 messages.error(request, "No se encontraron destinatarios válidos para el envío. Revisa tus filtros.")

        else:
             messages.error(request, "Error de validación: Por favor revisa los campos.")

    else:
        # Petición GET
        form = MensajeForm(request.user, initial=initial_data)
    
    # 5. Renderizar
    return render(request, 'chat/enviar.html', {
        'form': form,
        'mensaje_original': mensaje_original 
    })


@login_required
def leer_mensaje(request, mensaje_id):
    """
    Vista para ver la conversación completa y responder con archivos.
    PROTEGIDA CON SENTINEL (Filtro Anti-Acoso).
    """
    # Importaciones locales para asegurar disponibilidad
    from .models import MensajeInterno, SecurityLog
    from .utils import Sentinel
    
    # 1. Obtener el mensaje original
    mensaje_actual = get_object_or_404(MensajeInterno, id=mensaje_id)
    
    # Seguridad: Solo permitir ver si soy el remitente o el destinatario
    if request.user != mensaje_actual.destinatario and request.user != mensaje_actual.remitente:
        messages.error(request, "No tienes permiso para ver esta conversación.")
        return redirect('buzon_mensajes')

    # 2. Identificar al "otro" usuario en la conversación
    if mensaje_actual.remitente == request.user:
        otro_usuario = mensaje_actual.destinatario
    else:
        otro_usuario = mensaje_actual.remitente

    # ========================================================
    # 3. PROCESAR RESPUESTA (POST)
    # ========================================================
    if request.method == 'POST':
        cuerpo = request.POST.get('cuerpo', '').strip() # Asegurar string limpio
        archivo = request.FILES.get('archivo') # 🔥 CRÍTICO: Capturar el archivo

        # --- 🛡️ INICIO: FILTRO DE SEGURIDAD (EL CENTINELA) 🛡️ ---
        # Solo analizamos si hay texto escrito
        if cuerpo:
            es_toxico, motivo = Sentinel.is_toxic(cuerpo)

            if es_toxico:
                # A. Alerta al usuario
                messages.error(request, '🚫 Respuesta no enviada: Se detectó contenido inapropiado o irrespetuoso.')
                
                # B. Registro Forense (Silencioso para el admin)
                try:
                    SecurityLog.objects.create(
                        usuario=request.user,
                        contenido_intentado=cuerpo,
                        razon_bloqueo=motivo or "Lenguaje ofensivo en Respuesta de Chat"
                    )
                except Exception as e:
                    # En producción usarías logger, aquí print para depurar si falla
                    print(f"Error log seguridad: {e}")

                # C. Interrupción: Recargamos la página SIN guardar nada
                return redirect('leer_mensaje', mensaje_id=mensaje_id)
        # --- 🛡️ FIN DEL FILTRO 🛡️ ---

        # Solo guardamos si hay texto (y pasó el filtro) O hay un archivo
        if cuerpo or archivo:
            try:
                MensajeInterno.objects.create(
                    remitente=request.user,
                    destinatario=otro_usuario,
                    cuerpo=cuerpo, # Ya validado o vacío si solo es archivo
                    archivo=archivo, # 🔥 Guardamos el archivo en la BD
                    leido=False
                )
                # Recargamos la página para ver el mensaje enviado
                return redirect('leer_mensaje', mensaje_id=mensaje_id)
            except Exception as e:
                messages.error(request, f"Error al enviar: {e}")

    # 4. Marcar como leídos los mensajes que recibí de esa persona
    MensajeInterno.objects.filter(
        remitente=otro_usuario, 
        destinatario=request.user, 
        leido=False
    ).update(leido=True)

    # 5. Obtener el historial completo de la charla (Ordenado por fecha)
    historial = MensajeInterno.objects.filter(
        (Q(remitente=request.user) & Q(destinatario=otro_usuario)) |
        (Q(remitente=otro_usuario) & Q(destinatario=request.user))
    ).order_by('fecha_envio')

    # Asegúrate de que la ruta 'chat/leer.html' coincida con donde guardaste el HTML
    return render(request, 'chat/leer.html', {
        'mensaje_actual': mensaje_actual,
        'otro_usuario': otro_usuario,
        'historial': historial,
    })

# tasks/views.py

# tasks/views.py

#desde aqui 

# tasks/views.py

@role_required(['COORD_ACADEMICO', 'ADMINISTRADOR', 'PSICOLOGO', 'COORD_CONVIVENCIA'])
def dashboard_academico(request):
    """
    Tablero de Inteligencia Académica con MOTOR DE PREDICCIÓN.
    """
    # Pesos definidos en el sistema
    PESOS = {1: 0.20, 2: 0.30, 3: 0.30, 4: 0.20}

    # 1. Obtener notas finales que están perdiendo (< 3.0)
    # Filtramos solo cursos activos para datos reales
    notas_reprobadas = Nota.objects.filter(
        numero_nota=5, 
        valor__lt=3.0,
        materia__curso__activo=True
    ).select_related('estudiante', 'materia', 'materia__curso')

    # 2. PROCESAMIENTO Y PREDICCIÓN
    riesgo_map = {}
    
    for nota_final in notas_reprobadas:
        est_id = nota_final.estudiante.id
        
        # --- ALGORITMO DE PREDICCIÓN ---
        # 1. ¿Cuánto lleva acumulado?
        nota_acumulada = float(nota_final.valor)
        
        # 2. ¿Qué notas ya se tomaron? (Consultamos las parciales de este estudiante/materia)
        notas_parciales = Nota.objects.filter(
            estudiante=nota_final.estudiante,
            materia=nota_final.materia,
            periodo=nota_final.periodo,
            numero_nota__in=[1, 2, 3, 4]
        ).values_list('numero_nota', flat=True)
        
        # 3. Calcular peso evaluado y peso restante
        peso_evaluado = sum(PESOS[n] for n in notas_parciales)
        peso_restante = 1.0 - peso_evaluado
        
        # 4. Proyección: ¿Qué nota necesita en lo que falta para pasar con 3.0?
        # Fórmula: (Meta - Acumulado) / Peso_Restante
        if peso_restante > 0.05: # Si falta más del 5% por evaluar
            nota_necesaria = (3.0 - nota_acumulada)
            # Como el acumulado ya está ponderado, la nota necesaria matemática es directa si asumimos 
            # que nota_acumulada es la suma de (nota * peso).
            # Ajuste: nota_final.valor en tu sistema es la SUMA PONDERADA.
            # Meta acumulada total es 3.0.
            # Puntos que faltan = 3.0 - nota_acumulada.
            # Esos puntos deben conseguirse en el 'peso_restante'.
            # Nota promedio necesaria = Puntos Faltantes / Peso Restante.
            promedio_necesario = (3.0 - nota_acumulada) / peso_restante
        else:
            promedio_necesario = 100.0 # Ya no hay tiempo, nota infinita necesaria

        # 5. Clasificar Riesgo / Probabilidad de Pérdida
        if promedio_necesario > 5.0:
            probabilidad = "100% (Irrecuperable)"
            clase_riesgo = "bg-dark text-white" # Ya perdió matemáticamente
            nivel_riesgo = "CRÍTICO"
        elif promedio_necesario > 4.0:
            probabilidad = "85% (Muy Alta)"
            clase_riesgo = "bg-danger text-white"
            nivel_riesgo = "ALTO"
        elif promedio_necesario > 3.0:
            probabilidad = "50% (Media)"
            clase_riesgo = "bg-warning text-dark"
            nivel_riesgo = "MEDIO"
        else:
            probabilidad = "20% (Baja)"
            clase_riesgo = "bg-info text-dark"
            nivel_riesgo = "BAJO"

        # --- FIN ALGORITMO ---

        if est_id not in riesgo_map:
            riesgo_map[est_id] = {
                'estudiante': nota_final.estudiante,
                'curso': nota_final.materia.curso.nombre,
                'total_perdidas': 0,
                'materias': []
            }
        
        riesgo_map[est_id]['total_perdidas'] += 1
        riesgo_map[est_id]['materias'].append({
            'nombre': nota_final.materia.nombre,
            'nota_actual': nota_acumulada,
            'nota_necesaria': round(promedio_necesario, 2) if promedio_necesario < 10 else "> 5.0",
            'probabilidad': probabilidad,
            'clase_riesgo': clase_riesgo,
            'periodo': nota_final.periodo.nombre
        })

    # Ordenar: Primero los que tienen más materias perdidas
    lista_riesgo = sorted(riesgo_map.values(), key=lambda x: x['total_perdidas'], reverse=True)

    # 3. KPIs GLOBALES (Para las tarjetas de arriba)
    all_notas_finales = Nota.objects.filter(numero_nota=5, materia__curso__activo=True)
    total_evaluaciones = all_notas_finales.count()
    promedio_global = all_notas_finales.aggregate(Avg('valor'))['valor__avg'] or 0
    conteo_reprobadas = notas_reprobadas.count()
    tasa_reprobacion = (conteo_reprobadas / total_evaluaciones * 100) if total_evaluaciones > 0 else 0

    # 4. GRÁFICOS
    rendimiento_cursos = all_notas_finales.values('materia__curso__nombre').annotate(prom=Avg('valor')).order_by('materia__curso__nombre')
    labels_cursos = [x['materia__curso__nombre'] for x in rendimiento_cursos]
    data_cursos = [float(round(x['prom'], 2)) for x in rendimiento_cursos]

    rendimiento_materias = all_notas_finales.values('materia__nombre').annotate(prom=Avg('valor')).order_by('prom')[:10]
    labels_materias = [x['materia__nombre'] for x in rendimiento_materias]
    data_materias = [float(round(x['prom'], 2)) for x in rendimiento_materias]

    context = {
        'lista_riesgo': lista_riesgo,
        'kpi': {
            'promedio': round(promedio_global, 2),
            'tasa_reprobacion': round(tasa_reprobacion, 1),
            'total_evaluaciones': total_evaluaciones,
            'reprobadas': conteo_reprobadas
        },
        'chart_cursos_labels': json.dumps(labels_cursos),
        'chart_cursos_data': json.dumps(data_cursos),
        'chart_materias_labels': json.dumps(labels_materias),
        'chart_materias_data': json.dumps(data_materias),
        # Datos para dona (Aprobados vs Reprobados)
        'chart_distribucion_data': json.dumps([total_evaluaciones - conteo_reprobadas, conteo_reprobadas])
    }
    
    return render(request, 'admin/dashboard_academico.html', context)
# tasks/views.py (Agregar al final)

@role_required(STAFF_ROLES)
def historial_asistencia(request):
    """
    Vista para que Coordinación vea el histórico completo de asistencia.
    Permite filtrar por Curso y Estado (Falla, Tarde, etc).
    """
    # Filtros
    curso_id = request.GET.get('curso')
    estado = request.GET.get('estado')
    
    # Consulta base: Traemos todo ordenado por fecha (lo más reciente primero)
    asistencias = Asistencia.objects.select_related('estudiante', 'curso', 'materia', 'registrado_por').all().order_by('-fecha')

    # Aplicar filtros si existen
    if curso_id:
        asistencias = asistencias.filter(curso_id=curso_id)
    if estado:
        asistencias = asistencias.filter(estado=estado)
    
    # Paginación: 50 registros por página para no saturar
    paginator = Paginator(asistencias, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Listas para los selectores de filtro
    cursos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')
    
    return render(request, 'bienestar/historial_asistencia.html', {
        'page_obj': page_obj,
        'cursos': cursos,
        'current_curso': int(curso_id) if curso_id else '',
        'current_estado': estado,
        'total_registros': asistencias.count()
    })

# tasks/views.py

# ... (resto del código anterior) ...

# ===================================================================
# 🩺 MÓDULO DE BIENESTAR: PANEL PRINCIPAL
# ===================================================================

# Roles permitidos para el módulo
#Desde aqui
# ... (Importaciones anteriores se mantienen igual) ...

@role_required(STAFF_ROLES)
def dashboard_bienestar(request):
    """
    VISTA MAESTRA DE INTELIGENCIA INSTITUCIONAL - STRATOS
    ---------------------------------------------------
    - Gestión Documental (PEI/Manual).
    - Radar de Riesgo Académico Integral (Ranking de Reprobación).
    - Analítica de Asistencia y Deserción.
    - Control de Clima Escolar (Convivencia).
    - Gestión por Grupos (Acordeones).
    - [NUEVO] Historial de Seguimientos y Observaciones.
    """
    
    # ===================================================================
    # 0. GESTIÓN DOCUMENTAL (PEI / MANUAL)
    # ===================================================================
    if request.method == 'POST':
        # Subida de PEI
        if 'pei_file' in request.FILES:
            if request.user.perfil.rol in ['COORD_ACADEMICO', 'ADMINISTRADOR']:
                institucion, _ = Institucion.objects.get_or_create(id=1)
                archivo = request.FILES['pei_file']
                if archivo.name.lower().endswith('.pdf'):
                    institucion.archivo_pei = archivo
                    institucion.save()
                    messages.success(request, "✅ Proyecto Educativo Institucional (PEI) actualizado.")
                else:
                    messages.error(request, "❌ Error: El archivo debe ser un formato PDF válido.")
        
        # Subida de Manual de Convivencia (Expandido)
        elif 'manual_file' in request.FILES:
            if request.user.perfil.rol in ['COORD_CONVIVENCIA', 'ADMINISTRADOR']:
                institucion, _ = Institucion.objects.get_or_create(id=1)
                archivo = request.FILES['manual_file']
                if archivo.name.lower().endswith('.pdf'):
                    institucion.archivo_manual_convivencia = archivo
                    institucion.save()
                    messages.success(request, "✅ Manual de Convivencia actualizado correctamente.")
                else:
                    messages.error(request, "❌ Error: Solo se permiten archivos PDF.")
        
        return redirect('dashboard_bienestar')

    # ===================================================================
    # 1. MOTOR DE BÚSQUEDA INTELIGENTE
    # ===================================================================
    query = request.GET.get('q')
    estudiantes_busqueda = []
    if query:
        estudiantes_busqueda = User.objects.filter(
            Q(perfil__rol='ESTUDIANTE') &
            (Q(username__icontains=query) |
             Q(first_name__icontains=query) |
             Q(last_name__icontains=query))
        ).select_related('perfil').distinct()[:25]

    # ===================================================================
    # 2. RADAR DE RIESGO ACADÉMICO (EL MOTOR SOLICITADO)
    # ===================================================================
    # Escaneamos TODA la población estudiantil activa
    matriculas_activas = Matricula.objects.filter(activo=True).select_related('estudiante', 'curso')
    riesgo_academico_total = []
    total_materias_perdidas_institucional = 0

    for mat in matriculas_activas:
        est = mat.estudiante
        
        # Buscamos notas definitivas (Nota 5) menores a 3.0
        # Excluimos Convivencia para que el radar sea puramente académico
        notas_reprobadas = Nota.objects.filter(
            estudiante=est,
            numero_nota=5,
            valor__lt=3.0
        ).exclude(materia__nombre__icontains="Convivencia").select_related('materia')

        conteo_perdidas = notas_reprobadas.count()
        
        if conteo_perdidas > 0:
            total_materias_perdidas_institucional += conteo_perdidas
            
            # Recopilamos los nombres de las materias que está perdiendo
            materias_nombres = [n.materia.nombre for n in notas_reprobadas]
            
            # Calculamos promedio de las materias que pierde para desempatar riesgo
            prom_reprobacion = notas_reprobadas.aggregate(avg=Avg('valor'))['avg'] or 0

            riesgo_academico_total.append({
                'estudiante': est,
                'curso': mat.curso,
                'materias_perdidas': conteo_perdidas,
                'materias_nombres': materias_nombres,
                'promedio_riesgo': round(float(prom_reprobacion), 2)
            })

    # ORDENAMIENTO MAESTRO: Por cantidad de materias (Desc) y luego por promedio más bajo (Asc)
    riesgo_academico_total.sort(key=lambda x: (-x['materias_perdidas'], x['promedio_riesgo']))

    # ===================================================================
    # 3. ANALÍTICA DE GESTIÓN POR CURSOS (KPIs Y GRÁFICOS)
    # ===================================================================
    cursos_activos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')
    
    periodos_header = []
    primer_curso = cursos_activos.first()
    if primer_curso:
        periodos_header = Periodo.objects.filter(curso=primer_curso, activo=True).order_by('id')

    total_estudiantes_colegio = matriculas_activas.count()
    suma_promedios_acad = 0.0
    suma_promedios_conv = 0.0
    cursos_con_datos_acad = 0
    cursos_con_datos_conv = 0

    chart_labels = []      
    chart_data_acad = []   
    chart_data_conv = []  
    vista_cursos = []
    
    for curso in cursos_activos:
        mats_curso = matriculas_activas.filter(curso=curso)
        num_alumnos = mats_curso.count()

        # A. Promedio Convivencia del Curso
        val_conv = Nota.objects.filter(
            estudiante__matriculas__curso=curso,
            materia__nombre__icontains="Convivencia"
        ).aggregate(avg=Avg('valor'))['avg']
        prom_conv_curso = float(val_conv) if val_conv is not None else 0.0

        # B. Promedio Académico del Curso
        val_acad = Nota.objects.filter(
            estudiante__matriculas__curso=curso
        ).exclude(materia__nombre__icontains="Convivencia").aggregate(avg=Avg('valor'))['avg']
        prom_acad_curso = float(val_acad) if val_acad is not None else 0.0

        if num_alumnos > 0:
            chart_labels.append(f"{curso.nombre}")
            chart_data_acad.append(round(prom_acad_curso, 2))
            chart_data_conv.append(round(prom_conv_curso, 2))
            
            if prom_acad_curso > 0:
                suma_promedios_acad += prom_acad_curso
                cursos_con_datos_acad += 1
            if prom_conv_curso > 0:
                suma_promedios_conv += prom_conv_curso
                cursos_con_datos_conv += 1

        # Detalle para el Acordeón
        periodos_del_curso = list(Periodo.objects.filter(curso=curso, activo=True).order_by('id'))
        lista_estudiantes_curso = []
        ranking_academico_curso = []
        
        for m in mats_curso:
            estudiante = m.estudiante
            
            # Notas de convivencia para la tabla
            notas_conv_periodo = {}
            for p in periodos_del_curso:
                n_obj = Nota.objects.filter(
                    estudiante=estudiante, 
                    periodo=p, 
                    materia__nombre__icontains="Convivencia"
                ).aggregate(promedio=Avg('valor'))['promedio']
                notas_conv_periodo[p.id] = round(n_obj, 1) if n_obj is not None else "-"
            
            lista_estudiantes_curso.append({
                'obj': estudiante,
                'notas': notas_conv_periodo
            })

            # Datos para el Top 10 del grupo
            p_ind = Nota.objects.filter(estudiante=estudiante, materia__curso=curso).exclude(materia__nombre__icontains="Convivencia").aggregate(p=Avg('valor'))['p']
            ranking_academico_curso.append({
                'nombre': estudiante.get_full_name() or estudiante.username,
                'promedio': round(float(p_ind or 0), 2)
            })

        ranking_academico_curso.sort(key=lambda x: x['promedio'], reverse=True)

        if lista_estudiantes_curso:
            vista_cursos.append({
                'curso': curso,
                'estudiantes': lista_estudiantes_curso,
                'stats': {
                    'acad': round(prom_acad_curso, 2), 
                    'conv': round(prom_conv_curso, 2), 
                    'alumnos': num_alumnos
                },
                'top_10_academico': ranking_academico_curso[:10]
            })

    # ===================================================================
    # 4. KPIs FINALES Y ALERTAS
    # ===================================================================
    prom_global_acad = round(suma_promedios_acad / cursos_con_datos_acad, 2) if cursos_con_datos_acad > 0 else 0
    prom_global_conv = round(suma_promedios_conv / cursos_con_datos_conv, 2) if cursos_con_datos_conv > 0 else 0

    stats_asistencia = {
        'asistio': Asistencia.objects.filter(estado='ASISTIO').count(),
        'falla': Asistencia.objects.filter(estado='FALLA').count(),
        'excusa': Asistencia.objects.filter(estado='EXCUSA').count(),
        'tarde': Asistencia.objects.filter(estado='TARDE').count(),
    }
    
    top_fallas = Asistencia.objects.filter(estado='FALLA')\
        .values('estudiante__id', 'estudiante__first_name', 'estudiante__last_name', 'curso__nombre')\
        .annotate(total=Count('id'))\
        .order_by('-total')[:5]

    alertas_convivencia = Nota.objects.filter(materia__nombre__icontains="Convivencia")\
        .values('estudiante__id', 'estudiante__first_name', 'estudiante__last_name', 'materia__curso__nombre')\
        .annotate(promedio=Avg('valor'))\
        .filter(promedio__lt=3.5).order_by('promedio')[:5]
    
    institucion = Institucion.objects.first()

    # ===================================================================
    # 5. [AGREGADO] HISTORIAL DE SEGUIMIENTOS Y OBSERVACIONES
    # ===================================================================
    # Obtenemos los seguimientos para la tabla de historial inferior
    historial_seguimientos = Seguimiento.objects.select_related(
        'estudiante', 'profesional'
    ).all().order_by('-fecha')[:100]

    # Obtenemos las observaciones para la tabla maestra superior (Registro de casos)
    # Filtramos si hay query de búsqueda
    base_observaciones = Observacion.objects.select_related(
        'estudiante', 'autor'
    ).all().order_by('-fecha_creacion')

    if query:
        base_observaciones = base_observaciones.filter(
            Q(estudiante__username__icontains=query) |
            Q(estudiante__first_name__icontains=query) |
            Q(estudiante__last_name__icontains=query) |
            Q(descripcion__icontains=query)
        )
    
    # Limitamos para no saturar la vista inicial
    observaciones = base_observaciones[:50]

    context = {
        'estudiantes': estudiantes_busqueda, 
        'query': query,
        'vista_cursos': vista_cursos,
        'periodos': periodos_header,
        'institucion': institucion,
        'top_riesgo_academico': riesgo_academico_total, 
        'kpi': {
            'total_alumnos': total_estudiantes_colegio,
            'prom_global_acad': prom_global_acad,
            'prom_global_conv': prom_global_conv,
            'total_cursos': cursos_activos.count(),
            'total_materias_perdidas': total_materias_perdidas_institucional 
        },
        'chart_data': {
            'labels': json.dumps(chart_labels),
            'acad': json.dumps(chart_data_acad),
            'conv': json.dumps(chart_data_conv)
        },
        'stats_asistencia': json.dumps(list(stats_asistencia.values())),
        'top_fallas': top_fallas,
        'alertas_convivencia': alertas_convivencia,
        
        # --- NUEVOS DATOS PARA HISTORIAL Y PDF ---
        'historial_seguimientos': historial_seguimientos, # Para la tabla inferior
        'observaciones': observaciones, # Para la tabla superior (Maestra)
    }

    return render(request, 'bienestar/dashboard_bienestar.html', context)
#Hasta Aqui 
@role_required(['COORD_ACADEMICO', 'ADMINISTRADOR', 'PSICOLOGO', 'COORD_CONVIVENCIA'])
def reporte_consolidado(request):
    """
    Genera una 'Sábana de Notas' (Matriz Estudiantes vs Materias).
    CORREGIDO: Ahora incluye la institución en el contexto para evitar errores de renderizado.
    """
    cursos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')
    periodos = None
    
    # Filtros seleccionados
    curso_id = request.GET.get('curso_id')
    periodo_id = request.GET.get('periodo_id')
    
    datos_reporte = []
    materias = []
    curso_seleccionado = None
    periodo_seleccionado = None

    if curso_id:
        curso_seleccionado = get_object_or_404(Curso, id=curso_id)
        # Cargamos los periodos del curso seleccionado
        periodos = Periodo.objects.filter(curso_id=curso_id).order_by('id')

        if periodo_id:
            periodo_seleccionado = get_object_or_404(Periodo, id=periodo_id)
            
            # 1. Obtener todas las materias del curso
            materias = Materia.objects.filter(curso=curso_seleccionado).order_by('nombre')
            
            # 2. Obtener estudiantes matriculados
            matriculas = Matricula.objects.filter(curso=curso_seleccionado, activo=True).select_related('estudiante').order_by('estudiante__last_name')
            
            # 3. Construir la matriz
            for mat in matriculas:
                estudiante = mat.estudiante
                notas_estudiante = []
                promedio_acumulado = 0.0
                materias_perdidas = 0
                materias_con_nota = 0 # Contador para saber cuántas materias se promedian
                
                for materia in materias:
                    # Buscar la nota final (numero_nota=5) de este estudiante en esta materia y periodo
                    # Usamos .first() para seguridad
                    nota_obj = Nota.objects.filter(
                        estudiante=estudiante, 
                        materia=materia, 
                        periodo=periodo_seleccionado,
                        numero_nota=5
                    ).first()
                    
                    valor = float(nota_obj.valor) if nota_obj else 0.0
                    
                    if valor > 0:
                        materias_con_nota += 1
                        if valor < 3.0:
                            materias_perdidas += 1
                    
                    notas_estudiante.append({
                        'materia_id': materia.id,
                        'valor': valor
                    })
                    promedio_acumulado += valor

                # Cálculo seguro del promedio (Evitar división por cero)
                if len(materias) > 0:
                    # Opción A: Promedio sobre total de materias (diluye si faltan notas)
                    promedio_general = promedio_acumulado / len(materias)
                    # Opción B (Alternativa): promedio_general = promedio_acumulado / materias_con_nota if materias_con_nota > 0 else 0
                else:
                    promedio_general = 0.0
                
                datos_reporte.append({
                    'estudiante': estudiante,
                    'notas': notas_estudiante,
                    'promedio': round(promedio_general, 2),
                    'perdidas': materias_perdidas
                })

    # 4. CRÍTICO: Obtener la institución para el encabezado del reporte
    institucion = Institucion.objects.first()

    return render(request, 'admin/reporte_consolidado.html', {
        'cursos': cursos,
        'periodos': periodos,
        'curso_seleccionado': curso_seleccionado,
        'periodo_seleccionado': periodo_seleccionado,
        'materias': materias,
        'datos_reporte': datos_reporte,
        'institucion': institucion, # <--- ESTA LÍNEA ES LA QUE FALTABA Y ARREGLA EL ERROR
    })


# En views.py
def sabana_notas(request):
    """
    Vista alternativa o complementaria para la sábana de notas.
    """
    # 1. Configuración inicial
    cursos = Curso.objects.all().order_by('nombre')
    
    # Obtenemos nombres únicos de periodos para evitar duplicados en el selector
    nombres_periodos = Periodo.objects.values_list('nombre', flat=True).distinct().order_by('nombre')
    
    # Obtenemos la información del colegio para el encabezado oficial
    institucion = Institucion.objects.first()

    context = {
        'cursos': cursos,
        'nombres_periodos': nombres_periodos,
        'institucion': institucion, # Pasamos la info del colegio al template
        'datos_reporte': [],
        'materias': [],
        'curso_seleccionado': None,
        'periodo_seleccionado': None,
    }

    # 2. Captura de parámetros
    curso_id = request.GET.get('curso_id')
    periodo_nombre = request.GET.get('periodo_nombre')

    if curso_id and periodo_nombre:
        curso_seleccionado = get_object_or_404(Curso, id=curso_id)
        
        # Buscamos el periodo específico que pertenece a este curso por nombre
        periodo_seleccionado = Periodo.objects.filter(
            curso=curso_seleccionado, 
            nombre=periodo_nombre
        ).first()

        if periodo_seleccionado:
            context['curso_seleccionado'] = curso_seleccionado
            context['periodo_seleccionado'] = periodo_seleccionado

            # 3. Obtener Estudiantes Matriculados
            estudiantes_matriculados = Matricula.objects.filter(
                curso=curso_seleccionado,
                activo=True
            ).select_related('estudiante').order_by('estudiante__last_name')
            
            estudiante_ids = estudiantes_matriculados.values_list('estudiante_id', flat=True)

            # 4. Obtener Materias (Búsqueda Completa)
            # Busca: Materias del curso O Materias asignadas O Materias con notas existentes
            materias = Materia.objects.filter(
                Q(curso=curso_seleccionado) | 
                Q(asignaciones__curso=curso_seleccionado) |
                Q(notas__estudiante_id__in=estudiante_ids, notas__periodo=periodo_seleccionado)
            ).distinct().order_by('nombre')
            
            context['materias'] = materias

            # 5. Obtener Notas y Promediar (para definitivas)
            notas_qs = Nota.objects.filter(
                estudiante_id__in=estudiante_ids,
                periodo=periodo_seleccionado,
                materia__in=materias
            ).values('estudiante_id', 'materia_id').annotate(definitiva=Avg('valor'))

            # Mapa rápido para acceso O(1)
            notas_map = {
                (n['estudiante_id'], n['materia_id']): n['definitiva'] 
                for n in notas_qs
            }

            # 6. Armar la Matriz de Datos
            datos_reporte = []

            for matricula in estudiantes_matriculados:
                estudiante = matricula.estudiante
                lista_notas = []
                suma_promedios = 0
                materias_con_nota = 0
                perdidas = 0

                for materia in materias:
                    clave = (estudiante.id, materia.id)
                    valor = notas_map.get(clave, 0)
                    valor = float(round(valor, 1)) if valor else 0.0

                    if valor > 0:
                        suma_promedios += valor
                        materias_con_nota += 1
                        if valor < 3.0:
                            perdidas += 1
                    
                    lista_notas.append({'valor': valor})

                promedio_general = 0
                if materias_con_nota > 0:
                    promedio_general = round(suma_promedios / materias_con_nota, 2)

                datos_reporte.append({
                    'estudiante': estudiante,
                    'notas': lista_notas,
                    'promedio': promedio_general,
                    'perdidas': perdidas
                })

            context['datos_reporte'] = datos_reporte

    return render(request, 'admin/reporte_consolidado.html', context)

##fase 4 inicio 

# ===================================================================
# 🛡️ FASE IV (PASO 16): LÓGICA DE MODERACIÓN Y AUDITORÍA
# ===================================================================

# Nota: El decorador @role_required asume que tienes una implementación personalizada.
# Asumo que las clases Post y Comment también están importadas correctamente.

@login_required
# Mantenemos el decorador que me proporcionaste (asumo que 'role_required' existe y funciona)
@role_required(['ADMINISTRADOR', 'COORD_CONVIVENCIA', 'PSICOLOGO', 'COORD_ACADEMICO', 'DOCENTE'])
@require_POST
def moderar_eliminar_contenido(request):
    """
    API para eliminar Posts o Comentarios ofensivos.
    Genera un registro forense en AuditLog antes de borrar el objeto.
    """
    import json
    try:
        data = json.loads(request.body)
        
        # 🔥 CORRECCIÓN CRÍTICA: Cambiar 'tipo' por 'type' para coincidir con el JS del frontend.
        tipo_contenido = data.get('type') # Ahora busca 'type'
        item_id = data.get('id')
        motivo = data.get('motivo', 'Moderación por contenido inapropiado')

        # 1. Identificar el objeto
        if tipo_contenido == 'post':
            objeto = get_object_or_404(Post, id=item_id)
            autor_original = objeto.autor.username
            resumen_contenido = objeto.contenido[:100] 
            modelo_nombre = "Post Social"
            
        elif tipo_contenido == 'comment':
            objeto = get_object_or_404(Comment, id=item_id)
            autor_original = objeto.autor.username
            resumen_contenido = objeto.contenido[:100]
            modelo_nombre = "Comentario Social"
            
        else:
            # Ahora este error solo se disparará si el frontend envía un tipo inválido.
            return JsonResponse({'success': False, 'error': 'Tipo de contenido no válido'}, status=400)

        # 2. Seguridad: Verificación de Autoría Adicional
        # El decorador @role_required ya maneja que solo staff pueda acceder a esta API.
        # Ahora verificamos si el usuario es el autor, o el autor del post padre (si es comentario).
        
        es_admin = request.user.perfil.rol == 'ADMINISTRADOR'
        es_autor = objeto.autor == request.user
        
        if tipo_contenido == 'comment':
            # Si es un comentario, el autor del post también puede borrarlo.
            es_autor_post = objeto.post.autor == request.user
        else:
            es_autor_post = False
            
        if not (es_admin or es_autor or es_autor_post):
             return JsonResponse({'success': False, 'error': 'Permiso denegado: No es autor ni administrador.'}, status=403)


        # 3. AUDITORÍA FORENSE (La Caja Negra)
        AuditLog.objects.create(
            usuario=request.user, 
            accion='DELETE (MODERATION)',
            modelo_afectado=modelo_nombre,
            objeto_id=str(item_id),
            detalles=f"Autor original: {autor_original}. Moderado por: {request.user.username}. Motivo: {motivo}. Contenido eliminado: '{resumen_contenido}...'",
            ip_address=request.META.get('REMOTE_ADDR')
        )

        # 4. Eliminar el objeto
        objeto.delete()

        return JsonResponse({'success': True, 'message': 'Contenido eliminado y evento auditado correctamente.'})

    except Post.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'El post no fue encontrado.'}, status=404)
    except Comment.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'El comentario no fue encontrado.'}, status=404)
    except Exception as e:
        # Usamos logger.error en lugar de logger.exception si el objeto 'logger' es estándar
        logger.error(f"Error interno en moderación: {e}", exc_info=True) 
        return JsonResponse({'success': False, 'error': f'Error interno del servidor.'}, status=500)

# ===================================================================
# 🏗️ FASE IV (PASO 17): VISTA DEL FEED SOCIAL (MURO)
# ===================================================================

# ===================================================================
# 🏗️ FASE IV (PASO 17 - CORREGIDO): VISTA DEL FEED SOCIAL (MURO GLOBAL)
# ===================================================================

@login_required
def social_feed(request):
    """
    Muro Social Comunitario.
    Maneja la creación de Posts, Comentarios, Grupos y la Búsqueda.
    IMPORTANTE: El feed principal SOLO muestra posts GENERALES (donde grupo es NULL).
    """
    # 🛡️ IMPORTACIONES LOCALES DE SEGURIDAD
    from .models import Post, Comment, SocialGroup
    from .forms import PostForm
    from django.core.paginator import Paginator
    from django.db.models import Q # Importamos Q para el OR en las búsquedas
    from django.shortcuts import redirect
    from django.contrib import messages

    # 1. Recuperar posts base: SOLO PUBLICACIONES GENERALES (grupo__isnull=True)
    posts_qs = Post.objects.filter(
        grupo__isnull=True  # 🔥 FILTRO CRÍTICO: Excluye posts hechos dentro de grupos
    ).select_related(
        'autor', 
        'autor__perfil',
        'grupo' 
    ).prefetch_related(
        'comentarios', 
        'comentarios__autor__perfil', 
        'reacciones',
        'reacciones__usuario'
    ).order_by('-es_destacado', '-creado_en')

    # 1.1. Lógica de BÚSQUEDA (Aplicada sobre los posts generales)
    query = request.GET.get('q')
    if query:
        # Si hay búsqueda, filtra los posts generales por Contenido o Autor
        posts_qs = posts_qs.filter(
            Q(contenido__icontains=query) | 
            Q(autor__first_name__icontains=query) |
            Q(autor__last_name__icontains=query) |
            Q(autor__username__icontains=query)
        ).distinct()
        
    # 2. Paginación
    paginator = Paginator(posts_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 3. Inicializar formulario
    form = PostForm()

    # 4. Procesar Formularios (Post vs Comentario)
    if request.method == 'POST':
        # 🟢 CASO A: CREAR UN POST
        if 'publicar_post' in request.POST:
            form = PostForm(request.POST, request.FILES)
            if form.is_valid():
                nuevo_post = form.save(commit=False)
                nuevo_post.autor = request.user
                
                # Verificar si es anuncio oficial (solo admins)
                if request.user.perfil.rol == 'ADMINISTRADOR' and 'es_anuncio' in request.POST:
                     nuevo_post.tipo = 'ANUNCIO'
                
                # Nota: Si el post no tiene 'grupo' en el formulario (por defecto), 
                # se guardará con grupo=NULL, cumpliendo el filtro del feed.
                nuevo_post.save()
                messages.success(request, '¡Publicación creada!')
                return redirect('social_feed') 
            else:
                messages.error(request, 'Error al publicar. Verifica el contenido.')

        # 🔵 CASO B: CREAR UN COMENTARIO
        elif 'publicar_comentario' in request.POST:
            post_id = request.POST.get('post_id')
            contenido = request.POST.get('contenido')
            
            if post_id and contenido:
                try:
                    post = Post.objects.get(id=post_id)
                    Comment.objects.create(
                        post=post,
                        autor=request.user,
                        contenido=contenido
                    )
                    messages.success(request, 'Comentario agregado.')
                    return redirect('social_feed') 
                except Post.DoesNotExist:
                    messages.error(request, 'El post que intentas comentar no existe.')
            else:
                messages.warning(request, 'El comentario no puede estar vacío.')

    # 5. DATOS PARA LA BARRA LATERAL (GRUPOS)
    grupos_sugeridos = SocialGroup.objects.all().prefetch_related('members').order_by('-created_at')[:5]
    
    context = {
        'page_obj': page_obj, 
        'post_form': form,
        'titulo_seccion': 'Comunidad Learning Labs',
        'grupos_sugeridos': grupos_sugeridos,
        'q': query # Devolvemos el query para que el buscador mantenga el texto
    }

    return render(request, 'social_feed.html', context)

# ===================================================================
# ⚡ FASE IV (PASO 18): API DE REACCIONES (AJAX)
# ===================================================================

@login_required
@require_POST
def api_reaction(request):
    """
    Endpoint AJAX para alternar reacciones (Like/Love/etc) en Posts o Comentarios.
    Retorna JSON con el nuevo conteo para actualizar el frontend sin recargar.
    """
    try:
        data = json.loads(request.body)
        obj_type = data.get('type') # 'post' o 'comment'
        obj_id = data.get('id')
        reaction_type = data.get('reaction', 'LIKE') # Default a LIKE

        # 1. Determinar el modelo al que se reacciona
        if obj_type == 'post':
            model = Post
        elif obj_type == 'comment':
            model = Comment
        else:
            return JsonResponse({'success': False, 'error': 'Tipo de objeto inválido'}, status=400)

        # 2. Obtener el objeto y su ContentType
        obj = get_object_or_404(model, id=obj_id)
        ct = ContentType.objects.get_for_model(model)

        # 3. Lógica de Toggle (Poner/Quitar/Cambiar)
        # Buscamos si ya existe una reacción de este usuario a este objeto
        reaction, created = Reaction.objects.get_or_create(
            usuario=request.user,
            content_type=ct,
            object_id=obj.id,
            defaults={'tipo': reaction_type}
        )

        action = ''
        if not created:
            # Si ya existía...
            if reaction.tipo == reaction_type:
                # ...y es la misma (dio Like a lo que ya tenía Like), la borramos (Toggle OFF)
                reaction.delete()
                action = 'removed'
            else:
                # ...pero es diferente (tenía Like y dio Love), la actualizamos
                reaction.tipo = reaction_type
                reaction.save()
                action = 'updated'
        else:
            # Si se creó nueva (Toggle ON)
            action = 'added'
            # --- GAMIFICACIÓN (Paso 22) ---
            # Aquí dispararemos la señal para dar puntos al autor del post en el futuro.

        # 4. Calcular totales actualizados para el frontend
        # Contamos cuántas reacciones quedan para actualizar el numerito en pantalla
        total = Reaction.objects.filter(content_type=ct, object_id=obj.id).count()
        
        # Opcional: Contar por tipos específicos si quieres mostrar "5 Likes, 2 Loves"
        # por ahora devolvemos el total general.

        return JsonResponse({
            'success': True,
            'action': action,
            'total': total,
            'current_reaction': reaction_type if action != 'removed' else None
        })

    except Exception as e:
        logger.exception(f"Error en api_reaction: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# ===================================================================
# 🤝 FASE IV (PASO 19): API SEGUIR USUARIOS (NETWORKING)
# ===================================================================

# Dentro de tasks/views.py (asumiendo que logger y las clases se importan arriba)

@login_required
@require_POST
def toggle_follow(request):
    """
    Alterna la relación de seguimiento usando explícitamente el modelo intermedio Follow.
    Esto soluciona el error "'Follow' instance expected".
    """
    try:
        data = json.loads(request.body)
        user_to_follow_id = data.get('user_id')

        if not user_to_follow_id:
            return JsonResponse({'success': False, 'error': 'ID de usuario no proporcionado'}, status=400)

        # Convertir a entero y validar
        user_id_int = int(user_to_follow_id)
        
        if user_id_int == request.user.id:
            return JsonResponse({'success': False, 'error': 'No puedes seguirte a ti mismo'}, status=400)

        target_user = get_object_or_404(User, id=user_id_int)
        
        # 🔥 LÓGICA DE TOGGLE CON MODELO INTERMEDIO 'Follow' 🔥
        # Buscamos si existe la relación en la tabla intermedia
        follow_instance = Follow.objects.filter(follower=request.user, following=target_user).first()
        
        action = ''
        message = ''
        
        if follow_instance:
            # Si existe, la borramos (Unfollow)
            follow_instance.delete()
            action = 'unfollowed'
            message = f"Dejaste de seguir a {target_user.username}"
        else:
            # Si no existe, la creamos (Follow)
            Follow.objects.create(follower=request.user, following=target_user)
            action = 'followed'
            message = f"Ahora sigues a {target_user.username}"
            
            # Notificación (Opcional)
            try:
                from .utils import crear_notificacion
                crear_notificacion(
                    target_user,
                    "Nuevo Seguidor",
                    f"{request.user.get_full_name()} ha comenzado a seguirte.",
                    "SISTEMA",
                    f"/social/profile/{request.user.username}/" 
                )
            except ImportError:
                pass # Ignorar si utils no está disponible o falla la importación

        # Devolver nuevos contadores consultando la tabla Follow
        # Contamos cuántas veces target_user aparece como 'following' (sus seguidores)
        followers_count = Follow.objects.filter(following=target_user).count()
        # Contamos cuántas veces el usuario actual aparece como 'follower' (a quién sigue)
        following_count = Follow.objects.filter(follower=request.user).count()

        return JsonResponse({
            'success': True,
            'action': action,
            'followers_count': followers_count,
            'following_count': following_count,
            'message': message
        })

    except Exception as e:
        logger.error(f"Error en toggle_follow: {e}")
        return JsonResponse({'success': False, 'error': f"Fallo interno: {str(e)}"}, status=500)
# ===================================================================
# 👤 FASE IV (PASO 20): VISTA DE PERFIL SOCIAL
# ===================================================================

@login_required
def ver_perfil_social(request, username):
    """
    Perfil público/privado del usuario.
    Muestra: Info básica, Estadísticas, Insignias y Timeline de posts.
    """
    # 1. Obtener el usuario del perfil (404 si no existe)
    perfil_user = get_object_or_404(User, username=username)
    
    # Intentar obtener el perfil o crearlo si falta (robustez)
    perfil, created = Perfil.objects.get_or_create(user=perfil_user)

    # 2. Estadísticas Sociales
    followers_count = perfil_user.seguidores.count()
    following_count = perfil_user.siguiendo.count()
    posts_count = Post.objects.filter(autor=perfil_user).count()

    # 3. Verificar si YO lo sigo (para el botón Seguir/Dejar de seguir)
    # Si soy yo mismo, is_following es False (no me sigo a mí mismo)
    is_following = False
    if request.user != perfil_user:
        is_following = Follow.objects.filter(follower=request.user, following=perfil_user).exists()

    # 4. Timeline del Usuario (Solo sus posts)
    posts_qs = Post.objects.filter(autor=perfil_user).order_by('-creado_en')
    
    # Paginación (5 posts por carga en el perfil para no saturar)
    paginator = Paginator(posts_qs, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 5. Gamificación (Medallas ganadas)
    # Traemos los logros obtenidos ordenados por fecha
    mis_logros = UserLogro.objects.filter(usuario=perfil_user).select_related('logro').order_by('-fecha_obtenido')

    context = {
        'perfil_user': perfil_user, # El objeto User del dueño del perfil
        'perfil': perfil,           # El objeto Perfil (con fotos, bio)
        'is_own_profile': (request.user == perfil_user), # ¿Es mi propio perfil?
        'is_following': is_following,
        
        # Stats
        'followers_count': followers_count,
        'following_count': following_count,
        'posts_count': posts_count,
        
        # Contenido
        'page_obj': page_obj,       # Posts paginados
        'mis_logros': mis_logros,   # Insignias
    }

    return render(request, 'perfil_social.html', context)

# ===================================================================
# 🔍 FASE IV (PASO 21): BUSCADOR GLOBAL INTELIGENTE
# ===================================================================

@login_required
def global_search(request):
    """
    Motor de búsqueda centralizado.
    Busca coincidencias en: Usuarios, Grupos, Posts y Preguntas del Foro.
    """
    query = request.GET.get('q', '').strip()
    
    # Inicializamos resultados vacíos
    results = {
        'users': [],
        'groups': [],
        'posts': [],
        'questions': []
    }
    
    total_results = 0

    if query:
        # 1. Buscar Usuarios (Nombre, Apellido o Username)
        # Excluimos al usuario que busca y a usuarios inactivos
        results['users'] = User.objects.filter(
            (Q(username__icontains=query) |
             Q(first_name__icontains=query) |
             Q(last_name__icontains=query)),
            is_active=True
        ).exclude(id=request.user.id)[:5] # Limitamos a 5 para no saturar

        # 2. Buscar Grupos (Nombre o Descripción)
        results['groups'] = Group.objects.filter(
            Q(nombre__icontains=query) |
            Q(descripcion__icontains=query)
        )[:5]

        # 3. Buscar en el Muro Social (Contenido)
        # Solo posts públicos o de gente que sigo (por privacidad básica)
        # Por simplicidad en la búsqueda global, mostramos coincidencias generales
        # pero idealmente filtraríamos por privacidad.
        results['posts'] = Post.objects.filter(
            contenido__icontains=query
        ).select_related('autor').order_by('-creado_en')[:5]

        # 4. Buscar en el Foro (Título o Contenido)
        results['questions'] = Question.objects.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query)
        ).order_by('-created_at')[:5]

        # Conteo total para mostrar en la interfaz
        total_results = len(results['users']) + len(results['groups']) + len(results['posts']) + len(results['questions'])

    context = {
        'query': query,
        'results': results,
        'total_results': total_results
    }

    return render(request, 'global_search.html', context)
# --- (Pegar esto al final de tasks/views.py) ---

@login_required
def lista_grupos(request):
    """Muestra todos los grupos disponibles para unirse."""
    #grupos = SocialGroup.objects.all().order_by('-creado_en')
    grupos = SocialGroup.objects.all().order_by('-created_at')
    return render(request, 'grupos/lista_grupos.html', {'grupos': grupos})

##Aqui tambien hice algo 

@login_required
def crear_grupo(request):
    """
    Solo Docentes y Administrativos pueden crear grupos.
    """
    # Importación local para evitar ciclos con models.py
    from .forms import SocialGroupForm 

    roles_permitidos = ['ADMINISTRADOR', 'DOCENTE', 'COORD_ACADEMICO', 'PSICOLOGO', 'COORD_CONVIVENCIA']
    
    if request.user.perfil.rol not in roles_permitidos:
        messages.error(request, "Los estudiantes no tienen permiso para crear grupos. Solicítalo a un docente.")
        return redirect('social_feed') # Redirigir al feed si no tiene permiso

    if request.method == 'POST':
        form = SocialGroupForm(request.POST, request.FILES)
        if form.is_valid():
            grupo = form.save(commit=False)
            
            # 1. Asignar el creador (campo 'creator' en inglés)
            grupo.creator = request.user
            
            grupo.save()
            
            # 2. Agregar al usuario como miembro y administrador
            grupo.members.add(request.user)
            grupo.admins.add(request.user)
            
            # 3. Mensaje de éxito usando 'name' (en inglés) <- ESTO ARREGLA TU ERROR
            messages.success(request, f'Grupo "{grupo.name}" creado exitosamente.')
            
            return redirect('detalle_grupo', grupo_id=grupo.id)
    else:
        form = SocialGroupForm()
    
    return render(request, 'grupos/crear_grupo.html', {'form': form})
##Aqui

@login_required
def detalle_grupo(request, grupo_id):
    """Muro exclusivo del grupo. Maneja Posts, Comentarios, Portada y EDICIÓN DE INFO."""
    
    # Importaciones locales para evitar ciclos
    from .models import SocialGroup, Post, Comment 
    from .forms import PostForm, SocialGroupForm
    
    # 1. Recuperar el grupo
    grupo = get_object_or_404(SocialGroup, id=grupo_id)
    
    # 2. Permisos (Usando los nombres correctos en inglés)
    es_miembro = grupo.members.filter(id=request.user.id).exists() 
    es_administrador_grupo = (request.user == grupo.creator or request.user.perfil.rol == 'ADMINISTRADOR')

    # 3. Consulta de Posts
    posts_qs = Post.objects.filter(grupo=grupo).select_related(
        'autor', 
        'autor__perfil'
    ).prefetch_related(
        'comentarios', 
        'comentarios__autor__perfil', 
        'reacciones'
    ).order_by('-creado_en')
    
    form = PostForm()
    
    if request.method == 'POST':
        
        # 🟢 CASO A: CAMBIO DE PORTADA
        if 'cambiar_portada' in request.POST and es_administrador_grupo:
            form_portada = SocialGroupForm(request.POST, request.FILES, instance=grupo)
            if form_portada.is_valid():
                form_portada.save()
                messages.success(request, "Foto de portada actualizada exitosamente.")
                return redirect('detalle_grupo', grupo_id=grupo.id)
            else:
                messages.error(request, "Error al subir la imagen.")

        # 🟠 CASO B: EDITAR INFORMACIÓN (NOMBRE Y DESCRIPCIÓN) - ¡NUEVO!
        elif 'editar_info_grupo' in request.POST and es_administrador_grupo:
            nuevo_nombre = request.POST.get('nombre_grupo')
            nueva_descripcion = request.POST.get('descripcion_grupo')
            
            if nuevo_nombre:
                grupo.name = nuevo_nombre
                grupo.description = nueva_descripcion
                grupo.save()
                messages.success(request, "Información del grupo actualizada correctamente.")
                return redirect('detalle_grupo', grupo_id=grupo.id)
            else:
                messages.error(request, "El nombre del grupo no puede estar vacío.")

        # 🔵 CASO C: PUBLICAR POST
        elif 'publicar_post' in request.POST:
            if not es_miembro:
                messages.error(request, "Debes unirte al grupo para publicar.")
                return redirect('detalle_grupo', grupo_id=grupo.id)
            
            form = PostForm(request.POST, request.FILES)
            if form.is_valid():
                post = form.save(commit=False)
                post.autor = request.user
                post.grupo = grupo 
                post.save()
                messages.success(request, 'Publicación creada en el grupo.')
                return redirect('detalle_grupo', grupo_id=grupo.id)
            else:
                messages.error(request, 'Error al publicar. Contenido inválido.')
        
        # 🟡 CASO D: COMENTAR
        elif 'publicar_comentario' in request.POST:
            if not es_miembro:
                messages.error(request, "Debes unirte al grupo para comentar.")
                return redirect('detalle_grupo', grupo_id=grupo.id)
                
            post_id = request.POST.get('post_id')
            contenido = request.POST.get('contenido')
            
            if post_id and contenido:
                try:
                    post = Post.objects.get(id=post_id)
                    Comment.objects.create(
                        post=post,
                        autor=request.user,
                        contenido=contenido
                    )
                    messages.success(request, 'Comentario agregado.')
                    return redirect('detalle_grupo', grupo_id=grupo.id) 
                except Post.DoesNotExist:
                    messages.error(request, 'El post que intentas comentar no existe.')
            else:
                messages.warning(request, 'No puedes enviar un comentario vacío.')
                
    # 3. Renderizar (Usando la ruta correcta)
    return render(request, 'grupos/detalle_grupo.html', {
        'grupo': grupo, 
        'es_miembro': es_miembro,
        'posts': posts_qs,
        'post_form': form,
        'es_administrador_grupo': es_administrador_grupo,
    })

# --- NUEVA VISTA PARA ELIMINAR GRUPO ---
@login_required
def eliminar_grupo(request, grupo_id):
    from .models import SocialGroup
    grupo = get_object_or_404(SocialGroup, id=grupo_id)
    
    # Verificar permisos (Solo Creador o Admin General)
    if request.user == grupo.creator or request.user.perfil.rol == 'ADMINISTRADOR':
        nombre_grupo = grupo.name
        grupo.delete()
        messages.success(request, f'El grupo "{nombre_grupo}" ha sido eliminado permanentemente.')
        return redirect('social_feed') 
    else:
        messages.error(request, "No tienes permiso para eliminar este grupo.")
        return redirect('detalle_grupo', grupo_id=grupo.id)


##unirse al grupo 

@login_required
def unirse_grupo(request, grupo_id):
    """Toggle para entrar/salir del grupo."""
    # Importación local para evitar errores circulares
    from .models import SocialGroup 
    
    grupo = get_object_or_404(SocialGroup, id=grupo_id)
    
    # 1. Verificar si el usuario YA es miembro (Usando 'members')
    if grupo.members.filter(id=request.user.id).exists():
        # CASO: SALIRSE DEL GRUPO
        grupo.members.remove(request.user)
        # Usamos 'name' porque así se llama en el modelo ahora
        messages.info(request, f'Has salido de {grupo.name}.')
        
        # Si se sale, lo mandamos al feed general para que no vea contenido privado
        return redirect('social_feed')
    else:
        # CASO: UNIRSE AL GRUPO
        grupo.members.add(request.user)
        messages.success(request, f'¡Bienvenido a {grupo.name}!')
        
        # 🔥 CAMBIO CLAVE: Si se une, lo mandamos ADENTRO del grupo
        # Así el usuario ve confirmación visual inmediata
        return redirect('detalle_grupo', grupo_id=grupo.id)


@login_required
def editar_perfil(request):
    """
    Permite al usuario editar sus datos de cuenta (User) y su perfil social (Perfil).
    Maneja la foto de portada, avatar, hobbies, metas, etc.
    """
    
    # 1. Cargar datos del usuario y el perfil
    user = request.user
    # Usamos getattr por seguridad, aunque el middleware debería haberlo creado
    perfil = getattr(user, 'perfil', None) 

    if request.method == 'POST':
        # 2. Cargar los formularios con la data enviada (POST y FILES)
        user_form = UserEditForm(request.POST, instance=user)
        
        # 🔥 CORRECCIÓN CLAVE: Usamos 'EditarPerfilForm' en lugar de 'PerfilEditForm'
        # Este es el que tiene los campos nuevos (portada, hobbies, etc.)
        profile_form = EditarPerfilForm(request.POST, request.FILES, instance=perfil)
        
        if user_form.is_valid() and profile_form.is_valid():
            try:
                with transaction.atomic():
                    # Guardar ambos modelos de forma segura
                    user_form.save()
                    profile_form.save()
                    
                    messages.success(request, '¡Tu perfil se ha actualizado correctamente!')
                    
                    # Redirigir al perfil público para ver los cambios
                    return redirect('ver_perfil_social', username=user.username)
            except Exception as e:
                messages.error(request, f'Ocurrió un error al guardar: {e}')
        else:
            messages.error(request, 'Hay errores en el formulario. Por favor revisa los campos en rojo.')
    
    else:
        # GET: Cargar los formularios con la información actual de la base de datos
        user_form = UserEditForm(instance=user)
        profile_form = EditarPerfilForm(instance=perfil)
    
    # Renderizamos el template que actualizamos antes
    return render(request, 'social/editar_perfil.html', {
        'user_form': user_form,
        'profile_form': profile_form # Se pasa como 'profile_form' para coincidir con el template
    })
##historial de notificaciones 

@login_required
def historial_notificaciones(request):
    """
    Muestra el historial completo de notificaciones del usuario,
    agrupadas por fecha en el template.
    """
    # Obtenemos todas las notificaciones, ordenadas por fecha descendente
    notificaciones = Notificacion.objects.filter(usuario=request.user).order_by('-fecha_creacion')
    
    # Opcional: Marcar todas como leídas al entrar al historial
    # notificaciones.filter(leido=False).update(leido=True)

    return render(request, 'notificaciones/historial.html', {
        'notificaciones': notificaciones
    })



@login_required
def editar_perfil(request):
    """
    Permite editar al mismo tiempo:
    1. Modelo User (Nombre, Apellido, Email) -> UserEditForm
    2. Modelo Perfil (Foto, Portada, Hobbies, Metas) -> EditarPerfilForm
    """
    user = request.user
    perfil = user.perfil # Asumimos que el perfil existe gracias al Signal o Middleware
    
    if request.method == 'POST':
        # 1. Cargamos los datos del formulario de Usuario
        user_form = UserEditForm(request.POST, instance=user)
        
        # 2. Cargamos los datos del formulario de Perfil (incluyendo archivos/fotos)
        profile_form = EditarPerfilForm(request.POST, request.FILES, instance=perfil)

        # 3. Validamos que AMBOS sean correctos
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()      # Guarda nombre, apellido, email
            profile_form.save()   # Guarda fotos, hobbies, metas
            
            messages.success(request, '¡Tu perfil se ha actualizado correctamente!')
            # Redirige a la vista del perfil público
            return redirect('ver_perfil_social', username=user.username)
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    
    else:
        # GET: Pre-llenamos los formularios con la información actual
        user_form = UserEditForm(instance=user)
        profile_form = EditarPerfilForm(instance=perfil)

    # 4. Enviamos AMBOS formularios al template
    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }
    
    return render(request, 'social/editar_perfil.html', context)


@login_required
def crear_comentario(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        contenido = request.POST.get('contenido')
        if contenido:
            Comentario.objects.create(
                autor=request.user,
                post=post,
                contenido=contenido
            )
            messages.success(request, 'Comentario agregado.')
    # Redirigir a la misma página desde donde se comentó
    return redirect(request.META.get('HTTP_REFERER', 'social_feed'))

##Aqui agregue las notificaciones 

@login_required
@require_POST
def mark_all_notifications_read(request):
    """
    Marca todas las notificaciones pendientes del usuario actual como leídas.
    Se llama vía AJAX cuando se abre la campana de notificaciones.
    """
    try:
        # 1. Identificar las notificaciones NO leídas del usuario.
        # CORRECCIÓN CRÍTICA: Cambiamos 'is_read' por 'leida' (que es el nombre real en tu BD).
        unread_notifications = Notificacion.objects.filter(
            usuario=request.user, 
            leida=False 
        )
        
        # 2. Actualizar el estado en lote a True.
        # CORRECCIÓN CRÍTICA: Actualizamos el campo 'leida'.
        updated_count = unread_notifications.update(leida=True)
        
        return JsonResponse({
            'success': True, 
            'new_count': 0, 
            'updated_items': updated_count
        })

    except Exception as e:
        # Imprime el error en la consola del servidor para depuración
        print(f"Error crítico marcando notificaciones: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

##Aqui inicie a agregar el boton del observador al acudiente 
try:
    from weasyprint import HTML, CSS
except ImportError:
    HTML = None

@login_required
def descargar_observador_acudiente(request, estudiante_id):
    """
    Genera y descarga el PDF del observador para el acudiente.
    """
    # 1. Validaciones de Seguridad (Igual que antes)
    estudiante = get_object_or_404(User, id=estudiante_id)
    es_mi_hijo = Acudiente.objects.filter(acudiente=request.user, estudiante=estudiante).exists()
    
    if not es_mi_hijo:
        messages.error(request, "No tienes permisos.")
        return redirect('dashboard_acudiente')

    matricula = Matricula.objects.filter(estudiante=estudiante).order_by('-id').first()
    
    if not matricula or not matricula.puede_ver_observador:
        messages.warning(request, "El observador aún no ha sido habilitado.")
        return redirect('dashboard_acudiente')

    # 2. Preparar Datos
    observaciones = Observacion.objects.filter(estudiante=estudiante).order_by('-fecha_creacion')
    institucion = Institucion.objects.first()
    curso = matricula.curso if matricula else None

    context = {
        'estudiante': estudiante,
        'observaciones': observaciones,
        'institucion': institucion,
        'curso': curso,
        'fecha_impresion': timezone.now(),
        'generado_por': request.user.get_full_name(),
        'es_oficial': True,
        # Importante: Para que las imágenes carguen en el PDF, a veces se necesita la URL base
        'request': request 
    }

    # 3. Generar PDF
    # Renderizamos el HTML a un string
    html_string = render_to_string('pdf/observador_template.html', context)

    if HTML:
        # Si WeasyPrint está instalado, generamos el PDF real
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'filename="Observador_{estudiante.username}.pdf"'
        
        # Base url es importante para cargar imágenes estáticas/media
        HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
        return response
    else:
        # Fallback: Si no hay librerías de PDF, mostramos el HTML para imprimir con Ctrl+P
        # Esto es lo que te estaba pasando, pero ahora sabes por qué.
        return HttpResponse(html_string)


# --- tasks/views.py ---

def cargar_periodos_por_curso(request):
    """
    API AJAX para cargar los periodos de un curso seleccionado.
    Permite que el Administrador y Staff vean los periodos en el reporte consolidado.
    """
    curso_id = request.GET.get('curso_id')
    
    if not curso_id:
        return JsonResponse([], safe=False)
    
    try:
        # 1. Obtener el curso
        curso = Curso.objects.get(id=curso_id)
        
        # 2. Filtrar periodos activos de ese curso
        # No filtramos por docente aquí, porque el Admin/Coord debe ver todo.
        periodos = Periodo.objects.filter(curso=curso, activo=True).values('id', 'nombre').order_by('id')
        
        return JsonResponse(list(periodos), safe=False)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)



# tasks/views.py

# tasks/views.py


@login_required
def ai_analysis_engine(request):
    """
    MOTOR CENTRAL DE ANÁLISIS (TIER 1000 - CONTEXTO REAL).
    Sincroniza la base de datos con la IA mediante inyección directa de contexto.
    """

    # 1. DETECCIÓN DE CONTEXTO (AJAX / JSON / HTML)
    accept_header = request.headers.get("Accept", "")
    is_ajax = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.GET.get("format") == "json"
        or "application/json" in accept_header.lower()
    )

    # 2. CONFIGURACIÓN INICIAL DE ACCIÓN Y ROL
    perfil = getattr(request.user, "perfil", None)
    rol_usuario = perfil.rol if perfil else "ESTUDIANTE"

    # Definir acción por defecto basada en el rol si no viene ninguna
    if rol_usuario == "DOCENTE":
        default_action = ACCION_MEJORAS_DOCENTE
    else:
        default_action = ACCION_MEJORAS_ESTUDIANTE

    action_type = request.GET.get("action", default_action)
    target_id = request.GET.get("target_id")
    user_query = request.GET.get("user_query")

    # 3. CAPTURA Y VALIDACIÓN DE MEMORIA (HISTORIAL)
    historial_msgs = []
    raw_history = request.GET.get("history")
    if raw_history:
        try:
            parsed = json.loads(raw_history)
            if isinstance(parsed, list):
                historial_msgs = [msg for msg in parsed if isinstance(msg, dict) and "role" in msg]
        except Exception:
            logger.warning("[AI] Error procesando historial de chat.")

    # 4. RUTEADO DE INTERFAZ (CHAT HTML)
    if action_type == ACCION_CHAT_SOCRATICO and not is_ajax:
        return render(request, "tasks/ai_chat.html", {"target_user": request.user})

    # 5. RESOLUCIÓN DEL TARGET_USER (Sujeto del análisis)
    target_user = request.user

    try:
        # Lógica de resolución de sujeto según rol
        if rol_usuario == "ACUDIENTE":
            if target_id:
                target_user = get_object_or_404(User, id=target_id)
            else:
                relacion = Acudiente.objects.filter(acudiente=request.user).select_related("estudiante").first()
                if not relacion:
                    raise ValueError("No se encontró un estudiante vinculado a su cuenta.")
                target_user = relacion.estudiante

        elif rol_usuario == "DOCENTE":
            target_user = request.user
            # Forzamos acción de docente si el sistema está intentando usar la de estudiante
            if action_type == ACCION_MEJORAS_ESTUDIANTE:
                action_type = ACCION_MEJORAS_DOCENTE

        elif target_id:
            target_user = get_object_or_404(User, id=target_id)

        # 6. CONSTRUCCIÓN DE CONTEXTO RICO (TIER 1000)
        # Importante: Asegúrate de que 'context_builder' esté importado al inicio del archivo
        try:
            contexto_enriquecido = context_builder.get_context(
                usuario=request.user,
                action_type=action_type,
                target_user=target_user
            )
        except Exception as e:
            logger.error(f"[AI] Error en ContextBuilder: {e}", exc_info=True)
            raise ValueError("No se pudo extraer la evidencia académica de la base de datos.")

        # 7. EJECUCIÓN DEL MOTOR DE IA (ORQUESTADOR)
        # Se envía el 'context_override' para que la IA use datos reales y no alucine
        resultado = ai_orchestrator.process_request(
            user=request.user,
            action_type=action_type,
            user_query=user_query,
            target_user=target_user,
            historial=historial_msgs,
            context_override=contexto_enriquecido # 🔥 ESTA ES LA CLAVE DE LOS DATOS REALES
        )

    except ValueError as e:
        resultado = {"success": False, "content": str(e), "source": "BUSINESS_LOGIC"}
    except Exception as e:
        logger.error("[AI] CRASH CRÍTICO EN ENGINE", exc_info=True)
        resultado = {"success": False, "content": "Error interno en el motor de IA."}

    # 8. RESPUESTA FINAL
    if is_ajax:
        return JsonResponse(resultado, safe=False)

    return render(request, "tasks/ai_report.html", {
        "ai_json_response": json.dumps(resultado, default=str, cls=DjangoJSONEncoder),
        "titulo_analisis": str(action_type).replace("_", " ").title(),
        "target_user": target_user
    })

@login_required
def test_ai_connection(request):
    """VISTA DE COMPATIBILIDAD PARA URLS.PY."""
    return ai_analysis_engine(request)

@login_required
def dashboard_ia_estudiante(request):
    """RENDERIZA EL PANEL PRINCIPAL DE IA."""
    context = {
        'titulo_pagina': 'Orientación Inteligente',
        'usuario_nombre': request.user.first_name or request.user.username,
    }
    return render(request, 'tasks/ai_dashboard.html', context)

def api_obtener_likes(request, post_id):
    try:
        # 1. Verificamos que el post exista
        post = get_object_or_404(Post, id=post_id)
        
        # 2. Obtenemos el ContentType del modelo Post
        # (Esto es necesario porque tu sistema usa relaciones genéricas)
        ct = ContentType.objects.get_for_model(Post)
        
        # 3. Buscamos en el modelo Reaction (inglés) usando content_type y object_id
        likes = Reaction.objects.filter(
            content_type=ct,
            object_id=post.id,
            tipo='LIKE'
        ).select_related('usuario__perfil') # Ojo: en api_reaction usas 'usuario', no 'autor'
        
        users_data = []
        
        for reaction in likes:
            # En tu modelo Reaction el campo es 'usuario', no 'autor'
            user = reaction.usuario 
            
            # Obtenemos la URL de la foto o null si no tiene
            avatar_url = None
            try:
                if hasattr(user, 'perfil') and user.perfil.foto_perfil:
                    avatar_url = user.perfil.foto_perfil.url
            except Exception:
                pass
                
            users_data.append({
                'username': user.username,
                'full_name': user.get_full_name() or user.username,
                'avatar_url': avatar_url
            })
            
        return JsonResponse({'users': users_data})

    except Exception as e:
        # Esto imprimirá el error real en tu terminal negra para que sepamos qué pasa
        print(f"ERROR EN api_obtener_likes: {e}") 
        return JsonResponse({'error': str(e)}, status=500)


#Aqui inicia la funcion para el reporte de la AI 

# ===================================================================
# 🖨️ CIRUGÍA: GENERADOR DE REPORTE IA EN PDF (INSTITUCIONAL)
# ===================================================================

@login_required
def download_ai_report_pdf(request):
    """
    Genera un PDF oficial con el análisis de la IA, formato institucional y firmas.
    Recibe los mismos parámetros que el motor de IA para reconstruir el contexto.
    """
    # 1. Recuperar parámetros
    action_type = request.GET.get('action')
    target_id = request.GET.get('target_id')
    user_query = request.GET.get('user_query', '')
    
    # 2. Identificar al usuario objetivo (Target)
    target_user = request.user
    if target_id:
        target_user = get_object_or_404(User, id=target_id)
    
    # 3. Obtener/Regenerar el análisis de la IA (Orquestador)
    # Reutilizamos tu lógica existente para obtener la data cruda
    try:
        resultado = ai_orchestrator.process_request(
            user=request.user,
            action_type=action_type,
            user_query=user_query,
            target_user=target_user,
            historial=[] # Para el reporte oficial, usamos el contexto fresco
        )
        
        contenido_raw = resultado.get('content', 'No se pudo generar el contenido.')
        
        # 4. Convertir Markdown a HTML para el PDF (Negritas, listas, etc.)
        contenido_html = markdown.markdown(contenido_raw)

    except Exception as e:
        logger.error(f"Error generando PDF IA: {e}")
        contenido_html = f"<p>Error al generar el reporte: {str(e)}</p>"

    # 5. Datos Institucionales
    institucion = Institucion.objects.first()
    
    # 6. Contexto para el Template PDF
    context = {
        'institucion': institucion,
        'fecha_impresion': timezone.now(),
        'solicitante': request.user,
        'objetivo': target_user,
        'tipo_reporte': action_type.replace('_', ' ').upper() if action_type else "REPORTE GENERAL",
        'contenido_html': mark_safe(contenido_html), # Marcamos como seguro para renderizar HTML
        'query_original': user_query
    }

    # 7. Renderizado con WeasyPrint
    if HTML is None:
        return HttpResponse("Error: WeasyPrint no está instalado en el servidor.", status=500)

    html_string = render_to_string('pdf/ai_report_template.html', context)
    base_url = request.build_absolute_uri('/')
    pdf = HTML(string=html_string, base_url=base_url).write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    filename = f"Reporte_IA_{target_user.username}_{timezone.now().strftime('%Y%m%d')}.pdf"
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    
    return response


# En tasks/views.py

@login_required
def ver_documentos_institucionales(request):
    """
    Vista pública para que CUALQUIER usuario autenticado (Estudiante, Acudiente, Docente)
    pueda ver y descargar los documentos oficiales.
    """
    institucion = Institucion.objects.first()
    
    # Si no hay institución creada, pasamos None para manejarlo en el template
    context = {
        'institucion': institucion
    }
    return render(request, 'institucion/documentos_publicos.html', context)

@role_required(['ADMINISTRADOR', 'COORD_ACADEMICO', 'COORD_CONVIVENCIA', 'PSICOLOGO'])
def historial_global_observaciones(request):
    """
    Vista de Inteligencia: Historial Global de Observaciones.
    Versión con Diagnóstico de Template integrado.
    """
    # --- 1. Lógica de Datos (Optimizada) ---
    # Usamos 'autor' porque ya confirmamos que 'creado_por' daba error.
    observaciones = Observacion.objects.select_related('estudiante', 'autor').all().order_by('-fecha_creacion')

    # --- 2. Filtro de Búsqueda Inteligente ---
    query = request.GET.get('q')
    if query:
        observaciones = observaciones.filter(
            Q(estudiante__first_name__icontains=query) |
            Q(estudiante__last_name__icontains=query) |
            Q(estudiante__username__icontains=query) | # Busca también por documento
            Q(descripcion__icontains=query)
        )

    # --- 3. Cálculo de KPIs (Estadísticas) ---
    total_obs = observaciones.count()
    
    # Conteos directos y seguros
    count_convivencia = observaciones.filter(tipo='CONVIVENCIA').count()
    count_academica = observaciones.filter(Q(tipo='ACADEMICO') | Q(tipo='ACADEMICA')).count()
    count_psicologia = observaciones.filter(Q(tipo='PSICOLOGIA') | Q(tipo='PSICOLOGICA')).count()

    context = {
        'observaciones': observaciones,
        'kpi': {
            'total': total_obs,
            'convivencia': count_convivencia,
            'academica': count_academica,
            'psicologia': count_psicologia,
        },
        'query': query
    }
    
    # --- 4. Renderizado con Diagnóstico de Error ---
    template_name = 'bienestar/historial_global_observaciones.html'
    
    try:
        # Intentamos cargar el template primero para verificar si existe
        get_template(template_name)
        return render(request, template_name, context)
        
    except TemplateDoesNotExist:
        # Si falla, mostramos un mensaje útil en pantalla en vez de Error 500
        import os
        from django.conf import settings
        
        debug_msg = f"""
        <div style='font-family: monospace; padding: 20px; background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb;'>
            <h3>⚠️ ERROR CRÍTICO: NO SE ENCUENTRA EL ARCHIVO HTML</h3>
            <p>Django buscó el archivo <strong>'{template_name}'</strong> y no lo encontró.</p>
            <hr>
            <p><strong>Verificación de Rutas en el Servidor:</strong></p>
            <ul>
        """
        # Listamos dónde está buscando Django
        for directory in settings.TEMPLATES[0]['DIRS']:
            debug_msg += f"<li>Buscando en: {directory}</li>"
            
        debug_msg += "</ul><p><strong>Asegúrate de que la carpeta se llame 'bienestar' (todo minúscula) en el servidor.</strong></p></div>"
        
        return HttpResponse(debug_msg)


#Agregando funcion nueva de bienestar para leer todo el pei, manual y demas 

# EN tasks/views.py (Al final del archivo)
# --- VISTA 1: GUARDAR (AJUSTADA PARA RETORNAR ID) ---
@require_POST
@login_required
def guardar_seguimiento(request):
    try:
        # 1. Recibir datos del Javascript
        estudiante_id = request.POST.get('estudiante_id')
        tipo = request.POST.get('tipo')
        descripcion = request.POST.get('descripcion') 

        if not all([estudiante_id, tipo, descripcion]):
            return JsonResponse({'success': False, 'error': 'Faltan datos obligatorios'}, status=400)

        # 2. Buscar estudiante
        estudiante = get_object_or_404(User, id=estudiante_id)

        # 3. Guardar en Base de Datos y ASIGNAR A VARIABLE
        nuevo_seguimiento = Seguimiento.objects.create(
            estudiante=estudiante,
            tipo=tipo,
            descripcion=descripcion,
            profesional=request.user, 
            # fecha se pone sola por el auto_now_add=True
        )

        # 🔥 CAMBIO CRÍTICO: Devolvemos el ID del nuevo registro
        return JsonResponse({'success': True, 'id': nuevo_seguimiento.id})

    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'El estudiante no existe'}, status=404)
    except Exception as e:
        print(f"Error guardando seguimiento: {e}") # O usa tu logger
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# --- VISTA 2: GENERAR PDF (WEASYPRINT) ---
@login_required
def generar_seguimiento_pdf(request, seguimiento_id):
    # 1. Obtener datos reales de la BD
    seguimiento = get_object_or_404(Seguimiento, id=seguimiento_id)
    institucion = Institucion.objects.first() # Traemos datos del colegio 

    # [cite_start]2. Mapeo de títulos según el tipo [cite: 2293]
    titulos = {
        "CONVIVENCIA": "ACTA DE COMPROMISO CONVIVENCIAL",
        "ACADEMICO": "COMPROMISO ACADÉMICO",
        "PSICOLOGIA": "REGISTRO DE ORIENTACIÓN ESCOLAR"
    }
    titulo_doc = titulos.get(seguimiento.tipo, "ACTA DE SEGUIMIENTO")

    # 3. Contexto para el template
    context = {
        'seguimiento': seguimiento,
        'estudiante': seguimiento.estudiante,
        'profesional': seguimiento.profesional,
        'institucion': institucion,
        'titulo': titulo_doc,
        'fecha_impresion': timezone.now(),
        # IMPORTANTE: Base URL para que WeasyPrint encuentre las imágenes estáticas/media
        'base_url': request.build_absolute_uri('/') 
    }

    # 4. Renderizar HTML
    # Asegúrate de haber creado este template en el Paso 2 (templates/pdf/seguimiento_oficial.html)
    html_string = render_to_string('pdf/seguimiento_oficial.html', context)

    # 5. Generar PDF
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()

    # 6. Respuesta HTTP
    response = HttpResponse(pdf_file, content_type='application/pdf')
    filename = f"Seguimiento_{seguimiento.estudiante.username}_{seguimiento.id}.pdf"
    
    # 'inline' abre en el navegador (recomendado para previsualizar)
    # Cambia a 'attachment' si prefieres que se descargue directo sin abrirse
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    
    return response