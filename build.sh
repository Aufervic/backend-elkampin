#!/usr/bin/env bash

pip install -r requirements.txt

python manage.py migrate

echo "from django.contrib.auth import get_user_model; User = get_user_model(); import os; username=os.environ.get('DJANGO_SUPERUSER_USERNAME'); email=os.environ.get('DJANGO_SUPERUSER_EMAIL'); password=os.environ.get('DJANGO_SUPERUSER_PASSWORD'); User.objects.filter(username=username).exists() or User.objects.create_superuser(username, email, password)" | python manage.py shell
