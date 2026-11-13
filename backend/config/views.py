import logging
from django.db import connection, DatabaseError
from django.http import JsonResponse

logger = logging.getLogger(__name__)

def health_check(request):
    try:
        # Attempt to communicate with postgreSQL

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse(
            {
                "status": "healthy",
                "database": "available"
            },
            status=200
        )
    except DatabaseError:
        logger.exception(
            "Database health check failed."
        )

        return JsonResponse(
            {
                "status": "unhealthy",
                "database": "unavailable"
            },
            status=503
        )