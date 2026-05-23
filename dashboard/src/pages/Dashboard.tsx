import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PauseCircle, PlayCircle, Monitor, Smartphone, Laptop, Plus, RefreshCw } from "lucide-react";
import { api, Child, Device, Alert } from "../lib/api";
import clsx from "clsx";

export default function Dashboard() {
  const [children, setChildren] = useState<Child[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [paused, setPaused] = useState<Set<number>>(new Set());
  const [scanning, setScanning] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.children.list(),
      api.devices.list(),
      api.alerts.list({ unread_only: true }),
    ]).then(([c, d, a]) => {
      setChildren(c);
      setDevices(d);
      setAlerts(a);
      setLoading(false);
    });
  }, []);

  async function scanDevices() {
    setScanning(true);
    const res = await api.devices.scan();
    setDevices(res.devices);
    setScanning(false);
  }

  async function togglePause(deviceId: number) {
    if (paused.has(deviceId)) {
      await api.devices.resume(deviceId);
      setPaused((p) => { const n = new Set(p); n.delete(deviceId); return n; });
    } else {
      await api.devices.pause(deviceId);
      setPaused((p) => new Set(p).add(deviceId));
    }
  }

  const unassigned = devices.filter((d) => d.child_id === null);

  if (loading) return <div className="text-slate-400 text-sm">Loading...</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Home</h1>
        <button
          onClick={scanDevices}
          disabled={scanning}
          className="flex items-center gap-2 text-sm text-brand-600 hover:text-brand-700 font-medium"
        >
          <RefreshCw size={15} className={scanning ? "animate-spin" : ""} />
          Scan network
        </button>
      </div>

      {/* Unread alerts banner */}
      {alerts.length > 0 && (
        <Link
          to="/alerts"
          className="block bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-800 font-medium hover:bg-amber-100 transition-colors"
        >
          {alerts.length} unread alert{alerts.length !== 1 ? "s" : ""} — tap to review
        </Link>
      )}

      {/* Children cards */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-medium text-slate-700">Children</h2>
        </div>
        {children.length === 0 ? (
          <div className="text-slate-400 text-sm">No children added yet.</div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {children.map((child) => {
              const childDevices = devices.filter((d) => d.child_id === child.id);
              return (
                <ChildCard
                  key={child.id}
                  child={child}
                  devices={childDevices}
                  paused={paused}
                  onTogglePause={togglePause}
                />
              );
            })}
          </div>
        )}
      </section>

      {/* Unassigned devices */}
      {unassigned.length > 0 && (
        <section>
          <h2 className="font-medium text-slate-700 mb-3">Unassigned devices ({unassigned.length})</h2>
          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
            {unassigned.map((d) => (
              <div key={d.id} className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-3">
                  <DeviceIcon type={d.device_type} />
                  <div>
                    <div className="text-sm font-medium">{d.label || d.hostname || d.mac}</div>
                    <div className="text-xs text-slate-400">{d.ip}</div>
                  </div>
                </div>
                <span className="text-xs text-slate-400">Not assigned</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function ChildCard({
  child,
  devices,
  paused,
  onTogglePause,
}: {
  child: Child;
  devices: Device[];
  paused: Set<number>;
  onTogglePause: (id: number) => void;
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <div className="font-semibold">{child.name}</div>
          <div className="text-xs text-slate-400">
            {child.age ? `Age ${child.age}` : ""}
            {child.age ? " · " : ""}
            {child.preset.replace("_", " ")}
          </div>
        </div>
        <Link
          to={`/child/${child.id}`}
          className="text-xs text-brand-600 hover:text-brand-700 font-medium"
        >
          Manage
        </Link>
      </div>

      {/* Devices */}
      {devices.length > 0 ? (
        <div className="space-y-1">
          {devices.map((d) => (
            <div key={d.id} className="flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <DeviceIcon type={d.device_type} size={14} />
                <span className={clsx("text-slate-600", paused.has(d.id) && "line-through text-slate-400")}>
                  {d.label || d.hostname || d.mac}
                </span>
                {paused.has(d.id) && (
                  <span className="text-xs bg-red-100 text-red-600 px-1.5 rounded">Paused</span>
                )}
              </div>
              <button
                onClick={() => onTogglePause(d.id)}
                className={clsx(
                  "p-1 rounded",
                  paused.has(d.id)
                    ? "text-green-600 hover:text-green-700"
                    : "text-slate-400 hover:text-red-500"
                )}
                title={paused.has(d.id) ? "Resume internet" : "Pause internet"}
              >
                {paused.has(d.id) ? <PlayCircle size={16} /> : <PauseCircle size={16} />}
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-xs text-slate-400">No devices assigned</div>
      )}

      {/* Quick links */}
      <div className="flex gap-3 pt-1 border-t border-slate-100">
        <Link to={`/child/${child.id}/categories`} className="text-xs text-slate-500 hover:text-brand-600">
          Categories
        </Link>
        <Link to={`/child/${child.id}/schedule`} className="text-xs text-slate-500 hover:text-brand-600">
          Schedule
        </Link>
        <Link to={`/reports?child=${child.id}`} className="text-xs text-slate-500 hover:text-brand-600">
          Reports
        </Link>
      </div>
    </div>
  );
}

function DeviceIcon({ type, size = 16 }: { type?: string | null; size?: number }) {
  const t = (type ?? "").toLowerCase();
  if (t.includes("phone") || t.includes("ios") || t.includes("ipad")) return <Smartphone size={size} className="text-slate-400" />;
  if (t.includes("laptop")) return <Laptop size={size} className="text-slate-400" />;
  return <Monitor size={size} className="text-slate-400" />;
}
