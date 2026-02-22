from django.conf import settings
from django.dispatch import receiver

from allauth.account.signals import user_logged_in


@receiver(user_logged_in)
def grant_staff_to_admin_emails(sender, request, user, **kwargs):
    admin_emails = getattr(settings, 'ADMIN_EMAILS', [])

    # user.email 또는 소셜 계정의 이메일로 매칭
    emails = {user.email}
    for sa in user.socialaccount_set.all():
        sa_email = sa.extra_data.get('email', '')
        if sa_email:
            emails.add(sa_email)

    if emails & set(admin_emails) and not user.is_staff:
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=['is_staff', 'is_superuser'])
