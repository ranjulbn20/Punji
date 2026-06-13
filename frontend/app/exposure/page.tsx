"use client";
import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, Cell,
} from "recharts";
import { ChevronDown, ChevronRight, RefreshCw, AlertTriangle, Info } from "lucide-react";
import { api, PortfolioExposure, StockExposure, SectorExposure } from "@/lib/api";

const DIRECT_COLOR = "#22d3ee";   // cyan-400
const INDIRECT_COLOR = "#6366f1"; // indigo-500
const ALERT_THRESHOLD = 10;       // % above which we flag concentration

function fmt(n: number) {
  return n.toFixed(2) + "%";
}

// ── Sector bar chart ──────────────────────────────────────────────────────────

function SectorChart({ sectors }: { sectors: SectorExposure[] }) {
  if (sectors.length === 0) return null;

  const data = sectors.map((s) => ({
    sector: s.sector.length > 16 ? s.sector.slice(0, 14) + ".." : s.sector,
    fullSector: s.sector,
    direct: Number(s.direct_pct.toFixed(2)),
    indirect: Number(s.indirect_pct.toFixed(2)),
  }));

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h2 className="mb-1 text-sm font-semibold text-foreground">Sector Exposure</h2>
      <p className="mb-4 text-xs text-muted-foreground">
        Combined allocation across direct stocks and MF underlying holdings
      </p>
      <div style={{ height: Math.max(200, data.length * 32) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: 48, left: 8, bottom: 0 }}
          >
            <XAxis
              type="number"
              tickFormatter={(v) => v + "%"}
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              dataKey="sector"
              type="category"
              width={120}
              tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,0.04)" }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload;
                return (
                  <div className="rounded-lg border border-border bg-popover p-2 text-xs shadow-lg">
                    <p className="mb-1 font-medium text-foreground">{d.fullSector}</p>
                    <p style={{ color: DIRECT_COLOR }}>Direct: {fmt(d.direct)}</p>
                    <p style={{ color: INDIRECT_COLOR }}>Via MFs: {fmt(d.indirect)}</p>
                    <p className="mt-1 font-semibold text-foreground">
                      Total: {fmt(d.direct + d.indirect)}
                    </p>
                  </div>
                );
              }}
            />
            <Bar dataKey="direct" stackId="a" fill={DIRECT_COLOR} radius={[0, 0, 0, 0]} name="Direct" />
            <Bar dataKey="indirect" stackId="a" fill={INDIRECT_COLOR} radius={[0, 3, 3, 0]} name="Via MFs" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex gap-5 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-3 rounded-sm" style={{ background: DIRECT_COLOR }} />
          Direct
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-3 rounded-sm" style={{ background: INDIRECT_COLOR }} />
          Via MFs
        </span>
      </div>
    </div>
  );
}

// ── Stock exposure row ────────────────────────────────────────────────────────

function StockRow({ stock }: { stock: StockExposure }) {
  const [open, setOpen] = useState(false);
  const isAlert = stock.total_pct >= ALERT_THRESHOLD;

  return (
    <div className="border-b border-border last:border-0">
      <button
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/40 transition-colors"
        onClick={() => setOpen((o) => !o)}
      >
        {/* Expand chevron */}
        <span className="shrink-0 text-muted-foreground">
          {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        </span>

        {/* Name + sector */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium text-foreground">{stock.name}</span>
            {isAlert && (
              <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-400" />
            )}
          </div>
          <span className="text-xs text-muted-foreground">{stock.sector}</span>
        </div>

        {/* Mini stacked bar */}
        <div className="hidden w-24 md:block">
          <div className="relative h-2 rounded-full bg-muted overflow-hidden">
            <div
              className="absolute inset-y-0 left-0 rounded-full"
              style={{
                width: `${Math.min(stock.direct_pct / (stock.total_pct || 1) * 100, 100)}%`,
                background: DIRECT_COLOR,
              }}
            />
            <div
              className="absolute inset-y-0 rounded-full"
              style={{
                left: `${Math.min(stock.direct_pct / (stock.total_pct || 1) * 100, 100)}%`,
                right: 0,
                background: INDIRECT_COLOR,
              }}
            />
          </div>
        </div>

        {/* Percentages */}
        <div className="shrink-0 text-right">
          <div className={`text-sm font-semibold ${isAlert ? "text-amber-400" : "text-foreground"}`}>
            {fmt(stock.total_pct)}
          </div>
          <div className="text-xs text-muted-foreground">
            {stock.direct_pct > 0 && (
              <span style={{ color: DIRECT_COLOR }}>{fmt(stock.direct_pct)}</span>
            )}
            {stock.direct_pct > 0 && stock.indirect_pct > 0 && " + "}
            {stock.indirect_pct > 0 && (
              <span style={{ color: INDIRECT_COLOR }}>{fmt(stock.indirect_pct)}</span>
            )}
          </div>
        </div>
      </button>

      {/* Expanded breakdown */}
      {open && (
        <div className="bg-muted/20 px-10 py-3 space-y-1">
          {stock.sources.map((src, i) => (
            <div key={i} className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">{src.label}</span>
              <span
                className="font-medium tabular-nums"
                style={{ color: src.instrument_type === "stock" ? DIRECT_COLOR : INDIRECT_COLOR }}
              >
                {fmt(src.pct)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ExposurePage() {
  const [data, setData] = useState<PortfolioExposure | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setLoading(true);
      setError(null);
      const result = await api.portfolio.exposure();
      setData(result);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function triggerRefresh() {
    try {
      setRefreshing(true);
      await api.portfolio.refreshCompositions();
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => { load(); }, []);

  const mfCount = data
    ? (data.by_stock.filter((s) => s.indirect_pct > 0).length > 0
        ? data.mf_without_composition.length
        : data.mf_without_composition.length)
    : 0;

  const mfsWithData = data
    ? (new Set(
        data.by_stock
          .flatMap((s) => s.sources.filter((src) => src.instrument_type === "mutual_fund").map((src) => src.label))
      ).size)
    : 0;

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-foreground">Portfolio Look-Through</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Consolidated exposure across direct stocks and mutual fund underlying holdings
          </p>
        </div>
        <div className="flex items-center gap-3">
          {data?.last_composition_date && (
            <span className="text-xs text-muted-foreground">
              MF data: {new Date(data.last_composition_date).toLocaleDateString("en-IN", { month: "short", year: "numeric" })}
            </span>
          )}
          <button
            onClick={triggerRefresh}
            disabled={refreshing || loading}
            className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
            Refresh MF data
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-24 text-muted-foreground">
          <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
          Computing exposure…
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {data && !loading && (
        <>
          {/* Summary chips */}
          <div className="flex flex-wrap gap-3">
            <div className="rounded-lg border border-border bg-card px-4 py-2 text-center">
              <div className="text-lg font-bold text-foreground">{data.by_stock.length}</div>
              <div className="text-xs text-muted-foreground">companies tracked</div>
            </div>
            <div className="rounded-lg border border-border bg-card px-4 py-2 text-center">
              <div className="text-lg font-bold text-foreground">{data.by_sector.length}</div>
              <div className="text-xs text-muted-foreground">sectors</div>
            </div>
            <div className="rounded-lg border border-border bg-card px-4 py-2 text-center">
              <div className="text-lg font-bold" style={{ color: INDIRECT_COLOR }}>
                {mfsWithData}
              </div>
              <div className="text-xs text-muted-foreground">MFs with look-through</div>
            </div>
            {data.mf_without_composition.length > 0 && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-center">
                <div className="text-lg font-bold text-amber-400">{data.mf_without_composition.length}</div>
                <div className="text-xs text-amber-600 dark:text-amber-400/70">MFs pending data</div>
              </div>
            )}
          </div>

          {/* No data at all */}
          {data.by_stock.length === 0 && data.by_sector.length === 0 && (
            <div className="rounded-xl border border-border bg-card p-8 text-center">
              <Info className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
              <p className="font-medium text-foreground">No exposure data yet</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Add stock holdings or import mutual funds to see your consolidated exposure.
              </p>
            </div>
          )}

          <div className="grid gap-6 lg:grid-cols-2">
            {/* Sector chart */}
            {data.by_sector.length > 0 && <SectorChart sectors={data.by_sector} />}

            {/* Stock exposure list */}
            {data.by_stock.length > 0 && (
              <div className="rounded-xl border border-border bg-card">
                <div className="border-b border-border px-4 py-3">
                  <h2 className="text-sm font-semibold text-foreground">Company Exposure</h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Click any row to see the breakdown by source
                  </p>
                </div>
                {/* Column headers */}
                <div className="flex items-center gap-3 px-4 py-2 text-xs text-muted-foreground border-b border-border">
                  <span className="w-3.5" />
                  <span className="flex-1">Company</span>
                  <span className="hidden w-24 text-center md:block">Split</span>
                  <div className="w-20 text-right">
                    <span>Total</span>
                    <br />
                    <span style={{ color: DIRECT_COLOR }}>D</span>
                    {" + "}
                    <span style={{ color: INDIRECT_COLOR }}>MF</span>
                  </div>
                </div>
                <div className="divide-y-0">
                  {data.by_stock.map((s) => (
                    <StockRow key={s.isin} stock={s} />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* MF without composition data */}
          {data.mf_without_composition.length > 0 && (
            <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
                <div>
                  <p className="text-sm font-medium text-foreground">
                    {data.mf_without_composition.length} mutual fund
                    {data.mf_without_composition.length > 1 ? "s" : ""} pending portfolio data
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    These funds represent{" "}
                    <span className="font-medium text-foreground">
                      {fmt(data.mf_without_composition.reduce((s, f) => s + f.pct_of_portfolio, 0))}
                    </span>{" "}
                    of your portfolio. Their underlying stocks are not yet included in the look-through above.
                    Click <strong>Refresh MF data</strong> to attempt fetching the latest AMFI portfolio disclosures.
                  </p>
                  <ul className="mt-2 space-y-1">
                    {data.mf_without_composition.map((f, i) => (
                      <li key={i} className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground truncate">{f.name}</span>
                        <span className="ml-4 shrink-0 font-medium text-amber-400">
                          {fmt(f.pct_of_portfolio)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
