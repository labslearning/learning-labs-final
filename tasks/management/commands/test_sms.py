from django.core.management.base import BaseCommand
from django.conf import settings
from twilio.rest import Client

class Command(BaseCommand):
    help = 'Envía un SMS personalizado desde la terminal para Nemesis Software'

    def add_arguments(self, parser):
        # El número de destino se pasa al ejecutar el comando
        parser.add_argument('numero_destino', type=str, help='Número destino (ej: +573132533008)')

    def handle(self, *args, **options):
        destinatario = options['numero_destino']

        # --- INTERFAZ NEMESIS SOFTWARE ---
        self.stdout.write(self.style.SUCCESS("\n" + "="*40))
        self.stdout.write(self.style.SUCCESS("🛡️  NEMESIS SOFTWARE - SMS GATEWAY"))
        self.stdout.write(self.style.SUCCESS("="*40))
        self.stdout.write(f"Destinatario: {destinatario}")
        
        # Pedir el mensaje por teclado
        mensaje_interactivo = input("\n📝 Escribe el mensaje que quieres enviar: ")

        # Verificar que no esté vacío
        if not mensaje_interactivo.strip():
            self.stdout.write(self.style.ERROR("❌ Error: No puedes enviar un mensaje vacío."))
            return

        try:
            # Inicializar el cliente de Twilio con tus credenciales de settings.py
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            
            self.stdout.write(f"📡 Conectando con Twilio...")

            # Enviar el mensaje
            message = client.messages.create(
                body=mensaje_interactivo,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=destinatario
            )

            # Confirmación de éxito
            self.stdout.write(self.style.SUCCESS(f'\n✅ ¡Mensaje aceptado por Twilio!'))
            self.stdout.write(f"🆔 SID: {message.sid}")
            self.stdout.write(f"💬 Texto: {mensaje_interactivo}")
            self.stdout.write(self.style.SUCCESS("="*40 + "\n"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error crítico de Nemesis Software: {str(e)}'))