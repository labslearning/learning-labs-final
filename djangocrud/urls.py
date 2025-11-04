# djangocrud/urls.py

from django.contrib import admin
from django.urls import path, include
from tasks import views # <-- 1. IMPORTACIÓN EXISTENTE

urlpatterns = [
    # --- 2. RUTAS DE BOLETINES (ADMIN) MOVISTAS ANTES DE 'admin/' ---
    # Este es el cambio clave para arreglar el NoReverseMatch
    path('admin/generar-boletin/<int:estudiante_id>/', views.generar_boletin_pdf_admin, name='admin_generar_boletin'),
    path('admin/api/toggle-boletin-permiso/', views.toggle_boletin_permiso, name='api_toggle_boletin_permiso'),
    
    # --- Rutas existentes ---
    path('admin/', admin.site.urls), # <-- Esta debe ir DESPUÉS de tus rutas de 'admin/'
    path('', include('tasks.urls')),  # Usa un prefijo para tus URLs
]

