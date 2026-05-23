import { useEffect, useState } from "react";
import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { api, hasToken } from "./lib/api";

import Layout from "./components/Layout";
import Login from "./pages/Login";
import Setup from "./pages/Setup";
import Dashboard from "./pages/Dashboard";
import Child from "./pages/Child";
import Categories from "./pages/Categories";
import Schedule from "./pages/Schedule";
import Reports from "./pages/Reports";
import Alerts from "./pages/Alerts";

export default function App() {
  const [ready, setReady] = useState(false);
  const [needsSetup, setNeedsSetup] = useState(false);
  const [needsLogin, setNeedsLogin] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api.setup.status().then((s) => {
      if (!s.password_set) {
        setNeedsSetup(true);
      } else if (!hasToken()) {
        setNeedsLogin(true);
      }
      setReady(true);
    });
  }, []);

  if (!ready) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin w-8 h-8 border-4 border-brand-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (needsSetup) return <Setup onComplete={() => { setNeedsSetup(false); navigate("/"); }} />;
  if (needsLogin) return <Login onLogin={() => { setNeedsLogin(false); navigate("/"); }} />;

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/child/:id" element={<Child />} />
        <Route path="/child/:id/categories" element={<Categories />} />
        <Route path="/child/:id/schedule" element={<Schedule />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
