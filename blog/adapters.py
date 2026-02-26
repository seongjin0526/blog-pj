from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class NoSignupAccountAdapter(DefaultAccountAdapter):
    """일반 id/pw 회원가입을 차단합니다."""

    def is_open_for_signup(self, request):
        return False


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """소셜 로그인(Google OAuth)을 통한 회원가입은 허용합니다."""

    def is_open_for_signup(self, request, sociallogin):
        return True
