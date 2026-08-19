import { useNavigate } from "react-router-dom";

export function FinalCTA() {
  const navigate = useNavigate();
  return (
    <section className="final-cta">
      <h2>Ready to see what your cloud is wasting?</h2>
      <div className="ctas">
        <button type="button" className="btn btn-primary" onClick={() => navigate("/signup")}>
          Start free trial
        </button>
        <button type="button" className="btn btn-ghost" onClick={() => navigate("/connect")}>
          See how it connects
        </button>
      </div>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="footer">
      <span>© {new Date().getFullYear()} Veya. All rights reserved.</span>
      <div className="flinks">
        <a>Privacy</a>
        <a>Terms</a>
        <a>Status</a>
      </div>
    </footer>
  );
}
