from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    # ⚠️ IMPORTANTE: ajusta esta dependencia al ÚLTIMO archivo ya aplicado en tu proyecto.
    # Si tu última fue '0003_fix_materia_curso_column_db_only', déjala así.
    # Si fue otra, cámbiala.
    dependencies = [
        ('tasks', '0003_add_curso_field_to_materia'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name='materia',
                    name='curso',
                    field=models.ForeignKey(
                        to='tasks.curso',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='materias',
                        verbose_name='Curso',
                    ),
                ),
            ],
        ),
    ]
