# tasks/ai/constants.py
# ==============================================================================
# VOCABULARIO OFICIAL DE IA - PROYECTO EDUCATIVO INSTITUCIONAL (PEI)
# ==============================================================================
# Este archivo define TODOS los términos permitidos para el uso de IA.
# Su objetivo es gobernanza, control de costos, auditoría y escalabilidad.
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. ROLES INSTITUCIONALES
# ------------------------------------------------------------------------------
ROL_PROFESOR = 'DOCENTE'
ROL_ESTUDIANTE = 'ESTUDIANTE'
ROL_ACUDIENTE = 'ACUDIENTE'
ROL_STAFF = 'STAFF'              # Psicología, Coordinación, Orientación
ROL_ADMIN = 'ADMINISTRADOR'

ROLES_IA_PERMITIDOS = [
    ROL_PROFESOR,
    ROL_ESTUDIANTE,
    ROL_ACUDIENTE,
    ROL_STAFF,
    ROL_ADMIN,
]

# ------------------------------------------------------------------------------
# 2. ACCIONES (INTENTS) DE LA IA - FASE 11 GLOBAL
# ------------------------------------------------------------------------------
# Perfil Estudiante: Mejora personalizada y Tutoría reflexiva
ACCION_MEJORAS_ESTUDIANTE = 'mejoras_estudiante'
ACCION_CHAT_SOCRATICO = 'chat_socratico'

# Perfil Docente: Optimización de aula y cumplimiento curricular
ACCION_MEJORAS_DOCENTE = 'mejoras_docente'
ACCION_ORIENTACION_CURSO = 'orientacion_curso'

# Perfil Acudiente: Puente entre colegio y casa
ACCION_APOYO_ACUDIENTE = 'apoyo_acudiente'

# Perfil Staff (Coordinación/Orientación): Análisis de tendencias y convivencia
ACCION_MEJORA_STAFF_ACADEMICO = 'staff_academico'
ACCION_ANALISIS_CONVIVENCIA = 'analisis_convivencia'

# Perfil Administrador: Auditoría estratégica
ACCION_CUMPLIMIENTO_PEI = 'cumplimiento_pei'

ACCIONES_IA_PERMITIDAS = [
    ACCION_MEJORAS_ESTUDIANTE,
    ACCION_CHAT_SOCRATICO,
    ACCION_MEJORAS_DOCENTE,
    ACCION_ORIENTACION_CURSO,
    ACCION_APOYO_ACUDIENTE,
    ACCION_MEJORA_STAFF_ACADEMICO,
    ACCION_ANALISIS_CONVIVENCIA,
    ACCION_CUMPLIMIENTO_PEI,
]

# ------------------------------------------------------------------------------
# 3. OPCIONES PARA FRONTEND (Visualización en Dashboards)
# ------------------------------------------------------------------------------
OPCIONES_ACCIONES_IA = (
    (ACCION_MEJORAS_ESTUDIANTE, 'Plan de Mejora Individual'),
    (ACCION_CHAT_SOCRATICO, 'Tutoría Socrática'),
    (ACCION_MEJORAS_DOCENTE, 'Estrategias de Mejora por Curso'),
    (ACCION_APOYO_ACUDIENTE, 'Guía de Apoyo en Casa'),
    (ACCION_MEJORA_STAFF_ACADEMICO, 'Reporte de Mejora Académica Global'),
    (ACCION_ANALISIS_CONVIVENCIA, 'Reporte de Mejora Convivencial'),
    (ACCION_CUMPLIMIENTO_PEI, 'Auditoría de Cumplimiento PEI'),
)

# ------------------------------------------------------------------------------
# 4. TIPOS DE DOCUMENTOS GENERADOS
# ------------------------------------------------------------------------------
DOC_REPORTE_PEDAGOGICO = 'reporte_pedagogico'
DOC_ORIENTACION_ESTUDIANTE = 'orientacion_estudiante'
DOC_ORIENTACION_ACUDIENTE = 'orientacion_acudiente'
DOC_REPORTE_CONVIVENCIA = 'reporte_convivencia'
DOC_REPORTE_INSTITUCIONAL = 'reporte_institucional'
DOC_AUDITORIA_PEI = 'reporte_auditoria_pei'

DOCUMENTOS_IA_PERMITIDOS = [
    DOC_REPORTE_PEDAGOGICO,
    DOC_ORIENTACION_ESTUDIANTE,
    DOC_ORIENTACION_ACUDIENTE,
    DOC_REPORTE_CONVIVENCIA,
    DOC_REPORTE_INSTITUCIONAL,
    DOC_AUDITORIA_PEI,
]

# ------------------------------------------------------------------------------
# 5. CONFIGURACIÓN TÉCNICA (DeepSeek)
# ------------------------------------------------------------------------------
MODEL_NAME = 'deepseek-chat'
MAX_TOKENS_PER_REQUEST = 4000