import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Activity,
  BookOpen,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Cpu,
  Gauge,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Radio,
  Settings2,
  ShieldCheck,
  Sun,
  X,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useTelemetry } from "../hooks/useTelemetry";
import { documentationUrl } from "../services/api";
import { StatusBadge } from "./StatusBadge";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand">
      <span className="brand-mark">
        <Radio size={23} strokeWidth={1.7} />
      </span>
      <div>
        <strong>
          NavSphere<span>®</span>
        </strong>
        {!compact && <small>TELEMETRY INTELLIGENCE</small>}
      </div>
    </div>
  );
}
export function Layout() {
  const { user, logout } = useAuth();
  const { deviceId, devices, selectDevice, connection, health } =
    useTelemetry();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [light, setLight] = useState(
    () => localStorage.getItem("navsphere-theme") === "light",
  );
  const [logoutError, setLogoutError] = useState("");
  const location = useLocation();
  const analytics = location.pathname.startsWith("/analytics");
  const section = analytics
    ? "Channel analytics"
    : location.pathname === "/controls"
      ? "Device controls"
      : location.pathname === "/account"
        ? "Account security"
        : "Overview";
  function theme() {
    const next = !light;
    setLight(next);
    localStorage.setItem("navsphere-theme", next ? "light" : "dark");
  }
  async function signOut() {
    try {
      await logout();
    } catch {
      setLogoutError("Sign out failed. Please retry.");
    }
  }
  return (
    <div className={`app-shell ${light ? "light" : ""}`}>
      {mobileOpen && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
        <div className="sidebar-brand">
          <Brand />
          <button
            className="icon-button mobile-only"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          >
            <X size={19} />
          </button>
        </div>
        <div className="workspace-label">
          WORKSPACE <span>LOCAL NETWORK</span>
        </div>
        <div className="workspace-card">
          <span className="workspace-icon">
            <Cpu size={20} />
          </span>
          <div>
            <strong>Device workspace</strong>
            <small>ESP32 telemetry platform</small>
          </div>
        </div>
        <div className="nav-label">MONITOR</div>
        <nav aria-label="Main navigation" onClick={() => setMobileOpen(false)}>
          <NavLink to="/" end>
            <LayoutDashboard size={18} />
            <span>Overview</span>
            <ChevronRight size={15} />
          </NavLink>
          <NavLink
            to="/analytics/analog-1"
            className={analytics ? "active" : ""}
          >
            <Activity size={18} />
            <span>Channel analytics</span>
          </NavLink>
          <NavLink to="/controls">
            <Settings2 size={18} />
            <span>Device controls</span>
          </NavLink>
        </nav>
        <div className="nav-label">MANAGE</div>
        <nav
          aria-label="Management navigation"
          onClick={() => setMobileOpen(false)}
        >
          <NavLink to="/account">
            <ShieldCheck size={18} />
            <span>Account & security</span>
          </NavLink>
          <a href={documentationUrl} target="_blank" rel="noreferrer">
            <BookOpen size={18} />
            <span>API documentation</span>
            <ChevronRight size={15} />
          </a>
        </nav>
        <div className="sidebar-bottom">
          <div className="edge-card">
            <div>
              <span
                className={`status-dot ${health?.mqtt_connected ? "online" : ""}`}
              />{" "}
              LOCAL EDGE NETWORK
            </div>
            <strong>360° visibility.</strong>
            <p>Your signals, in one clear view.</p>
            <Gauge className="edge-watermark" size={64} />
          </div>
          <button
            className="help-link"
            onClick={() =>
              window.open(documentationUrl, "_blank", "noopener,noreferrer")
            }
          >
            <CircleHelp size={17} />
            Documentation & support
            <ChevronRight size={14} />
          </button>
          <div className="user-card">
            <span className="avatar">
              {user?.username.slice(0, 2).toUpperCase()}
            </span>
            <div>
              <strong>{user?.username}</strong>
              <small>
                {user?.role === "admin" ? "Administrator" : "Viewer"}
              </small>
            </div>
            <button
              className="icon-button"
              onClick={() => void signOut()}
              aria-label="Sign out"
            >
              <LogOut size={17} />
            </button>
          </div>
          {logoutError && (
            <p className="error-text" role="alert">
              {logoutError}
            </p>
          )}
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-only"
              aria-label="Open navigation"
              onClick={() => setMobileOpen(true)}
            >
              <Menu size={21} />
            </button>
            <span className="breadcrumb-workspace">Workspace</span>
            <ChevronRight size={13} />
            <strong>{section}</strong>
          </div>
          <div className="topbar-right">
            <StatusBadge
              state={connection === "connected" ? "good" : "warning"}
            >
              {connection === "connected"
                ? "Live stream connected"
                : connection === "connecting"
                  ? "Connecting stream"
                  : "Stream interrupted"}
            </StatusBadge>
            <span className="topbar-divider" />
            <button
              className="icon-button"
              onClick={theme}
              aria-label={light ? "Use dark theme" : "Use light theme"}
            >
              {light ? <Moon size={18} /> : <Sun size={18} />}
            </button>
            <span className="topbar-avatar">
              {user?.username[0]?.toUpperCase()}
            </span>
          </div>
        </header>
        <main className="page-content">
          <div className="page-toolbar">
            <span className="eyebrow">
              <span className="cyan-line" /> NAVSPHERE / TELEMETRY
            </span>
            <label className="device-picker">
              <Cpu size={15} />
              <select
                aria-label="Select device"
                value={deviceId}
                onChange={(event) => selectDevice(event.target.value)}
              >
                {devices.length ? (
                  devices.map((device) => (
                    <option key={device.device_id} value={device.device_id}>
                      {device.device_id}
                    </option>
                  ))
                ) : (
                  <option value="ESP32_001">ESP32_001</option>
                )}
              </select>
              <ChevronDown size={14} />
            </label>
          </div>
          <Outlet />
        </main>
        <footer className="app-footer">
          <span>
            NavSphere <span className="footer-separator">/</span> 360°
            Visibility and Comprehensive Tracking
          </span>
          <span>
            All timestamps shown in local time{" "}
            <span className="status-dot online" />
          </span>
        </footer>
      </div>
    </div>
  );
}
