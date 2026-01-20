# tasks/urls.py



from django.urls import path

from . import views

from tasks import ai_views

from .views import (

    # ... tus otras vistas que ya tenías ...

    home,

    signup,

    signin,

    # ...

    crear_grupo,

    detalle_grupo,

    unirse_grupo,

    eliminar_grupo,  # <--- ¡AGREGA ESTA LÍNEA AQUÍ!

)



urlpatterns = [

    # ======================================================

    # RUTAS BÁSICAS Y AUTENTICACIÓN

    # ======================================================

    path('', views.home, name='home'),

    path('signup/', views.signup, name='signup'),

    path('signin/', views.signin, name='signin'),

    path('signout/', views.signout, name='signout'),

    path('logout/', views.signout, name='logout'), 



    # ======================================================

    # RUTAS DE CURSOS DEMO / CONTENIDO

    # ======================================================

    path('english/', views.english, name='english'),

    path('english2/', views.english2, name='english2'),

    path('english3/', views.english3, name='english3'),

    path('english4/', views.english4, name='english4'),

    path('ai/', views.ai, name='ai'),



    # ======================================================

    # RUTAS DE FORO Y COMUNIDAD

    # ======================================================

    path('forum/', views.forum, name='forum'),

    path('ask_question/', views.ask_question, name='ask_question'),

    path('question/<int:question_id>/', views.question_detail, name='question_detail'),

    path('answer/<int:question_id>/', views.answer_question, name='answer_question'),



    # ======================================================

    # DASHBOARDS POR ROL

    # ======================================================

    path('dashboard/estudiante/', views.dashboard_estudiante, name='dashboard_estudiante'),

    path('dashboard/docente/', views.dashboard_docente, name='dashboard_docente'),

    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),

    path('dashboard/director/', views.dashboard_director, name='dashboard_director'),

    path('dashboard/acudiente/', views.dashboard_acudiente, name='dashboard_acudiente'),



    # ======================================================

    # GESTIÓN ACADÉMICA: DOCENTES

    # ======================================================

    path('docente/subir-notas/<int:materia_id>/', views.subir_notas, name='subir_notas'),



    # ======================================================

    # GESTIÓN ACADÉMICA: ADMINISTRADORES

    # ======================================================

    path('gestion-academica/', views.gestion_academica, name='gestion_academica'),

    path('gestionar-cursos/', views.gestionar_cursos, name='gestionar_cursos'),

    #path('gestionar-profesores/', views.gestionar_profesores, name='gestionar_profesores'),

    path('asignar-materia-docente/', views.asignar_materia_docente, name='asignar_materia_docente'),

    path('asignar-curso-estudiante/', views.asignar_curso_estudiante, name='asignar_curso_estudiante'),

    path('asignar-materia-docente/', views.asignar_materia_docente, name='asignar_materia_docente'),



    # ======================================================

    # REGISTRO DE ALUMNOS

    # ======================================================

    path('registrar-alumnos-masivo/form/', views.registrar_alumnos_masivo_form, name='registrar_alumnos_masivo_form'),

    path('registrar-alumnos-masivo/', views.registrar_alumnos_masivo, name='registrar_alumnos_masivo'),

    path('registrar-alumno/', views.mostrar_registro_individual, name='mostrar_registro_individual'),

    path('registrar-alumno/guardar/', views.registrar_alumno_individual, name='registrar_alumno_individual'),



    # ======================================================

    # DIRECTORES DE CURSO

    # ======================================================

    path('director/panel-curso/<int:curso_id>/', views.panel_director_curso, name='panel_director_curso'),

    path('director/guardar-convivencia/<int:curso_id>/', views.guardar_convivencia, name='guardar_convivencia'),

    path('director/generar-boletin/<int:curso_id>/', views.generar_boletin, name='director_generar_boletin'),



    # ======================================================

    # GESTIÓN DE PERFILES, BOLETINES Y SEGURIDAD (PANEL)

    # ======================================================

    

    # Retiro de estudiantes

    path('panel/eliminar-estudiante/', views.admin_eliminar_estudiante, name='panel_eliminar_estudiante'),

    

    # Generación de Boletines (Admin)

    path('panel/generar-boletin/<int:estudiante_id>/', views.generar_boletin_pdf_admin, name='panel_generar_boletin'),

    

    # API Toggle Boletín

    path('panel/api/toggle-boletin-permiso/', views.toggle_boletin_permiso, name='panel_api_toggle_boletin_permiso'),



    # Rutas Generales del Panel

    path('panel/gestion-perfiles/', views.gestion_perfiles, name='gestion_perfiles'),

    path('panel/resetear-contrasena/', views.admin_reset_password, name='admin_reset_password'),

    path('panel/db-visual/', views.admin_db_visual, name='admin_db_visual'),

    path('panel/ex-alumnos/', views.admin_ex_estudiantes, name='admin_ex_estudiantes'),

    

    # Seguridad de cuenta

    path('cuenta/cambiar-clave/', views.cambiar_clave, name='cambiar_clave'),



    # Ruta de Acudiente (Boletín)

    path('acudiente/generar-boletin/<int:estudiante_id>/', views.generar_boletin_pdf_acudiente, name='generar_boletin_acudiente'),



    # ======================================================

    # MÓDULO BIENESTAR, CONVIVENCIA E INTELIGENCIA

    # ======================================================

    

    # Panel Principal

    path('bienestar/dashboard/', views.dashboard_bienestar, name='dashboard_bienestar'),

    

    # 🧠 Inteligencia Académica

    path('bienestar/inteligencia-academica/', views.dashboard_academico, name='dashboard_academico'),



    # 📊 Historial de Asistencia

    path('bienestar/historial-asistencia/', views.historial_asistencia, name='historial_asistencia'),

    

    # Historial de Observador y Operaciones

    path('bienestar/alumno/<int:estudiante_id>/', views.ver_observador, name='ver_observador'),

    path('bienestar/crear/<int:estudiante_id>/', views.crear_observacion, name='crear_observacion'),

    path('bienestar/editar/<int:observacion_id>/', views.editar_observacion, name='editar_observacion'),



    # PDF Observador Oficial

    path('pdf/observador/<int:estudiante_id>/', views.generar_observador_pdf, name='generar_observador_pdf'),



    # Gestión de Staff (Psicólogos, Coords)

    path('panel/gestionar-staff/', views.gestionar_staff, name='gestionar_staff'),

    

    # Desactivar Staff

    path('panel/staff/desactivar/<int:user_id>/', views.desactivar_staff, name='desactivar_staff'),

    

    # API Bloqueo Observador (Admin)

    path('panel/api/toggle-observador-permiso/', views.toggle_observador_permiso, name='panel_api_toggle_observador'),



    # ======================================================

    # 🩺 COMUNICACIÓN Y ASISTENCIA

    # ======================================================

    

    # 1. API Asistencia (Usada por el Modal en subir_notas)

    path('api/asistencia/', views.api_tomar_asistencia, name='api_tomar_asistencia'),



    # 2. Rutas Chat Profesional

    path('chat/buzon/', views.buzon_mensajes, name='buzon_mensajes'),

    path('chat/enviar/', views.enviar_mensaje, name='enviar_mensaje'),

    path('chat/leer/<int:mensaje_id>/', views.leer_mensaje, name='leer_mensaje'),



    # ======================================================

    # 🚀 RED SOCIAL & GRUPOS (FASE IV & V)

    # ======================================================

    

    path('social/feed/', views.social_feed, name='social_feed'),

    

    # 🔥 CORRECCIÓN: Descomentada y activa para que funcione el perfil

    path('social/profile/<str:username>/', views.ver_perfil_social, name='ver_perfil_social'),

    

    path('social/editar/', views.editar_perfil, name='editar_perfil'),

    

    # Buscador Global

    path('search/', views.global_search, name='global_search'),

    

    # APIs AJAX (Reacciones, Moderación, Follow)

    path('api/social/reaction/', views.api_reaction, name='api_reaction'),

    path('api/social/follow/', views.toggle_follow, name='api_toggle_follow'),

    path('api/social/moderate/', views.moderar_eliminar_contenido, name='moderar_eliminar_contenido'),



    # 🔥 RUTAS DE GRUPOS

    path('social/grupos/', views.lista_grupos, name='lista_grupos'),

    path('social/grupos/crear/', views.crear_grupo, name='crear_grupo'),

    path('social/grupos/<int:grupo_id>/', views.detalle_grupo, name='detalle_grupo'),

    path('social/grupos/<int:grupo_id>/unirse/', views.unirse_grupo, name='unirse_grupo'),



    # ======================================================

    # APIS INTERNAS (EXISTENTES)

    # ======================================================

    path('api/crear-curso/', views.api_crear_curso, name='api_crear_curso'),

    path('api/asignar-director/', views.api_asignar_director, name='api_asignar_director'),

    path('api/matricular/', views.matricular_estudiante, name='matricular_estudiante'),

    path('api/mover-estudiante/', views.api_mover_estudiante, name='api_mover_estudiante'),

    path('panel/reporte-consolidado/', views.reporte_consolidado, name='reporte_consolidado'),

    path('sabana-notas/', views.sabana_notas, name='sabana_notas'),

    

    # Esta línea estaba duplicada (ya está arriba), la dejo por seguridad aunque no es necesario

    path('social/perfil/editar/', views.editar_perfil, name='editar_perfil_alt'), # Renombrado name para evitar conflicto

    

    path('notificaciones/historial/', views.historial_notificaciones, name='historial_notificaciones'),

    path('social/comentario/<int:post_id>/', views.crear_comentario, name='crear_comentario'),

    path('social/grupos/<int:grupo_id>/eliminar/', eliminar_grupo, name='eliminar_grupo'),

    #estas 2 lineas linea 

    path('toggle-follow/', views.toggle_follow, name='toggle_follow'),

    #path('mark-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),

    #path('acudiente/observador/<int:estudiante_id>/', views.descargar_observador, name='descargar_observador'),

    path('acudiente/descargar-observador/<int:estudiante_id>/', views.descargar_observador_acudiente, name='descargar_observador_acudiente'),

    path('acudiente/descargar-observador/<int:estudiante_id>/', views.descargar_observador_acudiente, name='descargar_observador_acudiente'),

    path('notifications/mark-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),

    path('api/estudiantes-por-curso/<int:curso_id>/', views.api_get_students_by_course, name='api_get_students_by_course'),

    path('api/periodos/', views.cargar_periodos_por_curso, name='api_cargar_periodos'),

    path('prueba-ia/', views.test_ai_connection, name='test_ai'),

    path('orientacion/inteligente/', views.dashboard_ia_estudiante, name='dashboard_ia'),

    path('orientacion/inteligente/', views.test_ai_connection, name='orientacion_inteligente'),

    #path('orientacion/inteligente/', views.orientacion_inteligente_view, name='orientacion_inteligente'),

    path('api/chat-socratico/', ai_views.chat_socratico_api, name='api_chat_socratico'),

    path('ia/engine/', views.ai_analysis_engine, name='ai_engine'),

    #path('ia/engine/', views.ai_analysis_engine, name='ai_analysis_engine'),

    path('api/social/post/<int:post_id>/likes/', views.api_obtener_likes, name='api_post_likes'),

    path('ia/reporte/pdf/', views.download_ai_report_pdf, name='download_ai_report_pdf'),

    path('institucion/documentos/', views.ver_documentos_institucionales, name='documentos_institucionales'),

    path('bienestar/historial-global/', views.historial_global_observaciones, name='historial_global_observaciones'),

    path('guardar-seguimiento/', views.guardar_seguimiento, name='guardar_seguimiento'),

]