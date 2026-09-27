import { useNavigate } from "react-router-dom";
import ThemeToggle from "../ui/ThemeToggle";

export default function Navbar() {
  const navigate = useNavigate();

  return (
    <nav className="landing-nav">
      <div className="logo">
        <div className="mark">
          <span />
        </div>
        Veya
      </div>

      <div className="links">
        <a className="on">Product</a>
        <a>Pricing</a>
        <a>Docs</a>
        <a>Company</a>
      </div>

      <div className="cta">
        <ThemeToggle />
        <a className="signin" onClick={() => navigate("/login")}>
          Sign in
        </a>
        <button type="button" className="btn btn-primary" onClick={() => navigate("/signup")}>
          Start free
        </button>
      </div>
    </nav>
  );
}
