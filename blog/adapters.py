from allauth.account.adapter import DefaultAccountAdapter


class NoSignupAccountAdapter(DefaultAccountAdapter):
    """일반 id/pw 회원가입을 차단하고, 로그인 페이지 접근 시 홈으로 리다이렉트합니다."""

    def is_open_for_signup(self, request):
        return False
