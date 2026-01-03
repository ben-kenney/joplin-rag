# Joplin RAG Search

A Django-based web application that enables semantic search over your Joplin notes using Retrieval-Augmented Generation (RAG).

## Features

-   **SQLite Upload**: Securely upload your Joplin `database.sqlite` file.
-   **Semantic Search**: Search your notes using natural language queries, powered by OpenAI embeddings.
-   **OCR Integration**: Automatically indexes text extracted from images in your notes (requires Joplin's OCR feature to be active).
-   **Deep Linking**: Search results include deep links (`joplin://`) to open notes directly in your local Joplin desktop application.
-   **Efficient Processing**: Uses an ETL pipeline to process uploads in the background and only re-indexes modified notes.

## Architecture

This project uses a modern Python stack:

-   **Backend**: Django 5.0
-   **Database**: PostgreSQL with `pgvector` extension (for vector similarity search).
-   **Task Queue**: Celery with Redis (for asynchronous background processing).
-   **Dependency Management**: `uv` and `pyproject.toml`.
-   **AI/ML**: OpenAI `text-embedding-ada-002` for generating embeddings.

### How it Works

1.  **Upload**: You upload your `database.sqlite` file via the web interface.
2.  **ETL Process** (Background Task):
    -   The system reads notes and resources from the SQLite file.
    -   It merges OCR text from resources into the note body.
    -   Content is split into chunks.
    -   Embeddings are generated for each chunk using OpenAI.
    -   Metadata and Embeddings are stored in PostgreSQL (`pgvector`).
    -   *Note*: To respect privacy and storage, full note content is **not** duplicated in the Postgres database; it reads from the uploaded SQLite file on demand.
3.  **Search**:
    -   Your query is embedded.
    -   A vector similarity search runs against the PostgreSQL database.
    -   Results are ranked and presented with links to open them in Joplin.

## Development Setup

### Prerequisites

-   Docker & Docker Compose
-   OpenAI API Key

### Configuration

1.  **Environment Variables**:
    Copy the template and fill in your values.
    ```bash
    cp .env.template .env
    ```
    Ensure you set `OPENAI_API_KEY`. The database credentials in `.env.template` are set up for the Docker environment.

2.  **Start the Application**:
    ```bash
    docker-compose up --build
    ```

3.  **Run Migrations**:
    ```bash
    docker-compose exec web uv run python src/manage.py migrate
    ```

4.  **Create Admin User**:
    ```bash
    docker-compose exec web uv run python src/manage.py createsuperuser
    ```

5.  **Access**:
    -   Web App: http://localhost:8000
    -   Admin Panel: http://localhost:8000/admin

## Usage

1.  **Login/Signup**: Create an account or log in.
2.  **Upload Database**: Go to the "Upload" tab. Select your `database.sqlite` file (usually found in `~/.config/joplin-desktop/` on Linux).
3.  **Wait for Processing**: The system will process your notes in the background. This may take a few minutes depending on the size of your database.
4.  **Search**: Go to the "Search" tab. Enter a query (e.g., "receipts from last month" or "project ideas").
5.  **Open in Joplin**: Click the "Open in Joplin" button on a result to view the note in your desktop app.
