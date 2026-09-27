import { useTheme } from "../../context/ThemeContext";
import { Icon } from "../ui/Icon";

export default function ThemePicker() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="theme-picker">
      <div
        className={`theme-opt ${theme === "dark" ? "sel" : ""}`}
        onClick={() => setTheme("dark")}
        role="button"
        tabIndex={0}
      >
        <div className="swatch dark" />
        <div className="lbl">
          <Icon name="moon" style={{ width: 14, height: 14, display: "inline", marginRight: 6 }} />
          Dark
        </div>
      </div>
      <div
        className={`theme-opt ${theme === "light" ? "sel" : ""}`}
        onClick={() => setTheme("light")}
        role="button"
        tabIndex={0}
      >
        <div className="swatch light" />
        <div className="lbl">
          <Icon name="sun" style={{ width: 14, height: 14, display: "inline", marginRight: 6 }} />
          Light
        </div>
      </div>
    </div>
  );
}