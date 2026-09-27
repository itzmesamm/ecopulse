import { useEffect, useState } from "react";
import AppShell from "../components/layout/AppShell";
import Topbar from "../components/layout/Topbar";
import { Icon } from "../components/ui/Icon";
import { api } from "../services/api";

export default function Profile() {
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    api.getCurrentUser().then(setProfile).catch(() => {});
  }, []);

  const user = profile?.user;
  const account = profile?.account;

  return (
    <AppShell>
      <Topbar title="Profile" />
      <div className="page-sub">Your identity, role, and workspace details.</div>

      <div className="profile-layout">
        <section className="card panel profile-hero">
          <div className="profile-avatar">{user?.initials || "NM"}</div>
          <div>
            <h2>{user?.name || "Loading profile..."}</h2>
            <p>{user?.email || ""}</p>
            <span className="pill teal">{user?.role || "User"}</span>
          </div>
        </section>

        <section className="card panel profile-details">
          <div className="profile-detail">
            <Icon name="mail" />
            <div><span className="k">Email</span><strong>{user?.email || "Not available"}</strong></div>
          </div>
          <div className="profile-detail">
            <Icon name="building" />
            <div><span className="k">Workspace</span><strong>{account?.name || "Not available"}</strong></div>
          </div>
          <div className="profile-detail">
            <Icon name="cloud" />
            <div><span className="k">Primary provider</span><strong>{account?.provider || "Cloud account"}</strong></div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
