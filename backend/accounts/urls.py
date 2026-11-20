from django.urls import path
from .views import AdminBootstrapView, CurrentUserView

urlpatterns = [
    path(
        "bootstrap-admin/",
        AdminBootstrapView.as_view(),
        name="bootstrap-admin"
    ),
    path(
        "me/",
        CurrentUserView.as_view(),
        name="current-user"
    ),
]