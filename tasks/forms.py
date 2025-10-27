# ===================================================================
# tasks/forms.py (COMPLETO Y CORREGIDO)
# ===================================================================

"""
Formularios para la aplicación 'tasks'.

Este archivo define las clases de formularios que se utilizan para capturar
y validar la entrada de datos del usuario en toda la aplicación, desde
la creación de preguntas en el foro hasta la gestión de usuarios.
"""

from django import forms
# Importación del formulario base de Django para tener acceso a los campos
from django.contrib.auth.forms import PasswordChangeForm 
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import update_session_auth_hash # Necesario si necesitas forzar el re-login o actualización
from django.core.exceptions import ValidationError
from .models import Question, Answer, ROLES_CHOICES

# --- Formularios Existentes del Foro ---

class QuestionForm(forms.ModelForm):
    """Formulario para crear o editar una pregunta en el foro."""
    class Meta:
        model = Question
        fields = ['title', 'content']

class AnswerForm(forms.ModelForm):
    """Formulario para publicar una respuesta a una pregunta."""
    class Meta:
        model = Answer
        fields = ['content']

# --- NUEVOS FORMULARIOS ---

class BulkCSVForm(forms.Form):
    """
    Formulario para la subida de un archivo CSV en el panel de administración.
    Valida que se haya subido un archivo y se especifique el año escolar.
    """
    # 1. CAMBIO: Renombrado de 'archivo' a 'csv_file' para coincidir con la vista
    csv_file = forms.FileField(
        label="Seleccionar archivo CSV",
        help_text="Columnas requeridas: first_name, last_name, email, grado, acudiente_first_name, acudiente_last_name, acudiente_email, acudiente_cedula."
    )
    
    # 2. CAMBIO: Campo añadido para el año escolar, solucionando el KeyError
    anio_escolar = forms.CharField(
        label="Año Escolar",
        max_length=9,
        required=False, # Se permite que esté vacío para usar el valor por defecto en la vista
        help_text="Ej: 2025-2026. Si se deja en blanco, se usará el año actual.",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )


class PasswordChangeFirstLoginForm(forms.Form):
    """
    Formulario específico para el cambio de contraseña obligatorio.
    Implementa su propia lógica de validación y el método save()
    ya que utiliza nombres de campo personalizados ('nueva', 'confirmar').
    """
    nueva = forms.CharField(
        label="Nueva contraseña",
        widget=forms.PasswordInput,
        help_text="La contraseña debe tener al menos 8 caracteres."
    )
    confirmar = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput
    )

    def __init__(self, *args, **kwargs):
        # Se requiere el objeto 'user' para el validador de contraseñas de Django
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        """
        Método de validación para todo el formulario:
        1. Verifica que las contraseñas coincidan.
        2. Aplica los validadores de seguridad de Django (definidos en settings.py).
        """
        cleaned_data = super().clean()
        nueva = cleaned_data.get("nueva")
        confirmar = cleaned_data.get("confirmar")

        # 1. Validación de coincidencia
        if nueva and confirmar and nueva != confirmar:
            # Aquí se puede usar forms.ValidationError directamente o self.add_error
            self.add_error('confirmar', "Las contraseñas no coinciden.")
        
        # 2. Validación de seguridad (validate_password)
        if nueva and self.user:
            try:
                # La función validate_password utiliza los validadores de settings.py
                validate_password(nueva, self.user)
            except ValidationError as e:
                # Si falla, añadimos el error al campo 'nueva'
                self.add_error('nueva', e)
                
        return cleaned_data

    def save(self, commit=True):
        """
        Guarda la nueva contraseña del usuario. 
        Este método resuelve el AttributeError.
        """
        # Obtenemos la nueva contraseña del campo 'nueva'
        new_password = self.cleaned_data["nueva"]
        
        # Establecemos la nueva contraseña en el objeto de usuario
        self.user.set_password(new_password)
        
        # Guardamos el usuario en la base de datos
        if commit:
            self.user.save()
            
        # Devolvemos el objeto user actualizado, tal como lo hace PasswordChangeForm
        return self.user

class ProfileSearchForm(forms.Form):
    """
    Formulario para la búsqueda y filtrado de usuarios en el panel
    de 'Gestión de Perfiles' del administrador.
    """
    query = forms.CharField(
        required=False, 
        label="Buscar",
        widget=forms.TextInput(attrs={'placeholder': 'Usuario, nombre o apellido...'})
    )
    rol = forms.ChoiceField(
        required=False,
        # Se crea una lista de opciones a partir de ROLES_CHOICES
        choices=[('', 'Todos los roles')] + [r for r in ROLES_CHOICES if r[0] != 'DIRECTOR_CURSO'],
        label="Filtrar por rol"
    )