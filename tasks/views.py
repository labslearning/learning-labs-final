# -*- coding: utf-8 -*-
from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
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
from datetime import datetime, timedelta
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

# --- Modelos: Se añade Acudiente ---
from .models import (
    Question, Answer, Perfil, Curso, Nota, Materia,
    Periodo, AsignacionMateria, Matricula, ComentarioDocente,
    ActividadSemanal, LogroPeriodo, Convivencia, GRADOS_CHOICES,
    Acudiente, Institucion
)

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
from .forms import BulkCSVForm, PasswordChangeFirstLoginForm, ProfileSearchForm, QuestionForm, AnswerForm

# --- Utilidades: Se añaden las nuevas funciones de ayuda ---
from .utils import generar_username_unico, generar_contrasena_temporal, asignar_curso_por_grado


# --- Decoradores: Se añade el nuevo decorador ---
from .decorators import role_required

# --- INICIO DE MODIFICACIÓN 1 (continuación): Añadir Importaciones ---
from .services import get_student_report_context # Usamos el nuevo servicio
# --- FIN DE MODIFICACIÓN 1 ---


# Obtener el modelo de usuario de forma segura
User = get_user_model()

# Configuración de logging
logger = logging.getLogger(__name__)

# --- INICIO DE MODIFICACIÓN 1 (continuación): Importar WeasyPrint ---
try:
    from weasyprint import HTML
except ImportError:
    HTML = None
    logger.error("WeasyPrint no está instalado. La generación de PDF fallará.")
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

def signin(request):
    if request.method == 'GET':
        return render(request, "signin.html", {'form': AuthenticationForm()})

    form = AuthenticationForm(request, data=request.POST)

    # MODIFICACIÓN CLAVE: Captura el error de la forma de autenticación si no es válida.
    if not form.is_valid():
        error_messages = form.errors.get('__all__', [])

        # Loguear el error exacto para el diagnóstico
        if error_messages:
            for error in error_messages:
                logger.error(f"Fallo de autenticación: {error}")

        messages.error(request, 'Usuario o contraseña incorrectos.')
        return render(request, 'signin.html', {'form': form})

    user = form.get_user()
    login(request, user)

    # Redirección forzosa si el perfil requiere cambio de clave
    if hasattr(user, 'perfil') and user.perfil.requiere_cambio_clave:
        messages.info(request, 'Por motivos de seguridad, debes establecer una nueva contraseña.')
        return redirect('cambiar_clave')

    next_url = request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)

    if hasattr(user, 'perfil'):
        rol = user.perfil.rol
        if rol == 'ESTUDIANTE':
            return redirect('dashboard_estudiante')
        elif rol == 'ACUDIENTE':
            return redirect('dashboard_acudiente')
        elif rol == 'DOCENTE' or user.perfil.es_director:
            return redirect('dashboard_docente')
        elif rol == 'ADMINISTRADOR':
            return redirect('admin_dashboard')

    # Fallback si por alguna razón no tiene perfil
    messages.warning(request, 'No se encontró un perfil de usuario. Contacte al administrador.')
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
@role_required('ESTUDIANTE')
def dashboard_estudiante(request):
    estudiante = request.user
    perfil_estudiante = get_object_or_404(Perfil, user=estudiante)

    # Intenta obtener la matrícula activa más reciente del estudiante
    matricula = Matricula.objects.filter(estudiante=estudiante, activo=True).select_related('curso').first()

    curso = matricula.curso if matricula else None

    # Inicializar todas las colecciones de datos académicos
    materias_con_notas = {}
    comentarios_docente = {}
    actividades_semanales = {}
    convivencia_notas = {}
    logros_por_materia_por_periodo = {}
    periodos_disponibles = [] # Nuevo: Para que el estudiante sepa los periodos

    if curso:
        # Obtener los periodos para este curso
        periodos_disponibles = Periodo.objects.filter(curso=curso, activo=True).order_by('id')

        # Obtener las asignaciones de materia para este curso
        asignaciones = AsignacionMateria.objects.filter(curso=curso, activo=True).select_related('materia')
        materias = [a.materia for a in asignaciones]

        for materia in materias:
            # 1. Notas
            # Se usa .select_related('periodo') para optimizar
            notes = Nota.objects.filter(estudiante=estudiante, materia=materia).select_related('periodo').order_by('periodo__id', 'numero_nota')
            notas_por_periodo = {}
            for nota in notes:
                # Almacenamos el objeto nota por su numero_nota dentro del ID del periodo
                notas_por_periodo.setdefault(nota.periodo.id, {})[nota.numero_nota] = nota

            if notas_por_periodo:
                materias_con_notas[materia] = notas_por_periodo

            # 2. Comentarios del Docente
            comentarios = ComentarioDocente.objects.filter(estudiante=estudiante, materia=materia).order_by('-fecha_creacion')
            if comentarios.exists():
                comentarios_docente[materia.id] = comentarios

            # 3. Actividades Semanales
            actividades = ActividadSemanal.objects.filter(curso=curso, materia=materia).order_by('-fecha_creacion')
            if actividades.exists():
                actividades_semanales[materia.id] = actividades

            # 4. Logros
            logros_de_la_materia = LogroPeriodo.objects.filter(
                curso=curso,
                materia=materia,
            ).order_by('periodo__id', '-fecha_creacion')

            if logros_de_la_materia.exists():
                logros_por_periodo_temp = {}
                for logro in logros_de_la_materia:
                    logros_por_periodo_temp.setdefault(logro.periodo.id, []).append(logro)
                logros_por_materia_por_periodo[materia] = logros_por_periodo_temp

        # 5. Notas de Convivencia
        convivencia_existente = Convivencia.objects.filter(estudiante=estudiante, curso=curso).select_related('periodo')
        for convivencia in convivencia_existente:
            convivencia_notas[convivencia.periodo.id] = {'valor': convivencia.valor, 'comentario': convivencia.comentario}

    context = {
        'estudiante': estudiante,
        'perfil': perfil_estudiante,
        'curso': curso,
        'matricula': matricula, # Se incluye la matrícula
        'periodos_disponibles': periodos_disponibles, # Se incluyen los periodos
        'materias_con_notas': materias_con_notas,
        'comentarios_docente': comentarios_docente,
        'actividades_semanales': actividades_semanales,
        'logros_por_materia_por_periodo': logros_por_materia_por_periodo,
        'convivencia_notas': convivencia_notas,
    }

    return render(request, 'dashboard_estudiante.html', context)


# ===================================================================
# --- INICIO DE CIRUGÍA 2: FUNCIÓN dashboard_docente MODIFICADA ---
# ===================================================================
@role_required('DOCENTE')
def dashboard_docente(request):
    docente = request.user
    # Ordenamos por materia primero, para facilitar la nueva agrupación
    asignaciones = AsignacionMateria.objects.filter(docente=docente, activo=True)\
        .select_related('materia', 'curso').order_by('materia__nombre', 'curso__grado', 'curso__seccion')
    
    # --- ESTRUCTURA PARA PESTAÑA 1 (MIS MATERIAS) ---
    # Esta lógica se queda intacta, solo cambia el orden de 'asignaciones'
    materias_por_curso = {}
    total_estudiantes_unicos = set()
    
    # --- INICIO DE CIRUGÍA: NUEVA ESTRUCTURA PARA PESTAÑA 2 (ESTADÍSTICAS) ---
    # { materia_id: { 'materia_obj': obj, 'cursos': { curso_id: { 'curso_obj': obj, 'periodos': { periodo_id: {...} } } } } }
    estadisticas_por_materia = {}
    
    # --- FIN DE CIRUGÍA ---

    # Usamos un set para controlar qué estudiantes hemos contado
    estudiantes_contados = set()

    for asignacion in asignaciones:
        curso = asignacion.curso
        materia_actual = asignacion.materia
        
        if not curso:
            continue
            
        curso_key = f"{curso.get_grado_display()} {curso.seccion}"
        
        # --- Lógica para PESTAÑA 1 (MIS MATERIAS) ---
        if curso_key not in materias_por_curso:
            materias_por_curso[curso_key] = {
                'curso_obj': curso,
                'materias': [], 
                'es_director': (getattr(curso, 'director', None) == docente),
                'estudiantes': Matricula.objects.filter(curso=curso, activo=True).select_related('estudiante'),
            }
        
        # Contar estudiantes únicos (solo una vez por estudiante)
        for m in materias_por_curso[curso_key]['estudiantes']:
             total_estudiantes_unicos.add(m.estudiante.id)

        # Añadir materia a la lista de la Pestaña 1
        if materia_actual not in materias_por_curso[curso_key]['materias']:
            materias_por_curso[curso_key]['materias'].append(materia_actual)
        
        # --- FIN LÓGICA PESTAÑA 1 ---

        # --- INICIO DE CIRUGÍA: LÓGICA PARA PESTAÑA 2 (ESTADÍSTICAS) ---
        
        # 1. Asegurar que la materia existe en el dict
        if materia_actual.id not in estadisticas_por_materia:
            estadisticas_por_materia[materia_actual.id] = {
                'materia_obj': materia_actual,
                'cursos': {}
            }
        
        # 2. Asegurar que el curso existe dentro de la materia
        if curso.id not in estadisticas_por_materia[materia_actual.id]['cursos']:
            # Obtenemos los estudiantes de este curso (ya los tenemos en materias_por_curso)
            estudiantes_del_curso = materias_por_curso[curso_key]['estudiantes']
            estudiante_ids = [m.estudiante_id for m in estudiantes_del_curso]
            periodos_curso = Periodo.objects.filter(curso=curso, activo=True).order_by('id')
            
            estadisticas_por_materia[materia_actual.id]['cursos'][curso.id] = {
                'curso_obj': curso,
                'periodos': {} # Se llenará ahora
            }

            # 3. Calcular estadísticas para CADA periodo
            for periodo in periodos_curso:
                # Calcular promedio de ESTA materia en ESTE curso en ESTE periodo
                promedio_materia_periodo = Nota.objects.filter(
                    estudiante_id__in=estudiante_ids,
                    materia=materia_actual,
                    periodo=periodo,
                    numero_nota=5 # Promedio ponderado
                ).aggregate(promedio=Avg('valor'))['promedio']

                # Obtener logros de ESTA materia en ESTE curso en ESTE periodo
                logros_periodo = LogroPeriodo.objects.filter(
                    curso=curso, 
                    docente=docente,
                    materia=materia_actual, # <-- Filtro clave
                    periodo=periodo
                ).order_by('-fecha_creacion')

                # REQUISITO: Si hay notas O hay logros, SÍ se añade el periodo
                if promedio_materia_periodo is not None or logros_periodo.exists():
                    estadisticas_por_materia[materia_actual.id]['cursos'][curso.id]['periodos'][periodo.id] = {
                        'periodo_obj': periodo,
                        'promedio': promedio_materia_periodo,
                        'logros': logros_periodo
                    }
        
        # --- FIN DE CIRUGÍA ---

    context = {
        'docente': docente,
        'materias_por_curso': materias_por_curso, # Para la Pestaña 1
        'estadisticas_por_materia': estadisticas_por_materia, # Para la Pestaña 2
        'total_cursos': len(materias_por_curso), # Total de cursos únicos
        'total_materias': len(estadisticas_por_materia), # Total de materias únicas
        'total_estudiantes': len(total_estudiantes_unicos),
    }
    return render(request, 'dashboard_docente.html', context)
# ===================================================================
# --- FIN DE CIRUGÍA 2 ---
# ===================================================================

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
@role_required('DOCENTE')
def subir_notas(request, materia_id):
    asignacion = get_object_or_404(AsignacionMateria, materia_id=materia_id, docente=request.user, activo=True)
    materia = asignacion.materia
    curso = asignacion.curso
    estudiantes_matriculados = Matricula.objects.filter(curso=curso, activo=True).select_related('estudiante')
    periodos = Periodo.objects.filter(curso=curso, activo=True).order_by('id')

    # Lógica para crear periodos si no existen (sin cambios)
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
            # Lógica de Actividades Semanales (sin cambios)
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
                        ActividadSemanal.objects.create(
                            curso=curso, materia=materia, docente=request.user,
                            titulo=titulo if titulo else 'Actividad de la Semana',
                            descripcion=descripcion,
                            fecha_inicio=fecha_inicio,
                            fecha_fin=fecha_fin,
                        )

            # Lógica de Logros (sin cambios)
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
                                    LogroPeriodo.objects.filter(id=lid, docente=request.user).update(
                                        descripcion=desc
                                    )
                                else:
                                    LogroPeriodo.objects.create(
                                        curso=curso,
                                        periodo=periodo_obj,
                                        docente=request.user,
                                        materia=materia,
                                        descripcion=desc
                                    )
                except json.JSONDecodeError as e:
                    logger.exception("JSONDecodeError en logros_json_data: %s", e)
                    messages.error(request, "Error al procesar los logros. Formato de datos no válido.")

            # Lógica de Notas (sin cambios, ya estaba correcta)
            for m in estudiantes_matriculados:
                estudiante = m.estudiante
                for periodo in periodos:
                    for i in NUM_NOTAS:
                        nota_key = f'nota_{estudiante.id}_{periodo.id}_{i}'
                        valor_nota = request.POST.get(nota_key)
                        if valor_nota and valor_nota.strip():
                            try:
                                nota_valor = Decimal(valor_nota)
                                if ESCALA_MIN <= nota_valor <= ESCALA_MAX:
                                    Nota.objects.update_or_create(
                                        estudiante=estudiante, materia=materia, periodo=periodo,
                                        numero_nota=i,
                                        defaults={
                                            'valor': nota_valor.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
                                            'descripcion': get_description_nota(i),
                                            'registrado_por': request.user
                                        }
                                    )
                                else:
                                    messages.error(request, f'Nota ({get_description_nota(i)}) inválida para {estudiante.get_full_name() or estudiante.username}.')
                            except (ValueError, decimal.InvalidOperation):
                                messages.error(request, f'Nota ({get_description_nota(i)}) inválida para {estudiante.get_full_name() or estudiante.username}.')

            # Lógica de Promedio (sin cambios, ya estaba correcta)
            usuario_sistema, _ = User.objects.get_or_create(
                username='sistema',
                defaults={'email': 'sistema@tuproyecto.com', 'is_active': False, 'is_staff': False, 'is_superuser': False}
            )
            for m in estudiantes_matriculados:
                estudiante = m.estudiante
                for periodo in periodos:
                    notas_periodo_db = Nota.objects.filter(
                        estudiante=estudiante, materia=materia, periodo=periodo,
                        numero_nota__in=NUM_NOTAS
                    ).values('numero_nota', 'valor')
                    promedio = Decimal('0.0')
                    for n in notas_periodo_db:
                        promedio += n['valor'] * PESOS_NOTAS.get(n['numero_nota'], Decimal('0.0'))
                    if notas_periodo_db:
                        Nota.objects.update_or_create(
                            estudiante=estudiante, materia=materia, periodo=periodo,
                            numero_nota=5,
                            defaults={
                                'valor': promedio.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
                                'descripcion': 'Promedio ponderado del periodo',
                                'registrado_por': usuario_sistema
                            }
                        )

            # ======================================================
            # INICIO DE LA CORRECCIÓN (Guardar Comentarios)
            # ======================================================
            #
            # Ahora iteramos por cada periodo DENTRO de cada estudiante
            # para guardar el comentario específico de ese periodo.
            #
            for m in estudiantes_matriculados:
                estudiante = m.estudiante
                for periodo in periodos:
                    # La clave ahora debe incluir el ID del periodo
                    comentario_key = f'comentario_{estudiante.id}_{periodo.id}'
                    texto = request.POST.get(comentario_key)

                    if texto and texto.strip():
                        # Añadimos 'periodo=periodo' al 'update_or_create'
                        ComentarioDocente.objects.update_or_create(
                            docente=request.user, estudiante=estudiante, materia=materia, periodo=periodo,
                            defaults={'comentario': texto.strip()}
                        )
                    elif not (texto or "").strip():
                        # Añadimos 'periodo=periodo' al filtro 'delete'
                        ComentarioDocente.objects.filter(docente=request.user, estudiante=estudiante, materia=materia, periodo=periodo).delete()
            #
            # ======================================================
            # FIN DE LA CORRECCIÓN
            # ======================================================

            messages.success(request, 'Cambios guardados: Notas, comentarios, actividades y logros.')
            return redirect('subir_notas', materia_id=materia.id)

    # --- Lógica de Carga (GET) ---

    estudiante_ids = [m.estudiante_id for m in estudiantes_matriculados]
    periodo_ids = [p.id for p in periodos]

    # Lógica de Notas (sin cambios, ya estaba correcta)
    notas_qs = Nota.objects.filter(
        estudiante_id__in=estudiante_ids,
        materia=materia,
        periodo_id__in=periodo_ids
    ).values('estudiante_id', 'periodo_id', 'numero_nota', 'valor')

    notas_data = {}
    for m in estudiantes_matriculados:
        notas_data[m.estudiante.id] = {'estudiante': m.estudiante, 'periodos': {p.id: {} for p in periodos}}

    for nota in notas_qs:
        estudiante_id = nota['estudiante_id']
        periodo_id = nota['periodo_id']
        numero_nota = nota['numero_nota']
        valor = nota['valor']
        if estudiante_id in notas_data and periodo_id in notas_data[estudiante_id]['periodos']:
            notas_data[estudiante_id]['periodos'][periodo_id][numero_nota] = valor

    # ======================================================
    # INICIO DE LA CORRECCIÓN (Cargar Comentarios)
    # ======================================================
    #
    # Reemplazamos la consulta simple por una consulta que
    # carga todos los comentarios y los organiza en un
    # diccionario anidado, igual que las notas.
    #
    comentarios_qs = ComentarioDocente.objects.filter(
        docente=request.user,
        materia=materia,
        estudiante_id__in=estudiante_ids
    ).select_related('periodo')

    # Inicializamos: {estudiante_id: {periodo_id: "comentario", ...}}
    comentarios_data = {}
    for m in estudiantes_matriculados:
        comentarios_data[m.estudiante.id] = {p.id: "" for p in periodos}

    # Poblamos el diccionario con los comentarios que existen
    for c in comentarios_qs:
        if c.estudiante_id in comentarios_data and c.periodo_id in comentarios_data[c.estudiante_id]:
            comentarios_data[c.estudiante_id][c.periodo.id] = c.comentario
    #
    # ======================================================
    # FIN DE LA CORRECCIÓN
    # ======================================================

    # Lógica de Actividades y Logros (sin cambios)
    actividades_semanales_existentes = ActividadSemanal.objects.filter(curso=curso, materia=materia).order_by('-fecha_creacion')
    logros_existentes = LogroPeriodo.objects.filter(curso=curso, docente=request.user, materia=materia).order_by('periodo__id', '-fecha_creacion')
    logros_por_periodo = {}
    for logro in logros_existentes:
        logros_por_periodo.setdefault(logro.periodo.id, []).append({'id': logro.id, 'descripcion': logro.descripcion, 'periodo_id': logro.periodo.id})

    # Contexto final
    context = {
        'materia': materia, 'curso': curso, 'estudiantes_matriculados': estudiantes_matriculados,
        'periodos': periodos,
        'notas_data': notas_data,
        'comentarios_data': comentarios_data, # <--- 'comentarios_data' ahora está anidado
        'actividades_semanales': actividades_semanales_existentes,
        'logros_por_periodo': json.dumps(logros_por_periodo),
        'rango_notas': NUM_NOTAS, 'escala_min': ESCALA_MIN, 'escala_max': ESCALA_MAX, 'nota_aprobacion': NOTA_APROBACION,
        'grados': GRADOS_CHOICES, 'secciones': _secciones_disponibles()
    }
    return render(request, 'subir_notas.html', context)
# ===================================================================
# FIN DE LA FUNCIÓN CORREGIDA
# ===================================================================

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

@role_required('ADMINISTRADOR')
def gestionar_profesores(request):
    profesores = User.objects.filter(
        Q(perfil__rol='DOCENTE') | Q(perfil__es_director=True)
    ).select_related('perfil').order_by('first_name', 'last_name').distinct()
    cursos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')
    materias = Materia.objects.all().order_by('nombre')
    if request.method == 'POST':
        if 'crear_profesor' in request.POST:
            username = request.POST.get('username')
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            email = request.POST.get('email')
            password = request.POST.get('password')
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=username, first_name=first_name, last_name=last_name,
                        email=email, password=password
                    )
                    Perfil.objects.create(user=user, rol='DOCENTE', requiere_cambio_clave=True)
                    messages.success(request, f'Profesor {username} creado exitosamente.')
            except IntegrityError:
                messages.error(request, 'El nombre de usuario o email ya existe.')
            except Exception as e:
                messages.error(request, f'Ocurrió un error: {e}')
        elif 'asignar_materia' in request.POST:
            materia_id = request.POST.get('materia_id')
            docente_id = request.POST.get('docente_id')
            curso_id = request.POST.get('curso_id')
            try:
                materia = get_object_or_404(Materia, id=materia_id)
                docente = get_object_or_404(User, id=docente_id)
                curso = get_object_or_404(Curso, id=curso_id)
                AsignacionMateria.objects.update_or_create(
                    materia=materia, curso=curso,
                    defaults={'docente': docente, 'activo': True}
                )
                messages.success(request, 'Materia asignada correctamente al docente.')
            except IntegrityError:
                messages.error(request, 'Esta asignación ya existe.')
            except Exception as e:
                messages.error(request, f'Ocurrió un error: {e}')
            return redirect('asignar_materia_docente')

    context = {
        'docentes': profesores,
        'cursos': cursos,
        'materias': materias,
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
@role_required('ADMINISTRADOR')
@require_POST
@csrf_protect
def admin_eliminar_estudiante(request):
    """
    "Retira" a un estudiante (Soft Delete) y archiva sus boletines.
    1. Genera un boletín por CADA AÑO (matrícula) cursado.
    2. Guarda los PDFs en BoletinArchivado.
    3. Desactiva al Estudiante (User.is_active = False).
    4. Desactiva al Acudiente (si queda huérfano).
    """
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

                    pdf_file = ContentFile(pdf_content, name=f"boletin_{estudiante_nombre}_{matricula.anio_escolar}.pdf")

                    curso_obj = contexto_historico.get('curso')

                    # Guardar en el modelo BoletinArchivado
                    BoletinArchivado.objects.create(
                        nombre_estudiante=estudiante_nombre,
                        username_estudiante=estudiante_a_retirar.username,
                        grado_archivado=curso_obj.grado,
                        seccion_archivada=curso_obj.seccion,
                        anio_lectivo_archivado=curso_obj.anio_escolar,
                        eliminado_por=request.user,
                        archivo_pdf=pdf_file
                    )
                    boletines_generados += 1

                except Exception as e:
                    logger.exception(f"Fallo al generar boletín histórico para {estudiante_nombre} (Año: {matricula.anio_escolar}): {e}")
                    boletines_fallidos += 1

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
                messages.info(request, f"Se generaron y archivaron {boletines_generados} boletines de respaldo (uno por año cursado).")
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
# ===================================================================
# 🩺 FIN DE CIRUGÍA B
# ===================================================================


@role_required('ADMINISTRADOR')
def asignar_materia_docente(request):
    docentes = User.objects.filter(
        Q(perfil__rol='DOCENTE') | Q(perfil__es_director=True)
    ).select_related('perfil').order_by('first_name', 'last_name').distinct()
    cursos = Curso.objects.filter(activo=True).order_by('grado', 'seccion')
    materias = Materia.objects.all().select_related('curso').order_by('curso__grado', 'curso__seccion', 'nombre') # Ordenar por curso
    asignaciones = AsignacionMateria.objects.filter(activo=True).select_related(
        'materia', 'curso', 'docente'
    ).order_by('curso__grado', 'curso__seccion', 'materia__nombre')

    if request.method == 'POST':
        if 'crear_materia' in request.POST:
            nombre = request.POST.get('nombre')
            curso_id = request.POST.get('curso_id')
            if nombre and curso_id:
                try:
                    curso_obj = get_object_or_404(Curso, id=curso_id)
                    materia_obj, created = Materia.objects.get_or_create(
                        nombre=nombre.strip().title(),
                        curso=curso_obj
                    )
                    if created:
                        messages.success(request, f'Materia "{nombre}" creada para el curso {curso_obj}.')
                    else:
                        messages.info(request, f'La materia "{nombre}" ya existía para el curso {curso_obj}.')
                except IntegrityError:
                    messages.error(request, f'Ya existe una materia con el nombre "{nombre}" en ese curso.')
                except Exception as e:
                    messages.error(request, f'Ocurrió un error: {e}')
            else:
                messages.error(request, "Nombre de materia y curso son obligatorios.")

        elif 'asignar_docente' in request.POST:
            materia_id = request.POST.get('materia_id')
            docente_id = request.POST.get('docente_id')
            
            # 🚨 INICIO DE LA CORRECCIÓN 🚨
            # Eliminamos la variable 'curso_id' que viene del formulario,
            # ya que estaba causando el conflicto de validación.
            # curso_id = request.POST.get('curso_id') # <-- LÍNEA ELIMINADA

            try:
                materia_obj = get_object_or_404(Materia, id=materia_id)
                docente_obj = get_object_or_404(User, id=docente_id)

                # Obtenemos el curso correcto DIRECTAMENTE desde la materia seleccionada.
                curso_obj = materia_obj.curso
                
                # Ya no necesitamos la validación, porque el curso
                # SIEMPRE coincidirá con la materia.
                # if materia_obj.curso_id != int(curso_id): # <-- BLOQUE ELIMINADO

                # Esta lógica (que corregimos la vez anterior) ahora funcionará
                # porque 'curso_obj' es el correcto.
                AsignacionMateria.objects.update_or_create(
                    materia=materia_obj,
                    curso=curso_obj,
                    defaults={
                        'docente': docente_obj, 
                        'activo': True
                    }
                )
                
                messages.success(request, f'Materia "{materia_obj.nombre}" asignada a {docente_obj.get_full_name()} en el curso {curso_obj}.')
            except IntegrityError:
                messages.error(request, 'Esta asignación ya existe.')
            except Exception as e:
                logger.error(f"Error en asignar_materia_docente: {e}") # Añadido para mejor depuración
                messages.error(request, f'Ocurrió un error al asignar la materia: {e}')
            
            # 🚨 FIN DE LA CORRECCIÓN 🚨
            
        return redirect('asignar_materia_docente')

    context = {
        'docentes': docentes,
        'cursos': cursos,
        'materias': materias,
        'asignaciones': asignaciones
    }
    
    # Esta ruta de plantilla es correcta según tu primer archivo
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

@login_required
@role_required('ACUDIENTE')
def dashboard_acudiente(request):
    """
    Panel de control para el acudiente. Muestra la información de todos los estudiantes vinculados.

    Correcciones:
    - usar objeto Materia como clave en materias_con_notas (para que plantilla pueda usar `.nombre`)
    - construir para cada estudiante las mismas colecciones que usa dashboard_estudiante
    - Se añade el 'perfil' de cada estudiante para compatibilidad total con la plantilla del estudiante.
    """
    acudiente_user = request.user

    # obtener vínculos acudiente -> estudiantes
    # Optimizamos incluyendo el perfil del estudiante
    vinculados = Acudiente.objects.filter(acudiente=acudiente_user).select_related('estudiante', 'estudiante__perfil')

    if not vinculados.exists():
        messages.error(request, "No tienes estudiantes vinculados. Por favor, contacta a la administración.")
        return render(request, 'dashboard_acudiente.html', {'estudiantes_data': []})

    estudiantes_data = []

    for vinculo in vinculados:
        estudiante = vinculo.estudiante

        # Obtenemos el perfil (ya precargado con select_related si existe)
        perfil_estudiante = getattr(estudiante, 'perfil', None)

        # matrícula activa más reciente
        matricula = Matricula.objects.filter(estudiante=estudiante, activo=True).select_related('curso').first()
        curso = matricula.curso if matricula else None

        # colecciones por estudiante (mismo formato que dashboard_estudiante)
        materias_con_notas = {}
        comentarios_docente = {}
        actividades_semanales = {}
        convivencia_notas = {}
        logros_por_materia_por_periodo = {}
        periodos_disponibles = []

        if curso:
            # periodos y materias del curso
            periodos_disponibles = list(Periodo.objects.filter(curso=curso, activo=True).order_by('id'))
            asignaciones = AsignacionMateria.objects.filter(curso=curso, activo=True).select_related('materia')
            materias = [a.materia for a in asignaciones]

            # Notas del estudiante en las materias del curso
            # Se optimiza la consulta para traer notas de todas las materias de una vez
            notas_qs = Nota.objects.filter(
                estudiante=estudiante, materia__in=materias
            ).select_related('periodo', 'materia').order_by('periodo__id', 'numero_nota')

            for nota in notas_qs:
                materia_obj = nota.materia  # <-- objeto Materia
                periodo_id = nota.periodo.id
                # clave = objeto materia (no id) para que la plantilla pueda usar materia.nombre
                materias_con_notas.setdefault(materia_obj, {}).setdefault(periodo_id, {})[nota.numero_nota] = nota

            # Comentarios por materia del docente
            comentarios_qs = ComentarioDocente.objects.filter(estudiante=estudiante, materia__in=materias).select_related('materia', 'docente')
            for c in comentarios_qs:
                # clave = materia.id (así lo usa la plantilla del estudiante)
                comentarios_docente.setdefault(c.materia.id, []).append(c)

            # Actividades semanales del curso por materia
            actividades_qs = ActividadSemanal.objects.filter(curso=curso, materia__in=materias).order_by('-fecha_creacion').select_related('materia')
            for act in actividades_qs:
                # clave = materia.id (así lo usa la plantilla del estudiante)
                actividades_semanales.setdefault(act.materia.id, []).append(act)

            # Logros por materia y periodo
            logros_qs = LogroPeriodo.objects.filter(curso=curso, materia__in=materias).order_by('periodo__id', '-fecha_creacion').select_related('periodo', 'materia')
            for logro in logros_qs:
                # clave = objeto materia (así lo usa la plantilla del estudiante)
                logros_por_materia_por_periodo.setdefault(logro.materia, {}).setdefault(logro.periodo.id, []).append(logro)

            # Convivencia (notas) del estudiante
            convivencia_qs = Convivencia.objects.filter(estudiante=estudiante, curso=curso).select_related('periodo')
            for conv in convivencia_qs:
                convivencia_notas[conv.periodo.id] = {'valor': conv.valor, 'comentario': conv.comentario}

        # ahora agregamos el bloque con la misma estructura que espera la plantilla dashboard_estudiante.html
        estudiantes_data.append({
            'estudiante': estudiante,
            'perfil': perfil_estudiante, # <-- AÑADIDO PARA COMPATIBILIDAD
            'curso': curso,
            'matricula': matricula, # <-- AÑADIDO PARA COMPATIBILIDAD
            'periodos_disponibles': periodos_disponibles,
            'materias_con_notas': materias_con_notas,
            'comentarios_docente': comentarios_docente,
            'actividades_semanales': actividades_semanales,
            'logros_por_materia_por_periodo': logros_por_materia_por_periodo,
            'convivencia_notas': convivencia_notas,
        })

    context = {
        'acudiente': acudiente_user,
        'estudiantes_data': estudiantes_data
    }
    return render(request, 'dashboard_acudiente.html', context)


@login_required
def cambiar_clave(request):
    """
    Permite a los usuarios cambiar su contraseña, especialmente la primera vez.
    """
    if request.method == 'POST':
        # Usa PasswordChangeFirstLoginForm
        form = PasswordChangeFirstLoginForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)

            if hasattr(user, 'perfil'):
                user.perfil.requiere_cambio_clave = False
                user.perfil.save(update_fields=['requiere_cambio_clave'])

            messages.success(request, '¡Tu contraseña ha sido cambiada exitosamente!')
            return redirect('signin') # Redirige a signin para el flujo normal a su dashboard
        else:
            messages.error(request, 'Por favor corrige los errores a continuación.')
    else:
        # Usa PasswordChangeFirstLoginForm.
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

def _generar_boletin_pdf_logica(request, matricula_id: int):
    """
    Función interna que contiene la lógica de renderizado de PDF
    para una MATRÍCULA específica.
    """
    if HTML is None:
        raise Exception("El módulo de generación de PDF (WeasyPrint) no está instalado.")

    # Llama al service refactorizado con el ID de la matrícula
    context = get_student_report_context(matricula_id)
    if not context:
        raise Http404(f"No se encontró contexto para la matrícula_id: {matricula_id}")

    context['request'] = request

    html_string = render_to_string('pdf/boletin_template.html', context)

    # WeasyPrint necesita una base_url para encontrar archivos estáticos (CSS, logo)
    base_url = request.build_absolute_uri('/')
    pdf = HTML(string=html_string, base_url=base_url).write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    # 'inline' abre el PDF en el navegador, 'attachment' lo descarga
    response['Content-Disposition'] = f'inline; filename="boletin_{context["estudiante"].username}_{context["curso"].anio_escolar}.pdf"'
    return response

# ===================================================================
# 🩺 FIN DE CIRUGÍA A
# ===================================================================


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