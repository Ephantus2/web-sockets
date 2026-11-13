from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.db import DatabaseError

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