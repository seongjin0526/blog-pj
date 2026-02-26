from django.conf import settings
from django.dispatch import receiver

from allauth.socialaccount.signals import pre_social_login


@receiver(pre_social_login)
def grant_staff_to_owner(sender, request, sociallogin, **kwargs):
    owner_email = getattr(settings, 'OWNER_EMAIL', '')
    if not owner_email:
        return

    user = sociallogin.user
    if user.is_staff:
        return

    email = sociallogin.account.extra_data.get('email', '')
    email_verified = sociallogin.account.extra_data.get('email_verified', False)

    if email_verified and email == owner_email:
        user.is_staff = True
        user.is_superuser = True
        if user.pk:
            user.save(update_fields=['is_staff', 'is_superuser'])
