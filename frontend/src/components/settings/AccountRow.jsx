import { IconBadge, Pill } from "../ui/Pill";

export default function AccountRow({ account }) {
  return (
    <div className="account-row">
      <IconBadge icon="cloud" tone="blue" />
      <div className="info">
        <div className="name">{account.name}</div>
        <div className="sub">{account.provider} · last sync {account.lastSync}</div>
      </div>
      <Pill tone={account.status === "connected" ? "green" : "orange"}>
        {account.status === "connected" ? "Connected" : "Pending"}
      </Pill>
    </div>
  );
}