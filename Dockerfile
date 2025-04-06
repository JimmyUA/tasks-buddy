# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
# Port that Cloud Run expects the container to listen on
ENV PORT 8080

# Set the working directory in the container
WORKDIR /code

# Install system dependencies if any (e.g., for libraries that need C extensions)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# Copy the dependencies file to the working directory
COPY ./requirements.txt /code/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY ./ /code
# Copy the .env file IF needed AND you understand the security implications
# (Generally better to use Cloud Run secrets or env vars for production)
# COPY ./.env /code/.env
# IMPORTANT: DO NOT copy the service account key file into the image.
# Use Cloud Run's ability to mount secrets or use the service account identity.

# Command to run the application using uvicorn
# Use 0.0.0.0 to listen on all network interfaces within the container
# Use the PORT environment variable provided by Cloud Run
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]