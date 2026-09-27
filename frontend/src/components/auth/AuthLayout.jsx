import { useNavigate } from "react-router-dom";
import ThemeToggle from "../ui/ThemeToggle";

export default function AuthLayout({ children }) {
  const navigate = useNavigate();
  return (
    <div className="auth-shell">
      <div
        style={{
          position: "fixed",
          top: 24,
          left: 32,
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <div className="logo" onClick={() => navigate("/")} style={{ cursor: "pointer" }}>
          <div className="mark">
            <span />
          </div>
          Veya
        </div>
      </div>
      <div style={{ position: "fixed", top: 20, right: 32 }}>
        <ThemeToggle />
      </div>
      {children}
    </div>
  );
}
