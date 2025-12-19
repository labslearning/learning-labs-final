# tasks/ai_views.py

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
import json

from .ai.orchestrator import ai_orchestrator
from .ai.constants import ACCION_CHAT_SOCRATICO

@login_required
@require_POST
def chat_socratico_api(request):
    try:
        data = json.loads(request.body)
        mensaje_usuario = data.get('mensaje')
        materia_actual = data.get('materia', 'General')
        
        if not mensaje_usuario:
            return JsonResponse({"error": "Mensaje vacío"}, status=400)

        resultado = ai_orchestrator.process_request(
            user=request.user,
            action_type=ACCION_CHAT_SOCRATICO,
            user_query=mensaje_usuario,
            materia_actual=materia_actual,
            temperature=0.6
        )

        if resultado['success']:
            return JsonResponse({
                "status": "success",
                "respuesta": resultado['content'],
                "meta": resultado['meta']
            })
        else:
            return JsonResponse({
                "status": "error",
                "mensaje": resultado['content'],
                "tipo_error": resultado['source']
            }, status=403 if resultado['source'] == 'POLICY' else 500)

    except Exception as e:
        return JsonResponse({"error": f"Error interno: {str(e)}"}, status=500)
