from django.contrib.auth.tokens import PasswordResetTokenGenerator


class StaffPasswordTokenGenerator(PasswordResetTokenGenerator):
    """Use Django's password reset token lifecycle for staff invitations/resets."""


staff_password_token = StaffPasswordTokenGenerator()
