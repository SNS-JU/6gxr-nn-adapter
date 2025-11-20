# Use official Python image
FROM python:3.12.3-slim

# Use Tini to properly forward signals to Waitress
RUN apt-get update && apt-get install tini -y

# Prevent Python from writing pyc files and buffering output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Copy dependency file first for better build caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Expose port
EXPOSE 5000

# Run Waitress in a sub-directory
WORKDIR /app/src

# Use Tini as the entry point for the Waitress process
ENTRYPOINT ["/usr/bin/tini", "--"]

# Run the NNA application in Waitress
CMD ["waitress-serve", "--listen=*:5000", "nna:app"]
