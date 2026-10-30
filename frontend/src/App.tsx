import { Navigate, Route, Routes } from "react-router-dom";

import { MainSiteLayout } from "./components/layout/MainSiteLayout";
import { PublicWorkspaceLayout } from "./components/layout/PublicWorkspaceLayout";
import { DashboardLayout } from "./components/layout/DashboardLayout";
import { FullPageSpinner } from "./components/ui";
import { SessionProvider, useSession } from "./context/SessionContext";
import { LandingPage } from "./features/main-site/LandingPage";
import { NotFoundPage } from "./features/main-site/NotFoundPage";
import { TeacherDirectoryPage } from "./features/main-site/TeacherDirectoryPage";
import { TeacherProfilePage } from "./features/main-site/TeacherProfilePage";
import { PublicHomePage } from "./features/workspace-shell/PublicHomePage";
import { WorkspaceGateMessage } from "./features/workspace-shell/WorkspaceGateMessage";
import { SignupPage } from "./features/student/SignupPage";
import { StudentLoginPage } from "./features/student/StudentLoginPage";
import { ResetPasswordPage } from "./features/student/ResetPasswordPage";
import { MyEnrollmentsPage } from "./features/student/dashboard/MyEnrollmentsPage";
import { CourseDetailPage } from "./features/student/dashboard/CourseDetailPage";
import { StudentCoursesPage } from "./features/student/dashboard/StudentCoursesPage";
import { TeacherLoginPage } from "./features/teacher/LoginPage";
import { TeacherSetPasswordPage } from "./features/teacher/SetPasswordPage";
import { TeacherSettingsPage } from "./features/teacher/dashboard/SettingsPage";
import { PaymentsReviewPage } from "./features/teacher/dashboard/PaymentsPage";
import { TeacherCoursesPage } from "./features/teacher/dashboard/TeacherCoursesPage";
import { StudentsReviewPage } from "./features/teacher/dashboard/StudentsPage";
import { RequireApprovedStudent, RequireAuth } from "./routes/guards";

/**
 * Top-level router. One app serves the main domain and every workspace
 * sub-domain; the mode (main vs workspace, and which slug) is resolved in
 * SessionContext from the hostname.
 */
function AppRoutes() {
  const { workspaceState, user } = useSession();
  const isWorkspace = workspaceState !== "main";

  if (isWorkspace && workspaceState === "loading") {
    return <FullPageSpinner />;
  }

  // Suspended or unknown slug: the whole app is replaced by the gate message,
  // mirroring how the backend rejects every operation for these workspaces.
  if (workspaceState === "unavailable" || workspaceState === "not_found") {
    return <WorkspaceGateMessage />;
  }

  // Signed-in users land on their dashboard instead of the anonymous pages.
  if (user) {
    const dashboardPath = user.role === "teacher" ? "/teacher/students" : "/courses";
    return (
      <Routes>
        {isWorkspace && (
          <>
            <Route path="/" element={<Navigate to={dashboardPath} replace />} />
            {/* The public CTAs (login / signup / reset) still exist in the nav
                and on a browser-back page, but a signed-in user has no auth
                screens: send them to their dashboard. */}
            <Route path="/login" element={<Navigate to={dashboardPath} replace />} />
            <Route path="/signup" element={<Navigate to={dashboardPath} replace />} />
            <Route path="/reset-password" element={<Navigate to={dashboardPath} replace />} />
            <Route element={<DashboardLayout />}>
              <Route path="/courses" element={<StudentCoursesPage />} />
              <Route path="/courses/:courseId" element={<CourseDetailPage />} />
            </Route>
            {/* Students-only pages */}
            <Route element={<RequireApprovedStudent />}>
              <Route element={<DashboardLayout />}>
                <Route path="/my-enrollments" element={<MyEnrollmentsPage />} />
              </Route>
            </Route>
            {/* Teacher-only pages */}
            <Route element={<RequireAuth roles={["teacher"]} />}>
              <Route element={<DashboardLayout />}>
                <Route path="/teacher/students" element={<StudentsReviewPage />} />
                <Route path="/teacher/courses" element={<TeacherCoursesPage />} />
                <Route path="/teacher/payments" element={<PaymentsReviewPage />} />
                <Route path="/teacher/settings" element={<TeacherSettingsPage />} />
              </Route>
            </Route>
            <Route element={<DashboardLayout />}>
              <Route path="*" element={<NotFoundPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </>
        )}
        {!isWorkspace && (
          <Route path="*" element={<Navigate to="/" replace />} />
        )}
      </Routes>
    );
  }

  return (
    <Routes>
      {isWorkspace ? (
        <>
          <Route element={<PublicWorkspaceLayout />}>
            <Route path="/" element={<PublicHomePage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/login" element={<StudentLoginPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
          {/* Private teacher routes (not wrapped in the public chrome) */}
          <Route path="/teacher/login" element={<TeacherLoginPage />} />
          <Route path="/teacher/set-password" element={<TeacherSetPasswordPage />} />
        </>
      ) : (
        <Route element={<MainSiteLayout />}>
          <Route path="/" element={<LandingPage />} />
          <Route path="/teachers" element={<TeacherDirectoryPage />} />
          <Route path="/teachers/:slug" element={<TeacherProfilePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      )}
    </Routes>
  );
}

export default function App() {
  return (
    <SessionProvider>
      <div className="min-h-screen">
        <AppRoutes />
      </div>
    </SessionProvider>
  );
}
