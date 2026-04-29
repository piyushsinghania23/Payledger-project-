web: cd backend && gunicorn payto.wsgi --bind 0.0.0.0:$PORT
worker: cd backend && celery -A payto worker -l info
beat: cd backend && celery -A payto beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
