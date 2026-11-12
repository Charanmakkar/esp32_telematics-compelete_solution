import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { Radio } from "lucide-react";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import { TelemetryProvider } from "./hooks/useTelemetry";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { ControlsPage } from "./pages/ControlsPage";
import { AccountPage } from "./pages/AccountPage";

function Protected() {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading)
    return (
      <div className="app-loading" role="status">
        <Radio size={34} />
        <strong>Connecting to your workspace…</strong>
      </div>
    );
  if (!user)
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return (
    <TelemetryProvider>
      <Outlet />
    </TelemetryProvider>
  );
}
export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<Protected />}>
          <Route element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="analytics/:channelId" element={<AnalyticsPage />} />
            <Route path="controls" element={<ControlsPage />} />
            <Route path="account" element={<AccountPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  );
}
