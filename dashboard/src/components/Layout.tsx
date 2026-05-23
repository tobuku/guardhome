import { ReactNode, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Shield, LayoutDashboard, Bell, BarChart2, Menu, X, LogOut,
} from "lucide-react";
import { clearToken } from "../lib/api";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";

const NAV = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/reports", icon: BarChart2, label: "Reports" },
  { to: "/alerts", icon: Bell, label: "Alerts" },
];

export default function Layout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  function logout() {
    clearToken();
    navigate("/");
    window.location.reload();
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Top bar */}
      <header className="bg-white border-b border-slate-200 h-14 flex items-center px-4 gap-3 sticky top-0 z-40">
        <button className="md:hidden p-1" onClick={() => setOpen(!open)}>
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
        <Shield className="text-brand-600" size={22} />
        <span className="font-bold text-brand-700 text-lg">GuardHome</span>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={logout}
            className="flex items-center gap-1 text-slate-500 hover:text-slate-800 text-sm px-2 py-1 rounded"
          >
            <LogOut size={15} />
            <span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
      </header>

      <div className="flex flex-1">
        {/* Sidebar */}
        <nav
          className={clsx(
            "fixed inset-y-0 left-0 z-30 bg-white border-r border-slate-200 w-56 pt-14 transition-transform md:translate-x-0 md:static md:flex md:flex-col",
            open ? "translate-x-0" : "-translate-x-full"
          )}
        >
          <ul className="p-3 space-y-1">
            {NAV.map(({ to, icon: Icon, label }) => (
              <li key={to}>
                <Link
                  to={to}
                  onClick={() => setOpen(false)}
                  className={clsx(
                    "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                    location.pathname === to
                      ? "bg-brand-50 text-brand-700"
                      : "text-slate-600 hover:bg-slate-100"
                  )}
                >
                  <Icon size={16} />
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        {/* Overlay for mobile */}
        {open && (
          <div
            className="fixed inset-0 z-20 bg-black/30 md:hidden"
            onClick={() => setOpen(false)}
          />
        )}

        {/* Main content */}
        <main className="flex-1 p-4 md:p-6 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
