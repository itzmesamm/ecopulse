import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AuthLayout from "../components/auth/AuthLayout";
import ProviderGrid from "../components/connect/ProviderGrid";
import GrantAccess from "../components/connect/GrantAccess";
import { Icon } from "../components/ui/Icon";
import { api } from "../services/api";

const STEPS = ["Choose provider", "Grant access", "You're all set"];

export default function ConnectCloud() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [providers, setProviders] = useState([]);
  const [policy, setPolicy] = useState("");
  const [checklist, setChecklist] = useState([]);
  const [selectedProvider, setSelectedProvider] = useState("aws");
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getCloudProviders().then(setProviders);
  }, []);

  useEffect(() => {
    api.getIamPolicySnippet(selectedProvider).then(setPolicy);
    api.getAccessChecklist(selectedProvider).then(setChecklist);
  }, [selectedProvider]);

  async function handleNext() {
    if (step === 1) {
      setConnecting(true);
      setError("");
      const result = await api.connectCloud(selectedProvider);
      if (!result.ok) {
        setError(result.error || "Failed to connect cloud provider.");
        setConnecting(false);
        return;
      }
      setConnecting(false);
    }
    if (step < STEPS.length - 1) setStep((s) => s + 1);
    else navigate("/dashboard");
  }

  function handleBack() {
    if (step === 0) navigate(-1);
    else setStep((s) => s - 1);
  }

  return (
    <AuthLayout>
      <div className="wizard-shell">
        <div className="wizard-head">
          <h2>Connect your cloud</h2>
          <p>Takes about 3 minutes. You can add more accounts later.</p>
        </div>

        <div className="wsteps">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={`wstep ${i < step ? "done" : i === step ? "now" : ""}`}
            />
          ))}
        </div>

        <div className="reassure">
          <span>
            <span className="dot" /> Read-only access
          </span>
          <span>
            <span className="dot" /> Revoke anytime
          </span>
          <span>
            <span className="dot" /> SOC 2 Type II
          </span>
        </div>

        {step === 0 && (
          <ProviderGrid
            providers={providers}
            selected={selectedProvider}
            onSelect={setSelectedProvider}
          />
        )}

        {step === 1 && <GrantAccess policy={policy} checklist={checklist} />}

        {step === 2 && (
          <div className="card" style={{ padding: 44, textAlign: "center" }}>
            <div className="icon-badge teal" style={{ width: 56, height: 56, margin: "0 auto 18px" }}>
              <Icon name="circleCheck" />
            </div>
            <h3 style={{ fontSize: 20, marginBottom: 8 }}>
              {providers.find((p) => p.id === selectedProvider)?.name || "Cloud"} connected
            </h3>
            <p style={{ color: "var(--text-2)", fontSize: 14 }}>
              Veya is now ingesting billing, infra, GPU, and Kubernetes data.
              Your dashboard will populate within a few minutes.
            </p>
          </div>
        )}

        {error && (
          <div style={{ color: "var(--red)", fontSize: 13, marginTop: 12, textAlign: "center" }}>
            {error}
          </div>
        )}

        <div className="wizard-nav">
          <button type="button" className="btn btn-ghost" onClick={handleBack}>
            Back
          </button>
          <button type="button" className="btn btn-primary" onClick={handleNext} disabled={connecting}>
            {connecting
              ? "Connecting…"
              : step === STEPS.length - 1
              ? "Go to dashboard"
              : "Continue"}
          </button>
        </div>
      </div>
    </AuthLayout>
  );
}
