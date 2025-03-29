#!/bin/bash

# Exit if any command fails
set -e  

echo "Checking Ubuntu version..."
lsb_release -a

echo "Adding NVIDIA GPG Key..."
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -

echo "Adding NVIDIA Docker repository..."
echo "deb https://nvidia.github.io/nvidia-docker/ubuntu24.04/amd64/ nvidia-docker main" | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

echo "Updating package lists..."
sudo apt-get update

echo "Installing NVIDIA Container Toolkit and nvidia-docker2..."
sudo apt-get install -y nvidia-container-toolkit nvidia-docker2

echo "Restarting Docker..."
sudo systemctl restart docker

echo "Checking if NVIDIA runtime is available..."
docker run --rm --gpus all nvidia/cuda:12.2.0-runtime-ubuntu20.04 nvidia-smi

echo "✅ GPU Docker setup completed!"
