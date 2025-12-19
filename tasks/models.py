from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
import os
from datetime import timedelta
from datetime import date
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.utils.text import slugify

from .ai.constants import (
    # 1. Configuración General y Roles
    ROLES_IA_PERMITIDOS,
    ACCIONES_IA_PERMITIDAS,
    MODEL_NAME,

    # 2. Tipos de Documentos Oficiales (Fase 6)
    DOC_REPORTE_PEDAGOGICO,
    DOC_ORIENTACION_ESTUDIANTE,
    DOC_ORIENTACION_ACUDIENTE,
    DOC_REPORTE_CONVIVENCIA,
    DOC_REPORTE_INSTITUCIONAL,
    DOCUMENTOS_IA_PERMITIDOS  # Útil si necesitas validar listas
)

# ===================================================================
# CONSTANTES Y OPCIONES
# ===================================================================

GRADOS_CHOICES = (
    ('PREKINDER', 'Prekinder'),
    ('KINDER', 'Kinder'),
    ('JARDIN', 'Jardín'),
    ('TRANSICION', 'Transición'),
    ('1', 'Primer grado'),
    ('2', 'Segundo grado'),
    ('3', 'Tercer grado'),
    ('4', 'Cuarto grado'),
    ('5', 'Quinto grado'),
    ('6', 'Sexto grado'),
    ('7', 'Séptimo grado'),
    ('8', 'Octavo grado'),
    ('9', 'Noveno grado'),
    ('10', 'Décimo grado'),
    ('11', 'Undécimo grado'),
)

ROLES_CHOICES = (
    ('ESTUDIANTE', 'Estudiante'),
    ('DOCENTE', 'Docente'),
    ('ADMINISTRADOR', 'Administrador'),
    ('DIRECTOR_CURSO', 'Director de Curso'),
    ('ACUDIENTE', 'Acudiente'),
    ('PSICOLOGO', 'Psicólogo'),
    ('COORD_CONVIVENCIA', 'Coord. Convivencia'),
    ('COORD_ACADEMICO', 'Coord. Académico'),
)

# ===================================================================
# PERFILES Y USUARIOS
# ===================================================================

class Perfil(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    rol = models.CharField(max_length=20, choices=ROLES_CHOICES, default='ESTUDIANTE')
    
    # --- FLAGS ADMINISTRATIVOS ---
    es_director = models.BooleanField(default=False)
    requiere_cambio_clave = models.BooleanField(default=False)
    
    # --- IDENTIDAD VISUAL Y SOCIAL ---
    foto_perfil = models.ImageField(upload_to='perfiles/avatars/', blank=True, null=True, verbose_name="Foto de Perfil")
    foto_portada = models.ImageField(upload_to='perfiles/covers/', blank=True, null=True, verbose_name="Foto de Portada")
    biografia = models.TextField(max_length=500, blank=True, verbose_name="Sobre mí")
    
    # --- NUEVOS CAMPOS: INTERESES Y GUSTOS ---
    hobbies = models.TextField(blank=True, null=True, verbose_name="Mis Hobbies")
    gustos_musicales = models.CharField(max_length=255, blank=True, null=True, verbose_name="Música favorita")
    libros_favoritos = models.TextField(blank=True, null=True, verbose_name="Libros que me gustan")
    materia_favorita = models.CharField(max_length=100, blank=True, null=True, verbose_name="Materia favorita")
    metas_anio = models.TextField(blank=True, null=True, verbose_name="Metas del año lectivo")
    
    # --- GAMIFICACIÓN Y ESTADO ---
    puntos_reputacion = models.IntegerField(default=0, verbose_name="Reputación Académica")
    last_seen = models.DateTimeField(null=True, blank=True, verbose_name="Última vez visto")
    
    # --- PRIVACIDAD ---
    perfil_publico = models.BooleanField(default=True, help_text="Si es falso, solo profesores y compañeros de curso pueden verlo.")

    def __str__(self):
        return f'{self.user.username} ({self.get_rol_display()})'

    class Meta:
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuario'
        
    @property
    def esta_en_linea(self):
        """Retorna True si el usuario tuvo actividad en los últimos 5 minutos."""
        if self.last_seen:
            now = timezone.now()
            return now - self.last_seen < timezone.timedelta(minutes=5)
        return False


class SocialGroup(models.Model):
    """
    Espacios sociales temáticos (Clubs, Grupos de Estudio, Deportes).
    """
    PRIVACIDAD_CHOICES = (
        ('PUBLICO', 'Público (Cualquiera puede unirse)'),
        ('PRIVADO', 'Privado (Requiere aprobación)'),
    )

    # 1. NOMBRE: Quitamos el default para que guarde el nombre real
    name = models.CharField(max_length=100, verbose_name="Nombre del Grupo")
    
    # Slug para URLs amigables
    slug = models.SlugField(unique=True, blank=True, null=True)
    
    description = models.TextField(blank=True, verbose_name="Descripción")
    
    # Imagen de portada
    image = models.ImageField(upload_to='groups/covers/', blank=True, null=True, verbose_name="Imagen de Portada")
    
    # 2. CREADOR: Quitamos default=1 para asignar el usuario real en la vista
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='created_groups', 
        verbose_name="Creador",
        null=True, 
        blank=True
    )
    
    # 3. MIEMBROS: Relación limpia para permitir .add() y .remove()
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name='social_groups', 
        verbose_name="Miembros",
        blank=True
    )
    
    admins = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name='admin_groups', 
        blank=True, 
        verbose_name="Administradores"
    )

    # Configuración
    tipo_privacidad = models.CharField(max_length=10, choices=PRIVACIDAD_CHOICES, default='PUBLICO')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Grupo Social"
        verbose_name_plural = "Grupos Sociales"
        ordering = ['-created_at']

    def __str__(self):
        return self.name
        
    def save(self, *args, **kwargs):
        # Generar slug automáticamente basado en el nombre real
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while SocialGroup.objects.filter(slug=slug).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_member_count(self):
        return self.members.count()

    def es_miembro(self, user):
        """Devuelve True si el usuario es miembro del grupo"""
        return self.members.filter(id=user.id).exists()

    @property
    def is_public(self):
        return self.tipo_privacidad == 'PUBLICO'

class GroupMember(models.Model):
    """
    Tabla intermedia para miembros de grupo con roles.
    """
    ROL_CHOICES = (
        ('ADMIN', 'Administrador'),
        ('MODERATOR', 'Moderador'),
        ('MEMBER', 'Miembro'),
    )

    grupo = models.ForeignKey(SocialGroup, on_delete=models.CASCADE)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rol = models.CharField(max_length=10, choices=ROL_CHOICES, default='MEMBER')
    unido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('grupo', 'usuario')
        verbose_name = "Miembro de Grupo"
        verbose_name_plural = "Miembros de Grupo"

    def __str__(self):
        return f"{self.usuario.username} en {self.grupo.name} ({self.get_rol_display()})"


class Acudiente(models.Model):
    acudiente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='estudiantes_a_cargo',
        limit_choices_to={'perfil__rol': 'ACUDIENTE'},
        verbose_name='Usuario Acudiente'
    )
    estudiante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='acudientes_asignados',
        limit_choices_to={'perfil__rol': 'ESTUDIANTE'},
        verbose_name='Usuario Estudiante'
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')

    class Meta:
        verbose_name = 'Vínculo Acudiente-Estudiante'
        verbose_name_plural = 'Vínculos Acudiente-Estudiante'
        unique_together = ('acudiente', 'estudiante')

    def __str__(self):
        acudiente_nombre = self.acudiente.get_full_name() or self.acudiente.username
        estudiante_nombre = self.estudiante.get_full_name() or self.estudiante.username
        return f"Acudiente: {acudiente_nombre} -> Estudiante: {estudiante_nombre}"

# ===================================================================
# INSTITUCIONAL Y ACADÉMICO BÁSICO
# ===================================================================

class Institucion(models.Model):
    nombre = models.CharField(max_length=150)
    logo = models.ImageField(upload_to="logos_institucionales/", null=True, blank=True)
    direccion = models.CharField(max_length=150, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    correo = models.EmailField(blank=True, null=True)
    nit = models.CharField(max_length=50, blank=True, null=True)
    ciudad = models.CharField(max_length=100, blank=True, null=True)
    departamento = models.CharField(max_length=100, blank=True, null=True)
    resolucion = models.CharField(max_length=200, blank=True, null=True)
    lema = models.CharField(max_length=200, blank=True, null=True)
    anio_lectivo = models.CharField(max_length=10, default="2025")
    
    archivo_pei = models.FileField(
        upload_to='documentos_institucionales/', 
        null=True, 
        blank=True, 
        verbose_name="Documento PEI (PDF)",
        help_text="Carga aquí el Proyecto Educativo Institucional en formato PDF."
    )

    class Meta:
        verbose_name = "Institución"
        verbose_name_plural = "Información Institucional"

    def __str__(self):
        return getattr(self, 'nombre', f"Institución sin nombre (ID: {self.pk or 'Nueva'})")


class Curso(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    director = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cursos_dirigidos',
        verbose_name='Director de Curso',
        limit_choices_to={'perfil__rol__in': ['DOCENTE']}
    )
    capacidad_maxima = models.IntegerField(default=40, verbose_name='Capacidad Máxima')
    anio_escolar = models.CharField(max_length=9, default='2025-2026', verbose_name='Año Escolar')
    seccion = models.CharField(max_length=100, default='A', verbose_name='Sección')
    grado = models.CharField(max_length=20, choices=GRADOS_CHOICES, default='6', verbose_name='Grado')
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')

    class Meta:
        unique_together = ['grado', 'seccion', 'anio_escolar']
        verbose_name = 'Curso'
        verbose_name_plural = 'Cursos'
        ordering = ['grado', 'seccion']

    def __str__(self):
        return f"{self.get_grado_display()} {self.seccion} - {self.anio_escolar}"

    def esta_completo(self):
        return self.matriculados.filter(activo=True).count() >= self.capacidad_maxima


class Materia(models.Model):
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='materias', verbose_name='Curso')

    class Meta:
        unique_together = ('nombre', 'curso')
        verbose_name = 'Materia'
        verbose_name_plural = 'Materias'

    def __str__(self):
        return f'{self.nombre} ({self.curso.nombre})'


class Periodo(models.Model):
    nombre = models.CharField(max_length=50, verbose_name='Nombre')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='periodos', verbose_name='Curso')
    fecha_inicio = models.DateField(default=timezone.now, verbose_name='Fecha de Inicio')
    fecha_fin = models.DateField(default=timezone.now, verbose_name='Fecha de Fin')
    activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        unique_together = ('nombre', 'curso')
        verbose_name = 'Periodo'
        verbose_name_plural = 'Periodos'

    def __str__(self):
        return f'{self.nombre} ({self.curso.nombre})'


class Matricula(models.Model):
    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='matriculas')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='matriculados')
    anio_escolar = models.CharField(max_length=9, default='2025-2026', verbose_name='Año Escolar')
    fecha_matricula = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Matrícula')
    activo = models.BooleanField(default=True)

    puede_generar_boletin = models.BooleanField(
        default=True,
        verbose_name="Acudiente puede generar boletín",
        help_text="Si está desactivado, el acudiente no podrá generar boletín desde su panel."
    )
    puede_ver_observador = models.BooleanField(
        default=True,
        verbose_name="Acudiente puede ver Observador",
        help_text="Si está desactivado, el acudiente no podrá descargar el observador."
    )

    class Meta:
        unique_together = ['estudiante', 'anio_escolar']
        verbose_name = 'Matrícula'
        verbose_name_plural = 'Matrículas'

    def __str__(self):
        return f"{self.estudiante.username} - {self.curso.nombre} ({self.anio_escolar})"


class AsignacionMateria(models.Model):
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='asignaciones')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='asignaciones_materias')
    docente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='materias_asignadas')
    periodo_academico = models.CharField(max_length=20, default='2025-1', verbose_name='Periodo Académico')
    activo = models.BooleanField(default=True)
  
    class Meta:
        unique_together = ['materia', 'curso', 'docente']
        verbose_name = 'Asignación de Materia'
        verbose_name_plural = 'Asignaciones de Materias'

    def __str__(self):
        return f"{self.docente.username} -> {self.materia.nombre} en {self.curso.nombre}"

# ===================================================================
# GESTIÓN ACADÉMICA (NOTAS, LOGROS, ACTIVIDADES)
# ===================================================================

class Nota(models.Model):
    valor = models.DecimalField(max_digits=4, decimal_places=2, verbose_name='Valor')
    descripcion = models.CharField(max_length=100, blank=True, verbose_name='Descripción')
    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notas')
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='notas', verbose_name='Materia')
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name='notas', verbose_name='Periodo')
    numero_nota = models.IntegerField(default=1, verbose_name='Número de Nota')
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Registro')
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='notas_registradas'
    )

    class Meta:
        unique_together = ['estudiante', 'materia', 'periodo', 'numero_nota']
        verbose_name = 'Nota'
        verbose_name_plural = 'Notas'

    def __str__(self):
        return f'Nota {self.numero_nota} de {self.estudiante.username} en {self.materia.nombre} ({self.valor})'


class LogroPeriodo(models.Model):
    docente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='logros_registrados', verbose_name='Docente')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='logros_periodo', verbose_name='Curso')
    materia = models.ForeignKey(Materia, on_delete=models.SET_NULL, null=True, blank=True, related_name='logros_materia', verbose_name='Materia')
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name='logros', verbose_name='Periodo')
    descripcion = models.TextField(verbose_name='Descripción del Logro')
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')

    class Meta:
        verbose_name = "Logro del Periodo"
        verbose_name_plural = "Logros de los Periodos"
        unique_together = ('curso', 'periodo', 'docente', 'materia')
        ordering = ['periodo', '-fecha_creacion']

    def __str__(self):
        return f"Logro de {self.docente.username} para {self.curso.nombre} en {self.periodo.nombre}"


class ActividadSemanal(models.Model):
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='actividades')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='actividades_semanales')
    titulo = models.CharField(max_length=200, default='Actividad de la Semana', verbose_name='Título')
    descripcion = models.TextField(verbose_name='Descripción')
    fecha_inicio = models.DateField(null=True, blank=True, verbose_name='Fecha de Inicio')
    fecha_fin = models.DateField(null=True, blank=True, verbose_name='Fecha de Finalización')
    docente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Docente')
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')

    def __str__(self):
        return f'{self.titulo} - {self.materia.nombre} ({self.curso.nombre})'

    class Meta:
        verbose_name = "Actividad Semanal"
        verbose_name_plural = "Actividades Semanales"
        ordering = ['-fecha_creacion']


class ComentarioDocente(models.Model):
    docente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comentarios_escritos')
    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comentarios_recibidos')
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='comentarios')
    comentario = models.TextField(verbose_name='Comentario')
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        verbose_name = 'Comentario del Docente'
        verbose_name_plural = 'Comentarios de los Docentes'
        unique_together = ('docente', 'estudiante', 'materia', 'periodo')
        ordering = ['-fecha_creacion']

    def __str__(self):
        if self.periodo:
            return f"Comentario de {self.docente.username} para {self.estudiante.username} en {self.materia.nombre} ({self.periodo.nombre})"
        return f"Comentario de {self.docente.username} para {self.estudiante.username} en {self.materia.nombre} (Sin periodo)"

# ===================================================================
# BIENESTAR Y CONVIVENCIA (OBSERVADOR, CONVIVENCIA, ASISTENCIA)
# ===================================================================

class Convivencia(models.Model):
    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='convivencias')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='convivencias_curso')
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name='convivencias_periodo')
    valor = models.DecimalField(max_digits=3, decimal_places=2, help_text="Valor de la nota de 0.0 a 5.0")
    comentario = models.TextField(blank=True, null=True, help_text="Comentario opcional del director de curso")
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='convivencias_registradas')
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('estudiante', 'curso', 'periodo')
        verbose_name = "Nota de Convivencia"
        verbose_name_plural = "Notas de Convivencia"
        ordering = ['-periodo', 'estudiante']

    def __str__(self):
        return f"Convivencia de {self.estudiante.username} en {self.curso.nombre} ({self.periodo.nombre})"


class Observacion(models.Model):
    TIPO_CHOICES = (
        ('CONVIVENCIA', 'Situación de Convivencia'),
        ('ACADEMICA', 'Compromiso Académico'),
        ('PSICOLOGIA', 'Orientación Psicológica'),
        ('FELICITACION', 'Felicitación / Reconocimiento'),
    )

    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='observaciones')
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='observaciones_creadas')
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, related_name='observaciones')

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descripcion = models.TextField(verbose_name="Descripción de la situación")
    compromisos_estudiante = models.TextField(blank=True, verbose_name="Compromisos del Estudiante")
    compromisos_familia = models.TextField(blank=True, verbose_name="Compromisos de la Familia/Acudiente")

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    fecha_limite_edicion = models.DateTimeField(editable=False)

    def save(self, *args, **kwargs):
        if not self.id:
            self.fecha_limite_edicion = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    @property
    def es_editable(self):
        return timezone.now() < self.fecha_limite_edicion

    class Meta:
        verbose_name = "Observación del Alumno"
        verbose_name_plural = "Observaciones"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.estudiante}"


class Asistencia(models.Model):
    ESTADO_CHOICES = (
        ('ASISTIO', 'Asistió'),
        ('FALLA', 'Falla Injustificada'),
        ('EXCUSA', 'Falla Excusada'),
        ('TARDE', 'Llegada Tardía'),
    )
    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='asistencias')
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE)
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    fecha = models.DateField(default=timezone.now)
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='ASISTIO')
    observacion = models.CharField(max_length=200, blank=True, null=True)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='asistencias_tomadas')

    class Meta:
        unique_together = ('estudiante', 'materia', 'fecha')
        verbose_name = 'Registro de Asistencia'
        ordering = ['-fecha']

# ===================================================================
# HISTÓRICO Y ARCHIVOS (BOLETINES ANTIGUOS)
# ===================================================================

def ruta_archivo_boletin(instance, filename):
    grado_folder = instance.grado_archivado.replace(' ', '_').lower()
    anio_folder = instance.anio_lectivo_archivado.replace('-', '_')
    username_limpio = "".join(c for c in instance.username_estudiante if c.isalnum() or c in ('-', '_')).rstrip()
    filename = f"boletin_{username_limpio}_{anio_folder}.pdf"
    return os.path.join('boletines_archivados', anio_folder, grado_folder, filename)

class BoletinArchivado(models.Model):
    nombre_estudiante = models.CharField(max_length=255, db_index=True, help_text="Nombre completo del estudiante al momento del retiro.")
    username_estudiante = models.CharField(max_length=150, db_index=True, help_text="Username (documento) del estudiante para referencia.")
    grado_archivado = models.CharField(max_length=20, choices=GRADOS_CHOICES, db_index=True, help_text="El grado que cursaba el estudiante.")
    seccion_archivada = models.CharField(max_length=100, help_text="La sección que cursaba.")
    anio_lectivo_archivado = models.CharField(max_length=9, db_index=True, help_text="El año escolar de este boletín.")
    
    fecha_eliminado = models.DateTimeField(auto_now_add=True, help_text="Fecha y hora en que se generó este archivo.")
    eliminado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='boletines_archivados_por_mi')
    archivo_pdf = models.FileField(upload_to=ruta_archivo_boletin, help_text="El archivo PDF del boletín.")

    class Meta:
        verbose_name = "Boletín Archivado (Exalumno)"
        verbose_name_plural = "Boletines Archivados (Exalumnos)"
        ordering = ['-anio_lectivo_archivado', 'grado_archivado', 'nombre_estudiante']
        unique_together = ('username_estudiante', 'anio_lectivo_archivado')

    def __str__(self):
        return f"Boletín de {self.nombre_estudiante} ({self.anio_lectivo_archivado})"

# ===================================================================
# COMUNICACIÓN (FOROS, CHAT, NOTIFICACIONES)
# ===================================================================

class Question(models.Model):
    title = models.CharField(max_length=200, verbose_name='Título')
    content = models.TextField(verbose_name='Contenido')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Usuario')

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = 'Pregunta'
        verbose_name_plural = 'Preguntas'
        ordering = ['-created_at']


class Answer(models.Model):
    question = models.ForeignKey(Question, related_name='answers', on_delete=models.CASCADE)
    content = models.TextField(verbose_name='Contenido')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Usuario')

    def __str__(self):
        return f'Respuesta de {self.user.username} en {self.question.title}'

    class Meta:
        verbose_name = 'Respuesta'
        verbose_name_plural = 'Respuestas'
        ordering = ['created_at']


class ChatRoom(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Nombre')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Sala de Chat'
        verbose_name_plural = 'Salas de Chat'


class ActiveUser(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Usuario')
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, null=True, verbose_name='Sala de Chat')
    last_activity = models.DateTimeField(auto_now=True, verbose_name='Última Actividad')

    class Meta:
        unique_together = ('user', 'room')
        verbose_name = 'Usuario Activo'
        verbose_name_plural = 'Usuarios Activos'

    def __str__(self):
        return f'{self.user.username} en {self.room.name}'


class Notificacion(models.Model):
    TIPO_CHOICES = (
        ('ASISTENCIA', 'Novedad de Asistencia'),
        ('OBSERVADOR', 'Nueva Observación'),
        ('ACTIVIDAD', 'Nueva Actividad'),
        ('MENSAJE', 'Nuevo Mensaje'),
        ('SISTEMA', 'Sistema'),
    )
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mis_notificaciones')
    titulo = models.CharField(max_length=100)
    mensaje = models.TextField()
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='SISTEMA')
    leida = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    link_destino = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        ordering = ['-fecha_creacion']


class MensajeInterno(models.Model):
    remitente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mensajes_enviados')
    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mensajes_recibidos')
    asunto = models.CharField(max_length=200)
    cuerpo = models.TextField()
    leido = models.BooleanField(default=False)
    fecha_envio = models.DateTimeField(auto_now_add=True)
    
    archivo = models.FileField(upload_to='adjuntos_chat/', blank=True, null=True, verbose_name="Archivo Adjunto")
    
    class Meta:
        ordering = ['-fecha_envio']
        verbose_name = "Mensaje Profesional"

    def __str__(self):
        return f"De {self.remitente} para {self.destinatario}: {self.asunto}"


# ===================================================================
# 🏗️ FASE I: RED SOCIAL (FEED, COMENTARIOS Y REACCIONES)
# ===================================================================

class Post(models.Model):
    TIPO_POST_CHOICES = (
        ('PUBLICACION', 'Publicación General'),
        ('ANUNCIO', 'Anuncio Oficial'), 
        ('EVENTO', 'Evento'),
    )

    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    contenido = models.TextField(verbose_name="¿Qué estás pensando?")
    tipo = models.CharField(max_length=20, choices=TIPO_POST_CHOICES, default='PUBLICACION')
    
    imagen = models.ImageField(upload_to='social_feed/images/', blank=True, null=True)
    archivo = models.FileField(upload_to='social_feed/files/', blank=True, null=True)
    
    # Vinculado al modelo SocialGroup unificado
    grupo = models.ForeignKey('SocialGroup', on_delete=models.CASCADE, null=True, blank=True, related_name='posts')
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    es_destacado = models.BooleanField(default=False)

    reacciones = GenericRelation('Reaction') 

    class Meta:
        verbose_name = "Publicación Social"
        verbose_name_plural = "Publicaciones Sociales"
        ordering = ['-es_destacado', '-creado_en']

    def __str__(self):
        return f"{self.autor.username}: {self.contenido[:30]}..."

    @property
    def total_reacciones(self):
        return self.reacciones.count()

    @property
    def total_comentarios(self):
        return self.comentarios.count()


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comentarios')
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    contenido = models.TextField()
    
    padre = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='respuestas')
    
    creado_en = models.DateTimeField(auto_now_add=True)
    reacciones = GenericRelation('Reaction')

    class Meta:
        ordering = ['creado_en'] 

    def __str__(self):
        return f"Comentario de {self.autor.username} en {self.post.id}"

    @property
    def es_respuesta(self):
        return self.padre is not None


class Reaction(models.Model):
    TIPO_REACCION_CHOICES = (
        ('LIKE', '👍 Me gusta'),
        ('LOVE', '❤️ Me encanta'),
        ('WOW', '😲 Me asombra'),
        ('SAD', '😢 Me entristece'),
        ('ANGRY', '😡 Me enoja'),
    )

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=10, choices=TIPO_REACCION_CHOICES, default='LIKE')
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'content_type', 'object_id')
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.usuario.username} reaccionó {self.tipo}"

# ===================================================================
# 🏗️ FASE I (PASO 2): SEGUIDORES
# ===================================================================

class Follow(models.Model):
    follower = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='siguiendo', on_delete=models.CASCADE)
    following = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='seguidores', on_delete=models.CASCADE)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')
        verbose_name = "Seguimiento"
        verbose_name_plural = "Seguimientos"
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.follower.username} sigue a {self.following.username}"


# ===================================================================
# 🏗️ FASE I (PASO 3): GAMIFICACIÓN Y RECOMPENSAS
# ===================================================================

class Logro(models.Model):
    CLASE_ICONO_CHOICES = (
        ('BRONZE', 'Bronce (Básico)'),
        ('SILVER', 'Plata (Intermedio)'),
        ('GOLD', 'Oro (Avanzado)'),
        ('DIAMOND', 'Diamante (Experto)'),
    )

    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, help_text="Identificador único")
    descripcion = models.TextField()
    imagen = models.ImageField(upload_to='gamification/badges/', blank=True, null=True)
    clase_css = models.CharField(max_length=20, choices=CLASE_ICONO_CHOICES, default='BRONZE')
    puntos_otorgados = models.IntegerField(default=10)
    es_oculto = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Definición de Logro"
        verbose_name_plural = "Definiciones de Logros"

    def __str__(self):
        return f"{self.nombre} (+{self.puntos_otorgados} pts)"


class UserLogro(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='logros_obtenidos')
    logro = models.ForeignKey(Logro, on_delete=models.CASCADE)
    fecha_obtenido = models.DateTimeField(auto_now_add=True)
    es_destacado = models.BooleanField(default=False)

    class Meta:
        unique_together = ('usuario', 'logro') 
        verbose_name = "Logro de Usuario"
        verbose_name_plural = "Logros de Usuarios"
        ordering = ['-fecha_obtenido']

    def __str__(self):
        return f"{self.usuario.username} ganó {self.logro.nombre}"

# ===================================================================
# 🏗️ FASE I (PASO 4): SEGURIDAD Y AUDITORÍA
# ===================================================================

class Report(models.Model):
    RAZONES_CHOICES = (
        ('BULLYING', 'Acoso o Intimidación'),
        ('HATE', 'Lenguaje de Odio'),
        ('SPAM', 'Spam o Contenido Basura'),
        ('VIOLENCE', 'Violencia o Amenazas'),
        ('SEXUAL', 'Contenido Sexual'),
        ('OTHER', 'Otro motivo'),
    )
    
    ESTADO_CHOICES = (
        ('PENDING', 'Pendiente de Revisión'),
        ('RESOLVED', 'Resuelto / Tomada Acción'),
        ('DISMISSED', 'Descartado / Falso Reporte'),
    )

    denunciante = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='reportes_realizados', on_delete=models.CASCADE)
    razon = models.CharField(max_length=20, choices=RAZONES_CHOICES)
    descripcion = models.TextField(blank=True, verbose_name="Detalles adicionales")
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDING')
    resolucion = models.TextField(blank=True, help_text="Nota del moderador")
    resuelto_por = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='reportes_resueltos', null=True, blank=True, on_delete=models.SET_NULL)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Reporte de Moderación"
        verbose_name_plural = "Reportes de Moderación"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Reporte {self.get_razon_display()} por {self.denunciante.username}"


class AuditLog(models.Model):
    ACCION_CHOICES = (
        ('CREATE', 'Creación'),
        ('UPDATE', 'Edición'),
        ('DELETE', 'Eliminación'),
        ('LOGIN', 'Inicio de Sesión'),
        ('LOGIN_FAIL', 'Fallo de Login'),
        ('SENSITIVE', 'Acceso Sensible'),
    )

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    accion = models.CharField(max_length=20, choices=ACCION_CHOICES)
    modelo_afectado = models.CharField(max_length=100) 
    objeto_id = models.CharField(max_length=100, null=True, blank=True)
    detalles = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de Auditoría"
        verbose_name_plural = "Registros de Auditoría"
        ordering = ['-fecha']

    def __str__(self):
        user_str = self.usuario.username if self.usuario else "Sistema/Anon"
        return f"[{self.fecha}] {user_str} - {self.accion} en {self.modelo_afectado}"


# In tasks/models.py

class SecurityLog(models.Model):
    TIPOS_ALERTA = (
        ('VOCABULARIO', 'Vocabulario Ofensivo'),
        ('ACOSO', 'Posible Acoso/Bullying'),
    )
    
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='alertas_seguridad')
    contenido_intentado = models.TextField()
    razon_bloqueo = models.CharField(max_length=255)
    fecha = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Reporte de Seguridad"
        verbose_name_plural = "Reportes de Seguridad"
        ordering = ['-fecha']

    def __str__(self):
        return f"ALERTA: {self.usuario.username} - {self.fecha}"


# ==============================================================================
# PASO 0.2: PERIODO ACADÉMICO (GOBERNANZA Y CONTROL DE COSTOS)
# ==============================================================================

class PeriodoAcademico(models.Model):
    """
    Representa un periodo académico institucional y actúa como el
    GOBERNADOR FISCAL del uso de IA.
    
    Controla: Tiempo, Costos (Límites) y Unicidad.
    """

    nombre = models.CharField(
        max_length=100,
        unique=True,
        help_text="Ej: 2025-1, Año Lectivo 2025, Trimestre 2"
    )

    fecha_inicio = models.DateField(
        help_text="Fecha oficial de inicio del periodo académico"
    )

    fecha_fin = models.DateField(
        help_text="Fecha oficial de finalización del periodo académico"
    )

    activo = models.BooleanField(
        default=False,
        help_text="🔴 CRÍTICO: Solo un periodo puede estar activo. Al activar este, se desactivan los demás."
    )

    # ------------------------------------------------------------------
    # GOBERNANZA DE IA (Control de Costos Dinámico)
    # ------------------------------------------------------------------
    # Definimos los límites AQUÍ para poder ajustarlos desde el Admin
    # sin tocar el código si el presupuesto cambia.
    
    limite_intentos_profesor = models.IntegerField(
        default=10,  # Aumentado un poco para dar margen a pruebas iniciales
        help_text="Intentos de IA profunda (DeepSeek) permitidos por periodo para docentes."
    )
    
    limite_intentos_estudiante = models.IntegerField(
        default=2,
        help_text="Intentos de IA profunda permitidos por periodo para estudiantes."
    )

    limite_intentos_acudiente = models.IntegerField(
        default=1,
        help_text="Intentos de IA para orientación familiar por periodo."
    )

    limite_intentos_staff = models.IntegerField(
        default=50,
        help_text="Intentos para Staff (Psicología/Coord) para análisis institucional."
    )

    # ------------------------------------------------------------------
    # AUDITORÍA
    # ------------------------------------------------------------------
    creado_en = models.DateTimeField(auto_now_add=True)
    cerrado_en = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Fecha en que el periodo fue cerrado institucionalmente"
    )

    class Meta:
        ordering = ['-fecha_inicio']
        verbose_name = "Periodo Académico (Governance)"
        verbose_name_plural = "Periodos Académicos (Governance)"

    def __str__(self):
        estado = "✅ ACTIVO" if self.activo else "⏹ INACTIVO"
        return f"{self.nombre} ({estado})"

    def clean(self):
        """Validación de integridad de datos antes de guardar."""
        if self.fecha_inicio and self.fecha_fin and self.fecha_inicio > self.fecha_fin:
            raise ValidationError("La fecha de inicio no puede ser posterior a la fecha de fin.")

    def save(self, *args, **kwargs):
        """
        Garantiza que SOLO UN periodo sea activo a la vez.
        Si activamos este, matamos la actividad de los otros.
        """
        if self.activo:
            # Desactivar todos los demás periodos activos
            PeriodoAcademico.objects.filter(activo=True).exclude(pk=self.pk).update(activo=False)
        
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------
    # LÓGICA DE NEGOCIO
    # ------------------------------------------------------------------

    def cerrar_periodo(self):
        """Cierra el periodo académicamente y detiene el consumo de IA asociado."""
        self.activo = False
        self.cerrado_en = timezone.now()
        self.save(update_fields=["activo", "cerrado_en"])

    @classmethod
    def obtener_periodo_activo(cls):
        """
        Devuelve el periodo académico activo (El Gobernador actual).
        Optimizado para no traer toda la tabla.
        """
        return cls.objects.filter(activo=True).first()

    @property
    def esta_vigente(self):
        """Verifica si HOY estamos dentro de las fechas calendario."""
        hoy = timezone.now().date()
        if not self.fecha_inicio or not self.fecha_fin:
            return False
        return self.fecha_inicio <= hoy <= self.fecha_fin



# ==============================================================================
# PASO 0.3: CEREBRO INSTITUCIONAL (PEI)
# ==============================================================================

class PEIResumen(models.Model):
    """
    Almacena el Proyecto Educativo Institucional (PEI) procesado.
    
    ESTRATEGIA DE AHORRO DE TOKENS:
    En lugar de enviar documentos crudos (PDF/Docx) al LLM, enviamos este JSON.
    El 'ContextBuilder' seleccionará solo las llaves necesarias para cada prompt.
    
    Ahorro estimado: 80% de tokens de entrada por consulta.
    """
    
    version = models.CharField(
        max_length=50, 
        unique=True, 
        help_text="Ej: v2025.1 - Actualización Manual Convivencia"
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    activo = models.BooleanField(
        default=True, 
        help_text="Solo una versión del PEI es la 'Verdad Absoluta' a la vez."
    )
    
    # El Corazón del sistema:
    contenido_estructurado = models.JSONField(
        default=dict,
        help_text="JSON estructurado con Misión, Visión, Ejes, Evaluación y Convivencia."
    )
    
    comentarios_cambio = models.TextField(
        blank=True, 
        help_text="Justificación de los cambios en esta versión (Auditoría)."
    )

    class Meta:
        verbose_name = "Conocimiento PEI (JSON)"
        verbose_name_plural = "Versiones del PEI"
        ordering = ['-fecha_creacion']

    def __str__(self):
        estado = "🟢 VIGENTE" if self.activo else "archivado"
        return f"PEI {self.version} [{estado}]"

    def save(self, *args, **kwargs):
        """
        Gobernanza de Datos:
        Asegura que solo exista una versión del PEI activa para evitar
        esquizofrenia institucional en las respuestas de la IA.
        """
        if self.activo:
            PEIResumen.objects.filter(activo=True).exclude(pk=self.pk).update(activo=False)
        super().save(*args, **kwargs)

    @property
    def resumen_hash(self):
        """
        Genera una firma rápida para el sistema de Caching (Fase 3).
        Si el PEI cambia, el caché debe invalidarse automáticamente.
        """
        return f"{self.version}-{self.fecha_creacion.timestamp()}"

class AIUsageLog(models.Model):
    """
    Registro forense inmutable de toda interacción con la IA.
    
    OBJETIVOS:
    1. Control de costos (Tokens exactos).
    2. Seguridad (Detectar abuso de usuarios).
    3. Depuración (Registro de errores de API).
    4. Auditoría (Cumplimiento pedagógico).
    """

    # 1. ¿QUIÉN Y CUÁNDO?
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, # Si se borra el usuario, el log queda (auditoría)
        null=True,
        related_name='ai_logs'
    )
    
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    
    periodo = models.ForeignKey(
        'PeriodoAcademico',
        on_delete=models.PROTECT, # 🔒 SEGURIDAD: No se puede borrar un periodo si ya se gastó dinero en él.
        null=True,
        help_text="Periodo académico activo durante la consulta."
    )

    # 2. ¿BAJO QUÉ REGLAS?
    rol_usado = models.CharField(
        max_length=50,
        choices=[(r, r) for r in ROLES_IA_PERMITIDOS],
        help_text="El rol con el que el usuario firmó la petición (Docente, Estudiante, etc)."
    )
    
    accion = models.CharField(
        max_length=50,
        choices=[(a, a) for a in ACCIONES_IA_PERMITIDAS],
        help_text="La intención pedagógica (Intents)."
    )

    # 3. ¿CUÁNTO COSTÓ? (LA FACTURA)
    modelo_utilizado = models.CharField(max_length=50, default=MODEL_NAME)
    
    tokens_entrada = models.IntegerField(default=0, help_text="Contexto + Prompt (Lo que enviamos)")
    tokens_salida = models.IntegerField(default=0, help_text="Respuesta generada (Lo que recibimos)")
    tiempo_ejecucion = models.FloatField(default=0.0, help_text="Segundos que tardó la respuesta")

    # 4. RESULTADO TÉCNICO
    exitoso = models.BooleanField(default=True)
    
    error_mensaje = models.TextField(
        blank=True, 
        null=True, 
        help_text="Si falló, aquí guardamos el stacktrace o mensaje de error de la API."
    )

    # 5. METADATA (NO GUARDAMOS EL PROMPT ENTERO POR PRIVACIDAD/ESPACIO)
    metadata_tecnica = models.JSONField(
        default=dict,
        blank=True,
        help_text="Datalles técnicos: pei_version, razon_fallo, intentos_restantes, costo_estimado_usd."
    )

    class Meta:
        verbose_name = "Log de Uso IA"
        verbose_name_plural = "Auditoría de IA"
        ordering = ['-fecha']
        # Índices compuestos para reportes rápidos de consumo en el Dashboard
        indexes = [
            models.Index(fields=['usuario', 'periodo']),
            models.Index(fields=['rol_usado', 'fecha']),
        ]

    def __str__(self):
        status = "✅" if self.exitoso else "❌"
        user_str = str(self.usuario) if self.usuario else "ANÓNIMO"
        return f"{status} {self.fecha.strftime('%Y-%m-%d %H:%M')} | {user_str} | {self.accion}"

    @property
    def costo_total_tokens(self):
        """Suma total para cálculo rápido de impacto."""
        return self.tokens_entrada + self.tokens_salida



class AIDocumento(models.Model):
    """
    Representa un documento oficial generado por la IA.
    A diferencia del Log (técnico), esto es visible para el usuario.
    
    Ejemplos: "Plan de Mejora 2025-1", "Reporte de Curso 6A".
    """
    
    TIPOS_DOC_CHOICES = (
        (DOC_REPORTE_PEDAGOGICO, 'Reporte Pedagógico Docente'),
        (DOC_ORIENTACION_ESTUDIANTE, 'Plan de Mejora Estudiantil'),
        (DOC_ORIENTACION_ACUDIENTE, 'Orientación Familiar'),
        (DOC_REPORTE_CONVIVENCIA, 'Reporte de Convivencia'),
        (DOC_REPORTE_INSTITUCIONAL, 'Análisis Institucional (PEI)'),
    )

    titulo = models.CharField(max_length=200, help_text="Ej: Plan de Mejora - Matemáticas")
    
    tipo = models.CharField(max_length=50, choices=TIPOS_DOC_CHOICES)
    
    # PROPIEDAD Y TRAZABILIDAD
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='documentos_ia',
        verbose_name="Propietario del Documento"
    )
    
    periodo = models.ForeignKey(
        PeriodoAcademico, 
        on_delete=models.PROTECT,
        verbose_name="Periodo Académico"
    )
    
    pei_version = models.ForeignKey(
        PEIResumen, 
        on_delete=models.SET_NULL, 
        null=True,
        help_text="Bajo qué versión del PEI se generó este documento."
    )
    
    # Enlace técnico (Opcional, pero recomendado para auditoría cruzada)
    log_origen = models.OneToOneField(
        AIUsageLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Enlace al log técnico que generó este documento."
    )

    # CONTENIDO
    contenido = models.TextField(help_text="Respuesta oficial de la IA en Markdown.")
    
    # EVIDENCIA (SNAPSHOT)
    contexto_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="""
        FOTO EXACTA de los datos usados (Notas, Observaciones) al momento de generar.
        Sirve como evidencia inmutable.
        """
    )

    # ESTADO
    creado_en = models.DateTimeField(auto_now_add=True)
    es_publico = models.BooleanField(
        default=True, 
        help_text="Si es True, acudientes o directores pueden verlo."
    )

    class Meta:
        verbose_name = "Documento IA Oficial"
        verbose_name_plural = "Documentos IA Oficiales"
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['usuario', 'tipo', 'periodo']),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.usuario} ({self.creado_en.strftime('%Y-%m-%d')})"

    def save(self, *args, **kwargs):
        # Generar título automático si no existe
        if not self.titulo:
            self.titulo = f"{self.get_tipo_display()} - {timezone.now().strftime('%d/%m/%Y')}"
        super().save(*args, **kwargs)