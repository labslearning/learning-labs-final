# tasks/ai/deepseek_client.py

import requests
from django.conf import settings
from .constants import MODEL_NAME


class DeepSeekClient:
    """
    CLIENTE HTTP PURO PARA DEEPSEEK.
    """

    API_URL = "https://api.deepseek.com/chat/completions"
    TIMEOUT_SECONDS = 45

    def get_completion(self, messages_list, config=None):
        """
        Envía mensajes a DeepSeek y retorna respuesta + uso de tokens.
        """

        # ------------------------------------------------------------------
        # 1. VALIDACIÓN DE API KEY (CORREGIDA)
        # ------------------------------------------------------------------
        # Buscamos el nombre de la variable definida en settings.py
        api_key = getattr(settings, "DEEPSEEK_API_KEY", None)
        
        if not api_key:
            return {
                "success": False,
                "error": "Error de configuración: DEEPSEEK_API_KEY no definida en settings.py"
            }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # ------------------------------------------------------------------
        # 2. CONFIGURACIÓN BASE + OVERRIDE
        # ------------------------------------------------------------------
        final_config = {
            "temperature": 0.7,
            "max_tokens": 1500,
            "top_p": 1.0,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0
        }

        if isinstance(config, dict):
            final_config.update(config)

        payload = {
            "model": MODEL_NAME,
            "messages": messages_list,
            "stream": False,
            **final_config
        }

        # ------------------------------------------------------------------
        # 3. LLAMADA HTTP
        # ------------------------------------------------------------------
        try:
            response = requests.post(
                self.API_URL,
                json=payload,
                headers=headers,
                timeout=self.TIMEOUT_SECONDS
            )

            # --------------------------------------------------------------
            # 4. MANEJO DE ERRORES DE SALDO O API
            # --------------------------------------------------------------
            if response.status_code != 200:
                error_msg = response.text
                # Simplificar mensajes comunes para el usuario
                if "insufficient_balance" in error_msg:
                    error_msg = "Saldo insuficiente en la cuenta de DeepSeek. Por favor recarga créditos."
                
                return {
                    "success": False,
                    "error": f"DeepSeek API Error {response.status_code}: {error_msg}"
                }

            # --------------------------------------------------------------
            # 5. PROCESAR RESPUESTA EXITOSA
            # --------------------------------------------------------------
            data = response.json()

            try:
                ai_message = data["choices"][0]["message"]["content"]
                usage_data = data.get("usage", {})
                request_id = data.get("id", "unknown_request_id")
            except (KeyError, IndexError):
                return {
                    "success": False,
                    "error": "Formato inesperado en la respuesta de DeepSeek."
                }

            return {
                "success": True,
                "content": ai_message,
                "request_id": request_id,
                "usage": {
                    "prompt_tokens": usage_data.get("prompt_tokens", 0),
                    "completion_tokens": usage_data.get("completion_tokens", 0),
                    "total_tokens": usage_data.get("total_tokens", 0)
                }
            }

        # ------------------------------------------------------------------
        # 6. MANEJO DE EXCEPCIONES DE RED
        # ------------------------------------------------------------------
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Timeout: La IA tardó demasiado en responder."}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "Error de conexión: Verifica tu internet."}
        except Exception as e:
            return {"success": False, "error": f"Error inesperado: {str(e)}"}


# INSTANCIA GLOBAL
deepseek_client = DeepSeekClient()