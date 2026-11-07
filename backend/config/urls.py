from django.urls import include, path

urlpatterns = [
    path("api/auth/", include("accounts.urls")),
    path("api/", include("chamas.urls")),
    path("api/", include("rules.urls")),
    path("api/", include("finance.urls")),
    path("api/", include("payments.urls")),
    path("api/", include("reports.urls")),
]
