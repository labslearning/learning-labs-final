from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
import os # <-- 🩺 CIRUGÍA: Importación añadida para la ruta del archivo

# Constantes para definir los grados y roles, centralizados para evitar duplicación.
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

# ROL 'ACUDIENTE' AÑADIDO
ROLES_CHOICES = (
    ('ESTUDIANTE', 'Estudiante'),
    ('DOCENTE', 'Docente'),
    ('ADMINISTRADOR', 'Administrador'),
    ('DIRECTOR_CURSO', 'Director de Curso'),
    ('ACUDIENTE', 'Acudiente'),
)


class Perfil(models.Model):
    """
    Extiende el modelo de usuario de Django para incluir roles y otra información.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    rol = models.CharField(max_length=20, choices=ROLES_CHOICES, default='ESTUDIANTE')
    es_director = models.BooleanField(default=False)
    requiere_cambio_clave = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.user.username} ({self.get_rol_display()})'

    class Meta:
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuario'


class Curso(models.Model):
    """
    Representa un curso o grado escolar (ej. 6° A).
    """
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
        # Corregido para manejar 'get_grado_display' que devuelve el nombre completo
        return f"{self.get_grado_display()} {self.seccion} - {self.anio_escolar}"

    def esta_completo(self):
        return self.matriculados.filter(activo=True).count() >= self.capacidad_maxima


# ===================================================================
# 1. AÑADIDO: MODELO 'INSTITUCION'
# ===================================================================
class Institucion(models.Model):
    """
    Almacena la información de la institución para los encabezados del boletín.
    """
    nombre = models.CharField(max_length=150)
    logo = models.ImageField(upload_to="logos_institucion/", null=True, blank=True)
    direccion = models.CharField(max_length=150)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    correo = models.EmailField(blank=True, null=True)
    nit = models.CharField(max_length=50, blank=True, null=True)
    ciudad = models.CharField(max_length=100, blank=True, null=True)
    departamento = models.CharField(max_length=100, blank=True, null=True)
    resolucion = models.CharField(max_length=200, blank=True, null=True)
    lema = models.CharField(max_length=200, blank=True, null=True)
    anio_lectivo = models.CharField(max_length=10, default="2025")

    class Meta:
        verbose_name = "Institución"
        verbose_name_plural = "Información Institucional"

    def __str__(self):
        return self.nombre
# ===================================================================
# FIN DEL MODELO 'INSTITUCION'
# ===================================================================


class Materia(models.Model):
    """
    Representa una materia académica (ej. Matemáticas).
    """
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
    """
    Representa un periodo académico dentro de un curso (ej. Primer Periodo).
    """
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


class Nota(models.Model):
    """
    Almacena la calificación de un estudiante para una actividad en una materia.
    """
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


# ===================================================================
# INICIO DE LA CORRECCIÓN
# ===================================================================
class ComentarioDocente(models.Model):
    """
    Permite a los docentes dejar comentarios para los estudiantes.
    """
    docente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comentarios_escritos')
    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comentarios_recibidos')
    materia = models.ForeignKey(Materia, on_delete=models.CASCADE, related_name='comentarios')
    comentario = models.TextField(verbose_name='Comentario')
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')
  
    # --- CAMPO AÑADIDO ---
    periodo = models.ForeignKey(Periodo, on_delete=models.CASCADE, null=True, blank=True)
    # --- FIN DEL CAMPO AÑADIDO ---

    class Meta:
        verbose_name = 'Comentario del Docente'
        verbose_name_plural = 'Comentarios de los Docentes'
        # --- RESTRICCIÓN MODIFICADA ---
        unique_together = ('docente', 'estudiante', 'materia', 'periodo')
        # --- FIN DE LA MODIFICACIÓN ---
        ordering = ['-fecha_creacion']

    def __str__(self):
        # --- MÉTODO __STR__ MODIFICADO ---
        if self.periodo:
            return f"Comentario de {self.docente.username} para {self.estudiante.username} en {self.materia.nombre} ({self.periodo.nombre})"
        return f"Comentario de {self.docente.username} para {self.estudiante.username} en {self.materia.nombre} (Sin periodo)"
# ===================================================================
# FIN DE LA CORRECCIÓN
# ===================================================================


class Matricula(models.Model):
    """
    Asocia a un estudiante con un curso para un año escolar específico.
    """
    estudiante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='matriculas')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='matriculados')
    anio_escolar = models.CharField(max_length=9, default='2025-2026', verbose_name='Año Escolar')
    fecha_matricula = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Matrícula')
    activo = models.BooleanField(default=True)

    # ===================================================================
    # 2. AÑADIDO: CAMPO 'puede_generar_boletin'
    # ===================================================================
    puede_generar_boletin = models.BooleanField(
        default=True,
        verbose_name="Acudiente puede generar boletín",
        help_text="Si está desactivado, el acudiente no podrá generar boletín desde su panel."
    )
    # ===================================================================
    # FIN DEL CAMPO AÑADIDO
    # ===================================================================

    class Meta:
        unique_together = ['estudiante', 'anio_escolar']
        verbose_name = 'Matrícula'
        verbose_name_plural = 'Matrículas'

    def __str__(self):
        return f"{self.estudiante.username} - {self.curso.nombre} ({self.anio_escolar})"


class Acudiente(models.Model):
    """
    Define el vínculo entre un usuario Acudiente y un usuario Estudiante.
    """
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


class AsignacionMateria(models.Model):
    """
    Asigna un docente a una materia dentro de un curso específico.
    """
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


class ActividadSemanal(models.Model):
    """
    Representa una actividad semanal publicada por un docente para un curso y materia.
    """
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


class LogroPeriodo(models.Model):
    """
    Almacena los logros académicos de un periodo específico para un curso.
    """
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


# --- Modelos de foro y chat ---
class Question(models.Model):
    """
    Modelo para una pregunta en el foro.
    """
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
    """
    Modelo para una respuesta a una pregunta del foro.
    """
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
    """
    Modelo para una sala de chat.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name='Nombre')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Sala de Chat'
        verbose_name_plural = 'Salas de Chat'


class ActiveUser(models.Model):
    """
    Modelo para rastrear a los usuarios activos en una sala de chat.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name='Usuario')
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, null=True, verbose_name='Sala de Chat')
    last_activity = models.DateTimeField(auto_now=True, verbose_name='Última Actividad')

    class Meta:
        unique_together = ('user', 'room')
        verbose_name = 'Usuario Activo'
        verbose_name_plural = 'Usuarios Activos'

    def __str__(self):
        return f'{self.user.username} en {self.room.name}'


class Convivencia(models.Model):
    """
    Modelo para almacenar la nota de convivencia de un estudiante por periodo.
    """
    estudiante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='convivencias'
    )
    curso = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='convivencias_curso'
    )
    periodo = models.ForeignKey(
        Periodo,
        on_delete=models.CASCADE,
        related_name='convivencias_periodo'
    )
    valor = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        help_text="Valor de la nota de 0.0 a 5.0"
    )
    comentario = models.TextField(
        blank=True,
        null=True,
        help_text="Comentario opcional del director de curso"
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='convivencias_registradas'
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('estudiante', 'curso', 'periodo')
        verbose_name = "Nota de Convivencia"
        verbose_name_plural = "Notas de Convivencia"
        ordering = ['-periodo', 'estudiante']

    def __str__(self):
        return f"Convivencia de {self.estudiante.username} en {self.curso.nombre} ({self.periodo.nombre})"


# ===================================================================
# 🩺 INICIO DE CIRUGÍA: PASO 1 (Añadido al final)
# ===================================================================

def ruta_archivo_boletin(instance, filename):
    """
    Genera una ruta de archivo organizada para los boletines archivados:
    media/boletines_archivados/AÑO_LECTIVO/GRADO/archivo.pdf
    """
    # Normaliza el nombre del grado para usarlo en la ruta
    grado_folder = instance.grado_archivado.replace(' ', '_').lower()
    anio_folder = instance.anio_lectivo_archivado.replace('-', '_')
    
    # Limpia el nombre de usuario para que sea seguro
    username_limpio = "".join(c for c in instance.username_estudiante if c.isalnum() or c in ('-', '_')).rstrip()
    
    # Asegura un nombre de archivo único
    filename = f"boletin_{username_limpio}_{anio_folder}.pdf"
    
    return os.path.join('boletines_archivados', anio_folder, grado_folder, filename)

class BoletinArchivado(models.Model):
    """
    Almacena el PDF de un boletín generado en el momento en que
    un estudiante es "retirado" (Soft Delete).
    Guarda una copia por cada año que el estudiante cursó.
    """
    # Datos para búsqueda y filtrado
    nombre_estudiante = models.CharField(
        max_length=255, 
        db_index=True, 
        help_text="Nombre completo del estudiante al momento del retiro."
    )
    username_estudiante = models.CharField(
        max_length=150, 
        db_index=True, 
        help_text="Username (documento) del estudiante para referencia."
    )
    grado_archivado = models.CharField(
        max_length=20, 
        choices=GRADOS_CHOICES, 
        db_index=True,
        help_text="El grado que cursaba el estudiante en este boletín."
    )
    seccion_archivada = models.CharField(
        max_length=100, 
        help_text="La sección (ej. 'A') que cursaba."
    )
    anio_lectivo_archivado = models.CharField(
        max_length=9, 
        db_index=True, 
        help_text="El año escolar de este boletín (ej. '2024-2025')."
    )
    
    # Datos de auditoría
    fecha_eliminado = models.DateTimeField(
        auto_now_add=True,
        help_text="Fecha y hora en que se generó este archivo (retiro)."
    )
    eliminado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='boletines_archivados_por_mi',
        help_text="Administrador que realizó el retiro."
    )
    
    # El archivo PDF
    archivo_pdf = models.FileField(
        upload_to=ruta_archivo_boletin,
        help_text="El archivo PDF del boletín."
    )

    class Meta:
        verbose_name = "Boletín Archivado (Exalumno)"
        verbose_name_plural = "Boletines Archivados (Exalumnos)"
        ordering = ['-anio_lectivo_archivado', 'grado_archivado', 'nombre_estudiante']
        # Asegura que no podamos archivar dos veces el boletín
        # del mismo estudiante para el mismo año.
        unique_together = ('username_estudiante', 'anio_lectivo_archivado')

    def __str__(self):
        return f"Boletín de {self.nombre_estudiante} ({self.anio_lectivo_archivado})"

# ===================================================================
# 🩺 FIN DE CIRUGÍA: PASO 1
# ===================================================================