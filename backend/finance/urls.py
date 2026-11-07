from django.urls import path

from finance import views

urlpatterns = [
    path("chamas/<uuid:chama_id>/contribution-schedules/", views.ScheduleView.as_view()),
    path("chamas/<uuid:chama_id>/contribution-schedules/generate/",
         views.GenerateScheduleView.as_view()),
    path("chamas/<uuid:chama_id>/contributions/", views.ContributionView.as_view()),
    path("chamas/<uuid:chama_id>/reports/overview/", views.OverviewView.as_view()),
]
