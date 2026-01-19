# tasks/ai/context_builder.py

# Solo importamos Avg porque se usa en _get_rendimiento_como_docente
from django.db.models import Avg
from tasks.models import (
    Nota, Observacion, PEIResumen, 
    Matricula, Asistencia, Materia
)

# 👇 EL CEREBRO: Conectamos con el servicio que tiene la "verdad" del Dashboard
# (Las líneas que "faltan" aquí, ahora viven dentro de este Servicio)
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
    EL ORQUESTADOR DE CONTEXTO (Versión Enterprise).
    Ensambla la narrativa para la IA usando datos del Service Layer (Global)
    y consultas directas optimizadas (Individual).
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
            # 🔥 ARQUITECTURA LIMPIA:
            # Aquí es donde ahorramos líneas. En lugar de recalcular todo aquí (y hacerlo mal),
            # le pedimos los datos perfectos al Servicio Institucional.
            datos_radiografia = InteligenciaInstitucionalService.get_radiografia_completa()

            return {
                "scope": "GLOBAL_INSTITUCIONAL",
                "tipo_analisis": "RADIOGRAFIA_INSTITUCIONAL_360",
                "solicitante": {
                    "username": str(usuario.username),
                    "rol": rol_solicitante
                },
                "pei_referencia": self._get_datos_pei(),
                
                # 👇 MARCO LEGAL: Reglas del Manual de Convivencia
                "marco_legal_convivencia": self._get_reglas_manual(),
                
                # 👇 DATA: La verdad única del sistema
                "data_colegio_completo": datos_radiografia
            }

        # =========================================================
        # 4. CONTEXTO INDIVIDUAL (ESTUDIANTE / DOCENTE)
        # =========================================================
        # Esta parte NO se ha tocado, mantiene toda tu lógica original.
        
        contexto = {
            "scope": "INDIVIDUAL",
            "tipo_analisis": "DESEMPEÑO_INDIVIDUAL",
            "sujeto_analizado": {
                "nombre_completo": str(target_user.get_full_name() or target_user.username),
                "rol": str(target_user.perfil.rol) if hasattr(target_user, 'perfil') else "N/A",
                "curso_actual": str(self._get_grado_actual(target_user)),
                "identificador": str(target_user.username)
            },
            "pei_referencia": self._get_datos_pei(),
            "normativa_aplicable": self._get_reglas_manual(), 
        }

        # --- DETECCIÓN DEL ROL DEL SUJETO ---
        rol_target = str(target_user.perfil.rol) if hasattr(target_user, 'perfil') else ""

        # ROL DOCENTE
        if rol_target == 'DOCENTE':
            contexto["dimension_pedagogica"] = self._get_rendimiento_como_docente(target_user)
            contexto["enfoque_pedagogico"] = "Analizar promedios de cursos y sugerir estrategias didácticas."

            # ALERTAS DE ESTUDIANTES EN RIESGO (Consulta optimizada)
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
                        f"Nota: {float(n.valor)}"
                    )
                contexto["alertas_estudiantes_riesgo"] = lista_alertas
            else:
                contexto["alertas_estudiantes_riesgo"] = []

        # ROL ESTUDIANTE (O Admin analizando estudiante específico)
        else:
            contexto["dimension_academica"] = self._get_rendimiento_integral(target_user)
            contexto["dimension_convivencial"] = self._get_resumen_convivencia(target_user)
            contexto["dimension_asistencia"] = self._get_resumen_asistencia(target_user)

            if action_type == ACCION_MEJORAS_DOCENTE:
                contexto["enfoque_pedagogico"] = "Sugerir estrategias de aula basadas en estos datos para el docente."
            elif action_type == ACCION_APOYO_ACUDIENTE:
                contexto["enfoque_familiar"] = "Traducir estos datos en acciones concretas para los padres en casa."
            elif action_type == ACCION_CHAT_SOCRATICO:
                contexto["enfoque_estudiante"] = "Modo Socrático: Guiar con preguntas sobre estos datos."
            elif action_type == ACCION_MEJORAS_ESTUDIANTE:
                pass

        return contexto

    # =========================================================
    # MÉTODOS DE SOPORTE (MANUAL DE CONVIVENCIA)
    # =========================================================

    def _get_reglas_manual(self):
        """
        Retorna las reglas clave del Manual de Convivencia para contexto IA.
        """
        return {
            "enfoque_disciplinario": "Formativo y Restaurativo (No Punitivo).",
            "clasificacion_faltas": {
                "inasistencias_graves": "Acumular más de 3 fallas activa protocolo de riesgo de deserción.",
                "bajo_rendimiento": "Reprobar 3 o más materias requiere firma de compromiso académico y citación a acudientes.",
                "convivencia_critica": "Nota de convivencia < 3.5 se considera Alerta Naranja."
            },
            "protocolos_clave": [
                "Ruta de Atención Integral para casos de bullying.",
                "Debido Proceso: Todo estudiante debe ser escuchado antes de una sanción."
            ]
        }

    # =========================================================
    # MÉTODOS DE SOPORTE INDIVIDUALES (Lógica Original Preservada)
    # =========================================================
    
    def _get_rendimiento_integral(self, usuario):
        notas = Nota.objects.filter(estudiante=usuario).select_related('materia', 'periodo')
        if not notas.exists():
            return {}
        reporte = {}
        for nota in notas:
            m_nombre = str(nota.materia.nombre)
            p_nombre = str(nota.periodo.nombre)
            if m_nombre not in reporte: reporte[m_nombre] = {}
            if p_nombre not in reporte[m_nombre]:
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
        return {"inasistencias_totales": fallas, "llegadas_tarde": tardes, "riesgo_desercion": "ALTO" if fallas > 5 else "BAJO"}

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

    def _get_datos_pei(self):
        pei = PEIResumen.objects.filter(activo=True).first()
        if pei and pei.contenido_estructurado:
            data = pei.contenido_estructurado
            return {
                "mision": str(data.get("identidad", {}).get("mision", "N/A")),
                "modelo_pedagogico": str(data.get("modelo_pedagogico", {}).get("enfoque", "Constructivista")),
                "valores_institucionales": [str(v) for v in data.get("identidad", {}).get("valores", [])]
            }
        return {
            "mision": "Formar líderes integrales con pensamiento crítico y responsabilidad social.",
            "modelo_pedagogico": "Constructivismo Social y Aprendizaje Significativo.",
            "valores_institucionales": ["Excelencia", "Respeto", "Innovación", "Solidaridad"]
        }

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