from django.urls import include, path

urlpatterns = [
    path("api/auth/", include("accounts.urls")),
    path("api/", include("chamas.urls")),
]
