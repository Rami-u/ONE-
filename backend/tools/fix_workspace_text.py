"""Repair the Workspace row whose text fields were saved as literal '?' characters
because of a console encoding issue during the first seed attempt. Run once:

    .venv\\Scripts\\python.exe manage.py shell -c "exec(open('tools/fix_workspace_text.py', encoding='utf-8').read())"
"""
import django, os  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.workspaces.models import Workspace  # noqa: E402

workspace = Workspace.objects.get(slug="science")
workspace.name = "مساحة العلوم"
workspace.headline = "علوم ورياضيات للمرحلة الثانوية"
workspace.bio = "خبرة أكثر من عشر سنوات في تدريس العلوم والرياضيات."
workspace.about = "أدرّس الفيزياء والكيمياء والرياضيات مع تدريبات أسبوعية واختبارات دورية."
workspace.payment_instructions = (
    "حوّل المبلغ إلى الحساب البنكي التالي ثم قدّم إشعار الدفع من صفحة تسجيلاتك:\n"
    "البنك الأهلي — رقم الحساب SA00 0000 0000 0000\n"
    "أو المحفظة الإلكترونية 0100 000 0000."
)
workspace.save(update_fields=["name", "headline", "bio", "about", "payment_instructions"])
print("workspace text repaired:", workspace.name.encode("unicode_escape")[:60])
