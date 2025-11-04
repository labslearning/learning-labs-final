# ===================================================================
# tasks/admin.py (COMPLETO Y CORREGIDO + Institucion)
# ===================================================================

"""
Configuración del panel de administración de Django para la app 'tasks'.

Este archivo registra los modelos de la aplicación para que sean gestionables
a través de la interfaz de administración de Django.
"""

from django.contrib import admin
# Se usa una importación relativa, que es la convención dentro de una app
from .models import (
    Perfil,
    Curso,
    Materia,
    Periodo,
    Nota,
    Question,
    Answer,
    ChatRoom,
    ActiveUser,
    Matricula,
    AsignacionMateria,
    ActividadSemanal,
    LogroPeriodo,
    Convivencia,
    Acudiente,
    Institucion,  # <-- 1. AÑADIDO SEGÚN EL PLAN
    # Task,    # Descomenta esta línea si tienes un modelo llamado Task
)

# Registro de los modelos para que aparezcan en el panel de administración
# admin.site.register(Task) # Descomenta si usas el modelo Task
admin.site.register(Perfil)
admin.site.register(Curso)
admin.site.register(Materia)
admin.site.register(Periodo)
admin.site.register(Nota)
admin.site.register(Question)
admin.site.register(Answer)
admin.site.register(ChatRoom)
admin.site.register(ActiveUser)
admin.site.register(Matricula)
admin.site.register(AsignacionMateria)
admin.site.register(ActividadSemanal)
admin.site.register(LogroPeriodo)
admin.site.register(Convivencia)
admin.site.register(Acudiente)
admin.site.register(Institucion)  # <-- 2. AÑADIDO SEGÚN EL PLAN