from django.urls import path

from payments import views

urlpatterns = [
    path("payments/stk-push/", views.StkPushView.as_view()),
    path("payments/callback/<str:secret>/", views.CallbackView.as_view()),
    path("payments/reconcile/", views.ReconcileView.as_view()),
    path("payments/<uuid:payment_id>/", views.PaymentDetailView.as_view()),
    path("payments/<uuid:payment_id>/simulate/", views.SimulateView.as_view()),
    path("chamas/<uuid:chama_id>/payments/", views.PaymentListView.as_view()),
]
