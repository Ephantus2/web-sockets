from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.db import DatabaseError
import redis
from django.conf import settings
from unittest.mock import patch

class HealthCheckTests(TestCase):
    def test_health_check_database_available(self):
        response = self.client.get(
            reverse("health-check")
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "healthy",
                "database": "available"
            }
        )

    @patch(
            "config.views.connection.cursor",
            side_effect=DatabaseError("Database connection failed")
    )
    def test_health_check_database_unavailable(self, mock_cursor):
        response = self.client.get(
            reverse("health-check")
        )

        self.assertEqual(
            response.json(),
            {
                "status": "unhealthy",
                "database": "unavailable"
            }
        )

        self.assertNotIn(
            "Database connection failed",
            response.content.decode()
        )

    @patch("config.views.redis.Redis.from_url")
    def test_redis_health_check_available(self, mock_from_url):
        mock_client = mock_from_url.return_value
        mock_client.ping.return_value = True

        response = self.client.get(
            reverse("redis-health-check")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "healthy",
                "redis": "available"
            }
        )
        mock_from_url.assert_called_once_with(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2
        )
        mock_client.close.assert_called_once()

    @patch("config.views.redis.Redis.from_url")
    def test_redis_health_check_unavailable(self, mock_from_url):
        mock_client = mock_from_url.return_value
        mock_client.ping.side_effect = redis.ConnectionError(
            "Redis server unavailable"
        )
        response = self.client.get(
            reverse("redis-health-check")
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {
            "status": "unhealthy",
            "redis": "unavailable"
        })
        self.assertNotIn(
            "Redis server unavailable",
            response.content.decode()
        )
        mock_client.close.assert_called_once()