import { useState, type FormEvent } from "react";
import {
  ArrowRight,
  Eye,
  EyeOff,
  LockKeyhole,
  Radio,
  ShieldCheck,
} from "lucide-react";
import { Navigate, useLocation } from "react-router-dom";
import { Brand } from "../components/Layout";
import { useAuth } from "../hooks/useAuth";

export function LoginPage() {
  const { user, login, loading } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const location = useLocation();
  if (user)
    return (
      <Navigate
        to={
          user.must_change_password ? "/account" : location.state?.from || "/"
        }
        replace
      />
    );
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(username, password);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not sign in. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-page">
      <section className="login-story">
        <Brand />
        <div className="login-story-main">
          <span className="eyebrow">
            <span className="cyan-line" /> CONNECTED INTELLIGENCE
          </span>
          <h1>
            A complete view.
            <br />
            <span>Ahead of every signal.</span>
          </h1>
          <p>
            From the edge to your screen, turn real-time telemetry into
            confident decisions.
          </p>
          <div className="orbital-visual" aria-hidden="true">
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="orbit orbit-three" />
            <div className="orbital-core">
              <Radio size={45} strokeWidth={1.2} />
            </div>
            <span className="orbit-node node-one" />
            <span className="orbit-node node-two" />
            <span className="orbit-node node-three" />
            <div className="signal-tag signal-tag-one">
              <span className="status-dot online" />
              SIX CHANNELS. ONE VIEW.
            </div>
            <div className="signal-tag signal-tag-two">
              <ShieldCheck size={14} />
              CONTROL WITH CONFIDENCE
            </div>
          </div>
        </div>
        <p className="login-story-footer">
          360° Visibility and Comprehensive Tracking
        </p>
      </section>
      <section className="login-form-section">
        <div className="login-form-card">
          <span className="login-lock">
            <LockKeyhole size={25} />
          </span>
          <span className="eyebrow">YOUR TELEMETRY WORKSPACE</span>
          <h2>Welcome to NavSphere</h2>
          <p>Sign in to monitor your devices and explore every signal.</p>
          <form onSubmit={(event) => void submit(event)}>
            <label htmlFor="username">Username</label>
            <input
              id="username"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              placeholder="Enter your username"
              maxLength={64}
              autoFocus
            />
            <label htmlFor="password">Password</label>
            <div className="password-field">
              <input
                id="password"
                type={show ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                placeholder="Enter your password"
                maxLength={256}
              />
              <button
                type="button"
                className="icon-button"
                aria-label={show ? "Hide password" : "Show password"}
                onClick={() => setShow(!show)}
              >
                {show ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>
            {error && (
              <div className="form-error" role="alert">
                {error}
              </div>
            )}
            <button
              className="button primary login-submit"
              disabled={busy || loading}
              type="submit"
            >
              {busy ? "Signing in…" : "Sign in to workspace"}
              <ArrowRight size={17} />
            </button>
          </form>
          <div className="secure-note">
            <ShieldCheck size={15} />
            Secure session · Role-based access
          </div>
          <p className="login-local-note">
            Use the account configured by your administrator. Initial
            development accounts require a password change after sign-in.
          </p>
        </div>
        <span className="login-copyright">NAVSPHERE · CONNECTED BY DESIGN</span>
      </section>
    </div>
  );
}
