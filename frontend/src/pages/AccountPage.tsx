import { useState, type FormEvent } from "react";
import { CheckCircle2, KeyRound, ShieldCheck } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { StatusBadge } from "../components/StatusBadge";

export function AccountPage() {
  const { user, changePassword } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSuccess(false);
    if (next !== confirm) {
      setError("The new passwords do not match.");
      return;
    }
    if (next.length < 12) {
      setError("Use at least 12 characters for your new password.");
      return;
    }
    setBusy(true);
    try {
      await changePassword(current, next);
      setSuccess(true);
      setCurrent("");
      setNext("");
      setConfirm("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password change failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Account & security</h1>
          <p>Manage access to your telemetry workspace.</p>
        </div>
        <StatusBadge state="good">
          <ShieldCheck size={13} />
          Authenticated session
        </StatusBadge>
      </div>
      {user?.must_change_password && (
        <div className="notice warning">
          <KeyRound size={18} />
          <span>
            <strong>Set your own password to continue.</strong> Your initial
            development credentials must be changed before sending commands.
          </span>
        </div>
      )}
      <div className="account-grid">
        <section className="panel account-form">
          <div className="panel-heading">
            <div>
              <h2>
                <KeyRound size={18} />
                Change password
              </h2>
              <p>Choose a unique password with at least 12 characters.</p>
            </div>
          </div>
          <form onSubmit={(event) => void submit(event)}>
            <label htmlFor="current-password">Current password</label>
            <input
              id="current-password"
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(event) => setCurrent(event.target.value)}
              required
              maxLength={256}
            />
            <label htmlFor="new-password">New password</label>
            <input
              id="new-password"
              type="password"
              autoComplete="new-password"
              value={next}
              onChange={(event) => setNext(event.target.value)}
              minLength={12}
              maxLength={256}
              required
            />
            <label htmlFor="confirm-password">Confirm new password</label>
            <input
              id="confirm-password"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              minLength={12}
              maxLength={256}
              required
            />
            {error && (
              <div className="form-error" role="alert">
                {error}
              </div>
            )}
            {success && (
              <div className="notice success" role="status">
                <CheckCircle2 size={17} />
                Password updated. Your account is ready.
              </div>
            )}
            <button className="button primary" type="submit" disabled={busy}>
              {busy ? "Updating password…" : "Update password"}
            </button>
          </form>
        </section>
        <section className="panel account-summary">
          <span className="account-avatar">
            {user?.username.slice(0, 2).toUpperCase()}
          </span>
          <h2>{user?.username}</h2>
          <StatusBadge state="neutral">
            {user?.role === "admin" ? "Administrator" : "Viewer"}
          </StatusBadge>
          <div className="account-detail">
            <span>Session</span>
            <strong>HttpOnly cookie</strong>
          </div>
          <div className="account-detail">
            <span>Command authorization</span>
            <strong>
              {user?.role === "admin"
                ? user.must_change_password
                  ? "Password change required"
                  : "Administrator"
                : "Read only"}
            </strong>
          </div>
          <p>
            Administrative requests are verified by the backend and protected
            with a CSRF token. No credentials are stored in browser storage.
          </p>
        </section>
      </div>
    </>
  );
}
