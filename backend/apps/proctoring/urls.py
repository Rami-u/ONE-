from django.urls import include, path

from apps.proctoring import student_urls, teacher_urls

urlpatterns = [
    path('', include(student_urls)),
    path('', include(teacher_urls)),
]
