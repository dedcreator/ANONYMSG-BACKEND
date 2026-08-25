from django.http import JsonResponse
from django.db import connection
import time

START_TIME = time.time()

def health_check(request):
    """
    Health check endpoint for Render / monitoring services (e.g. UptimeRobot).
    Pings database to verify connectivity and returns uptime and service status.
    """
    status = {
        "status": "healthy",
        "service": "anonmsg-backend",
        "uptime_seconds": round(time.time() - START_TIME, 2),
    }
    try:
        connection.ensure_connection()
        status["database"] = "connected"
    except Exception as e:
        status["status"] = "degraded"
        status["database"] = "disconnected"
        status["database_error"] = str(e)
        
    return JsonResponse(status, status=200)
