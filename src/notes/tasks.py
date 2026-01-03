from celery import shared_task
from .etl import JoplinETL
from .models import JoplinUpload

@shared_task
def process_database_task(upload_id):
    print(f"Starting processing for upload {upload_id}")
    try:
        etl = JoplinETL(upload_id)
        etl.process()
        print(f"Finished processing for upload {upload_id}")
    except Exception as e:
        print(f"Error processing upload {upload_id}: {e}")
