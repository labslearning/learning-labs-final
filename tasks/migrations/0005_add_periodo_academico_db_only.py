from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0004_sync_materia_curso_field'),  # <-- AJUSTA si tu última migración tiene otro nombre/numero
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema='public'
                      AND table_name='tasks_asignacionmateria'
                      AND column_name='periodo_academico'
                ) THEN
                    ALTER TABLE public.tasks_asignacionmateria
                    ADD COLUMN periodo_academico varchar(20) NOT NULL DEFAULT '2025-1';
                END IF;
            END $$;
            """,
            reverse_sql="""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema='public'
                      AND table_name='tasks_asignacionmateria'
                      AND column_name='periodo_academico'
                ) THEN
                    ALTER TABLE public.tasks_asignacionmateria
                    DROP COLUMN periodo_academico;
                END IF;
            END $$;
            """
        ),
    ]
