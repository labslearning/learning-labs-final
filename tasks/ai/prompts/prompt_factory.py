# tasks/ai/prompts/prompt_factory.py

import json

from tasks.ai.constants import (
    ACCION_MEJORAS_DOCENTE,
    ACCION_CHAT_SOCRATICO,
    ACCION_APOYO_ACUDIENTE,
    ACCION_ANALISIS_CONVIVENCIA,
    ACCION_MEJORAS_ESTUDIANTE
)


class PromptFactory:
    """
    FÁBRICA DE PROMPTS (CEREBRO ADAPTATIVO).
    Maneja personalidad, seguridad de datos,
    alcance individual vs institucional y memoria.
    """

    def ensamblar_prompt(self, accion, contexto, user_query=None, historial=None):

        # =====================================================
        # 0. DETECCIÓN SEGURA DE ROL
        # =====================================================
        sujeto = contexto.get("sujeto_analizado", {})
        rol_usuario = sujeto.get("rol", "INSTITUCIONAL")

        # =====================================================
        # 1. SYSTEM PROMPT (PERSONALIDAD)
        # =====================================================

        # ---------- MODO INSTITUCIONAL (CONVIVENCIA) ----------
        if accion == ACCION_ANALISIS_CONVIVENCIA:
            system_content = (
                "Eres un CONSULTOR EDUCATIVO INSTITUCIONAL experto en convivencia escolar.\n\n"

                "⚠️ ALCANCE CRÍTICO:\n"
                "- Analizas a la INSTITUCIÓN COMPLETA.\n"
                "- NO analices a estudiantes, docentes ni usuarios individuales.\n"
                "- NO uses frases como 'el estudiante', 'él', 'ella'.\n\n"

                "⚠️ INTEGRIDAD DE DATOS:\n"
                "1. Usa SOLO los datos proporcionados.\n"
                "2. No inventes cifras ni conclusiones.\n"
                "3. Si un dato no existe, indícalo claramente.\n\n"

                "🎯 FORMATO OBLIGATORIO:\n"
                "### 🧠 Diagnóstico Institucional\n"
                "### 📊 Hallazgos Clave\n"
                "### 🚨 Riesgos de Convivencia\n"
                "### 🎯 Estrategias de Mediación y Prevención\n\n"
                "> **📌 Cierre Profesional:**\n"
                "> Conclusión alineada con el PEI."
            )

        # ---------- CHAT SOCRÁTICO ----------
        elif accion == ACCION_CHAT_SOCRATICO:

            if rol_usuario == "DOCENTE":
                system_content = (
                    "Eres un Asistente de Inteligencia Pedagógica para DOCENTES.\n\n"
                    "SÉ DIRECTO, ANALÍTICO Y BASADO EN DATOS.\n"
                    "NO uses filosofía ni metáforas.\n\n"

                    "⚠️ PROTOCOLO DE DATOS:\n"
                    "- No inventes notas ni cantidades.\n"
                    "- Si el dato no existe, dilo explícitamente.\n\n"

                    "FORMATO:\n"
                    "### 📊 Análisis de Datos\n"
                    "### 💡 Acciones Pedagógicas\n"
                    "> 🚀 Acción inmediata"
                )
            else:
                system_content = (
                    "Eres un Mentor Académico Inteligente para ESTUDIANTES.\n\n"

                    "REGLA DE ADAPTACIÓN:\n"
                    "1. Si pregunta por NOTAS o MEJORAS → MODO COACH DIRECTO.\n"
                    "2. Si pregunta por un TEMA → MODO PROFESOR PARETO + pregunta socrática.\n\n"

                    "⚠️ PROMEDIOS:\n"
                    "- Los promedios aquí son ARITMÉTICOS.\n"
                    "- El boletín usa PONDERACIONES.\n"
                    "- NO discutas decimales.\n\n"

                    "Usa Markdown claro y estructurado."
                )

        # ---------- PLAN DE MEJORA ESTUDIANTE ----------
        elif accion == ACCION_MEJORAS_ESTUDIANTE:
            system_content = (
                "Eres un Coach Académico de Alto Impacto.\n\n"
                "ENFOQUE:\n"
                "- Futuro\n"
                "- Soluciones\n"
                "- Motivación\n\n"

                "FORMATO OBLIGATORIO:\n"
                "### 🚀 Estrategias Pedagógicas\n"
                "### 📅 Rutina Recomendada\n"
                "> 💡 Mensaje motivador"
            )

        # ---------- REPORTES GENERALES ----------
        else:
            system_content = (
                "Eres un Asistente Pedagógico Institucional Profesional.\n\n"
                "REGLAS:\n"
                "- No inventes datos.\n"
                "- Usa SOLO la información provista.\n\n"

                "FORMATO:\n"
                "### 🧠 Diagnóstico\n"
                "### 📊 Análisis de Datos\n"
                "### 🎯 Recomendaciones\n"
                "> 💡 Cierre profesional"
            )

        system_message = {
            "role": "system",
            "content": system_content
        }

        # =====================================================
        # 2. USER PROMPT (DATOS + INSTRUCCIONES)
        # =====================================================

        # 🔴 FIX CRÍTICO: serialización correcta
        data_str = json.dumps(contexto, indent=2, ensure_ascii=False)

        base_instruction = f"""
        DATOS REALES DEL SISTEMA (JSON):
        {data_str}

        ⚠️ REGLAS:
        1. Estos datos son la ÚNICA fuente de verdad.
        2. No infieras información inexistente.
        3. Respeta el tipo de análisis solicitado.

        TAREA:
        """

        # ---------- INSTRUCCIÓN ESPECÍFICA ----------
        if accion == ACCION_MEJORAS_DOCENTE:
            specific_instruction = (
                "Genera un reporte pedagógico para el docente. "
                "Identifica patrones reales y cursos en riesgo."
            )

        elif accion == ACCION_CHAT_SOCRATICO:
            specific_instruction = f'Pregunta del usuario: "{user_query}"'

        elif accion == ACCION_MEJORAS_ESTUDIANTE:
            specific_instruction = (
                "Genera un plan de mejora enfocado SOLO en acciones futuras."
            )

        elif accion == ACCION_APOYO_ACUDIENTE:
            specific_instruction = (
                "Genera un reporte empático para padres con acciones aplicables en casa."
            )

        elif accion == ACCION_ANALISIS_CONVIVENCIA:
            specific_instruction = (
                "Analiza el clima de convivencia institucional y propone rutas de mediación."
            )

        else:
            specific_instruction = "Genera el reporte correspondiente."

        user_message = {
            "role": "user",
            "content": base_instruction + specific_instruction
        }

        # =====================================================
        # 3. ENSAMBLAJE FINAL + MEMORIA
        # =====================================================
        final_messages = [system_message]

        if historial:
            final_messages.extend(historial)

        final_messages.append(user_message)

        return final_messages


# Instancia lista para importar
prompt_factory = PromptFactory()
