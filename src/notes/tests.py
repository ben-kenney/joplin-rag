from django.test import TestCase
from unittest.mock import MagicMock, patch
import sqlite3
import os
from .etl import JoplinETL
from .models import JoplinUpload, NoteMetadata, NoteChunk
from django.contrib.auth import get_user_model

User = get_user_model()

class ETLTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(email='test@example.com', password='password')
        # Create a dummy sqlite file
        self.db_path = 'test_joplin.sqlite'
        self.conn = sqlite3.connect(self.db_path)
        self.create_dummy_db()
        
        self.upload = JoplinUpload.objects.create(
            user=self.user,
            file=self.db_path # This simulates the file field path
        )
        
    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def create_dummy_db(self):
        cursor = self.conn.cursor()
        
        # Create tables
        cursor.execute("CREATE TABLE notes (id TEXT PRIMARY KEY, title TEXT, body TEXT, updated_time INT, parent_id TEXT, deleted_time INT DEFAULT 0)")
        cursor.execute("CREATE TABLE resources (id TEXT PRIMARY KEY, title TEXT, ocr_text TEXT)")
        cursor.execute("CREATE TABLE note_resources (note_id TEXT, resource_id TEXT)")
        
        # Insert data
        cursor.execute("INSERT INTO notes VALUES ('note1', 'Test Note', 'This is a test note body.', 1600000000000, 'folder1', 0)")
        cursor.execute("INSERT INTO resources VALUES ('res1', 'Screenshot', 'Extracted OCR Text')")
        cursor.execute("INSERT INTO note_resources VALUES ('note1', 'res1')")
        
        self.conn.commit()

    @patch('notes.etl.openai.OpenAI') 
    @patch('notes.etl.settings')
    def test_etl_process(self, mock_settings, mock_openai):
        # Mock settings
        mock_settings.OPENAI_API_KEY = 'fake-key'
        
        # Mock OpenAI embedding response
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_data = MagicMock()
        mock_data.embedding = [0.1] * 1536
        mock_response.data = [mock_data]
        mock_client.embeddings.create.return_value = mock_response
        
        # Initialize ETL
        etl = JoplinETL(self.upload.id)
        
        # Override db_path because FileField.path might point elsewhere in real run, 
        # but here we want our local dummy file
        etl.db_path = self.db_path
        
        # Run process
        etl.process()
        
        # Verify Metadata
        note = NoteMetadata.objects.get(joplin_id='note1')
        self.assertEqual(note.title, 'Test Note')
        self.assertEqual(note.user, self.user)
        
        # Verify Chunks
        chunks = NoteChunk.objects.filter(note=note)
        self.assertTrue(chunks.exists())
        
        # Check content logic (Body + OCR)
        first_chunk = chunks.first()
        self.assertIn("This is a test note body.", first_chunk.content)
        self.assertIn("Extracted OCR Text", first_chunk.content)
