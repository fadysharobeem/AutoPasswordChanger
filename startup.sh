#!/bin/bash

# Update the package list
sudo apt update

# Install required applications
sudo apt install -y python3-pip redis-server

# Upgrade pip, setuptools, and wheel
pip3 install --upgrade pip setuptools wheel

# Install required Python libraries
pip3 install schedule qrcode flask flask_session redis Pillow

# Feedback to the user
echo "Installation completed successfully!"
