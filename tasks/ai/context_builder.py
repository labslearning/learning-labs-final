# tasks/ai/context_builder.py

# Importamos Avg para cálculos de rendimiento
from django.db.models import Avg
# Importamos modelos necesarios
from tasks.models import (
    Nota, Observacion, PEIResumen, 
    Matricula, Asistencia, Materia, Institucion
)

# 👇 CONECTAMOS EL CEREBRO DE DATOS (Servicio de Inteligencia Institucional)
# Asegúrate de que tasks/services/__init__.py exista y exporte InteligenciaInstitucionalService
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
    EL ORQUESTADOR DE CONTEXTO (Versión Auditoría ISO 21001 - Optimizado).
    Estructura la información para máxima densidad y cumplimiento normativo.
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
        # 🔥 CORRECCIÓN: Quitamos ACCION_RIESGO_ACADEMICO de aquí para que no sea global
        ACCIONES_GLOBALES = [
            ACCION_CUMPLIMIENTO_PEI,
            ACCION_MEJORA_STAFF_ACADEMICO,
            ACCION_ANALISIS_CONVIVENCIA,
            ACCION_ANALISIS_GLOBAL_BIENESTAR
        ]

        # =========================================================
        # 3. CONTEXTO INSTITUCIONAL GLOBAL (COLEGIO COMPLETO)
        # =========================================================
        if action_type in ACCIONES_GLOBALES:
            # 🔥 PASO 1: Obtener la evidencia objetiva (Datos Reales)
            datos_radiografia = InteligenciaInstitucionalService.get_radiografia_completa()

            return {
                "scope": "GLOBAL_INSTITUCIONAL",
                "tipo_analisis": "AUDITORIA_CALIDAD_EDUCATIVA_ISO_21001",
                "solicitante": {
                    "username": str(usuario.username),
                    "rol": rol_solicitante
                },
                
                # 🔥 PASO 2: PROTOCOLO DE AUDITORÍA (OPTIMIZADO PARA EVITAR CORTES)
                "PROTOCOLO_DE_AUDITORIA_ISO_21001": {
                    "ROL_IA": "Auditor Líder ISO 21001.",
                    "OBJETIVO": "Dictamen de conformidad normativa (PEI/Manual) vs Realidad.",
                    
                    # 👇 ESTA SECCIÓN AYUDA A EVITAR CORTES DE RESPUESTA
                    "ESTRATEGIA_DE_RESPUESTA": [
                        "1. DENSIDAD ALTA: Usar lenguaje técnico y directo. Evitar introducciones o saludos largos.",
                        "2. FORMATO: Priorizar listas (bullets) y tablas Markdown para ahorrar tokens.",
                        "3. INTEGRIDAD: Si el espacio es limitado, priorizar las 'ACCIONES CORRECTIVAS' sobre el análisis descriptivo.",
                        "4. EVIDENCIA: Cada afirmación debe citar el Numeral Legal (Manual) o Componente (PEI)."
                    ],

                    "REQUISITOS_ISO_21001": [
                        "Clasificar hallazgos: 'No Conformidad Mayor' (Riesgo Crítico) o 'Oportunidad de Mejora'.",
                        "Calcular '% de Alineación Normativa' estimado.",
                        "Enfoque basado en riesgos (Deserción/Repitencia)."
                    ],

                    "MATRIZ_DE_DECISION_LEGAL": {
                        "CASO_CRITICO": "3+ materias perdidas o 3+ fallas = Activar Rutas de Permanencia (Numerales 7.1 y 6.2).",
                        "CASO_ALERTA": "1-2 materias perdidas = Plan de Mejoramiento (Numeral 7.1).",
                        "CONVIVENCIA": "Nota < 3.5 = Remisión a Orientación (Numeral 6.1)."
                    }
                },

                # 🔥 PASO 3: CRITERIOS DE AUDITORÍA (MANUAL Y PEI)
                "CRITERIOS_DE_AUDITORIA_VIGENTES": {
                    "PEI_INSTITUCIONAL": self._get_pei_estructurado(),
                    "MANUAL_DE_CONVIVENCIA": self._get_reglas_manual_estructuradas()
                },
                
                # 🔥 PASO 4: EVIDENCIA OBJETIVA (DATOS)
                "EVIDENCIA_OBJETIVA_DATOS": datos_radiografia
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
            "MARCO_LEGAL_APLICABLE": {
                "PEI": self._get_pei_estructurado(),
                "MANUAL": self._get_reglas_manual_estructuradas()
            },
            "PEI_REFERENCIA": self._get_datos_pei(), 
        }

        # --- DETECCIÓN DEL ROL DEL SUJETO ---
        rol_target = str(target_user.perfil.rol) if hasattr(target_user, 'perfil') else ""

        # A. ROL DOCENTE
        if rol_target == 'DOCENTE':
            contexto["dimension_pedagogica"] = self._get_rendimiento_como_docente(target_user)
            contexto["enfoque_pedagogico"] = "Analizar eficacia docente según Modelo Socio-Constructivista."

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

            # 👇 AQUÍ ESTÁ EL ARREGLO: Manejo individual de la acción de Riesgo Académico
            if action_type == ACCION_RIESGO_ACADEMICO:
                nombre_target = str(target_user.get_full_name() or target_user.username)
                contexto["INSTRUCCIONES_ESTRICTAS_IA"] = {
                    "ROL_ASIGNADO": "Consejero Académico y Orientador Vocacional (Director de Grupo).",
                    "OBJETIVO": f"Analizar las causas raíz del bajo rendimiento de {nombre_target} y proponer un plan de rescate.",
                    "ESTRUCTURA_RESPUESTA": [
                        "1. 🚨 DIAGNÓSTICO DE RIESGO: Identifica las materias críticas (<3.0) y calcula si está en peligro de perder el año (según Numeral 7.1 del Manual).",
                        "2. 🔍 ANÁLISIS DE CAUSAS: Cruza las notas con la asistencia. ¿Pierde por fallas o por dificultad académica?",
                        "3. 🤝 ESTRATEGIA DE INTERVENCIÓN: Redacta 3 compromisos concretos (Académico, Disciplinario y Familiar).",
                        "4. 📅 PLAN DE ACCIÓN INMEDIATO: Sugiere acciones para la próxima semana (Ej: 'Solicitar refuerzo en Matemáticas')."
                    ]
                }

            elif action_type == ACCION_MEJORAS_ESTUDIANTE:
                # 🔥 INSTRUCCIONES ESTRICTAS PARA EVITAR HORARIOS Y DAR ANÁLISIS DE DATOS
                contexto["INSTRUCCIONES_ESTRICTAS_IA"] = {
                    "PROHIBICION_ABSOLUTA": "⛔ ESTÁ PROHIBIDO GENERAR HORARIOS, CALENDARIOS O RUTINAS POR HORAS (Ej: 'Lunes 8:00 AM...'). NO LO HAGAS.",
                    "ROL_ASIGNADO": "Analista de Datos Educativos y Estratega Pedagógico.",
                    "OBJETIVO": "Realizar una autopsia de los datos académicos y generar un plan de choque basado en evidencias estadísticas.",
                    "ESTRUCTURA_DE_RESPUESTA_OBLIGATORIA": [
                        "1. 📊 DIAGNÓSTICO ESTADÍSTICO: Analiza si las notas están subiendo o bajando entre periodos. Cruza esto con las fallas de asistencia.",
                        "2. 🛡️ ANÁLISIS DE FORTALEZAS: Identifica las materias con notas altas (>4.0) y explica qué habilidades demuestran (ej: Lógica, Creatividad, Memoria).",
                        "3. ⚠️ ANÁLISIS DE BRECHAS (DEBILIDADES): Identifica las materias perdidas (<3.0). Explica POR QUÉ están fallando basándote en los datos (¿Es por inasistencia? ¿Es dificultad conceptual?).",
                        "4. 🛠️ ESTRATEGIA DE COBERTURA: Para cada debilidad, propón una TÉCNICA DE ESTUDIO concreta (Ej: 'Mapas Mentales' o 'Feynman'). NO digas 'estudia más'.",
                        "5. 🤖 HERRAMIENTA CLAVE (OBLIGATORIO): Recomienda explícitamente utilizar el 'Tutor Socrático' (disponible en el menú Learning Labs) para practicar preguntas difíciles y resolver dudas sin recibir la respuesta directa.",
                        "6. 🚀 PLAN DE MEJORA: Define 3 metas medibles para el próximo periodo (Ej: 'Subir promedio de Matemáticas a 3.5')."
                    ]
                }
            elif action_type == ACCION_APOYO_ACUDIENTE:
                contexto["objetivo"] = "Traducir hallazgos en pautas de acompañamiento familiar."
            elif action_type == ACCION_CHAT_SOCRATICO:
                contexto["objetivo"] = "Facilitar la autorreflexión del estudiante."

        return contexto

    # =========================================================
    # 📜 MÉTODOS DE SOPORTE: MARCO LEGAL (MANUAL REAL)
    # =========================================================

    def _get_reglas_manual_estructuradas(self):
        """
        Retorna las reglas EXACTAS del Manual de Convivencia 'Colegio Virtual Nueva Esperanza'.
        Esta es la "Norma de Referencia" para la auditoría.
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

    # =========================================================
    # 🏫 MÉTODOS DE SOPORTE: PEI ESTRUCTURADO (MODO "LEY")
    # =========================================================

    def _get_pei_estructurado(self):
        """
        Retorna los pilares del PEI del 'Colegio Virtual Nueva Esperanza'.
        Estructura basada en ISO 21001: Misión, Visión y Objetivos.
        """
        # Estructura BASE fija (esto siempre funcionará)
        datos_pei = {
            "IDENTIDAD_INSTITUCIONAL": {
                "NOMBRE": "Colegio Virtual Nueva Esperanza",
                "MODELO_ATENCION": "Aprendizaje remoto, sincrónico y asincrónico (Plataforma LMS).",
                "ALCANCE": "Nacional (Calendario A)."
            },
            "COMPONENTE_TELEOLOGICO": {
                "MISION": "Brindar educación de calidad mediante ambientes virtuales innovadores que promuevan autonomía, pensamiento crítico, alfabetización digital y competencias ciudadanas.",
                "VISION_2032": "Ser reconocidos como el mejor colegio virtual de Colombia, referente en personalización, inclusión digital y uso avanzado de IA educativa.",
                "PRINCIPIOS_Y_VALORES": ["Respeto y ciudadanía digital", "Ética de la información", "Pensamiento crítico", "Autonomía", "Responsabilidad tecnológica"]
            },
            "MODELO_PEDAGOGICO_VIRTUAL": {
                "INSPIRACION": "Constructivismo y Conectivismo.",
                "METODOLOGIAS_ACTIVAS": [
                    "Aprendizaje Basado en Proyectos (ABP) en entornos virtuales",
                    "Flipped Classroom (Aula invertida)",
                    "Microlearning y Gamificación",
                    "Integración de IA para retroalimentación"
                ],
                "ROL_DOCENTE": "Mediador digital, tutor virtual y diseñador de experiencias."
            },
            "PLAN_DE_ESTUDIOS_VIRTUAL": {
                "ENFOQUE": "Módulos digitales interactivos, sesiones en vivo y actividades asincrónicas.",
                "AREAS_CLAVE": ["Tecnología e Informática (Alta intensidad)", "Ciencias", "Humanidades", "Emprendimiento Digital"],
                "HERRAMIENTAS": "Analíticas de aprendizaje, laboratorios virtuales y rutas personalizadas."
            },
            "INCLUSION_Y_DIVERSIDAD": {
                "ESTRATEGIA": "Adaptaciones curriculares digitales, lectores de pantalla y tutoría personal en línea.",
                "ENFOQUE": "Educación diferencial en línea para estudiantes con diversas necesidades."
            },
            "PROYECTOS_TRANSVERSALES": [
                "Ciudadanía y Democracia Digital",
                "Bienestar Emocional Online",
                "Emprendimiento Digital",
                "STEAM"
            ]
        }

        # Intento de enriquecer con datos de BD (si existen), protegidos con try/except
        try:
            pei_db = PEIResumen.objects.filter(activo=True).first()
            if pei_db and pei_db.contenido_estructurado:
                data = pei_db.contenido_estructurado
                # Solo sobrescribimos si hay datos válidos, sino mantenemos la base fija
                mision_bd = data.get("identidad", {}).get("mision")
                if mision_bd:
                    datos_pei["COMPONENTE_TELEOLOGICO"]["MISION"] = str(mision_bd)
        except Exception:
            pass # Si falla la BD, usamos los datos fijos que definimos arriba

        return datos_pei

    # =========================================================
    # 📊 MÉTODOS DE SOPORTE: CONSULTAS INDIVIDUALES (LEGADO)
    # =========================================================
    
    def _get_datos_pei(self):
        """Método de soporte para compatibilidad con lógica individual existente"""
        pei_struct = self._get_pei_estructurado()
        return {
            "mision": pei_struct["COMPONENTE_TELEOLOGICO"]["MISION"],
            "modelo_pedagogico": pei_struct["MODELO_PEDAGOGICO_VIRTUAL"]["INSPIRACION"],
            "valores_institucionales": pei_struct["COMPONENTE_TELEOLOGICO"]["PRINCIPIOS_Y_VALORES"]
        }

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
        return {"inasistencias_totales": fallas, "llegadas_tarde": tardes, "riesgo_desercion": "ALTO" if fallas > 3 else "BAJO"} # Ajustado a 3 según Numeral 6.2

    def _get_rendimiento_como_docente(self, docente):
        """
        Calcula métricas de los cursos asignados al docente con validaciones de seguridad.
        """
        # 1. Buscamos materias donde el docente es titular
        materias = Materia.objects.filter(asignaciones__docente=docente).distinct()
        
        # Validación de seguridad: Si no tiene materias, retornamos mensaje en lugar de lista vacía muda
        if not materias.exists():
            return [{"mensaje": "No se encontraron asignaciones académicas activas para este periodo."}]

        reporte = []
        for mat in materias:
            notas_curso = Nota.objects.filter(materia=mat)
            
            # 2. Cálculo SEGURO del promedio (Evita el error 'NoneType' si no hay notas)
            agregados = notas_curso.aggregate(promedio=Avg('valor'))
            promedio_val = agregados['promedio']
            # Convertimos a float para evitar problemas de serialización JSON con Decimal
            promedio_final = float(promedio_val) if promedio_val is not None else 0.0
            
            # 3. Contamos estudiantes únicos (más preciso que contar notas)
            total_estudiantes = notas_curso.values('estudiante').distinct().count()
            
            # 4. Contamos reprobados reales (<3.0)
            reprobados = notas_curso.filter(valor__lt=3.0).values('estudiante').distinct().count()
            
            # 5. Cálculo de Tasa de Reprobación (Evita la división por Cero)
            if total_estudiantes > 0:
                tasa_reprobacion = (reprobados / total_estudiantes) * 100
            else:
                tasa_reprobacion = 0.0

            reporte.append({
                "materia": str(mat.nombre),
                "curso": str(mat.curso.nombre) if mat.curso else "Sin Curso",
                "promedio_grupo": round(promedio_final, 2),
                "total_estudiantes": total_estudiantes,
                "total_evaluaciones": notas_curso.count(),
                "cantidad_reprobando": reprobados,
                "tasa_reprobacion": f"{round(tasa_reprobacion, 1)}%" # Dato clave para la IA
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