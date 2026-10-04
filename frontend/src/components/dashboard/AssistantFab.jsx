import { Icon } from "../ui/Icon";

export default function AssistantFab({ onClick }) {
  return (
    <button type="button" className="assist-fab" onClick={onClick} aria-label="Open Veya assistant">
      <Icon name="assistant" />
      Ask Veya
    </button>
  );
}
