import { useEffect, useState } from "react";
import { Bell, AlertTriangle, Info, CheckCheck } from "lucide-react";
import { api, Alert, Child } from "../lib/api";
import clsx from "clsx";

const ALERT_ICONS: Record<string, React.ElementType> = {
  vpn_attempt: AlertTriangle,
  birthday_milestone: Info,
};

const ALERT_COLORS: Record<string, string> = {
  vpn_attempt: "text-amber-500 bg-amber-50",
  birthday_milestone: "text-blue-500 bg-blue-50",
};

export default function Alerts() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [children, setChildren] = useState<Child[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.alerts.list(), api.children.list()]).then(([a, c]) => {
      setAlerts(a);
      setChildren(c);
      setLoading(false);
    });
  }, []);

  async function markAllRead() {
    await api.alerts.markAllRead();
    setAlerts(alerts.map((a) => ({ ...a, read: true })));
  }

  async function markRead(id: number) {
    await api.alerts.markRead(id);
    setAlerts(alerts.map((a) => (a.id === id ? { ...a, read: true } : a)));
  }

  const childName = (id: number | null) =>
    children.find((c) => c.id === id)?.name ?? "Unknown";

  const unread = alerts.filter((a) => !a.read).length;

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold">Alerts</h1>
          {unread > 0 && (
            <span className="bg-brand-600 text-white text-xs font-bold px-2 py-0.5 rounded-full">
              {unread}
            </span>
          )}
        </div>
        {unread > 0 && (
          <button
            onClick={markAllRead}
            className="flex items-center gap-1.5 text-sm text-brand-600 hover:text-brand-700 font-medium"
          >
            <CheckCheck size={15} />
            Mark all read
          </button>
        )}
      </div>

      {loading && <div className="text-slate-400 text-sm">Loading...</div>}

      {!loading && alerts.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-200 px-6 py-10 text-center">
          <Bell className="mx-auto text-slate-300 mb-3" size={32} />
          <div className="text-slate-500 text-sm">No alerts yet.</div>
        </div>
      )}

      <div className="space-y-2">
        {alerts.map((alert) => {
          const Icon = ALERT_ICONS[alert.alert_type] ?? Bell;
          const color = ALERT_COLORS[alert.alert_type] ?? "text-slate-500 bg-slate-50";
          return (
            <div
              key={alert.id}
              onClick={() => !alert.read && markRead(alert.id)}
              className={clsx(
                "bg-white rounded-xl border border-slate-200 px-4 py-3 flex gap-3 cursor-pointer",
                !alert.read && "border-brand-200 bg-brand-50/30"
              )}
            >
              <div className={clsx("w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5", color)}>
                <Icon size={15} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <div className="font-medium text-sm">{alert.title}</div>
                  {!alert.read && (
                    <span className="w-2 h-2 rounded-full bg-brand-500 flex-shrink-0 mt-1.5" />
                  )}
                </div>
                {alert.detail && (
                  <div className="text-xs text-slate-500 mt-0.5">{alert.detail}</div>
                )}
                <div className="text-xs text-slate-400 mt-1">
                  {alert.child_id ? childName(alert.child_id) + " · " : ""}
                  {new Date(alert.ts).toLocaleString()}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
