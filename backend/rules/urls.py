from django.urls import path

from rules import views

urlpatterns = [
    path("chamas/<uuid:chama_id>/rules/", views.RulesView.as_view()),
    path("chamas/<uuid:chama_id>/rules/history/", views.RuleHistoryView.as_view()),
    path("chamas/<uuid:chama_id>/rules/<int:version_id>/<str:decision>/",
         views.RuleDecisionView.as_view()),
]
