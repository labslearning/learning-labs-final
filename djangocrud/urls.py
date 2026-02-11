# djangocrud/urls.py (VERSIÓN FINAL: TU CÓDIGO + ARREGLO RAILWAY)

from django.contrib import admin
# AGREGAMOS 're_path' AQUÍ ABAJO PARA PODER USAR LA LLAVE MAESTRA
from django.urls import path, include, re_path
from tasks import views_admin  # <--- Agrega esto
# ===================================================================
# 🩺 INICIO DE LA CIRUGÍA (SOLUCIÓN AL ERROR 404 de PDF)
# ===================================================================
# Importaciones necesarias para servir archivos media
from django.conf import settings
from django.conf.urls.static import static
# IMPORTAMOS ESTO PARA FORZAR LA VISUALIZACIÓN EN RAILWAY
from django.views.static import serve
from django.views.generic import TemplateView # <--- IMPORTANTE
# ===================================================================
# 🩺 FIN DE LA CIRUGÍA
# ===================================================================


urlpatterns = [
    # 1. La ruta de admin de Django (siempre debe estar)
    path('admin/', admin.site.urls),

    # 2. Incluimos TODAS las demás rutas desde 'tasks.urls'
    # Django ahora buscará en 'tasks.urls' CUALQUIER OTRA ruta (incluyendo 'panel/...')
    path('', include('tasks.urls')),
    path('sw.js', TemplateView.as_view(template_name='sw.js', content_type='application/javascript'), name='sw.js'),
    path('panel/cierre-anual/', views_admin.panel_cierre_anual, name='panel_cierre_anual'),
    # 2. NUEVA RUTA: Reversión (Time Machine)
    path('panel/cierre-anual/revertir/<int:log_id>/', views_admin.revertir_cierre_anual, name='revertir_cierre'),
]


# ===================================================================
# 🩺 INICIO DE LA CIRUGÍA (VISUALIZACIÓN DE FOTOS)
# ===================================================================

# CASO 1: MODO DEBUG (Tu computador local)
# Esta línea le da permiso a Django (SOLO si DEBUG=True)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# CASO 2: MODO PRODUCCIÓN (Railway)
# Aquí es donde estaba el problema. Railway tiene DEBUG=False.
# Con esto obligamos a Django a mostrar las fotos también en la nube.
else:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
    ]

# ===================================================================
# 🩺 FIN DE LA CIRUGÍA
# ===================================================================

