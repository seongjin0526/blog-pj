from django.conf import settings
from django.dispatch import receiver

from allauth.account.signals import user_logged_in


@receiver(user_logged_in)
def grant_staff_to_owner(sender, request, user, **kwargs):
    owner_email = getattr(settings, 'OWNER_EMAIL', '')
    if not owner_email:
        return

    if user.is_staff:
        return

    # socialaccount에서 verified 이메일만 수집
    verified_emails = set()
    for sa in user.socialaccount_set.all():
        if sa.extra_data.get('email_verified', False):
            sa_email = sa.extra_data.get('email', '')
            if sa_email:
                verified_emails.add(sa_email)

    if owner_email in verified_emails:
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=['is_staff', 'is_superuser'])
