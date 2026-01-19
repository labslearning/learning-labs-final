# tasks/ai/context_builder.py

# Importamos Avg porque se usa en la lógica de rendimiento docente (individual)
from django.db.models import Avg
# Importamos los modelos necesarios
from tasks.models import (
    Nota, Observacion, PEIResumen, 
    Matricula, Asistencia, Materia, Institucion
)

# 👇 CONECTAMOS EL CEREBRO DE DATOS (Arregla lo de Luciana y cuentas reales)
from tasks.services.institutional import InteligenciaInstitucionalService

from .constants import (
    ACCION_MEJORAS_ESTUDIANTE, 
    ACCION_CHAT_SOCRATICO,
    ACCION_MEJORAS_DOCENTE, 
    ACCION_APOYO_ACUDIENTE,
    ACCION_MEJORA_STAFF_ACADEMICO,
    ACCION_ANALISIS_CONVIVENCIA,
    ACCION_CUMPLIMIENTO_PEI,
    ACCION_ANALISIS_GLOBAL_BIENESTAR, 
    ACCION_RIESGO_ACADEMICO           
)

class ContextBuilder:
    """
    EL ORQUESTADOR DE CONTEXTO (Versión Definitiva con Marco Legal).
    Ensambla la narrativa para la IA usando datos del Service Layer (Global)
    y estructura el Manual de Convivencia como "Ley" para la IA.
    """

    def get_context(self, usuario, action_type=None, **kwargs):
        """
        Punto de entrada universal para generar contexto IA.
        """
        target_user = kwargs.get('target_user', usuario)

        # 1. VALIDACIÓN DEL USUARIO SOLICITANTE
        try:
            perfil_solicitante = usuario.perfil
            rol_solicitante = str(perfil_solicitante.rol)
        except AttributeError:
            rol_solicitante = "ADMINISTRADOR" 

        # =========================================================
        # 2. DEFINICIÓN DE ACCIONES GLOBALES
        # =========================================================
        ACCIONES_GLOBALES = [
            ACCION_CUMPLIMIENTO_PEI,
            ACCION_MEJORA_STAFF_ACADEMICO,
            ACCION_ANALISIS_CONVIVENCIA,
            ACCION_ANALISIS_GLOBAL_BIENESTAR,
            ACCION_RIESGO_ACADEMICO
        ]

        # =========================================================
        # 3. CONTEXTO INSTITUCIONAL GLOBAL (COLEGIO COMPLETO)
        # =========================================================
        if action_type in ACCIONES_GLOBALES:
            # 🔥 PASO 1: Obtener la verdad matemática (arregla promedios)
            datos_radiografia = InteligenciaInstitucionalService.get_radiografia_completa()

            return {
                "scope": "GLOBAL_INSTITUCIONAL",
                "tipo_analisis": "RADIOGRAFIA_INSTITUCIONAL_360",
                "solicitante": {
                    "username": str(usuario.username),
                    "rol": rol_solicitante
                },
                
                # 🔥 PASO 2: INSTRUCCIONES OBLIGATORIAS PARA LA IA
                # Esto obliga a la IA a leer el bloque "MARCO_LEGAL" antes de opinar.
                "DIRECTRICES_DE_AUDITORIA": {
                    "MANDATO_1": "Toda recomendación debe basarse en el 'MARCO_LEGAL_VIGENTE' suministrado.",
                    "MANDATO_2": "Citar explícitamente los Artículos del Manual o valores del PEI al proponer acciones.",
                    "EJEMPLO": "No digas 'mejorar nota', di 'Aplicar Artículo 25: Compromiso Académico'.",
                },

                # 🔥 PASO 3: EL MANUAL Y PEI ESTRUCTURADOS
                "MARCO_LEGAL_VIGENTE": {
                    "PEI_INSTITUCIONAL": self._get_datos_pei(),
                    "MANUAL_DE_CONVIVENCIA": self._get_reglas_manual_estructuradas() # <--- AQUÍ ESTÁ LA MAGIA
                },
                
                # 🔥 PASO 4: DATOS REALES
                "EVIDENCIA_ESTADISTICA": datos_radiografia
            }

        # =========================================================
        # 4. CONTEXTO INDIVIDUAL (ESTUDIANTE / DOCENTE)
        # =========================================================
        
        contexto = {
            "scope": "INDIVIDUAL",
            "tipo_analisis": "DESEMPEÑO_INDIVIDUAL",
            "sujeto_analizado": {
                "nombre_completo": str(target_user.get_full_name() or target_user.username),
                "rol": str(target_user.perfil.rol) if hasattr(target_user, 'perfil') else "N/A",
                "curso_actual": str(self._get_grado_actual(target_user)),
                "identificador": str(target_user.username)
            },
            "MARCO_LEGAL_APLICABLE": self._get_reglas_manual_estructuradas(), # También para individual
            "PEI_REFERENCIA": self._get_datos_pei(),
        }

        # --- DETECCIÓN DEL ROL DEL SUJETO ---
        rol_target = str(target_user.perfil.rol) if hasattr(target_user, 'perfil') else ""

        # A. ROL DOCENTE
        if rol_target == 'DOCENTE':
            contexto["dimension_pedagogica"] = self._get_rendimiento_como_docente(target_user)
            contexto["enfoque_pedagogico"] = "Analizar promedios de cursos y sugerir estrategias didácticas basadas en el PEI."

            # ALERTAS DE ESTUDIANTES EN RIESGO (Consulta Optimizada)
            materias_profe = Materia.objects.filter(asignaciones__docente=target_user)
            notas_riesgo = Nota.objects.filter(
                materia__in=materias_profe,
                valor__lt=3.5
            ).select_related('estudiante', 'materia', 'materia__curso')

            if notas_riesgo.exists():
                lista_alertas = []
                for n in notas_riesgo[:20]:
                    nombre_est = n.estudiante.get_full_name() or n.estudiante.username
                    lista_alertas.append(
                        f"- Estudiante: {nombre_est} | "
                        f"Curso: {n.materia.curso.nombre} | "
                        f"Materia: {n.materia.nombre} | "
                        f"Nota Actual: {float(n.valor)}"
                    )
                contexto["alertas_estudiantes_riesgo"] = lista_alertas
            else:
                contexto["alertas_estudiantes_riesgo"] = []

        # B. ROL ESTUDIANTE (O Admin analizando estudiante)
        else:
            contexto["dimension_academica"] = self._get_rendimiento_integral(target_user)
            contexto["dimension_convivencial"] = self._get_resumen_convivencia(target_user)
            contexto["dimension_asistencia"] = self._get_resumen_asistencia(target_user)

            if action_type == ACCION_MEJORAS_DOCENTE:
                contexto["objetivo"] = "Sugerir estrategias de aula para este estudiante."
            elif action_type == ACCION_APOYO_ACUDIENTE:
                contexto["objetivo"] = "Traducir estos datos en pautas de crianza y apoyo en casa."
            elif action_type == ACCION_CHAT_SOCRATICO:
                contexto["objetivo"] = "Guiar al estudiante mediante mayéutica para que reconozca sus fallas."
            elif action_type == ACCION_MEJORAS_ESTUDIANTE:
                pass 

        return contexto

    # =========================================================
    # 📜 MÉTODOS DE SOPORTE: MARCO LEGAL (MANUAL Y PEI)
    # =========================================================

    # =========================================================
    # 📜 MÉTODOS DE SOPORTE: MARCO LEGAL (MANUAL REAL)
    # =========================================================

    def _get_reglas_manual_estructuradas(self):
        """
        Retorna las reglas EXACTAS del Manual de Convivencia 'Colegio Virtual Nueva Esperanza'.
        Esto obliga a la IA a citar los numerales correctos (6.1, 7.1, etc.).
        """
        return {
            "IDENTIDAD_INSTITUCIONAL": {
                "NOMBRE": "Colegio Virtual Nueva Esperanza",
                "MODALIDAD": "100% Virtual",
                "PRINCIPIOS_Y_VALORES": "Respeto, responsabilidad, ética digital, autonomía, inclusión, pensamiento crítico."
            },
            "REGIMEN_ASISTENCIA_PUNTUALIDAD": {
                "NUMERAL_6_1_LLEGADAS_TARDE": "Más de 3 veces: Llamado de atención pedagógico. 4ta vez: Citación a acudiente y compromiso. Persistencia: Reporte a Comité.",
                "NUMERAL_6_2_INASISTENCIAS": "Más de 3 injustificadas: Registro automático, comunicación con acudiente y plan de recuperación obligatorio. Reincidencia: Falta Grave."
            },
            "REGIMEN_ACADEMICO": {
                "NUMERAL_7_1_PERDIDA_MATERIAS": "Pérdida de más de 3 materias: Activación inmediata de Plan de Mejoramiento Integral (PMI), tutorías obligatorias y citación formal a padres. Evalúa Consejo Académico.",
                "CONSECUENCIA_GRAVE": "La pérdida reiterada de áreas podrá implicar no promoción del grado."
            },
            "FALTAS_DISCIPLINARIAS": {
                "NUMERAL_8_CLASIFICACION": "Leves, Graves y Gravísimas. Incluye fraude, plagio, ciberacoso y uso indebido de IA.",
                "NUMERAL_12_USO_IA": "Permitida como apoyo. Uso para fraude o suplantación es FALTA GRAVE."
            },
            "DEBIDO_PROCESO": {
                "NUMERAL_10_GARANTIAS": "Defensa, contradicción, proporcionalidad, presunción de inocencia."
            }
        }

    def _get_datos_pei(self):
        """
        Extrae la esencia del PEI para alinear la cultura institucional.
        """
        pei = PEIResumen.objects.filter(activo=True).first()
        
        datos_base = {
            "IDENTIDAD": {
                "MISION": "Formar líderes integrales con pensamiento crítico y responsabilidad social.",
                "VISION": "Ser referente en innovación educativa y formación humanista.",
                "VALORES": ["Excelencia", "Respeto", "Innovación", "Solidaridad"]
            },
            "MODELO_PEDAGOGICO": {
                "ENFOQUE": "Constructivismo Social y Aprendizaje Significativo.",
                "METODOLOGIA": "Aprendizaje Basado en Proyectos (ABP) y Evaluación Formativa."
            }
        }

        # Si hay datos extraídos del PDF en la base de datos, los usamos
        if pei and pei.contenido_estructurado:
            data = pei.contenido_estructurado
            datos_base["IDENTIDAD"]["MISION"] = str(data.get("identidad", {}).get("mision", datos_base["IDENTIDAD"]["MISION"]))
            datos_base["MODELO_PEDAGOGICO"]["ENFOQUE"] = str(data.get("modelo_pedagogico", {}).get("enfoque", datos_base["MODELO_PEDAGOGICO"]["ENFOQUE"]))
            val = data.get("identidad", {}).get("valores", [])
            if val: datos_base["IDENTIDAD"]["VALORES"] = [str(v) for v in val]

        return datos_base

    # =========================================================
    # 📊 MÉTODOS DE SOPORTE: CONSULTAS INDIVIDUALES
    # =========================================================
    
    def _get_rendimiento_integral(self, usuario):
        notas = Nota.objects.filter(estudiante=usuario).select_related('materia', 'periodo')
        if not notas.exists(): return {}
        reporte = {}
        for nota in notas:
            m_nombre = str(nota.materia.nombre)
            p_nombre = str(nota.periodo.nombre)
            if m_nombre not in reporte: reporte[m_nombre] = {}
            if p_nombre not in reporte[m_nombre]:
                # Calculamos promedio real del periodo para esa materia
                notas_periodo = [float(n.valor) for n in notas if n.materia_id == nota.materia_id and n.periodo_id == nota.periodo_id]
                promedio = sum(notas_periodo) / len(notas_periodo) if notas_periodo else 0
                reporte[m_nombre][p_nombre] = {"promedio": round(promedio, 2), "logros": []}
            if nota.descripcion:
                reporte[m_nombre][p_nombre]["logros"].append(str(nota.descripcion))
        return reporte

    def _get_resumen_convivencia(self, usuario):
        eventos = Observacion.objects.filter(estudiante=usuario).order_by('-fecha_creacion')[:5]
        return [{"tipo": str(e.tipo), "descripcion": str(e.descripcion), "fecha": str(e.fecha_creacion)} for e in eventos]

    def _get_resumen_asistencia(self, usuario):
        fallas = Asistencia.objects.filter(estudiante=usuario, estado='FALLA').count()
        tardes = Asistencia.objects.filter(estudiante=usuario, estado='TARDE').count()
        return {"inasistencias_totales": fallas, "llegadas_tarde": tardes, "riesgo_desercion": "ALTO" if fallas > 3 else "BAJO"} # Ajustado a 3 según Artículo 25

    def _get_rendimiento_como_docente(self, docente):
        materias = Materia.objects.filter(asignaciones__docente=docente).distinct()
        if not materias.exists(): return []
        reporte = []
        for mat in materias:
            notas_curso = Nota.objects.filter(materia=mat)
            promedio = notas_curso.aggregate(Avg('valor'))['valor__avg'] or 0
            reprobados = notas_curso.filter(valor__lt=3.0).count()
            reporte.append({
                "materia": str(mat.nombre),
                "curso": str(mat.curso),
                "promedio_grupo": round(promedio, 2),
                "total_evaluaciones": notas_curso.count(),
                "estudiantes_reprobando": reprobados
            })
        return reporte

    def _get_grado_actual(self, usuario):
        matricula = Matricula.objects.filter(estudiante=usuario, activo=True).select_related('curso').first()
        if matricula and matricula.curso:
            return f"{matricula.curso.nombre} - Grado: {matricula.curso.get_grado_display()}"
        if hasattr(usuario, 'perfil') and usuario.perfil.rol == 'DOCENTE':
            cursos = Materia.objects.filter(asignaciones__docente=usuario).values_list('curso__nombre', flat=True).distinct()
            if cursos: return f"Docente en: {', '.join(cursos)}"
        return "Sin asignación académica vigente"

# Instancia única
context_builder = ContextBuilder()