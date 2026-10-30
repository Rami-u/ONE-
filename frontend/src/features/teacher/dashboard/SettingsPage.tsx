import { useCallback, useEffect, useState } from "react";

import { getWorkspaceSettings, updateWorkspaceSettings } from "../../../api/workspace";
import {
  Alert,
  Button,
  Card,
  FieldError,
  FullPageSpinner,
  Input,
  Label,
  PageHeader,
  Spinner,
  Textarea,
} from "../../../components/ui";
import { useSession } from "../../../context/SessionContext";
import { useApiErrorText } from "../../../lib/apiErrorText";
import { ApiError } from "../../../lib/apiClient";
import type { WorkspaceSettings } from "../../../types/api";

/**
 * Workspace settings (PATCH /workspaces/{slug}/): name, logo, headline, bio,
 * about, directory listing, and payment instructions. The slug is read-only.
 * Changing the logo uses a multipart request; everything else is JSON.
 */
export function TeacherSettingsPage() {
  const { slug, refreshWorkspace } = useSession();
  const errorToText = useApiErrorText();

  const [settings, setSettings] = useState<WorkspaceSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});

  // Editable form state
  const [name, setName] = useState("");
  const [headline, setHeadline] = useState("");
  const [bio, setBio] = useState("");
  const [about, setAbout] = useState("");
  const [isListed, setIsListed] = useState(false);
  const [paymentInstructions, setPaymentInstructions] = useState("");
  const [logo, setLogo] = useState<File | null>(null);
  const [logoPreviewUrl, setLogoPreviewUrl] = useState<string | null>(null);

  useEffect(
    () => () => {
      if (logoPreviewUrl) URL.revokeObjectURL(logoPreviewUrl);
    },
    [logoPreviewUrl],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setPageError(null);
    try {
      const response = await getWorkspaceSettings(slug ?? "");
      setSettings(response);
      setName(response.name);
      setHeadline(response.headline ?? "");
      setBio(response.bio ?? "");
      setAbout(response.about ?? "");
      setIsListed(response.is_listed);
      setPaymentInstructions(response.payment_instructions ?? "");
      setLogoPreviewUrl(response.logo);
    } catch (error) {
      setPageError(errorToText(error as ApiError, "تعذّر تحميل إعدادات المساحة."));
    } finally {
      setLoading(false);
    }
  }, [slug, errorToText]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setErrorText(null);
    setFieldErrors({});
    setSaved(false);
    try {
      const updated = await updateWorkspaceSettings(slug ?? "", {
        name,
        headline: headline || null,
        bio: bio || null,
        about: about || null,
        is_listed: isListed,
        payment_instructions: paymentInstructions || null,
        logo,
      });
      setSettings(updated);
      setLogoPreviewUrl(updated.logo);
      setLogo(null);
      setSaved(true);
      // The header shows the name/logo — refresh the branding too.
      await refreshWorkspace();
    } catch (error) {
      const apiError = error as ApiError;
      setFieldErrors(apiError.fieldErrors ?? {});
      setErrorText(errorToText(apiError, "تعذّر حفظ الإعدادات."));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <FullPageSpinner />;
  }

  if (!settings) {
    return <Alert tone="error">{pageError ?? "تعذّر تحميل الإعدادات."}</Alert>;
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="إعدادات المساحة" subtitle="هوية مساحتك، معلوماتك، وتعليمات الدفع التي يراها الطلاب." />

      <p className="mb-4 -mt-2 text-sm text-ink-secondary">
        العنوان:{" "}
        <span dir="ltr" className="rounded-control bg-soft px-1.5 py-0.5 text-[10px] font-semibold text-ink">
          {settings.slug}
        </span>{" "}
        (غير قابل للتعديل)
      </p>

      {saved && (
        <div className="mb-4">
          <Alert tone="success">تم حفظ الإعدادات.</Alert>
        </div>
      )}
      {errorText && (
        <div className="mb-4">
          <Alert tone="error">{errorText}</Alert>
        </div>
      )}

      <Card>
        <form className="space-y-4" onSubmit={(event) => void save(event)}>
          <div>
            <Label htmlFor="ws-name">اسم المساحة</Label>
            <Input
              id="ws-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              invalid={Boolean(fieldErrors.name)}
            />
            <FieldError messages={fieldErrors.name} />
          </div>

          <div>
            <Label htmlFor="ws-logo">الشعار (يحلّ محل الشعار الحالي)</Label>
            <div className="flex items-center gap-3">
              {logoPreviewUrl && (
                <img src={logoPreviewUrl} alt="الشعار الحالي" className="h-12 w-12 rounded-control object-cover" />
              )}
              <Input
                id="ws-logo"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(event) => setLogo(event.target.files?.[0] ?? null)}
                className="max-w-sm"
                invalid={Boolean(fieldErrors.logo)}
              />
            </div>
            <FieldError messages={fieldErrors.logo} />
          </div>

          <div>
            <Label htmlFor="ws-headline">العنوان التعريفي</Label>
            <Input
              id="ws-headline"
              value={headline}
              onChange={(event) => setHeadline(event.target.value)}
              placeholder="سطر واحد يعرّف بمساحتك"
              invalid={Boolean(fieldErrors.headline)}
            />
            <FieldError messages={fieldErrors.headline} />
          </div>

          <div>
            <Label htmlFor="ws-bio">نبذة</Label>
            <Textarea id="ws-bio" rows={3} value={bio} onChange={(event) => setBio(event.target.value)} invalid={Boolean(fieldErrors.bio)} />
            <FieldError messages={fieldErrors.bio} />
          </div>

          <div>
            <Label htmlFor="ws-about">عن المعلّم</Label>
            <Textarea id="ws-about" rows={5} value={about} onChange={(event) => setAbout(event.target.value)} invalid={Boolean(fieldErrors.about)} />
            <FieldError messages={fieldErrors.about} />
          </div>

          <div>
            <Label htmlFor="ws-payment">تعليمات الدفع</Label>
            <Textarea
              id="ws-payment"
              rows={4}
              value={paymentInstructions}
              onChange={(event) => setPaymentInstructions(event.target.value)}
              placeholder="كيف يدفع الطلاب؟ الحساب البنكي، المحفظة الإلكترونية، الأرقام المرجعية..."
              invalid={Boolean(fieldErrors.payment_instructions)}
            />
            <FieldError messages={fieldErrors.payment_instructions} />
          </div>

          <div>
            <label className="flex items-center gap-2 text-sm font-medium text-ink">
              <input
                type="checkbox"
                checked={isListed}
                onChange={(event) => setIsListed(event.target.checked)}
                className="h-4 w-4 rounded-control border-line text-accent"
              />
              الإدراج في دليل المعلّمين العام
            </label>
          </div>

          <Button type="submit" disabled={saving}>
            {saving && <Spinner className="h-4 w-4 border-accent-contrast/40 border-t-accent-contrast" />}
            {saving ? "جارٍ الحفظ..." : "حفظ الإعدادات"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
