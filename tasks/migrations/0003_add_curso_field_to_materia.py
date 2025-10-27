from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0002_add_acudiente_table_db_only'),
    ]

    operations = [
        migrations.AddField(
            model_name='materia',
            name='curso',
            field=models.ForeignKey(
                to='tasks.curso',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='materias',
                null=True  # Lo ponemos null=True para que no falle al crear la columna
            ),
        ),
    ]
