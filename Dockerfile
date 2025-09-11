# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies.
# Although I switched to mysql-connector-python, it's good practice
# to document and install any required build-time dependencies here.
# For now, none are needed for the python packages.

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Expose port 8000
EXPOSE 8000

# Default command to run the application
# For production, this should be replaced with a proper WSGI server like Gunicorn.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
