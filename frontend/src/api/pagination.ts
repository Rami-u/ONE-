import { apiRequest } from "../lib/apiClient";
import type { Page } from "../types/api";

/**
 * DRF pages every list endpoint at 20 items. Most workspace lists fit on one
 * page, but nothing in an API contract says they always will, so the frontend
 * follows the `next` link until the list is exhausted.
 */
export async function fetchAllPages<T>(path: string): Promise<T[]> {
  const items: T[] = [];
  let pageNumber = 1;
  for (;;) {
    const separator = path.includes("?") ? "&" : "?";
    const page: Page<T> = await apiRequest<Page<T>>(`${path}${separator}page=${pageNumber}`);
    items.push(...page.results);
    if (!page.next) {
      return items;
    }
    pageNumber += 1;
  }
}
