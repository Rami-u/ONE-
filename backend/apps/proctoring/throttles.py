from rest_framework.throttling import UserRateThrottle


class ProctoringFrameThrottle(UserRateThrottle):
    scope = "proctoring_frame"


class ProctoringBrowserEventThrottle(UserRateThrottle):
    scope = "proctoring_browser_event"