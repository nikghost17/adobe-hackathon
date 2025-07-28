# Use a specific, lightweight Python base image compatible with AMD64 architecture
# The --platform flag is crucial for compatibility with the judging environment.
FROM --platform=linux/amd64 python:3.9-slim

# Set the working directory inside the container to /app
WORKDIR /app

# Copy the requirements file first to leverage Docker's build cache.
# The dependencies will only be re-installed if this file changes.
COPY requirements.txt .

# Install all Python dependencies required by your full script.
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy all necessary application files and models ---

# Copy your Python scripts into the container's working directory (/app)
COPY main.py .
COPY parsing.py .

# Copy the 'models' directory and its contents into the container at /app/models/.
# This is essential for your first pipeline (`pdf_processing_pipeline`) to find the .pkl files.
COPY models/ ./models/


CMD ["python", "main.py"]