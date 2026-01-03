from celery import shared_task
from .etl import JoplinETL
from .models import JoplinUpload

@shared_task
def process_database_task(upload_id: int) -> None:
    """
    Celery task to process an uploaded Joplin database.
    
    Args:
        upload_id: The ID of the JoplinUpload instance to process.
    """
    print(f"Starting processing for upload {upload_id}")
    try:
        etl = JoplinETL(upload_id)
        etl.process()
        print(f"Finished processing for upload {upload_id}")
    except Exception as e:
        print(f"Error processing upload {upload_id}: {e}")
