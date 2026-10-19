from .managers import UserManager


def build_login_key(workspace_id, email):
    """Build a canonical account key from a workspace id and email address."""
    normalized_email = UserManager.normalize_email_address(email)
    prefix = str(workspace_id) if workspace_id is not None else "admin"
    return f"{prefix}:{normalized_email}"
