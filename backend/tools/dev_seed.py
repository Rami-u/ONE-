"""Development seed: platform admin, one teacher workspace, and sample content.

Run from backend/ with the venv python:
    ..\\.venv\\Scripts\\python.exe manage.py shell < tools/dev_seed.py

Idempotent — every creator checks for existing rows first.

Accounts created (all passwords are dev-only):
  Platform Admin  admin@wajha.dev   / admin1234!    login: admin:admin@wajha.dev
  Teacher         teacher@wajha.dev / teacher1234!  workspace slug: science
  Student         hana@wajha.dev    / student1234!  approved
  Student         yara@wajha.dev    / student1234!  pending review
  Courses: three published (one free), one draft; free course active for hana.
"""
from django.utils import timezone

from apps.accounts.models import User
from apps.courses.models import Course
from apps.enrollments.models import CourseEnrollment
from apps.workspaces.models import Workspace

# --- Platform admin -------------------------------------------------------
if not User.objects.filter(email="admin@wajha.dev").exists():
    User.objects.create_superuser(
        email="admin@wajha.dev",
        password="admin1234!",
        full_name="مدير المنصة",
    )
    print("created admin    admin@wajha.dev / admin1234!")

# --- Workspace + teacher ---------------------------------------------------
if not Workspace.objects.filter(slug="science").exists():
    Workspace.objects.create(
        slug="science",
        name="مساحة العلوم",
        headline="علوم ورياضيات للمرحلة الثانوية",
        bio="خبرة أكثر من عشر سنوات في تدريس العلوم والرياضيات.",
        about="أدرّس الفيزياء والكيمياء والرياضيات مع تدريبات أسبوعية واختبارات دورية.",
        is_listed=True,
        payment_instructions=(
            "حوّل المبلغ إلى الحساب البنكي التالي ثم قدّم إشعار الدفع من صفحة تسجيلاتك:\n"
            "البنك الأهلي — رقم الحساب SA00 0000 0000 0000\n"
            "أو المحفظة الإلكترونية 0100 000 0000."
        ),
    )
    print("created workspace slug 'science'")

workspace = Workspace.objects.get(slug="science")

if not User.objects.filter(email="teacher@wajha.dev").exists():
    User.objects.create_user(
        email="teacher@wajha.dev",
        password="teacher1234!",
        role="teacher",
        workspace=workspace,
        full_name="أحمد حسن",
    )
    print("created teacher  teacher@wajha.dev / teacher1234!  (approved automatically)")
teacher = User.objects.get(email="teacher@wajha.dev")

# --- Students --------------------------------------------------------------
approved_student = None
if not User.objects.filter(email="hana@wajha.dev").exists():
    approved_student = User.objects.create_user(
        email="hana@wajha.dev",
        password="student1234!",
        role="student",
        workspace=workspace,
        full_name="هنا السيد",
    )
    approved_student.approval_status = "approved"
    approved_student.reviewed_by = teacher
    approved_student.reviewed_at = timezone.now()
    approved_student.save(update_fields=["approval_status", "reviewed_by", "reviewed_at"])
    print("created student  hana@wajha.dev / student1234!  (approved)")
approved_student = approved_student or User.objects.get(email="hana@wajha.dev")

if not User.objects.filter(email="yara@wajha.dev").exists():
    User.objects.create_user(
        email="yara@wajha.dev",
        password="student1234!",
        role="student",
        workspace=workspace,
        full_name="يارا مراد",
    )
    print("created student  yara@wajha.dev / student1234!  (pending review)")

# --- Courses ----------------------------------------------------------------
COURSES = [
    {"title": "أساسيات الجبر", "description": "دورة تأسيسية في الجبر لكل المستويات: المعادلات، الدوال، والتحليل إلى العوامل.", "price": "0.00", "is_published": True},
    {"title": "التفاضل والتكامل", "description": "من المشتقات إلى التطبيقات العملية خطوة بخطوة مع أمثلة محلولة ودورات مساندات.", "price": "149.50", "is_published": True},
    {"title": "الكيمياء العامة", "description": "أساسيات الكيمياء: التفاعلات، الموازنة، والاحتفاظ بالكتلة.", "price": "99.00", "is_published": True},
    {"title": "مسوّدة — الفيزياء الفراغية", "description": "لم تُنشر بعد؛ تظهر فقط في إدارة دورات المعلّم.", "price": "0.00", "is_published": False},
]
for data in COURSES:
    if not Course.objects.filter(workspace=workspace, title=data["title"]).exists():
        Course.objects.create(workspace=workspace, **data)
        print(f"created course   {data['title']} ({'published' if data['is_published'] else 'draft'})")

free_course = Course.objects.get(workspace=workspace, title="أساسيات الجبر")
paid_course = Course.objects.get(workspace=workspace, title="التفاضل والتكامل")

# --- One active enrollment (free course) for the approved student -----------
if not CourseEnrollment.objects.filter(student=approved_student, course=free_course).exists():
    CourseEnrollment.objects.create(
        workspace=workspace,
        student=approved_student,
        course=free_course,
        status="active",
        price_at_enrollment=free_course.price,
        activated_at=timezone.now(),
    )
    print("enrolled         hana -> أساسيات الجبر (active)")

# One pending_payment enrollment so the payments review page has data
if not CourseEnrollment.objects.filter(student=approved_student, course=paid_course).exists():
    CourseEnrollment.objects.create(
        workspace=workspace,
        student=approved_student,
        course=paid_course,
        status="pending_payment",
        price_at_enrollment=paid_course.price,
    )
    print("enrolled         hana -> التفاضل والتكامل (pending_payment)")

print("seed complete.")
