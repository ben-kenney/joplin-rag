from typing import Any, Dict, List, Optional
import sqlite3
import os
from datetime import datetime
import pytz
from django.utils import timezone
from langchain_text_splitters import RecursiveCharacterTextSplitter
from django.conf import settings
from .models import NoteMetadata, NoteChunk, JoplinUpload
import openai

def get_process_time(timestamp_ms: Optional[int]) -> datetime:
    """
    Convert a Joplin timestamp (in milliseconds) to an aware UTC datetime object.

    Args:
        timestamp_ms: The timestamp from the Joplin database.

    Returns:
        An aware datetime object in UTC. Returns epoch start if input is None.
    """
    if not timestamp_ms:
        return datetime.fromtimestamp(0, tz=pytz.UTC)
    return datetime.fromtimestamp(timestamp_ms / 1000.0, tz=pytz.UTC)

class JoplinETL:
    """
    Extract, Transform, and Load logic for Joplin SQLite databases.
    Reads notes and resources from the SQLite file, generates embeddings,
    and stores them in the Django database.
    """

    def __init__(self, upload_id: int):
        """
        Initialize the ETL process for a specific upload.

        Args:
            upload_id: The ID of the JoplinUpload instance to process.
        """
        self.upload: JoplinUpload = JoplinUpload.objects.get(id=upload_id)
        self.db_path: str = self.upload.file.path
        self.openai_api_key: Optional[str] = settings.OPENAI_API_KEY
        self.new_count: int = 0
        self.updated_count: int = 0
        
        if not self.openai_api_key:
             print("Warning: OPENAI_API_KEY not found. Embeddings will fail if not using a mock.")

    def process(self) -> None:
        """
        Main entry point for the ETL process.
        Connects to the SQLite DB, maps resources to notes, and processes each note.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Map Resources (OCR Text) -> Note IDs
            # Joplin stores the relationship in the note_resources table.
            # We only CARE about resources that have OCR text (images that were processed).
            print("Fetching resources...")
            cursor.execute("""
                SELECT nr.note_id, r.ocr_text, r.title 
                FROM resources r
                JOIN note_resources nr ON r.id = nr.resource_id
                WHERE r.ocr_text != '' AND r.ocr_text IS NOT NULL
            """)
            note_resources: Dict[str, List[str]] = {}
            for row in cursor.fetchall():
                note_id = row['note_id']
                if note_id not in note_resources:
                    note_resources[note_id] = []
                note_resources[note_id].append(row['ocr_text'])

            # 2. Fetch Notes
            # We only want notes that haven't been deleted.
            print("Fetching notes...")
            cursor.execute("""
                SELECT id, title, body, updated_time, parent_id 
                FROM notes 
                WHERE deleted_time = 0
            """)
            
            notes = cursor.fetchall()
            print(f"Found {len(notes)} notes.")

            # 3. Process Each Note
            self.new_count = 0
            self.updated_count = 0
            
            for note in notes:
                self.process_note(note, note_resources.get(note['id'], []))
            
            # Update upload status and statistics
            self.upload.processed = True
            self.upload.new_notes_count = self.new_count
            self.upload.updated_notes_count = self.updated_count
            self.upload.save()
            conn.close()
            
        except Exception as e:
            # Store error message in the upload instance for user feedback
            self.upload.error_message = str(e)
            self.upload.save()
            raise e

    def process_note(self, note_row: sqlite3.Row, ocr_texts: List[str]) -> None:
        """
        Process a single note row from the SQLite database.
        Checks for updates, splits text into chunks, and generates embeddings.

        Args:
            note_row: A dictionary-like row from the 'notes' table.
            ocr_texts: A list of OCR text fragments associated with this note.
        """
        joplin_id = note_row['id']
        title = note_row['title']
        body = note_row['body']
        updated_ms = note_row['updated_time']
        updated_dt = get_process_time(updated_ms)
        parent_id = note_row['parent_id']

        # Check existing metadata in our Django DB
        metadata, created = NoteMetadata.objects.get_or_create(
            user=self.upload.user,
            joplin_id=joplin_id,
            defaults={
                'title': title,
                'last_updated': updated_dt,
                'parent_id': parent_id
            }
        )

        # If not created, check if update is needed (based on last_updated timestamp)
        if not created:
            if metadata.last_updated and updated_dt <= metadata.last_updated:
                # Already up to date, skip processing
                return
            
            # Update needed: delete old chunks and update metadata info
            print(f"Updating note {title}...")
            metadata.chunks.all().delete()
            metadata.title = title
            metadata.last_updated = updated_dt
            metadata.parent_id = parent_id
            metadata.save()
            self.updated_count += 1
        else:
            print(f"New note {title}...")
            self.new_count += 1

        # Prepare full content by appending OCR text from images to the end of the note
        full_text = body + "\n\n"
        if ocr_texts:
            full_text += "--- OCR TEXT FROM IMAGES ---\n"
            full_text += "\n\n".join(ocr_texts)

        # Split Text into manageable segments for embedding
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        texts = text_splitter.split_text(full_text)

        # Generate Embeddings & Save Chunks
        if not texts:
            return

        if self.openai_api_key:
            client = openai.OpenAI(api_key=self.openai_api_key)
            
            try:
                # Generate embeddings for all chunks in one batch
                response = client.embeddings.create(input=texts, model="text-embedding-ada-002")
                embeddings = [data.embedding for data in response.data]
                
                chunks_to_create = []
                for i, (text, embedding) in enumerate(zip(texts, embeddings)):
                    chunks_to_create.append(NoteChunk(
                        note=metadata,
                        chunk_index=i,
                        content=text,
                        embedding=embedding
                    ))
                
                # Bulk create for performance
                NoteChunk.objects.bulk_create(chunks_to_create)
                
            except Exception as e:
                print(f"Error generating embeddings for {title}: {e}")
        else:
             print(f"Skipping embeddings for {title} (No API Key)")
