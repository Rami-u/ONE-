import { useSession } from "../../context/SessionContext";
import { Card, FullPageSpinner } from "../../components/ui";

/**
 * Full-page replacement while the workspace is suspended or the slug is
 * unknown. The backend answers 403 ("Workspace is unavailable.") for suspended
 * workspaces and 404 for unknown slugs — this page mirrors that distinction.
 */
export function WorkspaceGateMessage() {
  const { workspaceState, booting } = useSession();

  if (booting) {
    return <FullPageSpinner />;
  }

  if (workspaceState === "unavailable") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-page px-6">
        <Card className="max-w-md text-center shadow-elevated">
          <h1 className="text-xl font-extrabold text-ink">هذه المساحة غير متاحة حاليًا</h1>
          <p className="mt-2 text-sm leading-[1.8] text-ink-secondary">
            تم إيقاف هذه المساحة مؤقتًا، وهي لا تقدّم خدماتها للطلاب أو المعلّمين الآن.
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-page px-6">
      <Card className="max-w-md text-center shadow-elevated">
        <h1 className="text-xl font-extrabold text-ink">لم يتم العثور على المساحة</h1>
        <p className="mt-2 text-sm leading-[1.8] text-ink-secondary">
          لا توجد مساحة بهذا العنوان. تأكد من الرابط أو زر الموقع الرئيسي.
        </p>
      </Card>
    </div>
  );
}
