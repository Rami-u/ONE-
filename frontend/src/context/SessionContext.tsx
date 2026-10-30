import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { getWorkspaceBranding, getWorkspacePublicProfile } from "../api/public";
import { getMe, logoutStudent } from "../api/studentAuth";
import { setApiWorkspace } from "../lib/apiClient";
import { resolvePageMode } from "../lib/slug";
import type { ApiUser, PublicTeacherProfile, WorkspaceBranding } from "../types/api";

export type WorkspaceLoadState = "loading" | "main" | "ready" | "not_found" | "unavailable";

interface SessionValue {
  slug: string | null;
  /** Branding once loaded; null before load, on the main domain, or when unreachable. */
  workspace: WorkspaceBranding | null;
  workspaceState: WorkspaceLoadState;
  /** Public profile shown on the workspace home (before and after login). */
  publicProfile: PublicTeacherProfile | null;
  user: ApiUser | null;
  /** True while the session bootstrap (branding + me) is still running. */
  booting: boolean;
  refreshUser: () => Promise<void>;
  refreshWorkspace: () => Promise<void>;
  signOut: () => Promise<void>;
  setUser: (user: ApiUser | null) => void;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const page = useMemo(() => resolvePageMode(), []);
  const slug = page.mode === "workspace" ? page.slug : null;

  const [workspace, setWorkspace] = useState<WorkspaceBranding | null>(null);
  const [publicProfile, setPublicProfile] = useState<PublicTeacherProfile | null>(null);
  const [workspaceState, setWorkspaceState] = useState<WorkspaceLoadState>(page.mode === "main" ? "main" : "loading");
  const [user, setUser] = useState<ApiUser | null>(null);
  const [booting, setBooting] = useState(page.mode === "workspace");

  /** Load branding; a suspended workspace answers 403, an unknown slug 404. */
  const refreshWorkspace = useCallback(async () => {
    if (!slug) return;
    try {
      const branding = await getWorkspaceBranding(slug);
      setWorkspace(branding);
      setWorkspaceState(branding.status === "suspended" ? "unavailable" : "ready");
      try {
        setPublicProfile(await getWorkspacePublicProfile(slug));
      } catch {
        setPublicProfile(null);
      }
    } catch (error) {
      void error;
      setWorkspace(null);
      setPublicProfile(null);
      // getWorkspaceBranding throws ApiError with the real status code.
      const status = (error as { status?: number }).status ?? 0;
      setWorkspaceState(status === 403 ? "unavailable" : "not_found");
    }
  }, [slug]);

  /** Session bootstrap: who is signed in to this workspace (any role). */
  const refreshUser = useCallback(async () => {
    if (!slug) {
      setUser(null);
      return;
    }
    try {
      setUser(await getMe(slug));
    } catch {
      setUser(null);
    }
  }, [slug]);

  useEffect(() => {
    setApiWorkspace(slug);
  }, [slug]);

  useEffect(() => {
    if (!slug) {
      setBooting(false);
      return;
    }
    let cancelled = false;
    (async () => {
      await Promise.all([refreshWorkspace(), refreshUser()]);
      if (!cancelled) setBooting(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [slug, refreshWorkspace, refreshUser]);

  const signOut = useCallback(async () => {
    if (slug) {
      await logoutStudent(slug);
    }
    setUser(null);
  }, [slug]);

  const value = useMemo<SessionValue>(
    () => ({
      slug,
      workspace,
      workspaceState,
      publicProfile,
      user,
      booting,
      refreshUser,
      refreshWorkspace,
      signOut,
      setUser,
    }),
    [slug, workspace, workspaceState, publicProfile, user, booting, refreshUser, refreshWorkspace, signOut],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) {
    throw new Error("useSession must be used inside <SessionProvider>.");
  }
  return value;
}
