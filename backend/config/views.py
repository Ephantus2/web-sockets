import logging
from django.db import connection, DatabaseError
from django.http import JsonResponse, HttpResponse
import redis
from django.conf import settings
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

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

def redis_health_check(requests):
    client = None
    try:
        # Connect using the existing Redis configuration
        client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2
        )

        # Verify that Redis responds
        response = client.ping()
        if not response:
            raise redis.RedisError("Redis PING failed")

        return JsonResponse(
            {
                "status": "healthy",
                "redis": "available"
            },
            status=200
        )
    except (redis.RedisError, ValueError):
        logger.exception("Redis health check failed.")
        return JsonResponse(
            {
                "status": "unhealthy",
                "redis": "unavailable"
            },
            status=503
        )
    finally:
        if client is not None:
            client.close()

def prometheus_metrics(request):
    metrics = generate_latest()

    return HttpResponse(
        metrics,
        content_type=CONTENT_TYPE_LATEST
    )