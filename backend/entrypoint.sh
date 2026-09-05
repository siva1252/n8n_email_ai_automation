#!/bin/sh
set -e
python manage.py migrate --noinput
python manage.py ensure_admin
python manage.py load_demo
exec gunicorn --bind 0.0.0.0:8000 --timeout 120 --workers 1 backend.wsgi:application
