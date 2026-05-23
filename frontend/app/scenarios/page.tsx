"use client";
import { useState } from "react";
import { FlaskConical, TrendingUp, TrendingDown, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

function fmt(n: number) {
  if (n >= 1_00_00_000) return `₹${(n / 1_00_00_000).toFixed(2)} Cr`;
  if (n >= 1_00_000) return `₹${(n / 1_00_000).toFixed(2)} L`;
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

const PRESETS = [
  { label: "Equity crash -30%", equity_return: -30, debt_return: 7 },
  { label: "Equity boom +40%", equity_return: 40, debt_return: 7 },
  { label: "High inflation (12%)", equity_return: 10, debt_return: 5, inflation_rate: 12 },
  { label: "Rate cut cycle", equity_return: 15, debt_return: 9 },
];

interface SimResult {
  p10: number;
  p50: number;
  p90: number;
  success_probability: number;
  goal_name?: string;
}

export default function ScenariosPage() {
  const [form, setForm] = useState({
    equity_return: "12",
    debt_return: "7",
    inflation_rate: "6",
    years: "10",
    monthly_sip: "25000",
  });
  const [results, setResults] = useState<SimResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function applyPreset(p: typeof PRESETS[0]) {
    setForm((f) => ({
      ...f,
      equity_return: String(p.equity_return),
      debt_return: String(p.debt_return),
      inflation_rate: String(p.inflation_rate ?? f.inflation_rate),
    }));
  }

  async function runSimulation(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResults(null);
    try {
      const data = await api.scenarios.simulate({
        equity_return_override: parseFloat(form.equity_return) / 100,
        debt_return_override: parseFloat(form.debt_return) / 100,
        inflation_rate: parseFloat(form.inflation_rate) / 100,
        years: parseInt(form.years),
        additional_monthly_sip: Math.round(parseFloat(form.monthly_sip || "0") * 100),
      });
      setResults(data as SimResult[]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Simulation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-xl font-semibold">Scenario Simulator</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Run Monte Carlo simulations with custom assumptions to see how your goals hold up.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[400px_1fr]">
        {/* Config panel */}
        <div className="space-y-4">
          {/* Presets */}
          <Card>
            <CardHeader><CardTitle>Quick Presets</CardTitle></CardHeader>
            <CardContent className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1">
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  onClick={() => applyPreset(p)}
                  className="rounded-lg border border-border px-3 py-2 text-left text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                >
                  {p.label}
                </button>
              ))}
            </CardContent>
          </Card>

          {/* Form */}
          <Card>
            <CardHeader><CardTitle>Custom Assumptions</CardTitle></CardHeader>
            <CardContent>
              <form onSubmit={runSimulation} className="space-y-3">
                <div className="space-y-1">
                  <Label>Equity Return (% p.a.)</Label>
                  <Input type="number" value={form.equity_return}
                    onChange={(e) => setForm({ ...form, equity_return: e.target.value })} step="0.5" />
                </div>
                <div className="space-y-1">
                  <Label>Debt Return (% p.a.)</Label>
                  <Input type="number" value={form.debt_return}
                    onChange={(e) => setForm({ ...form, debt_return: e.target.value })} step="0.5" />
                </div>
                <div className="space-y-1">
                  <Label>Inflation (% p.a.)</Label>
                  <Input type="number" value={form.inflation_rate}
                    onChange={(e) => setForm({ ...form, inflation_rate: e.target.value })} step="0.5" />
                </div>
                <div className="space-y-1">
                  <Label>Horizon (years)</Label>
                  <Input type="number" value={form.years}
                    onChange={(e) => setForm({ ...form, years: e.target.value })} min="1" max="40" />
                </div>
                <div className="space-y-1">
                  <Label>Additional Monthly SIP (₹)</Label>
                  <Input type="number" value={form.monthly_sip}
                    onChange={(e) => setForm({ ...form, monthly_sip: e.target.value })} />
                </div>

                {error && <p className="text-xs text-destructive">{error}</p>}

                <Button type="submit" className="w-full" disabled={loading}>
                  {loading
                    ? <><Loader2 className="h-4 w-4 animate-spin" /> Running 1,000 simulations…</>
                    : <><FlaskConical className="h-4 w-4" /> Run Simulation</>}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Results */}
        <div>
          {!results && !loading && (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                <FlaskConical className="h-8 w-8 text-muted-foreground" />
              </div>
              <div>
                <p className="font-medium">Configure & run a simulation</p>
                <p className="text-sm text-muted-foreground">
                  Adjust return assumptions and see the probability distribution for each of your goals.
                </p>
              </div>
            </div>
          )}

          {loading && (
            <div className="flex h-full items-center justify-center">
              <div className="text-center">
                <Loader2 className="mx-auto h-10 w-10 animate-spin text-primary" />
                <p className="mt-3 text-sm text-muted-foreground">Running 1,000 Monte Carlo paths…</p>
              </div>
            </div>
          )}

          {results && !loading && (
            <div className="space-y-4">
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
                Simulation Results
              </h2>
              {results.length === 0 ? (
                <Card>
                  <CardContent className="py-8 text-center text-sm text-muted-foreground">
                    No goals to simulate. <a href="/goals?create=true" className="text-primary hover:underline">Create a goal</a> first.
                  </CardContent>
                </Card>
              ) : (
                results.map((r, i) => {
                  const prob = r.success_probability * 100;
                  const color = prob >= 70 ? "text-green-400" : prob >= 40 ? "text-yellow-400" : "text-red-400";
                  return (
                    <Card key={i}>
                      <CardHeader>
                        <CardTitle className="text-base text-foreground">
                          {r.goal_name ?? `Goal ${i + 1}`}
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-muted-foreground">Success probability:</span>
                          <span className={`text-lg font-bold ${color}`}>{prob.toFixed(0)}%</span>
                        </div>

                        {/* Percentile bars */}
                        <div className="space-y-2">
                          {[
                            { label: "Pessimistic (P10)", value: r.p10, icon: TrendingDown, cls: "text-red-400" },
                            { label: "Median (P50)", value: r.p50, icon: null, cls: "text-foreground" },
                            { label: "Optimistic (P90)", value: r.p90, icon: TrendingUp, cls: "text-green-400" },
                          ].map(({ label, value, icon: Icon, cls }) => (
                            <div key={label} className="flex items-center justify-between text-sm">
                              <div className="flex items-center gap-1.5 text-muted-foreground">
                                {Icon && <Icon className={`h-3.5 w-3.5 ${cls}`} />}
                                {!Icon && <span className="h-3.5 w-3.5" />}
                                {label}
                              </div>
                              <span className={`font-semibold tabular-nums ${cls}`}>{fmt(value / 100)}</span>
                            </div>
                          ))}
                        </div>

                        {/* Range bar */}
                        <div className="relative h-3 rounded-full bg-muted">
                          <div
                            className="absolute inset-y-0 rounded-full bg-gradient-to-r from-red-500 via-yellow-400 to-green-500 opacity-60"
                            style={{ width: `${Math.min(prob, 100)}%` }}
                          />
                        </div>
                      </CardContent>
                    </Card>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
