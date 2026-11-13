"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView
)
from .views import health_check, redis_health_check, prometheus_metrics

urlpatterns = [
    path('admin/', admin.site.urls),
    #Authentication
    path(
        "api/token/",
        TokenObtainPairView.as_view(),
        name="token-obtain-pair"
    ),
    path(
        "api/token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh"
    ),
    path("health/", health_check, name="health-check"),
    path("health/redis/", redis_health_check, name="redis-health-check"),
    path("metrics/", prometheus_metrics, name="prometheus-metrics"),

    #chat APIs
    path("api/", include("chat.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/accounts/", include("accounts.urls"))
]
