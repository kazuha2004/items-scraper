#!/usr/bin/env bash
# exit on error
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Install the Chromium browser
playwright install chromium

# IMPORTANT: Render native environment does not allow sudo, so we cannot run install-deps.
# We will rely on Render's OS image having the necessary libraries.

