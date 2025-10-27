# ===================================================================
# tasks/utils.py (COMPLETO Y PROFESIONAL)
# ===================================================================

"""
Módulo de utilidades para la aplicación 'tasks'.

Este archivo centraliza funciones de ayuda reutilizables que no son vistas
directamente, como generadores de datos, normalizadores de texto y lógica
de negocio específica que puede ser llamada desde múltiples lugares.
"""

import re
import secrets
import string
import unicodedata
from django.contrib.auth.models import User
from .models import Curso
from typing import Optional

def _slugify_simple(text: str) -> str:
    """
    Función interna para normalizar y limpiar una cadena de texto.
    Convierte a minúsculas, elimina acentos y caracteres no alfanuméricos.
    
    :param text: La cadena de texto a procesar.
    :return: La cadena de texto normalizada.
    """
    try:
        text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    except (TypeError, AttributeError):
        return ""
    return re.sub(r'[^a-z0-9]+', '', text.lower())


def generar_username_unico(nombre: str, apellido: str) -> str:
    """
    Genera un nombre de usuario único basado en el nombre y apellido.
    
    Crea un nombre base (ej: 'jperez') y verifica si ya existe en la base de datos.
    Si existe, anexa un número secuencial (ej: 'jperez2', 'jperez3', ...)
    hasta encontrar uno disponible.

    :param nombre: El primer nombre del usuario.
    :param apellido: El apellido del usuario.
    :return: Un string con el nombre de usuario único generado.
    """
    base_username = f"{_slugify_simple(nombre[:1])}{_slugify_simple(apellido)}"
    if not base_username:
        base_username = "usuario"  # Fallback por si el nombre/apellido es inválido

    # Optimización: primero, verificar si el username base está disponible
    if not User.objects.filter(username=base_username).exists():
        return base_username

    # Si el base ya existe, buscar el siguiente sufijo numérico
    # Regex busca usernames que empiezan con la base y terminan en opcionales dígitos
    # ej: para 'jperez', busca 'jperez', 'jperez2', 'jperez10', etc.
    candidatos = User.objects.filter(username__regex=rf'^{re.escape(base_username)}\d*$').values_list('username', flat=True)
    
    sufijos = [int(u[len(base_username):]) for u in candidatos if u != base_username and u[len(base_username):].isdigit()]
    
    siguiente_sufijo = (max(sufijos) + 1) if sufijos else 2
    
    return f"{base_username}{siguiente_sufijo}"


def generar_contrasena_temporal(longitud: int = 12) -> str:
    """
    Genera una contraseña temporal segura y aleatoria.

    Utiliza el módulo 'secrets' de Python, que es criptográficamente seguro,
    para construir una contraseña con letras mayúsculas, minúsculas,
    números y un conjunto de símbolos comunes.

    :param longitud: La longitud deseada para la contraseña. Por defecto es 12.
    :return: Un string con la contraseña temporal generada.
    """
    alfabeto = string.ascii_letters + string.digits + "!@#$%^&*?"
    return ''.join(secrets.choice(alfabeto) for _ in range(longitud))


def asignar_curso_por_grado(grado: str, seccion: Optional[str] = None, anio_escolar: Optional[str] = None) -> Curso:
    """
    Busca y asigna el curso más apropiado para un estudiante según su grado.

    La lógica de asignación es la siguiente:
    1. Filtra los cursos activos por el grado y, opcionalmente, por sección y año escolar.
    2. Prioriza los cursos que aún no han alcanzado su capacidad máxima.
    3. Si todos los cursos que coinciden están llenos, busca cualquier otro curso
       activo del mismo grado como alternativa (fallback).
    4. Si no se encuentra absolutamente ningún curso para ese grado, lanza un error claro.

    :param grado: La clave del grado (ej: '6', 'PREKINDER') del modelo GRADOS_CHOICES.
    :param seccion: (Opcional) La sección específica a buscar (ej: 'A').
    :param anio_escolar: (Opcional) El año escolar específico (ej: '2025-2026').
    :return: Una instancia del modelo Curso que está disponible.
    :raises ValueError: Si no se encuentra ningún curso activo para el grado especificado.
    """
    qs = Curso.objects.filter(grado=grado, activo=True)
    
    if anio_escolar:
        qs = qs.filter(anio_escolar=anio_escolar)
    if seccion:
        qs = qs.filter(seccion__iexact=seccion) # Case-insensitive para la sección
    
    # Intenta encontrar un curso con cupo disponible
    for curso in qs.order_by('seccion', 'nombre'):
        if not curso.esta_completo():
            return curso
            
    # Si no hay cursos con cupo, o la sección no fue encontrada, busca una alternativa
    # en el mismo grado sin considerar la sección (si se especificó una).
    fallback_qs = Curso.objects.filter(grado=grado, activo=True)
    if anio_escolar:
        fallback_qs = fallback_qs.filter(anio_escolar=anio_escolar)

    for curso in fallback_qs.order_by('seccion', 'nombre'):
         if not curso.esta_completo():
            return curso

    # Si llegamos aquí, todos los cursos de ese grado están llenos o no existen.
    # Lanza un error claro para que el administrador sepa que debe crear un nuevo curso.
    raise ValueError(f"No hay cursos con cupo disponible para el grado '{grado}'. Por favor, crea uno nuevo en el panel de administración.")
