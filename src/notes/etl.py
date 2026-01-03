import sqlite3
import os
import re
from datetime import datetime
import pytz
from django.utils import timezone
from langchain_text_splitters import RecursiveCharacterTextSplitter
from django.conf import settings
from .models import NoteMetadata, NoteChunk, JoplinUpload
import openai

def get_process_time(timestamp_ms):
    """Convert Joplin timestamp (ms) to aware datetime."""
    if not timestamp_ms:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000.0, tz=pytz.UTC)

class JoplinETL:
    def __init__(self, upload_id):
        self.upload = JoplinUpload.objects.get(id=upload_id)
        self.db_path = self.upload.file.path
        self.openai_api_key = settings.OPENAI_API_KEY
        
        if not self.openai_api_key:
             print("Warning: OPENAI_API_KEY not found. Embeddings will fail if not using a mock.")

    def process(self):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Map Resources (OCR Text) -> Note IDs
            # Joplin stores links in note_resources
            print("Fetching resources...")
            cursor.execute("""
                SELECT nr.note_id, r.id as resource_id, r.ocr_text
                FROM resources r
                JOIN note_resources nr ON r.id = nr.resource_id
                WHERE r.ocr_text != '' AND r.ocr_text IS NOT NULL
            """)
            note_resources = {}
            for row in cursor.fetchall():
                note_id = row['note_id']
                if note_id not in note_resources:
                    note_resources[note_id] = {}
                # Store mapping of resource_id -> ocr_text
                note_resources[note_id][row['resource_id']] = row['ocr_text']

            # 2. Fetch Notes
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
                self.process_note(note, note_resources.get(note['id'], {}))
            
            self.upload.processed = True
            self.upload.new_notes_count = self.new_count
            self.upload.updated_notes_count = self.updated_count
            self.upload.save()
            conn.close()
            
        except Exception as e:
            self.upload.error_message = str(e)
            self.upload.save()
            raise e

    def process_note(self, note_row, resources_map):
        joplin_id = note_row['id']
        title = note_row['title']
        body = note_row['body']
        updated_ms = note_row['updated_time']
        updated_dt = get_process_time(updated_ms)
        parent_id = note_row['parent_id']

        # Check existing metadata
        metadata, created = NoteMetadata.objects.get_or_create(
            user=self.upload.user,
            joplin_id=joplin_id,
            defaults={
                'title': title,
                'last_updated': updated_dt,
                'parent_id': parent_id
            }
        )

        # If not created, check if update is needed
        force_update = False
        
        # Check if we need to force update because of broken links in existing data
        # This is a migration helper: if current chunks contain raw joplin links like ](:/ or old formatting, re-process.
        # We check the first chunk as a proxy or filter.
        if not created and not force_update:
             if metadata.chunks.filter(content__contains="](:/").exists() or metadata.chunks.filter(content__contains="**Image Text:**").exists():
                 print(f"Force updating {title} to fix links/format...")
                 force_update = True

        if not created and not force_update:
            if metadata.last_updated and updated_dt <= metadata.last_updated:
                # Already up to date
                return
            
        if not created: 
            # Update needed: delete old chunks and update metadata
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

        # Prepare Content
        # Substitute resource links with OCR text if available
        # Joplin links format: [title](:/resource_id) or ![title](:/resource_id)
        
        def replace_resource(match):
            # match.group(1) is alt text
            alt_text = match.group(1)
            # match.group(2) is resource_id
            resource_id = match.group(2)
            
            if resource_id in resources_map:
                ocr_text = resources_map[resource_id]
                # Return just the OCR text, cleaner integration
                return f"\n{ocr_text}\n"
            
            # Fallback: OCR missing. Replace with placeholder to avoid broken link image.
            return f" [Image: {alt_text}] "

        # Regex to match markdown links/images to local resources
        # Matches ![alt](:/id) or [alt](:/id)
        full_text = re.sub(r'!\[(.*?)\]\(:\/([a-zA-Z0-9]{32})\)', replace_resource, body)
        
        # We can also do non-image links if desired, but usually OCR is for images
        # full_text = re.sub(r'\[(.*?)\]\(:\/([a-zA-Z0-9]{32})\)', replace_resource, full_text)

        # Split Text
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
            # Using OpenAI client directly or langchain wrapper
            # Let's use OpenAI client for pgvector compatibility (list of floats)
            client = openai.OpenAI(api_key=self.openai_api_key)
            
            # Batch embedding generation could be better, but doing per note for simplicity now
            # Or map over texts
            try:
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
                
                NoteChunk.objects.bulk_create(chunks_to_create)
                
            except Exception as e:
                print(f"Error generating embeddings for {title}: {e}")
        else:
            # Mock or skip
             print(f"Skipping embeddings for {title} (No API Key)")
