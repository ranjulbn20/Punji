"use client";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Plus, RefreshCw, Target, Calendar, TrendingUp } from "lucide-react";
import { api, type Goal } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

function fmt(n: number) {
  if (n >= 1_00_00_000) return `₹${(n / 1_00_00_000).toFixed(2)} Cr`;
  if (n >= 1_00_000) return `₹${(n / 1_00_000).toFixed(2)} L`;
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function ProgressRing({ pct }: { pct: number }) {
  const r = 36;
  const circ = 2 * Math.PI * r;
  const offset = circ - (Math.min(pct, 100) / 100) * circ;
  const color = pct >= 70 ? "#22c55e" : pct >= 40 ? "#f59e0b" : "#ef4444";
  return (
    <svg width={88} height={88} className="rotate-[-90deg]">
      <circle cx={44} cy={44} r={r} stroke="var(--border)" strokeWidth={8} fill="none" />
      <circle
        cx={44} cy={44} r={r}
        stroke={color} strokeWidth={8} fill="none"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        strokeLinecap="round"
        style={{ transition: "stroke-dashoffset 0.5s ease" }}
      />
      <text x={44} y={44} textAnchor="middle" dominantBaseline="middle" fontSize={14} fontWeight={600}
        fill="currentColor" style={{ transform: "rotate(90deg)", transformOrigin: "44px 44px" }}>
        {pct.toFixed(0)}%
      </text>
    </svg>
  );
}

function yearsLeft(dateStr: string) {
  const diff = new Date(dateStr).getTime() - Date.now();
  const yrs = diff / (1000 * 60 * 60 * 24 * 365.25);
  if (yrs < 1) return `${Math.ceil(yrs * 12)} mo`;
  return `${yrs.toFixed(1)} yr`;
}

export default function GoalsPage() {
  const searchParams = useSearchParams();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(searchParams.get("create") === "true");
  const [form, setForm] = useState({ name: "", target_amount: "", target_date: "", monthly_sip_allocated: "" });
  const [saving, setSaving] = useState(false);

  async function loadGoals() {
    try {
      const data = await api.goals.list();
      setGoals(data);
    } catch {}
    finally { setLoading(false); }
  }

  useEffect(() => { loadGoals(); }, []);

  async function simulate(id: string) {
    setSimulating(id);
    try {
      await api.goals.simulate(id);
      await loadGoals();
    } catch {}
    finally { setSimulating(null); }
  }

  async function createGoal(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await api.goals.create({
        name: form.name,
        target_amount: Math.round(parseFloat(form.target_amount) * 100), // paise
        target_date: form.target_date,
        monthly_sip_allocated: Math.round(parseFloat(form.monthly_sip_allocated || "0") * 100),
      });
      setShowCreate(false);
      setForm({ name: "", target_amount: "", target_date: "", monthly_sip_allocated: "" });
      await loadGoals();
    } catch {}
    finally { setSaving(false); }
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Goals</h1>
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" />
          New Goal
        </Button>
      </div>

      {/* Create form */}
      {showCreate && (
        <Card className="mb-6 border-primary/40">
          <CardHeader><CardTitle>New Financial Goal</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={createGoal} className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1">
                  <Label>Goal Name</Label>
                  <Input placeholder="e.g. Retirement, House, Child Education"
                    value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
                </div>
                <div className="space-y-1">
                  <Label>Target Amount (₹)</Label>
                  <Input type="number" placeholder="e.g. 5000000"
                    value={form.target_amount} onChange={(e) => setForm({ ...form, target_amount: e.target.value })} required />
                </div>
                <div className="space-y-1">
                  <Label>Target Date</Label>
                  <Input type="date" value={form.target_date}
                    onChange={(e) => setForm({ ...form, target_date: e.target.value })} required />
                </div>
                <div className="space-y-1">
                  <Label>Monthly SIP (₹) — optional</Label>
                  <Input type="number" placeholder="e.g. 25000"
                    value={form.monthly_sip_allocated} onChange={(e) => setForm({ ...form, monthly_sip_allocated: e.target.value })} />
                </div>
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={saving}>{saving ? "Saving…" : "Create Goal"}</Button>
                <Button type="button" variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-52 rounded-xl" />)}
        </div>
      ) : goals.length === 0 ? (
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <Target className="h-12 w-12 text-muted-foreground" />
          <div>
            <p className="font-medium">No goals yet</p>
            <p className="text-sm text-muted-foreground">Set a financial goal to track your progress with Monte Carlo simulations</p>
          </div>
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="h-4 w-4" />
            Set a Goal
          </Button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {goals.map((g) => {
            const prob = g.success_probability ?? 0;
            const timeLeft = yearsLeft(g.target_date);
            return (
              <Card key={g.id} className="flex flex-col">
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <CardTitle className="truncate text-base text-foreground">{g.name}</CardTitle>
                      <div className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                        <Calendar className="h-3 w-3" />
                        {new Date(g.target_date).toLocaleDateString("en-IN", { year: "numeric", month: "short" })}
                        <span className="ml-1">({timeLeft} left)</span>
                      </div>
                    </div>
                    <Badge
                      variant={prob >= 70 ? "success" : prob >= 40 ? "warning" : "destructive"}
                      className="shrink-0"
                    >
                      {prob >= 70 ? "On Track" : prob >= 40 ? "At Risk" : "Off Track"}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col gap-4">
                  <div className="flex items-center gap-4">
                    <ProgressRing pct={prob} />
                    <div className="space-y-1 text-sm">
                      <div>
                        <p className="text-xs text-muted-foreground">Target</p>
                        <p className="font-semibold">{fmt(g.target_amount / 100)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground">Monthly SIP</p>
                        <p className="font-medium">{fmt(g.monthly_sip_allocated / 100)}</p>
                      </div>
                    </div>
                  </div>

                  <p className="text-xs text-muted-foreground">
                    {prob > 0
                      ? `Based on 1,000 Monte Carlo simulations`
                      : "Run simulation to see success probability"}
                  </p>

                  <button
                    onClick={() => simulate(g.id)}
                    disabled={simulating === g.id}
                    className={cn(
                      "mt-auto flex items-center justify-center gap-2 rounded-lg border border-border py-2 text-xs font-medium transition-colors hover:border-primary hover:text-primary",
                      simulating === g.id && "cursor-wait opacity-60"
                    )}
                  >
                    <TrendingUp className={cn("h-3.5 w-3.5", simulating === g.id && "animate-pulse")} />
                    {simulating === g.id ? "Running simulation…" : "Re-simulate"}
                  </button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
