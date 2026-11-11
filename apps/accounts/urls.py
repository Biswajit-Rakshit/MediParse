from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from apps.accounts.views import RegisterView, LoginView, MeView, OrganizationUserListCreateView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("users/", OrganizationUserListCreateView.as_view(), name="org-users"),
]