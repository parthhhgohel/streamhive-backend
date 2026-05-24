from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from ..views.auth_views import RegisterView, LoginView, LogoutView, ChangePasswordView, ForgotPasswordView, VerifyOTPView, ResetPasswordView
from ..views.oauth_views import GoogleLoginView, GoogleCallbackView, GitHubLoginView, GitHubCallbackView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot_password"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify_otp"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset_password"),

    # OAuth
    path("google/", GoogleLoginView.as_view(), name="google_login"),
    path("google/callback/", GoogleCallbackView.as_view(), name="google_callback"),
    path("github/", GitHubLoginView.as_view(), name="github_login"),
    path("github/callback/", GitHubCallbackView.as_view(), name="github_callback"),
]