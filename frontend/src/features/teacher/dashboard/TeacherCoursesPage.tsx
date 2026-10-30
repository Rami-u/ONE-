import { useCallback, useEffect, useState } from "react";

import { createCourse, listCourses, updateCourse } from "../../../api/courses";
import {
  Alert,
  Button,
  Card,
  CourseCover,
  cn,
  EmptyState,
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
import { formatDate, formatPrice } from "../../../lib/format";
import type { Course } from "../../../types/api";

/**
 * Course manager (§7.6 create/update). Teachers see all of their courses,
 * including unpublished drafts. Price is required at creation and prices of
 * "0.00" count as free courses. Editing inline: title, description, price,
 * and the published flag.
 */
export function TeacherCoursesPage() {
  const { slug } = useSession();
  const errorToText = useApiErrorText();

  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState<string | null>(null);

  // Create form
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newPrice, setNewPrice] = useState("");
  const [newPublished, setNewPublished] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createFieldErrors, setCreateFieldErrors] = useState<Record<string, string[]>>({});
  const [createError, setCreateError] = useState<string | null>(null);

  // Inline edit state: exactly one course edited at a time
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editPrice, setEditPrice] = useState("");
  const [savingId, setSavingId] = useState<number | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErrorText(null);
    try {
      const response = await listCourses(slug ?? "");
      setCourses(response);
    } catch (error) {
      setErrorText(errorToText(error as ApiError, "تعذّر تحميل دوراتك."));
    } finally {
      setLoading(false);
    }
  }, [slug, errorToText]);

  useEffect(() => {
    void load();
  }, [load]);

  function startEdit(course: Course) {
    setEditingId(course.id);
    setEditTitle(course.title);
    setEditDescription(course.description ?? "");
    setEditPrice(course.price);
    setRowError(null);
  }

  function cancelEdit() {
    setEditingId(null);
    setRowError(null);
  }

  async function submitCreate(event: React.FormEvent) {
    event.preventDefault();
    setCreating(true);
    setCreateError(null);
    setCreateFieldErrors({});
    try {
      await createCourse(slug ?? "", {
        title: newTitle,
        description: newDescription || null,
        price: newPrice || "0",
        is_published: newPublished,
      });
      setNewTitle("");
      setNewDescription("");
      setNewPrice("");
      setNewPublished(false);
      await load();
    } catch (error) {
      const apiError = error as ApiError;
      setCreateFieldErrors(apiError.fieldErrors ?? {});
      setCreateError(errorToText(apiError, "تعذّر إنشاء الدورة."));
    } finally {
      setCreating(false);
    }
  }

  async function submitEdit(course: Course) {
    setSavingId(course.id);
    setRowError(null);
    try {
      await updateCourse(slug ?? "", course.id, {
        title: editTitle,
        description: editDescription || null,
        price: editPrice || course.price,
        is_published: course.is_published,
      });
      setEditingId(null);
      await load();
    } catch (error) {
      const apiError = error as ApiError;
      setRowError(errorToText(apiError, "تعذّر حفظ الدورة."));
    } finally {
      setSavingId(null);
    }
  }

  async function togglePublished(course: Course) {
    setSavingId(course.id);
    setRowError(null);
    try {
      await updateCourse(slug ?? "", course.id, { is_published: !course.is_published });
      await load();
    } catch (error) {
      setRowError(errorToText(error as ApiError, "تعذّر تغيير حالة النشر."));
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div>
      <PageHeader title="إدارة الدورات" subtitle="أنشئ الدورات، احتفظ بالمسوّدات، وانشرها عندما تصبح جاهزة." />

      {errorText && (
        <div className="mb-4">
          <Alert tone="error">{errorText}</Alert>
        </div>
      )}

      {/* Create */}
      <Card className="mb-6">
        <h2 className="font-bold text-ink">دورة جديدة</h2>
        {createError && (
          <div className="mt-3">
            <Alert tone="error">{createError}</Alert>
          </div>
        )}
        <form className="mt-3 grid gap-3 sm:grid-cols-2" onSubmit={(event) => void submitCreate(event)}>
          <div className="sm:col-span-2">
            <Label htmlFor="new-title">العنوان</Label>
            <Input
              id="new-title"
              value={newTitle}
              onChange={(event) => setNewTitle(event.target.value)}
              required
              invalid={Boolean(createFieldErrors.title)}
            />
            <FieldError messages={createFieldErrors.title} />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="new-description">الوصف</Label>
            <Textarea
              id="new-description"
              rows={2}
              value={newDescription}
              onChange={(event) => setNewDescription(event.target.value)}
            />
            <FieldError messages={createFieldErrors.description} />
          </div>
          <div>
            <Label htmlFor="new-price">السعر (0 = مجانية)</Label>
            <Input
              id="new-price"
              type="number"
              dir="ltr"
              min="0"
              step="0.01"
              value={newPrice}
              onChange={(event) => setNewPrice(event.target.value)}
              placeholder="0.00"
              required
              invalid={Boolean(createFieldErrors.price)}
            />
            <FieldError messages={createFieldErrors.price} />
          </div>
          <div className="flex items-end gap-2 pb-1">
            <label className="flex items-center gap-2 text-sm font-medium text-ink">
              <input
                type="checkbox"
                checked={newPublished}
                onChange={(event) => setNewPublished(event.target.checked)}
                className="h-4 w-4 rounded border-line accent-[var(--accent)]"
              />
              نشر فوري
            </label>
            <Button type="submit" disabled={creating} className="ms-auto">
              {creating && <Spinner className="h-4 w-4 border-accent-contrast/40 border-t-accent-contrast" />}
              {creating ? "جارٍ الإنشاء..." : "إنشاء"}
            </Button>
          </div>
        </form>
      </Card>

      {/* List */}
      {loading ? (
        <FullPageSpinner />
      ) : courses.length === 0 ? (
        <EmptyState title="لا توجد دورات بعد" hint="أنشئ أول دورة من النموذج أعلاه." />
      ) : (
        <ul className="grid gap-3">
          {courses.map((course) =>
            editingId === course.id ? (
              <li key={course.id}>
                <Card>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <Label htmlFor={`edit-title-${course.id}`}>العنوان</Label>
                      <Input
                        id={`edit-title-${course.id}`}
                        value={editTitle}
                        onChange={(event) => setEditTitle(event.target.value)}
                      />
                    </div>
                    <div>
                      <Label htmlFor={`edit-price-${course.id}`}>السعر</Label>
                      <Input
                        id={`edit-price-${course.id}`}
                        type="number"
                        dir="ltr"
                        min="0"
                        step="0.01"
                        value={editPrice}
                        onChange={(event) => setEditPrice(event.target.value)}
                      />
                    </div>
                    <div className="sm:col-span-2">
                      <Label htmlFor={`edit-description-${course.id}`}>الوصف</Label>
                      <Textarea
                        id={`edit-description-${course.id}`}
                        rows={3}
                        value={editDescription}
                        onChange={(event) => setEditDescription(event.target.value)}
                      />
                    </div>
                  </div>
                  {rowError && (
                    <div className="mt-3">
                      <Alert tone="error">{rowError}</Alert>
                    </div>
                  )}
                  <div className="mt-3 flex justify-end gap-2">
                    <Button variant="secondary" onClick={cancelEdit}>
                      إلغاء
                    </Button>
                    <Button onClick={() => void submitEdit(course)} disabled={savingId === course.id}>
                      {savingId === course.id && (
                        <Spinner className="h-4 w-4 border-accent-contrast/40 border-t-accent-contrast" />
                      )}
                      حفظ
                    </Button>
                  </div>
                </Card>
              </li>
            ) : (
              <li key={course.id}>
                <Card className="flex flex-wrap items-center justify-between gap-4">
                  <div className="flex min-w-0 items-start gap-3">
                    <CourseCover courseId={course.id} title={course.title} size={44} />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="truncate font-bold text-ink">{course.title}</p>
                        <span
                          className={cn(
                            "shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold",
                            course.is_published
                              ? "bg-success-bg text-success"
                              : "border border-line bg-soft text-ink-secondary",
                          )}
                        >
                          {course.is_published ? "منشورة" : "مسوّدة"}
                        </span>
                      </div>
                      {course.description && (
                        <p className="mt-1 line-clamp-2 text-sm leading-[1.8] text-ink-secondary">{course.description}</p>
                      )}
                      <p className="mt-1 text-xs text-ink-muted">
                        <span dir="ltr">{formatPrice(course.price)}</span> · أُنشئت {formatDate(course.created_at)}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      onClick={() => void togglePublished(course)}
                      disabled={savingId === course.id}
                    >
                      {course.is_published ? "إلغاء النشر" : "نشر"}
                    </Button>
                    <Button onClick={() => startEdit(course)} disabled={savingId === course.id}>
                      تعديل
                    </Button>
                  </div>
                </Card>
              </li>
            ),
          )}
        </ul>
      )}

      {rowError && editingId === null && (
        <div className="mt-4">
          <Alert tone="error">{rowError}</Alert>
        </div>
      )}
    </div>
  );
}
