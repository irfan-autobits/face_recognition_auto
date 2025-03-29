# ARG BASE_IMAGE=nvidia/cuda:12.2.0-runtime-ubuntu20.04
ARG BASE_IMAGE=nvidia/cuda:12.2.0-devel-ubuntu20.04
FROM ${BASE_IMAGE}
# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies (including libgl1 for OpenCV)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    software-properties-common \
    tzdata \
    curl \
    python3 \
    python3-dev \
    python3-distutils \
    python3-pip \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Set the timezone to avoid interactive prompts
RUN ln -fs /usr/share/zoneinfo/Asia/Kolkata /etc/localtime && \
    echo "Asia/Kolkata" > /etc/timezone

# Upgrade pip and setuptools
RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools

# Install Python dependencies needed for your app
RUN pip install --no-cache-dir \
    flask \
    flask-cors \
    numpy \
    opencv-python \
    insightface \
    onnxruntime-gpu \
    uwsgi \
    python-dotenv

# Create a non-root user (appuser)
RUN useradd -m -s /bin/bash appuser

# Set the working directory and copy application code with proper ownership
WORKDIR /app
COPY --chown=appuser:appuser . /app

# Switch to the non-root user
USER appuser

# Expose the port
EXPOSE 5001

# Start uWSGI using the configuration file
CMD ["uwsgi", "--ini", "uwsgi.ini"]
