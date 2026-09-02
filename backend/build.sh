#!/usr/bin/env bash
# exit on error
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Install the Chromium browser
playwright install chromium

# IMPORTANT: Install the required Linux system dependencies for the browser
playwright install-deps chromium
