import { apiRequest } from "../lib/apiClient";
import { fetchAllPages } from "./pagination";
import type { Course } from "../types/api";

/** Course endpoints (§7.6) under /api/v1/workspaces/{slug}/courses/. */

const prefix = (slug: string): string => `/workspaces/${encodeURIComponent(slug)}/courses`;

/** GET /courses/ — teachers see all their courses; approved students see published ones. */
export function listCourses(slug: string): Promise<Course[]> {
  return fetchAllPages<Course>(`${prefix(slug)}/`);
}

/** GET /courses/{id}/ */
export function getCourse(slug: string, courseId: number): Promise<Course> {
  return apiRequest(`${prefix(slug)}/${courseId}/`);
}

export interface CourseInput {
  title: string;
  description: string | null;
  price: string;
  is_published: boolean;
}

/** POST /courses/ — price is required at creation. 201. */
export function createCourse(slug: string, input: CourseInput): Promise<Course> {
  return apiRequest(`${prefix(slug)}/`, { method: "POST", json: input });
}

/** PATCH /courses/{id}/ */
export function updateCourse(slug: string, courseId: number, patch: Partial<CourseInput>): Promise<Course> {
  return apiRequest(`${prefix(slug)}/${courseId}/`, { method: "PATCH", json: patch });
}
