FROM python:3.11-slim

WORKDIR /app

# Copy requirements first (before app code) so Docker can cache this layer.
# If your code changes but requirements don't, this step is skipped on rebuild = faster builds.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the actual application code
COPY . .

# The port the app listens on inside the container
EXPOSE 8002

# Same command you've been running manually with uvicorn,
# except --host 0.0.0.0 is required here so the container accepts
# connections from outside itself (127.0.0.1 alone won't work in Docker)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]