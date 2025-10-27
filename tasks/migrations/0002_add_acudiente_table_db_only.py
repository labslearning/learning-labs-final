from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # Cambios SOLO en la base de datos (no tocamos el "state" de Django)
            database_operations=[
                migrations.CreateModel(
                    name='Acudiente',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('creado_en', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')),
                        ('acudiente', models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='estudiantes_a_cargo',
                            limit_choices_to={'perfil__rol': 'ACUDIENTE'},
                            to=settings.AUTH_USER_MODEL,
                            verbose_name='Usuario Acudiente'
                        )),
                        ('estudiante', models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='acudientes_asignados',
                            limit_choices_to={'perfil__rol': 'ESTUDIANTE'},
                            to=settings.AUTH_USER_MODEL,
                            verbose_name='Usuario Estudiante'
                        )),
                    ],
                    options={
                        'verbose_name': 'Vínculo Acudiente-Estudiante',
                        'verbose_name_plural': 'Vínculos Acudiente-Estudiante',
                        'unique_together': {('acudiente', 'estudiante')},
                    },
                ),
            ],
            state_operations=[
                # No hacemos nada en el "state" porque Django ya cree que Acudiente existe desde 0001.
            ],
        ),
    ]
