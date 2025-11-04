# tasks/urls.py (VERSIÓN CORREGIDA Y PROFESIONAL)

from django.urls import path
from . import views

urlpatterns = [
    # --- RUTAS BÁSICAS Y AUTENTICACIÓN ---
    path('', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('signin/', views.signin, name='signin'),
    path('signout/', views.signout, name='signout'),
    path('logout/', views.signout, name='logout'), 

    # --- RUTAS DE CURSOS DEMO / CONTENIDO ---
    path('english/', views.english, name='english'),
    path('english2/', views.english2, name='english2'),
    path('english3/', views.english3, name='english3'),
    path('english4/', views.english4, name='english4'),
    path('ai/', views.ai, name='ai'),

    # --- RUTAS DE FORO Y COMUNIDAD ---
    path('forum/', views.forum, name='forum'),
    path('ask_question/', views.ask_question, name='ask_question'),
    path('question/<int:question_id>/', views.question_detail, name='question_detail'),
    path('answer/<int:question_id>/', views.answer_question, name='answer_question'),

    # --- DASHBOARDS POR ROL ---
    path('dashboard/estudiante/', views.dashboard_estudiante, name='dashboard_estudiante'),
    path('dashboard/docente/', views.dashboard_docente, name='dashboard_docente'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/director/', views.dashboard_director, name='dashboard_director'),
    path('dashboard/acudiente/', views.dashboard_acudiente, name='dashboard_acudiente'),

    # --- GESTIÓN ACADÉMICA: DOCENTES ---
    path('docente/subir-notas/<int:materia_id>/', views.subir_notas, name='subir_notas'),

    # --- GESTIÓN ACADÉMICA: ADMINISTRADORES ---
    path('gestion-academica/', views.gestion_academica, name='gestion_academica'),
    path('gestionar-cursos/', views.gestionar_cursos, name='gestionar_cursos'),
    path('gestionar-profesores/', views.gestionar_profesores, name='gestionar_profesores'),
    path('asignar-curso-estudiante/', views.asignar_curso_estudiante, name='asignar_curso_estudiante'),
    path('asignar-materia-docente/', views.asignar_materia_docente, name='asignar_materia_docente'),

    # --- REGISTRO DE ALUMNOS ---
    path('registrar-alumnos-masivo/form/', views.registrar_alumnos_masivo_form, name='registrar_alumnos_masivo_form'),
    path('registrar-alumnos-masivo/', views.registrar_alumnos_masivo, name='registrar_alumnos_masivo'),
    path('registrar-alumno/', views.mostrar_registro_individual, name='mostrar_registro_individual'),
    path('registrar-alumno/guardar/', views.registrar_alumno_individual, name='registrar_alumno_individual'),

    # --- DIRECTORES DE CURSO ---
    path('director/panel-curso/<int:curso_id>/', views.panel_director_curso, name='panel_director_curso'),
    path('director/guardar-convivencia/<int:curso_id>/', views.guardar_convivencia, name='guardar_convivencia'),
    path('director/generar-boletin/<int:curso_id>/', views.generar_boletin, name='director_generar_boletin'),
    
    
    # --- GESTIÓN DE PERFILES, BOLETINES Y SEGURIDAD (PREFIJO 'PANEL/') ---

    # ===================================================================
    # 🩺 INICIO DE CIRUGÍA 1: Mover 'admin/eliminar-estudiante/' a 'panel/'
    # ===================================================================
    path('panel/eliminar-estudiante/', views.admin_eliminar_estudiante, name='panel_eliminar_estudiante'),
    # ===================================================================
    # 🩺 FIN DE CIRUGÍA 1
    # ===================================================================
    
    # ===================================================================
    # 🩺 INICIO DE CIRUGÍA 2: Mover 'admin/generar-boletin/' a 'panel/'
    # ===================================================================
    path('panel/generar-boletin/<int:estudiante_id>/', views.generar_boletin_pdf_admin, name='panel_generar_boletin'),
    # ===================================================================
    # 🩺 FIN DE CIRUGÍA 2
    # ===================================================================
    
    # Ruta de Acudiente (Esta no genera conflicto, se queda igual)
    path('acudiente/generar-boletin/<int:estudiante_id>/', 
         views.generar_boletin_pdf_acudiente, 
         name='generar_boletin_acudiente'),
    
    # ===================================================================
    # 🩺 INICIO DE CIRUGÍA 3: Mover 'admin/api/toggle-boletin-permiso/' a 'panel/'
    # ===================================================================
    path('panel/api/toggle-boletin-permiso/', views.toggle_boletin_permiso, name='panel_api_toggle_boletin_permiso'),
    # ===================================================================
    # 🩺 FIN DE CIRUGÍA 3
    # ===================================================================

    # Rutas del panel que ya estaban correctas
    path('panel/gestion-perfiles/', views.gestion_perfiles, name='gestion_perfiles'),
    path('panel/resetear-contrasena/', views.admin_reset_password, name='admin_reset_password'),
    path('panel/db-visual/', views.admin_db_visual, name='admin_db_visual'),
    path('cuenta/cambiar-clave/', views.cambiar_clave, name='cambiar_clave'),
    path('panel/ex-alumnos/', views.admin_ex_estudiantes, name='admin_ex_estudiantes'),
]