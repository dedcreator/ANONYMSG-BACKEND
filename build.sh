#!/usr/bin/env bash
# exit on error
set -o errexit

echo "==> Current Python Version:"
python --version

echo "==> Upgrading build tools (pip, setuptools, wheel)..."
pip install --upgrade pip setuptools wheel

echo "==> Installing Python dependencies (preferring precompiled binary wheels)..."
pip install --prefer-binary -r requirements.txt

echo "==> Collecting static assets..."
python manage.py collectstatic --no-input

echo "==> Running database migrations..."
python manage.py migrate --no-input

echo "==> Build successfully completed!"

