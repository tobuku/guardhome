import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ChevronLeft, Plus, Trash2 } from "lucide-react";
import { api, Child, Schedule as ScheduleType } from "../lib/api";
import clsx from "clsx";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const PRESETS = [
  {
    label: "School hours",
    days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    start: "07:00",
    end: "15:00",
    action: "block_all",
  },
  {
    label: "Bedtime (weekdays)",
    days: ["Mon", "Tue", "Wed", "Thu", "Fri"],
    start: "21:00",
    end: "23:59",
    action: "block_all",
  },
  {
    label: "Bedtime (weekends)",
    days: ["Sat", "Sun"],
    start: "22:00",
    end: "23:59",
    action: "block_all",
  },
];

export default function Schedule() {
  const { id } = useParams<{ id: string }>();
  const childId = Number(id);

  const [child, setChild] = useState<Child | null>(null);
  const [schedules, setSchedules] = useState<ScheduleType[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);

  const [newName, setNewName] = useState("Bedtime");
  const [newDays, setNewDays] = useState<string[]>(["Mon", "Tue", "Wed", "Thu", "Fri"]);
  const [newStart, setNewStart] = useState("21:00");
  const [newEnd, setNewEnd] = useState("23:59");

  useEffect(() => {
    Promise.all([api.children.get(childId), api.rules.getSchedules(childId)]).then(
      ([c, s]) => {
        setChild(c);
        setSchedules(s);
        setLoading(false);
      }
    );
  }, [childId]);

  async function addSchedule() {
    const s = await api.rules.createSchedule(childId, {
      name: newName,
      days: newDays,
      start_time: newStart,
      end_time: newEnd,
      action: "block_all",
      enabled: true,
    });
    setSchedules([...schedules, s]);
    setAdding(false);
  }

  async function deleteSchedule(scheduleId: number) {
    await api.rules.deleteSchedule(childId, scheduleId);
    setSchedules(schedules.filter((s) => s.id !== scheduleId));
  }

  function applyPreset(p: (typeof PRESETS)[0]) {
    setNewName(p.label);
    setNewDays(p.days);
    setNewStart(p.start);
    setNewEnd(p.end);
  }

  function toggleDay(day: string) {
    setNewDays((d) => d.includes(day) ? d.filter((x) => x !== day) : [...d, day]);
  }

  if (loading) return <div className="text-slate-400 text-sm">Loading...</div>;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-2">
        <Link to={`/child/${childId}`} className="text-slate-400 hover:text-slate-600">
          <ChevronLeft size={20} />
        </Link>
        <h1 className="text-xl font-semibold">{child?.name} — Schedule</h1>
      </div>

      <p className="text-sm text-slate-500">
        Blocked windows cut all internet access for this child's devices.
        The internet resumes automatically when the window ends.
      </p>

      {/* Existing schedules */}
      <div className="space-y-3">
        {schedules.length === 0 && (
          <div className="text-sm text-slate-400">No schedules set.</div>
        )}
        {schedules.map((s) => (
          <div key={s.id} className="bg-white rounded-xl border border-slate-200 px-4 py-3 flex items-center justify-between">
            <div>
              <div className="font-medium text-sm">{s.name}</div>
              <div className="text-xs text-slate-400 mt-0.5">
                {s.days.join(", ")} · {s.start_time}–{s.end_time}
              </div>
            </div>
            <button
              onClick={() => deleteSchedule(s.id)}
              className="text-slate-300 hover:text-red-500 transition-colors"
            >
              <Trash2 size={16} />
            </button>
          </div>
        ))}
      </div>

      {/* Add schedule */}
      {!adding ? (
        <button
          onClick={() => setAdding(true)}
          className="flex items-center gap-2 text-sm text-brand-600 hover:text-brand-700 font-medium"
        >
          <Plus size={16} />
          Add blocked window
        </button>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-4">
          <h3 className="font-medium text-sm">New blocked window</h3>

          {/* Presets */}
          <div>
            <div className="text-xs text-slate-500 mb-2">Quick presets:</div>
            <div className="flex gap-2 flex-wrap">
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  onClick={() => applyPreset(p)}
                  className="px-3 py-1 text-xs rounded-full bg-slate-100 text-slate-600 hover:bg-brand-100 hover:text-brand-700 transition-colors"
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Name</label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 mb-2">Days</label>
            <div className="flex gap-2">
              {DAYS.map((day) => (
                <button
                  key={day}
                  onClick={() => toggleDay(day)}
                  className={clsx(
                    "w-9 h-9 rounded-full text-xs font-medium transition-colors",
                    newDays.includes(day)
                      ? "bg-brand-600 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  )}
                >
                  {day.slice(0, 1)}
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-4">
            <div className="flex-1">
              <label className="block text-xs font-medium text-slate-600 mb-1">Start</label>
              <input
                type="time"
                value={newStart}
                onChange={(e) => setNewStart(e.target.value)}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <div className="flex-1">
              <label className="block text-xs font-medium text-slate-600 mb-1">End</label>
              <input
                type="time"
                value={newEnd}
                onChange={(e) => setNewEnd(e.target.value)}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          </div>

          <div className="flex gap-3 justify-end">
            <button onClick={() => setAdding(false)} className="text-sm text-slate-500 hover:text-slate-700">
              Cancel
            </button>
            <button
              onClick={addSchedule}
              className="px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Add
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
