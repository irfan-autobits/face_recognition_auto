# Base image with CUDA 11.8 and cuDNN 8
FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04

# System dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-dev \
    build-essential \    
    python3.10-venv \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    g++ \
    make \
    cmake \
    pkg-config \
    libpcre3-dev \    
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Configure CUDA environment
ENV CUDA_HOME=/usr/local/cuda
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
ENV PATH=/usr/local/cuda/bin:$PATH
ENV PATH="/home/appuser/.local/bin:$PATH"

# Install specific CUDA toolkit components
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    cuda-toolkit-11-8 \
    cuda-libraries-11-8 \
    cuda-nvtx-11-8 \
    libcublas-11-8 \
    libcublas-dev-11-8 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and setuptools for a smoother build process
RUN python3 -m pip install --upgrade pip setuptools

# Create symbolic links for compatibility
RUN ln -s /usr/local/cuda-11.8 /usr/local/cuda && \
    ln -s /usr/lib/x86_64-linux-gnu/libcublas.so.11 /usr/lib/x86_64-linux-gnu/libcublas.so && \
    ln -s /usr/lib/x86_64-linux-gnu/libcublasLt.so.11 /usr/lib/x86_64-linux-gnu/libcublasLt.so

# Create application user
RUN useradd -m appuser
RUN usermod -aG video appuser

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Pre-download models
RUN python3 -c "from storage import ensure_available; ensure_available('models', 'buffalo_l', root='/home/appuser/.insightface')"

USER appuser


# Runtime configuration
EXPOSE 5001
CMD ["uwsgi", "--ini", "uwsgi.ini"]
