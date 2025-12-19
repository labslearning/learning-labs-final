# tasks/ai/context_builder.py

from django.db.models import Avg, Count
from django.contrib.auth.models import User
from tasks.models import (
    Nota, Observacion, PEIResumen, 
    Matricula, Asistencia, Periodo, Materia
)
from .constants import (
    ROL_ESTUDIANTE, 
    ACCION_MEJORAS_ESTUDIANTE, 
    ACCION_CHAT_SOCRATICO,
    ACCION_MEJORAS_DOCENTE, 
    ACCION_APOYO_ACUDIENTE,
    ACCION_MEJORA_STAFF_ACADEMICO,
    ACCION_ANALISIS_CONVIVENCIA,
    ACCION_CUMPLIMIENTO_PEI
)

class ContextBuilder:
    """
    EL DIGESTOR DE DATOS INSTITUCIONAL.
    Extrae la estructura de Materias, Notas, Convivencia y PEI.
    Capacidad multirrol: Individual (Laura) y Global (Colegio).
    Versión: Con Inyección de Estudiantes en Riesgo para Docentes.
    """

    def get_context(self, usuario, action_type=None, **kwargs):
        """
        Punto de entrada universal. 
        """
        target_user = kwargs.get('target_user', usuario)
        
        # 1. VALIDACIÓN DE PERFIL DEL SOLICITANTE
        try:
            perfil_solicitante = usuario.perfil
            rol_solicitante = str(perfil_solicitante.rol)
        except AttributeError:
            return {"error": "El usuario solicitante no tiene un perfil académico asociado."}

        # 2. CONSTRUCCIÓN DE CONTEXTO GLOBAL (ADMIN / STAFF)
        if action_type in [ACCION_CUMPLIMIENTO_PEI, ACCION_MEJORA_STAFF_ACADEMICO]:
            return {
                "tipo_analisis": "AUDITORIA_INSTITUCIONAL_GLOBAL",
                "solicitante": {
                    "username": str(usuario.username),
                    "rol": rol_solicitante
                },
                "pei_referencia": self._get_datos_pei(),
                "data_colegio_completo": self._get_contexto_institucional_global()
            }

        # 3. CONSTRUCCIÓN DE CONTEXTO INDIVIDUAL
        contexto = {
            "tipo_analisis": "DESEMPEÑO_INDIVIDUAL",
            "sujeto_analizado": {
                "nombre_completo": str(target_user.get_full_name() or target_user.username),
                "rol": str(target_user.perfil.rol) if hasattr(target_user, 'perfil') else "N/A",
                "curso_actual": str(self._get_grado_actual(target_user)),
                "identificador": str(target_user.username)
            },
            "pei_referencia": self._get_datos_pei(),
        }

        # --- LÓGICA DIFERENCIADA POR ROL ---
        rol_target = str(target_user.perfil.rol) if hasattr(target_user, 'perfil') else ""

        if rol_target == 'DOCENTE':
            # === ROL DOCENTE: LÓGICA PEDAGÓGICA Y ALERTAS DE RIESGO ===
            contexto["dimension_pedagogica"] = self._get_rendimiento_como_docente(target_user)
            contexto["enfoque_pedagogico"] = "Analizar promedios de cursos y sugerir estrategias didácticas."

            # [NUEVO] Inyectar lista de estudiantes reprobando para que el Chat sepa "A QUIÉN" ayudar
            # Buscamos notas menores a 3.5 en las materias de este profesor
            materias_profe = Materia.objects.filter(asignaciones__docente=target_user)
            notas_riesgo = Nota.objects.filter(
                materia__in=materias_profe,
                valor__lt=3.5
            ).select_related('estudiante', 'materia', 'materia__curso')

            if notas_riesgo.exists():
                lista_alertas = []
                # Limitamos a 20 registros para no desbordar el prompt
                for n in notas_riesgo[:20]:
                    nombre_est = n.estudiante.get_full_name() or n.estudiante.username
                    lista_alertas.append(
                        f"- Estudiante: {nombre_est} | "
                        f"Curso: {n.materia.curso.nombre} | "
                        f"Materia: {n.materia.nombre} | "
                        f"Nota: {n.valor}"
                    )
                contexto["alertas_estudiantes_riesgo"] = "\n".join(lista_alertas)
            else:
                contexto["alertas_estudiantes_riesgo"] = "No hay estudiantes con notas críticas (< 3.5) en sus cursos."

        else:
            # === ROL ESTUDIANTE: LÓGICA ACADÉMICA ===
            contexto["dimension_academica"] = self._get_rendimiento_integral(target_user)
            contexto["dimension_convivencial"] = self._get_resumen_convivencia(target_user)
            contexto["dimension_asistencia"] = self._get_resumen_asistencia(target_user)

            if action_type == ACCION_MEJORAS_DOCENTE:
                contexto["enfoque_pedagogico"] = "Sugerir estrategias de aula basadas en estos datos para el docente."
            elif action_type == ACCION_APOYO_ACUDIENTE:
                contexto["enfoque_familiar"] = "Traducir estos datos en acciones concretas para los padres en casa."
            elif action_type == ACCION_CHAT_SOCRATICO:
                contexto["enfoque_estudiante"] = "Modo Socrático: No dar respuestas, guiar con preguntas sobre estos datos."

        return contexto

    # --- MÉTODOS PARA ESTUDIANTES ---

    def _get_rendimiento_integral(self, usuario):
        """Mapa detallado de promedios."""
        notas = Nota.objects.filter(estudiante=usuario).select_related('materia', 'periodo')
        if not notas.exists(): return "Sin datos académicos registrados."

        reporte = {}
        for nota in notas:
            m_nombre = str(nota.materia.nombre)
            p_nombre = str(nota.periodo.nombre)
            
            if m_nombre not in reporte: reporte[m_nombre] = {}
            if p_nombre not in reporte[m_nombre]:
                notas_periodo = [n.valor for n in notas if n.materia_id == nota.materia_id and n.periodo_id == nota.periodo_id]
                avg_val = sum(notas_periodo) / len(notas_periodo) if notas_periodo else 0.0
                reporte[m_nombre][p_nombre] = {"promedio": round(float(avg_val), 2), "logros": []}
            
            if nota.descripcion:
                reporte[m_nombre][p_nombre]["logros"].append(str(nota.descripcion))
        return reporte

    def _get_resumen_convivencia(self, usuario):
        eventos = Observacion.objects.filter(estudiante=usuario).order_by('-fecha_creacion')[:5]
        if not eventos.exists(): return "Excelente conducta: Sin anotaciones."
        return [f"[{str(e.tipo)}] - {str(e.descripcion)}" for e in eventos]

    def _get_resumen_asistencia(self, usuario):
        fallas = Asistencia.objects.filter(estudiante=usuario, estado='FALLA').count()
        tardes = Asistencia.objects.filter(estudiante=usuario, estado='TARDE').count()
        return {"inasistencias_totales": int(fallas), "llegadas_tarde": int(tardes), "riesgo_desercion": "ALTO" if fallas > 5 else "BAJO"}
    
    # --- MÉTODOS PARA DOCENTES ---
    
    def _get_rendimiento_como_docente(self, docente):
        """
        Analiza las materias que dicta el profesor y el rendimiento de sus grupos.
        """
        materias = Materia.objects.filter(asignaciones__docente=docente).distinct()
        
        if not materias.exists():
            return "No tiene materias asignadas actualmente en el sistema."
            
        reporte_docente = []
        for mat in materias:
            notas_curso = Nota.objects.filter(materia=mat)
            promedio = notas_curso.aggregate(Avg('valor'))['valor__avg'] or 0.0
            reprobados = notas_curso.filter(valor__lt=3.0).count()
            total_notas = notas_curso.count()

            reporte_docente.append({
                "materia": str(mat.nombre),
                "curso": str(mat.curso), 
                "promedio_grupo": round(float(promedio), 2),
                "total_evaluaciones": total_notas,
                "estudiantes_reprobando": reprobados
            })
            
        return reporte_docente

    # --- MÉTODOS DE SOPORTE ---

    def _get_contexto_institucional_global(self):
        stats_materias = Nota.objects.values('materia__nombre').annotate(
            promedio_materia=Avg('valor'), volumen_notas=Count('id')
        ).order_by('promedio_materia')
        resumen_conducta = Observacion.objects.values('tipo').annotate(total_casos=Count('id')).order_by('-total_casos')
        
        return {
            "estadisticas_academicas": [{"materia": str(s['materia__nombre']), "promedio": round(float(s['promedio_materia']), 2)} for s in stats_materias],
            "estado_convivencia_global": [{"tipo_falta": str(a['tipo']), "conteo": int(a['total_casos'])} for a in resumen_conducta]
        }

    def _get_datos_pei(self):
        """
        Carga el ADN del colegio.
        """
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
            "valores_institucionales": ["Excelencia", "Respeto", "Innovación", "Solidaridad"],
            "nota": "Este es un PEI genérico por defecto (Base de datos sin PEI)."
        }

    def _get_grado_actual(self, usuario):
        """Identifica el curso y grado."""
        matricula = Matricula.objects.filter(estudiante=usuario, activo=True).select_related('curso').first()
        if matricula and matricula.curso:
            return f"{str(matricula.curso.nombre)} - Grado: {str(matricula.curso.get_grado_display())}"
        
        if hasattr(usuario, 'perfil') and usuario.perfil.rol == 'DOCENTE':
            cursos_profe = Materia.objects.filter(asignaciones__docente=usuario).values_list('curso__nombre', flat=True).distinct()
            if cursos_profe:
                return f"Docente en: {', '.join([str(c) for c in cursos_profe])}"
                
        return "Sin asignación académica vigente"

# Instancia única
context_builder = ContextBuilder()