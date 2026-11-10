from django.urls import path
from .views import AdminBootstrapView

urlpatterns = [
    path(
        "bootstrap-admin/",
        AdminBootstrapView.as_view(),
        name="bootstrap-admin"
    ),
]