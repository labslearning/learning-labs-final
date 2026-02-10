import logging
import datetime
from django.db import transaction
from tasks.models import ImportBatch, StagingRow, Perfil, HistorialAcademico
from .adapters.factory import AdapterFactory
from .quality import DataGuard
from .schema_learner import SchemaLearner

logger = logging.getLogger(__name__)

class ImportService:
    """
    🎻 ORQUESTADOR DE IMPORTACIÓN (ZERO-FAILURE)
    
    Gestiona el ciclo de vida completo:
    1. INGESTA: Subida, detección de formato y limpieza inicial (Staging).
    2. EJECUCIÓN: Aplicación de mapeo, validación de negocio y persistencia final.
    """

    def create_batch(self, file_obj, user, model_target: str, institucion_id=None) -> tuple[ImportBatch, dict]:
        """
        FASE 1: Subir -> Analizar -> Pre-guardar (Staging).
        """
        
        # 1. Obtener la herramienta correcta para leer el archivo
        adapter = AdapterFactory.get_adapter(file_obj)
        
        # 2. Extraer datos crudos
        df = adapter.extract_raw()
        total_rows = len(df)
        
        if total_rows == 0:
            raise ValueError("El archivo procesado está vacío o no contiene datos legibles.")

        # 3. Transacción Atómica: O se crea todo el staging o nada.
        with transaction.atomic():
            # A) Crear registro de auditoría
            batch = ImportBatch.objects.create(
                usuario=user,
                archivo_original=file_obj,
                nombre_archivo=file_obj.name,
                tipo_modelo=model_target,
                total_filas=total_rows,
                estado='MAPPING' 
            )

            # B) Volcado Masivo a Staging (Optimizado)
            raw_records = df.to_dict('records')
            staging_instances = []
            
            for idx, row_data in enumerate(raw_records):
                # DataGuard: Limpieza de llaves del diccionario
                clean_row = {DataGuard.clean_text(k): v for k, v in row_data.items()}
                
                staging_instances.append(
                    StagingRow(
                        batch=batch,
                        numero_fila=idx + 1,
                        data_original=clean_row,
                        es_valido=False 
                    )
                )
            
            # Bulk Create en lotes para no saturar memoria
            StagingRow.objects.bulk_create(staging_instances, batch_size=2000)

        logger.info(f"✅ Lote {batch.id} ingestada exitosamente. {total_rows} filas en staging.")

        # 4. Generar Inteligencia de Mapeo (Sugerencias)
        adapter_suggestions = adapter.infer_schema()
        final_suggestions = {}

        for col_name, meta in adapter_suggestions.items():
            known_field = SchemaLearner.get_historical_suggestion(col_name, model_target, institucion_id)
            
            if known_field:
                final_suggestions[col_name] = {
                    'tipo': 'APRENDIDO',
                    'campo_sugerido': known_field,
                    'confianza': 1.0
                }
            else:
                final_suggestions[col_name] = meta

        return batch, final_suggestions

    def execute_import(self, batch_id: str, mapping: dict) -> int:
        """
        FASE 2: Procesamiento y Escritura Final.
        Transforma los datos de Staging en registros reales de HistorialAcademico.
        """
        try:
            batch = ImportBatch.objects.get(id=batch_id)
        except ImportBatch.DoesNotExist:
            raise ValueError("El lote de importación no existe.")

        if batch.estado not in ['MAPPING', 'READY', 'FAILED']:
            raise ValueError(f"El lote no está en un estado válido para procesar (Estado: {batch.estado})")

        # 1. Aprender del mapeo del usuario (Memoria a Largo Plazo)
        for col_csv, field_sys in mapping.items():
            if field_sys:
                SchemaLearner.learn(
                    csv_header=col_csv, 
                    system_field=field_sys, 
                    model_type=batch.tipo_modelo
                )

        # 2. Identificar columna llave (ID Estudiante)
        col_id_estudiante = next((k for k, v in mapping.items() if v == 'CODIGO_ESTUDIANTE'), None)
        if not col_id_estudiante:
            raise ValueError("Configuración inválida: Falta mapear la columna 'Código/Identificación'.")

        processed_count = 0
        errores_count = 0
        
        # Usamos transacción atómica para garantizar integridad del lote
        with transaction.atomic():
            batch.estado = 'IMPORTING'
            batch.save()

            # Iteramos sobre filas pendientes
            # Optimización: Podríamos hacer pre-fetching de estudiantes aquí si fueran muchos
            for row in batch.filas_staging.filter(es_valido=False):
                raw = row.data_original
                
                # A) Identificación del Estudiante
                raw_id = raw.get(col_id_estudiante)
                student_code = DataGuard.clean_text(raw_id)
                
                if not student_code:
                    row.errores.append("Fila ignorada: No tiene código de estudiante.")
                    row.save()
                    errores_count += 1
                    continue

                # B) Búsqueda Robusta (Por Documento o Username)
                estudiante = Perfil.objects.filter(numero_documento=student_code).first()
                if not estudiante:
                    estudiante = Perfil.objects.filter(username=student_code).first()

                if not estudiante:
                    row.errores.append(f"Estudiante no encontrado en el sistema: {student_code}")
                    row.save()
                    errores_count += 1
                    continue

                # C) Extracción de Notas (Parsing)
                notas_extraidas = {}
                metadata_fuente = {} 

                for col_csv, target_field in mapping.items():
                    if target_field and target_field.startswith('MATERIA:'):
                        materia_nombre = target_field.split(':', 1)[1]
                        valor_raw = raw.get(col_csv)
                        valor_clean = DataGuard.clean_grade(valor_raw)
                        
                        # Solo guardamos datos significativos
                        if valor_clean > 0 or str(valor_raw).strip() in ['0', '0.0']:
                            notas_extraidas[materia_nombre] = valor_clean
                            metadata_fuente[materia_nombre] = str(valor_raw)

                if not notas_extraidas:
                    row.errores.append("Estudiante encontrado, pero sin notas válidas para importar.")
                    row.save()
                    errores_count += 1
                    continue

                # D) Versionado de Historial (Logica Snapshot)
                anio_actual = datetime.date.today().year
                
                # Buscar historial activo previo para desactivarlo (Soft Delete / Archivo)
                historial_previo = HistorialAcademico.objects.filter(
                    estudiante=estudiante,
                    anio_lectivo=anio_actual,
                    is_active=True
                ).select_for_update().first() # select_for_update evita condiciones de carrera

                version = 1
                parent = None
                
                if historial_previo:
                    historial_previo.is_active = False
                    historial_previo.save()
                    version = historial_previo.version + 1
                    parent = historial_previo

                # E) Creación del Nuevo Historial
                nuevo_historial = HistorialAcademico.objects.create(
                    estudiante=estudiante,
                    anio_lectivo=anio_actual,
                    nombre_institucion="Carga Masiva Excel", 
                    calificaciones_json=notas_extraidas,
                    meta_confianza=metadata_fuente,
                    version=version,
                    parent_version=parent,
                    lote_origen=batch,
                    is_active=True
                )

                # F) Actualizar Staging
                row.es_valido = True
                row.id_objeto_creado = str(nuevo_historial.id)
                row.errores = [] # Limpiar errores previos si hubo reintento
                row.save()
                
                processed_count += 1

            # Finalización del Lote
            batch.filas_procesadas = processed_count + errores_count
            batch.filas_exitosas = processed_count
            batch.filas_con_error = errores_count
            
            if processed_count > 0:
                batch.estado = 'COMPLETED'
            else:
                batch.estado = 'FAILED' # O 'COMPLETED' con 0 registros si así se desea manejar
                
            batch.save()
            
            logger.info(f"🏁 Importación finalizada. Éxitos: {processed_count}, Errores: {errores_count}")
            return processed_count