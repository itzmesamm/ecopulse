import { IconBadge } from "../ui/Pill";
import { Icon } from "../ui/Icon";

export default function SecurityBand() {
  return (
    <div className="security-band">
      <IconBadge icon="shield" tone="teal" size={52} />
      <h3>Read-only by default, action only with approval</h3>
      <p>
        Veya connects with least-privilege, read-only IAM roles. Nothing is
        stopped, resized, or deleted without a policy match or your explicit
        sign-off — and every action is written to an immutable audit log.
      </p>
      <div className="marks">
        <span>
          <Icon name="lock" /> Least-privilege IAM
        </span>
        <span>
          <Icon name="check" /> Full audit trail
        </span>
        <span>
          <Icon name="shield" /> Dry-run by default
        </span>
      </div>
    </div>
  );
}
