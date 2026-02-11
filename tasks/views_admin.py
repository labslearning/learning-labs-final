import datetime
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.views.decorators.http import require_POST


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.db import transaction

# Importamos el modelo y servicio evolucionado
from tasks.models import BovedaSeguridad
from tasks.services.vault import VaultManagerService



# Importaciones de modelos y servicios de arquitectura
from tasks.models import CierreAnualLog
from tasks.services.rollover import YearRolloverService, ReverseProtocolService

# --- DECORADORES DE SEGURIDAD ---
def is_superuser(user):
    """
    Gatekeeper: Verifica que el usuario sea Super Administrador (Rector/IT).
    Nadie más debe tener acceso a estos controles nucleares.
    """
    return user.is_active and user.is_superuser

# ==============================================================================
# 🦅 SALA DE GUERRA: CONTROL DE CIERRE
# ==============================================================================
@login_required
@user_passes_test(is_superuser)
def panel_cierre_anual(request):
    """
    Vista principal para gestionar el cierre de ciclo escolar.
    Muestra el estado actual y el historial de operaciones.
    """
    anio_actual = datetime.datetime.now().year
    anio_nuevo = anio_actual + 1
    
    if request.method == 'POST':
        # 1. CAPTCHA HUMANO (Verificación de Seguridad)
        confirmacion = request.POST.get('frase_confirmacion', '').strip()
        frase_esperada = f"CERRAR {anio_actual}"
        
        if confirmacion != frase_esperada:
            messages.error(request, f"⛔ ALERTA DE SEGURIDAD: La frase de confirmación es incorrecta. Se esperaba: '{frase_esperada}'")
            return redirect('panel_cierre_anual')
        
        # 2. EJECUCIÓN DEL PROTOCOLO (Llamada al Servicio)
        try:
            servicio = YearRolloverService(anio_actual, request.user)
            exito, mensaje, log_id = servicio.ejecutar_cierre()
            
            if exito:
                messages.success(request, f"✅ PROTOCOLO COMPLETADO: {mensaje}")
                messages.info(request, f"🎉 Bienvenido al Ciclo Escolar {anio_nuevo}. El sistema ha sido purgado y los históricos archivados.")
            else:
                messages.error(request, f"❌ ERROR CRÍTICO (ROLLBACK): El sistema se ha revertido automáticamente. Detalle: {mensaje}")
        except Exception as e:
            messages.error(request, f"🔥 FALLO DEL SISTEMA: {str(e)}")
            
        return redirect('panel_cierre_anual')

    # Recuperar historial de cierres para la tabla de auditoría
    # Usamos select_related para evitar consultas N+1 en la tabla
    historial_cierres = CierreAnualLog.objects.select_related('ejecutado_por').order_by('-fecha_ejecucion')[:10]
    
    context = {
        'anio_actual': anio_actual,
        'anio_siguiente': anio_nuevo,
        'historial': historial_cierres,
        'fecha_servidor': timezone.now()
    }
    return render(request, 'admin/cierre_anual.html', context)


# ==============================================================================
# ⏪ TIME MACHINE: REVERSIÓN DE EMERGENCIA
# ==============================================================================
@login_required
@user_passes_test(is_superuser)
@require_POST # Seguridad: Solo permite peticiones POST, bloquea acceso directo por URL
def revertir_cierre_anual(request, log_id):
    """
    Ejecuta la restauración de un backup previo.
    Solo puede ser invocado desde el botón de pánico en el historial.
    """
    try:
        # Instanciar el servicio de reversión
        servicio = ReverseProtocolService(log_id, request.user)
        exito, mensaje = servicio.ejecutar_reversion()
        
        if exito:
            messages.success(request, f"⏪ TIEMPO REVERTIDO: {mensaje}")
            messages.warning(request, "⚠️ El sistema ha regresado al estado anterior. Verifique que los datos sean correctos.")
        else:
            messages.error(request, f"❌ FALLO EN RESTAURACIÓN: {mensaje}")
            
    except CierreAnualLog.DoesNotExist:
        messages.error(request, "❌ Error: El registro de cierre solicitado no existe.")
    except Exception as e:
        messages.error(request, f"🔥 ERROR CRÍTICO DE SISTEMA: {str(e)}")
        
    return redirect('panel_cierre_anual')





# Helper de seguridad (Reutilizable)
def is_superuser(user):
    return user.is_active and user.is_superuser

@login_required
@user_passes_test(is_superuser)
def panel_boveda(request):
    """
    🛡️ CONTROLADOR DE CUSTODIA DIGITAL
    Gestiona la generación de snapshots inmutables y auditoría de integridad.
    """
    if request.method == 'POST':
        # 1. Validación de entrada profesional
        nombre = request.POST.get('nombre_respaldo', '').strip()
        if not nombre:
            nombre = f"RESPALDO_SISTEMA_{timezone.now().strftime('%Y%m%d_%H%M')}"
        
        # 2. Captura forense (Metadatos de red)
        # Obtenemos la IP real incluso tras un proxy (como Nginx o Railway)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        ip_cliente = x_forwarded_for.split(',')[0] if x_forwarded_for else request.META.get('REMOTE_ADDR')

        # 3. Orquestación del Servicio
        service = VaultManagerService(request.user, nombre, ip_cliente=ip_cliente)
        
        try:
            exito, resultado = service.generar_snapshot_militar()
            
            if exito:
                messages.success(
                    request, 
                    f"🛡️ Activo de Bóveda Sellado: '{nombre}'. Integridad verificada mediante SHA-256."
                )
            else:
                messages.error(request, f"❌ Fallo en la Bóveda: {resultado}")
                
        except Exception as e:
            messages.error(request, f"🔥 Error Crítico de Infraestructura: {str(e)}")
            
        return redirect('panel_boveda')

    # 4. Optimización de Query (Nivel Industrial)
    # Traemos solo los últimos 20, con select_related para evitar el problema de N+1 consultas
    respaldos = BovedaSeguridad.objects.select_related('generado_por').all()[:20]
    
    context = {
        'respaldos': respaldos,
        'config_seguridad': {
            'engine_version': '2.5.0-PRO',
            'last_sync': timezone.now(),
            'storage_status': 'ONLINE'
        }
    }
    
    return render(request, 'admin/boveda.html', context)

@login_required
@user_passes_test(is_superuser)
@require_POST
def verificar_integridad_respaldo(request, uuid_operacion):
    """
    Endpoint forense para verificar que un archivo no ha sido manipulado en el servidor.
    """
    respaldo = get_object_or_404(BovedaSeguridad, uuid_operacion=uuid_operacion)
    
    if respaldo.verificar_integridad():
        messages.success(request, f"✅ Integridad Confirmada: El hash SHA-256 coincide con el sello original.")
    else:
        messages.error(request, f"🚨 ALERTA DE SEGURIDAD: El archivo ha sido alterado o está corrupto.")
        
    return redirect('panel_boveda')