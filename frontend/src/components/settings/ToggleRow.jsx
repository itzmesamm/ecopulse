export default function ToggleRow({ label, desc, checked, onChange }) {
  return (
    <div className="toggle-row">
      <div>
        <div className="t">{label}</div>
        {desc && <div className="d">{desc}</div>}
      </div>
      <label className="switch">
        <input type="checkbox" checked={checked} onChange={(e) => onChange?.(e.target.checked)} />
        <span className="track" />
      </label>
    </div>
  );
}