import { useCallback } from "react";

import { ApiError } from "./apiClient";

/** Shared mapping of ApiError objects to user-facing sentences. */

export type ApiErrorTextFn = (error: ApiError, fallback: string) => string;

/**
 * A stable error->text mapper that works as an effect dependency. Shows the
 * server message when the backend sent one ({detail} / {message}), otherwise
 * the provided fallback.
 */
export function useApiErrorText(): ApiErrorTextFn {
  return useCallback<ApiErrorTextFn>((error, fallback) => {
    if (error instanceof ApiError) {
      if (error.message && error.status !== 0) return error.message;
      if (error.status === 0) return error.message;
    }
    return fallback;
  }, []);
}
