import { useTheme } from "../../context/ThemeContext";
import { Icon } from "./Icon";

export default function ThemeToggle({ compact = false }) {
  const { theme, setTheme } = useTheme();

  return (
    <div className="theme-toggle" role="group" aria-label="Theme">
      <button
        type="button"
        className={theme === "light" ? "active" : ""}
        onClick={() => setTheme("light")}
        aria-pressed={theme === "light"}
        title="Light theme"
      >
        <Icon name="sun" />
      </button>
      <button
        type="button"
        className={theme === "dark" ? "active" : ""}
        onClick={() => setTheme("dark")}
        aria-pressed={theme === "dark"}
        title="Dark theme"
      >
        <Icon name="moon" />
      </button>
      {!compact && null}
    </div>
  );
}
