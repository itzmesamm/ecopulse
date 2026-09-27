import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AuthLayout from "../components/auth/AuthLayout";
import { Icon } from "../components/ui/Icon";
import { api } from "../services/api";

export default function Login() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    const result = await api.login(form.email, form.password);
    setSubmitting(false);
    if (!result.ok) {
      setError(result.error || "Invalid email or password.");
      return;
    }
    navigate("/dashboard");
  }

  return (
    <AuthLayout>
      <div className="card auth-card">
        <h2>Welcome back</h2>
        <div className="sub">Sign in to your Veya workspace.</div>

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="email">Work email</label>
            <div className="input-wrap">
              <Icon name="mail" />
              <input
                id="email"
                type="email"
                required
                placeholder="you@company.com"
                value={form.email}
                onChange={(e) => update("email", e.target.value)}
              />
            </div>
          </div>

          <div className="field">
            <label htmlFor="password">Password</label>
            <div className="input-wrap">
              <Icon name="lock" />
              <input
                id="password"
                type="password"
                required
                placeholder="••••••••"
                value={form.password}
                onChange={(e) => update("password", e.target.value)}
              />
            </div>
          </div>

          {error && (
            <div style={{ color: "var(--red)", fontSize: 13, marginBottom: 8 }}>{error}</div>
          )}

          <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="auth-foot">
          Don't have an account? <a onClick={() => navigate("/signup")}>Start free trial</a>
        </div>
      </div>
    </AuthLayout>
  );
}
