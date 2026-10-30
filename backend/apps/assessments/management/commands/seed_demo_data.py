import os
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.assessments.exam_services import (
    create_exam,
    publish_exam,
    replace_exam_questions,
)
from apps.assessments.models import (
    Exam,
    LessonTopic,
    Question,
    QuestionTopic,
    Topic,
)
from apps.assessments.question_services import create_question
from apps.assessments.question_validation import validate_question_content
from apps.assessments.seed_data import organic_chemistry as data
from apps.courses.models import Course, CourseSection, Lesson
from apps.enrollments.models import CourseEnrollment
from apps.workspaces.models import Workspace

PASSWORD_ENV = "DEMO_USER_PASSWORD"


class Command(BaseCommand):
    help = "Seed a demo chemistry workspace (development only)."

    def add_arguments(self, parser):
        parser.add_argument("--password", default=None)
        parser.add_argument("--workspace-slug", default="demo-chem")
        parser.add_argument("--students", type=int, default=5)

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo_data runs only when DEBUG is true.")
        password = options["password"] or os.environ.get(PASSWORD_ENV)
        if not password:
            raise CommandError(
                f"A password is required: pass --password or set {PASSWORD_ENV}."
            )
        if options["students"] < 1:
            raise CommandError("--students must be at least 1.")

        with transaction.atomic():
            summary = self.seed(options["workspace_slug"], options["students"], password)

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        for key, value in summary.items():
            self.stdout.write(f"  {key}: {value}")

    # ---- helpers -----------------------------------------------------

    def _full_create(self, model, **fields):
        obj = model(**fields)
        obj.full_clean()
        obj.save()
        return obj

    def _get_or_create(self, model, lookup, **defaults):
        obj = model.objects.filter(**lookup).first()
        if obj is not None:
            return obj, False
        return self._full_create(model, **lookup, **defaults), True

    # ---- main --------------------------------------------------------

    def seed(self, slug, student_count, password):
        workspace, _ = self._get_or_create(
            Workspace,
            {"slug": slug},
            name="Demo Chemistry",
            status=Workspace.Status.ACTIVE,
            is_listed=True,
            headline="Learn organic chemistry step by step",
            bio="Demo workspace with sample questions and exams.",
        )

        teacher = User.objects.filter(workspace=workspace, email="teacher@demo.local").first()
        if teacher is None:
            teacher = User.objects.create_user(
                email="teacher@demo.local",
                password=password,
                full_name="Demo Teacher",
                workspace=workspace,
                role=User.Role.TEACHER,
            )

        students = []
        for number in range(1, student_count + 1):
            email = f"student{number}@demo.local"
            student = User.objects.filter(workspace=workspace, email=email).first()
            if student is None:
                student = User.objects.create_user(
                    email=email,
                    password=password,
                    full_name=f"Demo Student {number}",
                    workspace=workspace,
                    role=User.Role.STUDENT,
                    approval_status=User.ApprovalStatus.APPROVED,
                )
            students.append(student)

        course, _ = self._get_or_create(
            Course,
            {"workspace": workspace, "title": data.COURSE["title"]},
            description=data.COURSE["description"],
            price=Decimal("0.00"),
            is_published=True,
        )

        for student in students:
            self._get_or_create(
                CourseEnrollment,
                {"workspace": workspace, "student": student, "course": course},
                status=CourseEnrollment.Status.ACTIVE,
                price_at_enrollment=Decimal("0.00"),
                activated_at=timezone.now(),
            )

        sections = []
        for item in data.SECTIONS:
            section, _ = self._get_or_create(
                CourseSection,
                {"workspace": workspace, "course": course, "title": item["title"]},
                position=item["position"],
            )
            sections.append(section)

        lessons = []
        for item in data.LESSONS:
            lesson, _ = self._get_or_create(
                Lesson,
                {"workspace": workspace, "course": course, "title": item["title"]},
                section=sections[item["section"]],
                content=item["content"],
                position=item["position"],
                is_published=True,
            )
            lessons.append(lesson)

        topics = {}
        for item in data.TOPICS:
            topic, _ = self._get_or_create(
                Topic,
                {"workspace": workspace, "slug": item["slug"]},
                course=course,
                name=item["name"],
            )
            topics[item["slug"]] = topic
            self._get_or_create(
                LessonTopic,
                {"workspace": workspace, "lesson": lessons[item["lesson"]], "topic": topic},
            )

        questions = []
        for item in data.QUESTIONS:
            question = Question.objects.filter(workspace=workspace, stem=item["stem"]).first()
            if question is None:
                options, correct = validate_question_content(
                    item["question_type"], item["options"], item["correct_answer"]
                )
                question = create_question(
                    workspace,
                    {
                        "question_type": item["question_type"],
                        "stem": item["stem"],
                        "options": options,
                        "correct_answer": correct,
                        "explanation": item["explanation"],
                        "difficulty": item["difficulty"],
                        "points": Decimal(item["points"]),
                        "course": course,
                        "status": Question.Status.APPROVED,
                    },
                )
            self._get_or_create(
                QuestionTopic,
                {
                    "workspace": workspace,
                    "question": question,
                    "topic": topics[item["topic"]],
                },
            )
            questions.append(question)

        exams = []
        for item in data.EXAMS:
            exam = Exam.objects.filter(
                workspace=workspace, course=course, title=item["title"]
            ).first()
            if exam is None:
                passing = item["passing_score"]
                exam = create_exam(
                    workspace,
                    {
                        "course": course,
                        "title": item["title"],
                        "description": item["description"],
                        "duration_minutes": item["duration_minutes"],
                        "max_attempts": item["max_attempts"],
                        "proctoring_enabled": item["proctoring_enabled"],
                        "passing_score": Decimal(passing) if passing else None,
                    },
                )
                replace_exam_questions(
                    exam.pk,
                    workspace,
                    [
                        {"question_id": questions[index].pk, "points_override": None}
                        for index in item["questions"]
                    ],
                )
                if item["publish"]:
                    publish_exam(exam.pk, workspace)
                exam.refresh_from_db()
            exams.append(exam)

        return {
            "workspace": workspace.slug,
            "teacher": teacher.email,
            "students": ", ".join(s.email for s in students),
            "course": course.title,
            "lessons": len(lessons),
            "topics": len(topics),
            "questions": len(questions),
            "exams": ", ".join(f"{e.title} [{e.status}]" for e in exams),
        }