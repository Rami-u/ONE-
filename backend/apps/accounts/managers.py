from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    @staticmethod
    def normalize_email_address(email):
        if not email:
            raise ValueError("An email address is required.")
        return email.strip().lower()

    def create_user(self, email, password=None, **extra_fields):
        role = extra_fields.get("role")
        workspace = extra_fields.get("workspace")
        if role == "admin":
            raise ValueError("Use create_superuser() to create a platform admin.")
        if workspace is None:
            raise ValueError("A workspace is required for non-admin accounts.")
        if role is None:
            raise ValueError("A role is required.")

        email = self.normalize_email_address(email)
        if role in {"teacher", "assistant"}:
            extra_fields["approval_status"] = "approved"
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email=None, password=None, **extra_fields):
        supplied_login_key = extra_fields.pop("login_key", None)
        if email is None and supplied_login_key and supplied_login_key.startswith("admin:"):
            email = supplied_login_key.removeprefix("admin:")
        email = self.normalize_email_address(email)

        extra_fields["role"] = "admin"
        extra_fields["workspace"] = None
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        extra_fields["is_active"] = True
        extra_fields["approval_status"] = "approved"
        user = self.model(email=email, **extra_fields)
        if supplied_login_key and supplied_login_key != user.expected_login_key:
            raise ValueError("login_key is derived from the admin email.")
        user.set_password(password)
        user.save(using=self._db)
        return user
