bind = "127.0.0.1:8000"
workers = 2  # для 1 ГБ RAM достаточно 2 workers
timeout = 120
accesslog = "logs/gunicorn_access.log"
errorlog = "logs/gunicorn_error.log"
capture_output = True
enable_stdio_inheritance = True