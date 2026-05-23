import { useState } from "react";
import { Shield, Plus, Trash2 } from "lucide-react";
import { api, setToken, WizardChild } from "../lib/api";

const PRESETS = [
  { value: "elementary",   label: "Elementary (K-5)",      desc: "Very restrictive" },
  { value: "middle_school", label: "Middle School (6-8)",  desc: "Moderate" },
  { value: "high_school",  label: "High School (9-12)",    desc: "Light restrictions" },
];

interface Props { onComplete: () => void; }

export default function Setup({ onComplete }: Props) {
  const [step, setStep] = useState(0);
  const [networkName, setNetworkName] = useState("Our Home");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [children, setChildren] = useState<WizardChild[]>([
    { name: "", age: 10, preset: "middle_school" },
  ]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const steps = ["Welcome", "Password", "Add Children", "Done"];

  async function finish() {
    setLoading(true);
    setError("");
    try {
      // Step 1: set password (also returns token)
      const res = await api.setup.setPassword(password);
      setToken(res.access_token);

      // Step 2: set network name
      await api.setup.setNetworkName(networkName);

      // Step 3: bulk add children
      const valid = children.filter((c) => c.name.trim());
      if (valid.length > 0) {
        await api.setup.bulkAddChildren(valid);
      }

      // Step 4: mark wizard complete (triggers AdGuard sync)
      await api.setup.complete();

      onComplete();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Setup failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-3">
            <Shield className="text-brand-600" size={40} />
          </div>
          <h1 className="text-2xl font-bold text-brand-700">GuardHome Setup</h1>
          <p className="text-slate-500 text-sm mt-1">Takes about 2 minutes</p>
        </div>

        {/* Progress dots */}
        <div className="flex justify-center gap-2 mb-8">
          {steps.map((s, i) => (
            <div
              key={s}
              className={`h-2 rounded-full transition-all ${
                i === step ? "w-8 bg-brand-600" : i < step ? "w-2 bg-brand-400" : "w-2 bg-slate-300"
              }`}
            />
          ))}
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
          {step === 0 && (
            <div className="space-y-5">
              <h2 className="text-lg font-semibold">Welcome to GuardHome</h2>
              <p className="text-sm text-slate-600">
                GuardHome is a self-hosted parental control platform that runs on your home network.
                No cloud account, no monthly fee.
              </p>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  What should we call your home network?
                </label>
                <input
                  type="text"
                  value={networkName}
                  onChange={(e) => setNetworkName(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="The Johnson Family"
                />
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="space-y-5">
              <h2 className="text-lg font-semibold">Set a parent password</h2>
              <p className="text-sm text-slate-600">
                This protects your GuardHome dashboard. Only parents should know this password.
              </p>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Confirm password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              {error && <p className="text-red-600 text-sm">{error}</p>}
            </div>
          )}

          {step === 2 && (
            <div className="space-y-5">
              <h2 className="text-lg font-semibold">Add your children</h2>
              <p className="text-sm text-slate-600">
                GuardHome will apply age-appropriate filter presets automatically.
                You can customize everything later.
              </p>
              <div className="space-y-4">
                {children.map((child, i) => (
                  <div key={i} className="border border-slate-200 rounded-xl p-4 space-y-3">
                    <div className="flex gap-3">
                      <input
                        type="text"
                        placeholder="Child's name"
                        value={child.name}
                        onChange={(e) => {
                          const next = [...children];
                          next[i] = { ...next[i], name: e.target.value };
                          setChildren(next);
                        }}
                        className="flex-1 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                      />
                      <input
                        type="number"
                        placeholder="Age"
                        value={child.age}
                        min={1}
                        max={18}
                        onChange={(e) => {
                          const next = [...children];
                          next[i] = { ...next[i], age: Number(e.target.value) };
                          setChildren(next);
                        }}
                        className="w-20 border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                      />
                      {children.length > 1 && (
                        <button
                          onClick={() => setChildren(children.filter((_, j) => j !== i))}
                          className="text-slate-400 hover:text-red-500"
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                    <div className="flex gap-2 flex-wrap">
                      {PRESETS.map((p) => (
                        <button
                          key={p.value}
                          onClick={() => {
                            const next = [...children];
                            next[i] = { ...next[i], preset: p.value };
                            setChildren(next);
                          }}
                          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                            child.preset === p.value
                              ? "bg-brand-600 text-white"
                              : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                          }`}
                        >
                          {p.label}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <button
                onClick={() => setChildren([...children, { name: "", age: 10, preset: "middle_school" }])}
                className="flex items-center gap-2 text-brand-600 text-sm font-medium hover:text-brand-700"
              >
                <Plus size={16} />
                Add another child
              </button>
            </div>
          )}

          {step === 3 && (
            <div className="text-center space-y-4">
              <div className="text-4xl">🛡️</div>
              <h2 className="text-lg font-semibold">All set!</h2>
              <p className="text-sm text-slate-600">
                GuardHome is configured. Point your router's DNS server to this machine's IP address
                to enable filtering for all home devices.
              </p>
              {error && <p className="text-red-600 text-sm">{error}</p>}
            </div>
          )}

          {/* Nav buttons */}
          <div className="mt-8 flex justify-between">
            {step > 0 && step < 3 ? (
              <button
                onClick={() => setStep(step - 1)}
                className="px-4 py-2 text-sm text-slate-600 hover:text-slate-900"
              >
                Back
              </button>
            ) : <div />}

            {step < 2 && (
              <button
                onClick={() => {
                  if (step === 1) {
                    if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
                    if (password !== confirmPassword) { setError("Passwords do not match."); return; }
                    setError("");
                  }
                  setStep(step + 1);
                }}
                className="px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium rounded-lg transition-colors"
              >
                Next
              </button>
            )}

            {step === 2 && (
              <button
                onClick={() => { setStep(3); finish(); }}
                disabled={loading}
                className="px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
              >
                {loading ? "Setting up..." : "Finish setup"}
              </button>
            )}

            {step === 3 && (
              <button
                onClick={onComplete}
                disabled={loading}
                className="px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
              >
                Go to Dashboard
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
