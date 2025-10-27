# ===================================================================
# tasks/middleware.py (COMPLETO Y PROFESIONAL)
# ===================================================================

"""
Middleware personalizado para la aplicación 'tasks'.

Este módulo contiene clases de middleware que interceptan el ciclo de
petición/respuesta de Django para añadir funcionalidades transversales
a todo el sitio, como la seguridad y la gestión de sesiones.
"""

from django.shortcuts import redirect
from django.urls import reverse

class ForcePasswordChangeMiddleware:
    """
    Middleware que obliga a los usuarios a cambiar su contraseña.

    Si un usuario autenticado tiene el atributo 'requiere_cambio_clave'
    en su perfil establecido como True, este middleware lo redirigirá
    automáticamente a la página de cambio de contraseña en cada petición.

    Se definen excepciones para rutas esenciales como la propia página de
    cambio de clave, el logout y el panel de administración de Django,
    para evitar bucles de redirección infinitos.
    """
    def __init__(self, get_response):
        """Inicializa el middleware."""
        self.get_response = get_response

    def __call__(self, request):
        """
        Este método se ejecuta en cada petición.
        Verifica el estado del usuario y redirige si es necesario.
        """
        # El middleware solo debe actuar sobre usuarios ya autenticados.
        if request.user.is_authenticated:
            
            # Rutas que siempre deben ser accesibles, incluso con el flag activo.
            # Usamos un set para una búsqueda más eficiente (O(1)).
            allowed_paths = {
                reverse('cambiar_clave'),
                reverse('signout'),
            }

            perfil = getattr(request.user, 'perfil', None)

            # Comprobar la condición para redirigir:
            # 1. El usuario tiene un perfil.
            # 2. El perfil requiere cambio de clave.
            # 3. La ruta solicitada NO está en las excepciones.
            # 4. La ruta solicitada NO es parte del panel de admin de Django.
            if (perfil and 
                perfil.requiere_cambio_clave and 
                request.path not in allowed_paths and
                not request.path.startswith('/admin/')):
                
                # Redirige al usuario a la vista de cambio de contraseña.
                return redirect('cambiar_clave')
        
        # Si no se cumplen las condiciones, la petición continúa su flujo normal.
        response = self.get_response(request)
        return response
