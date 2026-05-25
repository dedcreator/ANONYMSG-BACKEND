import os
import sys

# Add your project directory to the path
path = '/home/yourusername/anonmsg-backend'
if path not in sys.path:
    sys.path.append(path)

# Set Django settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'anonmsg_backend.settings'

# Create WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
