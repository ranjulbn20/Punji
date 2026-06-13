"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  TrendingUp, TrendingDown, Wallet, BarChart3, ArrowRight, MessageSquare,
} from "lucide-react";
import {
  AreaChart, Area, PieChart, Pie, Cell, Tooltip, ResponsiveContainer, XAxis, YAxis,
} from "recharts";
import { api, type PortfolioSummary, type Alert } from "@/lib/api";
import { usePunji } from "@/store";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

function fmt(n: number) {
  if (n >= 1_00_00_000) return `₹${(n / 1_00_00_000).toFixed(2)} Cr`;
  if (n >= 1_00_000) return `₹${(n / 1_00_000).toFixed(2)} L`;
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function pct(n: number) {
  const sign = n >= 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

const DONUT_COLORS: Record<string, string> = {
  equity: "#6366f1",
  debt: "#22d3ee",
  gold: "#f59e0b",
  real_estate: "#10b981",
  cash: "#94a3b8",
  other: "#a78bfa",
};

const SEVERITY_BADGE: Record<string, "destructive" | "warning" | "default"> = {
  critical: "destructive",
  warning: "warning",
  info: "default",
};

function MetricCard({
  title, value, sub, positive,
}: { title: string; value: string; sub?: string; positive?: boolean }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent>
        <p className="text-2xl font-bold">{value}</p>
        {sub !== undefined && (
          <p className={cn("mt-1 text-sm font-medium", positive ? "text-green-400" : positive === false ? "text-red-400" : "text-muted-foreground")}>
            {sub}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const { portfolioSummary, setPortfolioSummary } = usePunji();
  const [perf, setPerf] = useState<{ date: string; portfolio_value: number }[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [quickAsk, setQuickAsk] = useState("");

  const load = useCallback(async () => {
    try {
      const [sum, perfData, alertData] = await Promise.all([
        api.portfolio.summary(),
        api.portfolio.performance("1y"),
        api.alerts.list({ limit: "5", is_read: "false" }),
      ]);
      setPortfolioSummary(sum as PortfolioSummary);
      setPerf((perfData as { chart_data: { date: string; portfolio_value: number }[] }).chart_data ?? []);
      setAlerts(alertData as Alert[]);
    } catch {}
    finally { setLoading(false); }
  }, [setPortfolioSummary]);

  useEffect(() => { load(); }, [load]);

  const alloc = portfolioSummary?.allocation as Record<string, number> | undefined;
  const donutData = alloc
    ? Object.entries(alloc).map(([k, v]) => ({ name: k, value: v }))
    : [];

  const isGain = (portfolioSummary?.total_pnl_pct ?? 0) >= 0;

  function handleQuickAsk(e: React.FormEvent) {
    e.preventDefault();
    if (quickAsk.trim()) router.push(`/chat?q=${encodeURIComponent(quickAsk.trim())}`);
  }

  return (
    <div className="p-6">
      <h1 className="mb-6 text-xl font-semibold">Portfolio Overview</h1>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="Total Value"
            value={fmt(portfolioSummary?.total_value ?? 0)}
          />
          <MetricCard
            title="Total Invested"
            value={fmt(portfolioSummary?.total_invested ?? 0)}
          />
          <MetricCard
            title="Unrealised P&L"
            value={fmt(portfolioSummary?.total_pnl_amount ?? 0)}
            sub={pct(portfolioSummary?.total_pnl_pct ?? 0)}
            positive={isGain}
          />
          <MetricCard
            title="Portfolio XIRR"
            value={portfolioSummary?.portfolio_xirr != null ? pct(portfolioSummary.portfolio_xirr) : "—"}
            positive={portfolioSummary?.portfolio_xirr != null ? portfolioSummary.portfolio_xirr >= 0 : undefined}
          />
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]">
        {/* Left column */}
        <div className="space-y-6">
          {/* Performance chart */}
          <Card>
            <CardHeader>
              <CardTitle>Portfolio Performance (1Y)</CardTitle>
            </CardHeader>
            <CardContent>
              {perf.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={perf}>
                    <defs>
                      <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                    <YAxis
                      tick={{ fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                    />
                    <Tooltip
                      formatter={(v) => [fmt(Number(v)), "Value"]}
                      contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
                    />
                    <Area type="monotone" dataKey="portfolio_value" stroke="#6366f1" strokeWidth={2} fill="url(#grad)" />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-52 items-center justify-center text-sm text-muted-foreground">
                  No performance data yet
                </div>
              )}
            </CardContent>
          </Card>

          {/* Quick Ask */}
          <Card>
            <CardHeader><CardTitle>Ask Punji</CardTitle></CardHeader>
            <CardContent>
              <form onSubmit={handleQuickAsk} className="flex gap-2">
                <input
                  value={quickAsk}
                  onChange={(e) => setQuickAsk(e.target.value)}
                  placeholder="e.g. How is my portfolio doing? Should I rebalance?"
                  className="flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <button
                  type="submit"
                  className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                >
                  <MessageSquare className="h-4 w-4" />
                  Ask
                </button>
              </form>
            </CardContent>
          </Card>

          {/* Recent Alerts */}
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Recent Alerts</CardTitle>
              <Link href="/alerts" className="flex items-center gap-1 text-xs text-primary hover:underline">
                View all <ArrowRight className="h-3 w-3" />
              </Link>
            </CardHeader>
            <CardContent>
              {alerts.length === 0 ? (
                <p className="text-sm text-muted-foreground">No unread alerts</p>
              ) : (
                <div className="space-y-3">
                  {alerts.map((a) => (
                    <div key={a.id} className="flex items-start gap-3">
                      <Badge variant={SEVERITY_BADGE[a.severity] ?? "default"} className="mt-0.5 shrink-0">
                        {a.severity}
                      </Badge>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{a.title}</p>
                        <p className="truncate text-xs text-muted-foreground">{a.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right column */}
        <div className="space-y-6">
          {/* Allocation donut */}
          <Card>
            <CardHeader><CardTitle>Asset Allocation</CardTitle></CardHeader>
            <CardContent>
              {donutData.length > 0 ? (
                <>
                  <ResponsiveContainer width="100%" height={180}>
                    <PieChart>
                      <Pie
                        data={donutData}
                        cx="50%"
                        cy="50%"
                        innerRadius={55}
                        outerRadius={80}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {donutData.map((entry) => (
                          <Cell key={entry.name} fill={DONUT_COLORS[entry.name] ?? "#94a3b8"} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(v) => [`${Number(v).toFixed(1)}%`, ""]}
                        contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="mt-2 space-y-1.5">
                    {donutData.map((d) => (
                      <div key={d.name} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <span
                            className="inline-block h-2 w-2 rounded-full"
                            style={{ background: DONUT_COLORS[d.name] ?? "#94a3b8" }}
                          />
                          <span className="capitalize text-muted-foreground">{d.name}</span>
                        </div>
                        <span className="font-medium">{Number(d.value).toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="flex h-44 items-center justify-center text-sm text-muted-foreground">
                  No allocation data
                </div>
              )}
            </CardContent>
          </Card>

          {/* Quick links */}
          <Card>
            <CardHeader><CardTitle>Quick Actions</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {[
                { href: "/holdings?import=true", label: "Import Holdings", icon: BarChart3 },
                { href: "/goals?create=true", label: "Set a Goal", icon: TrendingUp },
                { href: "/scenarios", label: "Run Scenario", icon: TrendingDown },
                { href: "/chat", label: "Chat with Punji", icon: MessageSquare },
              ].map(({ href, label, icon: Icon }) => (
                <Link
                  key={href}
                  href={href}
                  className="flex items-center justify-between rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4" />
                    {label}
                  </div>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
