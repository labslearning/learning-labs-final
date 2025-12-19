# tasks/ai/prompts.py

import json
from .constants import (
    ACCION_MEJORAS_ESTUDIANTE,
    ACCION_CHAT_SOCRATICO,
    ACCION_MEJORAS_DOCENTE,
    ACCION_APOYO_ACUDIENTE,
    ACCION_MEJORA_STAFF_ACADEMICO,
    ACCION_ANALISIS_CONVIVENCIA,
    ACCION_CUMPLIMIENTO_PEI
)

class PromptFactory:
    """
    LA FÁBRICA DE INSTRUCCIONES INSTITUCIONAL.
    Ensambla la personalidad y el guion pedagógico según el rol del usuario.
    """

    def crear_mensaje_sistema(self, contexto):
        """Define la identidad inmutable basada en el PEI."""
        # Manejo de datos globales vs individuales para el PEI
        institucion = contexto.get('institucion', contexto.get('pei_referencia', {}))
        
        mision = institucion.get('mision', 'Formar integralmente.')
        valores = institucion.get('valores', 'Excelencia y Respeto')
        enfoque = institucion.get('modelo_pedagogico', institucion.get('enfoque', 'Constructivismo'))

        return (
            f"Eres el Asistente de Inteligencia Institucional del colegio. "
            f"Tu brújula ética y pedagógica es el PEI.\n"
            f"MISIÓN: {mision}\n"
            f"VALORES: {valores}\n"
            f"ENFOQUE: {enfoque}.\n"
            f"REGLA CRÍTICA: Adapta tu lenguaje al rol del usuario. "
            f"Usa formato Markdown (Negritas, Listas, Títulos) para estructurar tu respuesta de forma profesional."
        )

    def ensamblar_prompt(self, accion, contexto, user_query=None):
        """Construye la lista de mensajes exacta para DeepSeek."""
        # 1. Identidad
        system_content = self.crear_mensaje_sistema(contexto)
        
        # 2. Inyección de Datos (Context Injection)
        datos_json = json.dumps(contexto, ensure_ascii=False, indent=2)
        context_instruction = (
            f"\n\n[DATOS ACADÉMICOS Y CONTEXTO]\n"
            f"```json\n{datos_json}\n```\n"
            f"Analiza estos datos con rigor. Si no hay datos suficientes, indícalo amablemente."
        )

        messages = [
            {"role": "system", "content": system_content + context_instruction}
        ]

        # 3. Lógica de Guiones por Perfil (Acciones Fase 11)
        if accion == ACCION_MEJORAS_ESTUDIANTE:
            user_content = self._prompt_mejoras_estudiante()

        elif accion == ACCION_CHAT_SOCRATICO:
            user_content = self._prompt_socratico(user_query)

        elif accion == ACCION_MEJORAS_DOCENTE:
            user_content = self._prompt_mejoras_docente()

        elif accion == ACCION_APOYO_ACUDIENTE:
            user_content = self._prompt_apoyo_acudiente()

        elif accion == ACCION_MEJORA_STAFF_ACADEMICO:
            user_content = self._prompt_staff_academico()

        elif accion == ACCION_ANALISIS_CONVIVENCIA:
            user_content = self._prompt_convivencia()

        elif accion == ACCION_CUMPLIMIENTO_PEI:
            user_content = self._prompt_auditoria_admin()
            
        else:
            user_content = f"Consulta: {user_query or 'Realiza un análisis general de los datos.'}"

        messages.append({"role": "user", "content": user_content})
        return messages

    # ------------------------------------------------------------------
    # GUIONES ESPECÍFICOS (PERSONALIDADES CORREGIDAS)
    # ------------------------------------------------------------------

    def _prompt_mejoras_estudiante(self):
        return (
            "Como mi tutor personal, analiza mi historial académico y convivencia. "
            "Háblame directamente a mí (el estudiante) con tono motivador.\n"
            "1. Resalta mis fortalezas.\n"
            "2. Identifica mis materias críticas.\n"
            "3. Dame un plan de 3 pasos concretos para mejorar mis notas esta semana."
        )

    def _prompt_socratico(self, query):
        pregunta = query if query else "Hola, soy tu tutor. ¿Qué quieres aprender hoy?"
        return (
            f"PREGUNTA DEL USUARIO: '{pregunta}'\n\n"
            "ROL: Eres un MENTOR PEDAGÓGICO CONSTRUCTIVISTA (Experto y Claro).\n"
            "INSTRUCCIONES CLAVE PARA TU RESPUESTA:\n"
            "1. ENSEÑANZA: Explica el concepto solicitado con profundidad, claridad y analogías. "
            "Si el usuario pregunta sobre un tema (ej. Física, Historia), explícalo sin dudar, aunque su perfil sea de otra área.\n"
            "2. CONTEXTO: Si puedes, relaciona el tema con los intereses del perfil, pero prioriza responder la duda del usuario.\n"
            "3. VERIFICACIÓN: Al final de tu explicación, haz una pregunta reflexiva breve para asegurar que entendí.\n"
            "4. NO seas un interrogador pasivo; tu objetivo es iluminar el conocimiento."
        )

    def _prompt_mejoras_docente(self):
        return (
            "Eres un consultor pedagógico experto. Analiza el rendimiento de este curso/estudiante.\n"
            "Genera un reporte profesional que incluya:\n"
            "- **Diagnóstico**: Patrones de rendimiento detectados en el JSON.\n"
            "- **Estrategias**: Sugiere 2 metodologías didácticas específicas (ej: ABP, Gamificación) aplicables para mejorar estos resultados."
        )

    def _prompt_apoyo_acudiente(self):
        return (
            "Dirígete al padre de familia con empatía y claridad. "
            "Traduce los datos técnicos (JSON) a un lenguaje humano.\n"
            "Genera una **Guía de Apoyo Familiar** que incluya:\n"
            "1. **Resumen de Logros**: Qué está haciendo bien el estudiante.\n"
            "2. **Áreas de Atención**: Dónde necesita ayuda.\n"
            "3. **Consejos para el Hogar**: 3 acciones prácticas (rutinas, diálogo) para apoyarlo en casa."
        )

    def _prompt_staff_academico(self):
        return (
            "Eres analista de coordinación académica. Revisa las tendencias globales.\n"
            "Identifica si existe un problema sistémico en alguna materia o grado.\n"
            "Propón una estrategia de nivelación institucional alineada con la Misión del PEI."
        )

    def _prompt_convivencia(self):
        return (
            "Analiza las anotaciones de convivencia y el perfil psicosocial.\n"
            "1. Clasifica el clima escolar/comportamiento.\n"
            "2. Identifica patrones (agresión, aislamiento, liderazgo).\n"
            "3. Sugiere una estrategia de intervención basada en justicia restaurativa."
        )

    def _prompt_auditoria_admin(self):
        return (
            "**INFORME EJECUTIVO DE AUDITORÍA (PEI)**\n"
            "Analiza los KPIs institucionales globales (Promedios, Asistencia, Convivencia).\n"
            "1. **Estado del Arte**: ¿Estamos cumpliendo con la visión de excelencia?\n"
            "2. **Alertas Críticas**: Riesgos de deserción o bajo rendimiento masivo.\n"
            "3. **Recomendaciones Estratégicas**: Acciones para Rectoría."
        )

# Instancia global
prompt_factory = PromptFactory()