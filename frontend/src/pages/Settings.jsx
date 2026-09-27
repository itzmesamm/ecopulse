import { useEffect, useState } from "react";
import AppShell from "../components/layout/AppShell";
import Topbar from "../components/layout/Topbar";
import ThemePicker from "../components/settings/ThemePicker";
import AccountRow from "../components/settings/AccountRow";
import ToggleRow from "../components/settings/ToggleRow";
import { api } from "../services/api";

export default function Settings() {
  const [accounts, setAccounts] = useState([]);
  const [types, setTypes] = useState([]);
  const [channels, setChannels] = useState([]);
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    api.getConnectedAccounts().then(setAccounts);
    api.getCurrentUser().then(setProfile);
    api.getNotificationSettings().then((res) => {
      setTypes(res.types);
      setChannels(res.channels);
    });
  }, []);

  function toggleType(id, enabled) {
    setTypes((list) => list.map((t) => (t.id === id ? { ...t, enabled } : t)));
    api.updateNotificationSetting(id, enabled);
  }

  function toggleChannel(id, enabled) {
    setChannels((list) => list.map((c) => (c.id === id ? { ...c, enabled } : c)));
    api.updateNotificationSetting(id, enabled);
  }

  return (
    <AppShell>
      <Topbar title="Settings" />
      <div className="page-sub">Manage appearance, your account, connected clouds, and notifications.</div>

      <div className="card panel settings-section">
        <h3>Appearance</h3>
        <div className="desc">Choose how Veya looks on this device.</div>
        <ThemePicker />
      </div>

      <div className="card panel settings-section">
        <h3>Account</h3>
        <div className="desc">Your profile information.</div>
        <div className="toggle-row">
          <div>
            <div className="t">{profile?.user.name || "Loading profile..."}</div>
            <div className="d">{profile?.user.email}</div>
          </div>
          <span className="pill blue">{profile?.user.role || "User"}</span>
        </div>
        <div className="toggle-row">
          <div>
            <div className="t">Primary workspace</div>
            <div className="d">{profile?.account.name || "Loading workspace..."}</div>
          </div>
          <span className="pill teal">{profile?.account.provider || "Cloud"}</span>
        </div>
      </div>

      <div className="card panel settings-section">
        <h3>Connected clouds</h3>
        <div className="desc">Accounts feeding data into your dashboard.</div>
        {accounts.map((a) => (
          <AccountRow key={a.id} account={a} />
        ))}
      </div>

      <div className="card panel settings-section">
        <h3>Notification types</h3>
        <div className="desc">Choose which events trigger an alert.</div>
        {types.map((t) => (
          <ToggleRow
            key={t.id}
            label={t.label}
            desc={t.desc}
            checked={t.enabled}
            onChange={(v) => toggleType(t.id, v)}
          />
        ))}
      </div>

      <div className="card panel settings-section">
        <h3>Notification channels</h3>
        <div className="desc">Where alerts get delivered.</div>
        {channels.map((c) => (
          <ToggleRow
            key={c.id}
            label={c.label}
            desc={c.desc}
            checked={c.enabled}
            onChange={(v) => toggleChannel(c.id, v)}
          />
        ))}
      </div>
    </AppShell>
  );
}