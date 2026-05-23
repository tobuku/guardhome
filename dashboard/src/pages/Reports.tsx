import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, Child, DaySummary, TopDomain, DnsLogEntry } from "../lib/api";

export default function Reports() {
  const [searchParams] = useSearchParams();
  const childParam = searchParams.get("child");

  const [children, setChildren] = useState<Child[]>([]);
  const [selectedChild, setSelectedChild] = useState<number | undefined>(
    childParam ? Number(childParam) : undefined
  );
  const [summary, setSummary] = useState<DaySummary[]>([]);
  const [topDomains, setTopDomains] = useState<{ top_allowed: TopDomain[]; top_blocked: TopDomain[] } | null>(null);
  const [log, setLog] = useState<DnsLogEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.children.list().then(setChildren);
  }, []);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.reports.summary(selectedChild),
      api.reports.topDomains(selectedChild),
      api.reports.log({ child_id: selectedChild, limit: 50 }),
    ]).then(([s, t, l]) => {
      setSummary(s);
      setTopDomains(t);
      setLog(l);
      setLoading(false);
    });
  }, [selectedChild]);

  const totalQueries = summary.reduce((a, b) => a + b.total, 0);
  const totalBlocked = summary.reduce((a, b) => a + (b.blocked ?? 0), 0);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-semibold">Reports</h1>
        <select
          value={selectedChild ?? ""}
          onChange={(e) => setSelectedChild(e.target.value ? Number(e.target.value) : undefined)}
          className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option value="">All children</option>
          {children.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <StatCard label="Queries (7 days)" value={totalQueries.toLocaleString()} />
        <StatCard label="Blocked" value={totalBlocked.toLocaleString()} accent="red" />
        <StatCard
          label="Block rate"
          value={totalQueries > 0 ? `${Math.round((totalBlocked / totalQueries) * 100)}%` : "—"}
        />
      </div>

      {/* Daily bar chart */}
      {summary.length > 0 && (
        <section>
          <h2 className="font-medium mb-3">Last 7 days</h2>
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="flex items-end gap-1 h-24">
              {summary.slice(0, 7).reverse().map((day) => {
                const pct = totalQueries > 0 ? (day.total / (totalQueries / summary.length)) * 60 : 0;
                return (
                  <div key={day.date} className="flex-1 flex flex-col items-center gap-1">
                    <div
                      className="w-full bg-brand-500 rounded-t"
                      style={{ height: `${Math.max(4, Math.min(96, pct))}px` }}
                    />
                    <div className="text-xs text-slate-400">{day.date.slice(5)}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {/* Top domains */}
      {topDomains && (
        <div className="grid gap-4 sm:grid-cols-2">
          <section>
            <h2 className="font-medium mb-3">Top visited (24h)</h2>
            <DomainList domains={topDomains.top_allowed} />
          </section>
          <section>
            <h2 className="font-medium mb-3">Top blocked (24h)</h2>
            <DomainList domains={topDomains.top_blocked} accent />
          </section>
        </div>
      )}

      {/* Recent log */}
      <section>
        <h2 className="font-medium mb-3">Recent activity</h2>
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          {loading && <div className="px-4 py-3 text-sm text-slate-400">Loading...</div>}
          {!loading && log.length === 0 && (
            <div className="px-4 py-3 text-sm text-slate-400">No queries recorded yet.</div>
          )}
          <div className="divide-y divide-slate-100 max-h-96 overflow-auto">
            {log.map((entry) => (
              <div key={entry.id} className="flex items-center justify-between px-4 py-2.5 text-sm">
                <div className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      entry.blocked ? "bg-red-400" : "bg-green-400"
                    }`}
                  />
                  <span className="font-mono text-xs text-slate-700 truncate max-w-[200px] sm:max-w-xs">
                    {entry.domain}
                  </span>
                </div>
                <span className="text-xs text-slate-400 flex-shrink-0">
                  {new Date(entry.ts).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 px-4 py-3">
      <div className={`text-2xl font-bold ${accent === "red" ? "text-red-500" : "text-slate-900"}`}>
        {value}
      </div>
      <div className="text-xs text-slate-500 mt-0.5">{label}</div>
    </div>
  );
}

function DomainList({ domains, accent }: { domains: TopDomain[]; accent?: boolean }) {
  if (domains.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-400">
        None
      </div>
    );
  }
  const max = domains[0]?.hits ?? 1;
  return (
    <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
      {domains.slice(0, 10).map((d) => (
        <div key={d.domain} className="px-4 py-2 flex items-center gap-3">
          <div className="flex-1 min-w-0">
            <div className="text-xs font-mono text-slate-700 truncate">{d.domain}</div>
            <div
              className={`mt-1 h-1 rounded-full ${accent ? "bg-red-300" : "bg-brand-300"}`}
              style={{ width: `${(d.hits / max) * 100}%` }}
            />
          </div>
          <div className="text-xs text-slate-400 flex-shrink-0">{d.hits}</div>
        </div>
      ))}
    </div>
  );
}
