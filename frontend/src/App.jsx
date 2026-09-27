import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeContext";
import { UserProvider } from "./context/UserContext";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import ConnectCloud from "./pages/ConnectCloud";
import Dashboard from "./pages/Dashboard";
import { api } from "./services/api";
import Analytics from "./pages/Analytics";
import Insights from "./pages/Insights";
import Alerts from "./pages/Alerts";
import GreenOps from "./pages/GreenOps";
import Settings from "./pages/Settings";
import Profile from "./pages/Profile";

function RequireAuth({ children }) {
  if (!api.isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <UserProvider>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />

          <Route
            path="/connect"
            element={
              <RequireAuth>
                <ConnectCloud />
              </RequireAuth>
            }
          />

          <Route
            path="/dashboard"
            element={
              <RequireAuth>
                <Dashboard />
              </RequireAuth>
            }
          />

          <Route
            path="/analytics"
            element={
              <RequireAuth>
                <Analytics />
              </RequireAuth>
            }
          />

          <Route
            path="/insights"
            element={
              <RequireAuth>
                <Insights />
              </RequireAuth>
            }
          />

          <Route
            path="/alerts"
            element={
              <RequireAuth>
                <Alerts />
              </RequireAuth>
            }
          />

          <Route
            path="/greenops"
            element={
              <RequireAuth>
                <GreenOps />
              </RequireAuth>
            }
          />

          <Route
            path="/settings"
            element={
              <RequireAuth>
                <Settings />
              </RequireAuth>
            }
          />

          <Route
            path="/profile"
            element={
              <RequireAuth>
                <Profile />
              </RequireAuth>
            }
          />
        </Routes>
        </UserProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}