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
  const [accessKeyId, setAccessKeyId] = useState("");
  const [secretAccessKey, setSecretAccessKey] = useState("");
  const [sessionToken, setSessionToken] = useState("");
  const [region, setRegion] = useState("us-east-1");
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
      const result = await api.connectCloud(selectedProvider, {
        access_key_id: accessKeyId,
        secret_access_key: secretAccessKey,
        ...(sessionToken && { session_token: sessionToken }),
        region,
      });
      if (!result.ok) {
        setError(result.error || "Failed to connect cloud provider.");
        setConnecting(false);
        return;
      }
      setAccessKeyId("");
      setSecretAccessKey("");
      setSessionToken("");
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
            <span className="dot" /> Tagged instances only
          </span>
          <span>
            <span className="dot" /> Admin approval to stop
          </span>
          <span>
            <span className="dot" /> Credentials encrypted
          </span>
        </div>

        {step === 0 && (
          <ProviderGrid
            providers={providers}
            selected={selectedProvider}
            onSelect={setSelectedProvider}
          />
        )}

        {step === 1 && (
          <>
            <GrantAccess policy={policy} checklist={checklist} />
            {selectedProvider === "aws" ? (
              <div className="cloud-credentials">
                <h3>AWS account credentials</h3>
                <p>Credentials are sent to the backend for verification and encryption. Automation is limited to instances tagged EcoPulseAutomation=enabled.</p>
                <label htmlFor="aws-access-key">Access key ID</label>
                <input id="aws-access-key" autoComplete="off" value={accessKeyId} onChange={(event) => setAccessKeyId(event.target.value)} />
                <label htmlFor="aws-secret-key">Secret access key</label>
                <input id="aws-secret-key" type="password" autoComplete="new-password" value={secretAccessKey} onChange={(event) => setSecretAccessKey(event.target.value)} />
                <label htmlFor="aws-session-token">Session token <span>(temporary credentials only)</span></label>
                <input id="aws-session-token" type="password" autoComplete="new-password" value={sessionToken} onChange={(event) => setSessionToken(event.target.value)} />
                <label htmlFor="aws-region">Default region</label>
                <input id="aws-region" value={region} onChange={(event) => setRegion(event.target.value)} placeholder="us-east-1" />
              </div>
            ) : (
              <div className="workflow-message">AWS is the only live execution connector currently available. GCP and Azure setup is not enabled yet.</div>
            )}
          </>
        )}

        {step === 2 && (
          <div className="card" style={{ padding: 44, textAlign: "center" }}>
            <div className="icon-badge teal" style={{ width: 56, height: 56, margin: "0 auto 18px" }}>
              <Icon name="circleCheck" />
            </div>
            <h3 style={{ fontSize: 20, marginBottom: 8 }}>
              {providers.find((p) => p.id === selectedProvider)?.name || "Cloud"} connected
            </h3>
            <p style={{ color: "var(--text-2)", fontSize: 14 }}>
              AWS identity verified and encrypted credentials stored. Billing and telemetry ingestion must be configured separately.
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
