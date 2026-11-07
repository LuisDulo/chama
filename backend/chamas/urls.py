from django.urls import path

from chamas import views

urlpatterns = [
    path("chamas/", views.ChamaListView.as_view()),
    path("chamas/discover/", views.DiscoverView.as_view()),
    path("chamas/<uuid:chama_id>/", views.ChamaDetailView.as_view()),
    path("chamas/<uuid:chama_id>/join/", views.JoinView.as_view()),
    path("chamas/<uuid:chama_id>/leave/", views.LeaveView.as_view()),
    path("chamas/<uuid:chama_id>/invite/", views.InviteView.as_view()),
    path("chamas/<uuid:chama_id>/members/", views.MemberListView.as_view()),
    path("chamas/<uuid:chama_id>/members/<uuid:membership_id>/role/",
         views.MemberRoleView.as_view()),
    path("chamas/<uuid:chama_id>/members/<uuid:membership_id>/<str:action>/",
         views.MemberActionView.as_view()),
    path("chamas/<uuid:chama_id>/roles/", views.RoleListView.as_view()),
    path("chamas/<uuid:chama_id>/roles/<int:role_id>/", views.RoleDetailView.as_view()),
    path("chamas/<uuid:chama_id>/audit-logs/", views.AuditView.as_view()),
    path("invitations/accept/", views.AcceptInvitationView.as_view()),
]
