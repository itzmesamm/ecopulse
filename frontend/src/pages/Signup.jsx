import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AuthLayout from "../components/auth/AuthLayout";
import { Icon } from "../components/ui/Icon";
import { api } from "../services/api";

const ROLES = ["Platform Eng", "FinOps", "DevOps", "Engineering Lead"];

export default function Signup() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", company: "", email: "", password: "", role: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    const result = await api.signup(form.email, form.password, form.company, form.name);
    setSubmitting(false);
    if (!result.ok) {
      setError(result.error || "Signup failed. Please try again.");
      return;
    }
    navigate("/connect");
  }

  return (
    <AuthLayout>
      <div className="card auth-card">
        <h2>Create your workspace</h2>
        <div className="sub">Free for 14 days. No credit card required.</div>

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="name">Full name</label>
            <div className="input-wrap">
              <Icon name="user" />
              <input
                id="name"
                required
                placeholder="Nikita Malhotra"
                value={form.name}
                onChange={(e) => update("name", e.target.value)}
              />
            </div>
          </div>

          <div className="field">
            <label htmlFor="company">Company</label>
            <div className="input-wrap">
              <Icon name="building" />
              <input
                id="company"
                required
                placeholder="Meridian Systems"
                value={form.company}
                onChange={(e) => update("company", e.target.value)}
              />
            </div>
          </div>

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
                placeholder="At least 8 characters"
                value={form.password}
                onChange={(e) => update("password", e.target.value)}
              />
            </div>
          </div>

          <div className="field">
            <label>Your role</label>
            <div className="role-grid">
              {ROLES.map((r) => (
                <div
                  key={r}
                  className={`role-opt ${form.role === r ? "sel" : ""}`}
                  onClick={() => update("role", r)}
                  role="button"
                  tabIndex={0}
                >
                  {r}
                </div>
              ))}
            </div>
          </div>

          {error && (
            <div style={{ color: "var(--red)", fontSize: 13, marginBottom: 8 }}>{error}</div>
          )}

          <button
            type="submit"
            className="btn btn-primary btn-block"
            disabled={submitting}
            style={{ marginTop: 6 }}
          >
            {submitting ? "Creating workspace…" : "Continue"}
          </button>
        </form>

        <div className="auth-foot">
          Already have an account? <a onClick={() => navigate("/login")}>Sign in</a>
        </div>
      </div>
    </AuthLayout>
  );
}
