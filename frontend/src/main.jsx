import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";

import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/ui.css";
import "./styles/pages.css";
import "./styles/app-shell.css";
import "./styles/dashboard.css";
import "./styles/landing.css";
import "./styles/auth.css";


createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
