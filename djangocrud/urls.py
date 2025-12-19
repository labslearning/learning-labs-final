# djangocrud/urls.py (VERSIÓN CORREGIDA Y LIMPIA)

from django.contrib import admin
from django.urls import path, include

# ===================================================================
# 🩺 INICIO DE LA CIRUGÍA (SOLUCIÓN AL ERROR 404 de PDF)
# ===================================================================
# Importaciones necesarias para servir archivos media en MODO DEBUG
from django.conf import settings
from django.conf.urls.static import static
# ===================================================================
# 🩺 FIN DE LA CIRUGÍA
# ===================================================================


urlpatterns = [
    # 1. La ruta de admin de Django (siempre debe estar)
    path('admin/', admin.site.urls),

    # 2. Incluimos TODAS las demás rutas desde 'tasks.urls'
    # Django ahora buscará en 'tasks.urls' CUALQUIER OTRA ruta (incluyendo 'panel/...')
    path('', include('tasks.urls')),
]


# ===================================================================
# 🩺 INICIO DE LA CIRUGÍA (SOLUCIÓN AL ERROR 404 de PDF)
# ===================================================================

# Esta línea le da permiso a Django (SOLO si DEBUG=True)
# para servir los archivos que están en MEDIA_ROOT (tu carpeta 'media')
# cuando se solicitan a través de MEDIA_URL (el prefijo '/media/').
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# ===================================================================
# 🩺 FIN DE LA CIRUGÍA
# ===================================================================