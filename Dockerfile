FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project definition
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-install-project

# Copy source code
COPY . .

# Set python path to include src
ENV PYTHONPATH="${PYTHONPATH}:/app/src"

# Run migrations and start server (default command, can be overridden)
CMD ["uv", "run", "python", "src/manage.py", "runserver", "0.0.0.0:8000"]
