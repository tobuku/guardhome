import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { api, Child } from "../lib/api";
import clsx from "clsx";

const CATEGORY_DEFS = [
  {
    group: "Adult Content",
    items: [
      { key: "adult",      label: "Adult / Pornography",   desc: "All pornographic and sexually explicit content" },
      { key: "gore",       label: "Gore & Graphic Violence", desc: "Graphic injuries, death, torture" },
      { key: "gore_anime", label: "Gore Anime",             desc: "Hentai gore, ero-guro, horror anime" },
    ],
  },
  {
    group: "Harmful Content",
    items: [
      { key: "gambling",            label: "Gambling",                desc: "Online casinos, sports betting, poker" },
      { key: "drugs",               label: "Drugs & Alcohol",         desc: "Drug purchase sites, pro-drug content" },
      { key: "political_extremism", label: "Political Extremism",     desc: "Hate groups, radicalization content" },
      { key: "self_harm",           label: "Self-Harm / Eating Disorders", desc: "Pro-ana, self-harm methods, suicide methods" },
    ],
  },
  {
    group: "Social & Entertainment",
    items: [
      { key: "social_media", label: "Social Media",  desc: "Facebook, Instagram, TikTok, Twitter, Snapchat" },
      { key: "gaming",       label: "Gaming Sites",  desc: "Online gaming portals (not platform stores)" },
      { key: "streaming",    label: "Streaming",     desc: "Netflix, Hulu, YouTube, Twitch, Disney+" },
      { key: "chat_apps",    label: "Chat Apps",     desc: "Discord, WhatsApp, Telegram" },
    ],
  },
  {
    group: "Bypass Attempts",
    items: [
      { key: "vpn", label: "VPN / Proxy Services", desc: "VPN providers and anonymizing proxies" },
    ],
  },
];

export default function Categories() {
  const { id } = useParams<{ id: string }>();
  const childId = Number(id);

  const [child, setChild] = useState<Child | null>(null);
  const [rules, setRules] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.children.get(childId),
      api.children.getCategories(childId),
    ]).then(([c, r]) => {
      setChild(c);
      setRules(r);
      setLoading(false);
    });
  }, [childId]);

  async function toggle(category: string) {
    const current = rules[category] ?? false;
    const next = !current;
    setRules((r) => ({ ...r, [category]: next }));
    setSaving(category);
    await api.children.setCategory(childId, category, next);
    setSaving(null);
  }

  if (loading) return <div className="text-slate-400 text-sm">Loading...</div>;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-2">
        <Link to={`/child/${childId}`} className="text-slate-400 hover:text-slate-600">
          <ChevronLeft size={20} />
        </Link>
        <h1 className="text-xl font-semibold">{child?.name} — Content Filters</h1>
      </div>

      <p className="text-sm text-slate-500">
        Toggle categories on or off. Changes take effect immediately on all assigned devices.
      </p>

      {CATEGORY_DEFS.map((group) => (
        <section key={group.group}>
          <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-2">
            {group.group}
          </h2>
          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
            {group.items.map(({ key, label, desc }) => {
              const blocked = rules[key] ?? false;
              return (
                <div key={key} className="flex items-center justify-between px-4 py-3">
                  <div className="flex-1 pr-4">
                    <div className="text-sm font-medium">{label}</div>
                    <div className="text-xs text-slate-400">{desc}</div>
                  </div>
                  <Toggle
                    on={blocked}
                    disabled={saving === key}
                    onChange={() => toggle(key)}
                  />
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

function Toggle({
  on,
  onChange,
  disabled,
}: {
  on: boolean;
  onChange: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      role="switch"
      aria-checked={on}
      onClick={onChange}
      disabled={disabled}
      className={clsx(
        "relative w-11 h-6 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:opacity-50",
        on ? "bg-brand-600" : "bg-slate-200"
      )}
    >
      <span
        className={clsx(
          "absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform",
          on ? "translate-x-5" : "translate-x-0"
        )}
      />
    </button>
  );
}
