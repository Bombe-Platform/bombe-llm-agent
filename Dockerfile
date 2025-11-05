# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container at /app
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Set the command to run the application
# Use Gunicorn with 1 worker (Cloud Run handles horizontal scaling at instance level)
# Binds to PORT environment variable (Cloud Run sets this dynamically, defaults to 8080)
# 240s timeout allows for long-running LLM queries, graceful shutdown after 30s
CMD ["sh", "-c", "gunicorn -w 1 -k uvicorn.workers.UvicornWorker --timeout 240 --graceful-timeout 30 -b 0.0.0.0:${PORT:-8080} main:app"]
