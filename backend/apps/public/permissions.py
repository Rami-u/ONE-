from rest_framework.permissions import AllowAny


class PublicAccess(AllowAny):
    """Allow unauthenticated access with any HTTP method; views are read-only by implementing only GET."""
