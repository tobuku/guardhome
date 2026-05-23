import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Download, ChevronRight, Smartphone } from "lucide-react";
import { api, Child as ChildType, Device } from "../lib/api";

export default function Child() {
  const { id } = useParams<{ id: string }>();
  const childId = Number(id);

  const [child, setChild] = useState<ChildType | null>(null);
  const [devices, setDevices] = useState<Device[]>([]);
  const [allDevices, setAllDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.children.get(childId),
      api.devices.list(),
    ]).then(([c, d]) => {
      setChild(c);
      setAllDevices(d);
      setDevices(d.filter((dev) => dev.child_id === childId));
      setLoading(false);
    });
  }, [childId]);

  async function assignDevice(deviceId: number) {
    await api.devices.assign(deviceId, childId);
    const updated = await api.devices.list();
    setAllDevices(updated);
    setDevices(updated.filter((d) => d.child_id === childId));
  }

  async function unassignDevice(deviceId: number) {
    await api.devices.assign(deviceId, null);
    const updated = await api.devices.list();
    setAllDevices(updated);
    setDevices(updated.filter((d) => d.child_id === childId));
  }

  if (loading || !child) return <div className="text-slate-400 text-sm">Loading...</div>;

  const unassigned = allDevices.filter((d) => d.child_id === null);

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{child.name}</h1>
          <div className="text-sm text-slate-500">
            {child.age ? `Age ${child.age}` : ""}
            {child.preset ? ` · ${child.preset.replace("_", " ")} preset` : ""}
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <QuickLink to={`/child/${childId}/categories`} label="Content filters" />
        <QuickLink to={`/child/${childId}/schedule`} label="Schedule" />
        <QuickLink to={`/reports?child=${childId}`} label="Activity report" />
      </div>

      {/* Devices */}
      <section>
        <h2 className="font-medium mb-3">Assigned devices</h2>
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
          {devices.length === 0 && (
            <div className="px-4 py-3 text-sm text-slate-400">No devices assigned yet.</div>
          )}
          {devices.map((d) => (
            <div key={d.id} className="flex items-center justify-between px-4 py-3">
              <div>
                <div className="text-sm font-medium">{d.label || d.hostname || d.mac}</div>
                <div className="text-xs text-slate-400">{d.mac} · {d.ip}</div>
              </div>
              <button
                onClick={() => unassignDevice(d.id)}
                className="text-xs text-red-500 hover:text-red-700"
              >
                Remove
              </button>
            </div>
          ))}
        </div>

        {unassigned.length > 0 && (
          <div className="mt-3">
            <div className="text-xs font-medium text-slate-500 mb-2">Add a device:</div>
            <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
              {unassigned.map((d) => (
                <div key={d.id} className="flex items-center justify-between px-4 py-3">
                  <div>
                    <div className="text-sm">{d.label || d.hostname || d.mac}</div>
                    <div className="text-xs text-slate-400">{d.ip}</div>
                  </div>
                  <button
                    onClick={() => assignDevice(d.id)}
                    className="text-xs text-brand-600 hover:text-brand-700 font-medium"
                  >
                    Assign
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* iOS Profile download */}
      <section className="bg-sky-50 border border-sky-200 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <Smartphone className="text-sky-600 mt-0.5" size={20} />
          <div className="flex-1">
            <div className="font-medium text-sky-900 text-sm">iOS / iPadOS Configuration Profile</div>
            <p className="text-xs text-sky-700 mt-1">
              Download and install this profile on {child.name}'s iPhone or iPad to enforce
              restrictions even if DNS is changed. Requires no MDM server.
            </p>
            <a
              href={api.agents.iosProfileUrl(childId)}
              download
              className="inline-flex items-center gap-1.5 mt-3 bg-sky-600 hover:bg-sky-700 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
            >
              <Download size={13} />
              Download .mobileconfig
            </a>
          </div>
        </div>
      </section>
    </div>
  );
}

function QuickLink({ to, label }: { to: string; label: string }) {
  return (
    <Link
      to={to}
      className="flex items-center justify-between bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm font-medium text-slate-700 hover:border-brand-400 hover:text-brand-700 transition-colors"
    >
      {label}
      <ChevronRight size={15} className="text-slate-400" />
    </Link>
  );
}
