from django.urls import path

from reports import views

urlpatterns = [
    path("chamas/<uuid:chama_id>/reports/my-statement/", views.MyStatementView.as_view()),
    path("chamas/<uuid:chama_id>/reports/members/<uuid:membership_id>/statement/",
         views.MemberStatementView.as_view()),
    path("chamas/<uuid:chama_id>/reports/financial-statements/",
         views.GroupStatementView.as_view()),
]
