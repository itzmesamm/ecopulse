import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeContext";
import { UserProvider } from "./context/UserContext";
import { api } from "./services/api";

const Landing = lazy(() => import("./pages/Landing"));
const Login = lazy(() => import("./pages/Login"));
const Signup = lazy(() => import("./pages/Signup"));
const ConnectCloud = lazy(() => import("./pages/ConnectCloud"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Analytics = lazy(() => import("./pages/Analytics"));
const Insights = lazy(() => import("./pages/Insights"));
const Alerts = lazy(() => import("./pages/Alerts"));
const GreenOps = lazy(() => import("./pages/GreenOps"));
const Settings = lazy(() => import("./pages/Settings"));
const Profile = lazy(() => import("./pages/Profile"));

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
        <Suspense fallback={<div className="route-loading" role="status">Loading page…</div>}>
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
        </Suspense>
        </UserProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}