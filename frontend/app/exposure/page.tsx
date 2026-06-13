"use client";
import { useEffect, useState, useMemo } from "react";
import { ChevronDown, ChevronRight, RefreshCw, AlertTriangle, Info } from "lucide-react";
import { api, PortfolioExposure, StockExposure, SectorExposure } from "@/lib/api";

const DIRECT_COLOR = "#22d3ee";
const INDIRECT_COLOR = "#6366f1";
const ALERT_THRESHOLD = 10;

function fmt(n: number) {
  return n.toFixed(2) + "%";
}

// ── Sector exposure — custom inline bars ──────────────────────────────────────

function SectorExposurePanel({ sectors }: { sectors: SectorExposure[] }) {
  const maxPct = useMemo(
    () => Math.max(...sectors.map((s) => s.total_pct), 1),
    [sectors]
  );

  return (
    <div className="rounded-xl border border-border bg-card flex flex-col">
      <div className="border-b border-border px-5 py-4">
        <h2 className="text-sm font-semibold text-foreground">Sector Exposure</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Combined allocation across direct stocks and MF underlying holdings
        </p>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-5 px-5 pt-3 pb-1 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-3 rounded-sm" style={{ background: DIRECT_COLOR }} />
          Direct
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-3 rounded-sm" style={{ background: INDIRECT_COLOR }} />
          Via MFs
        </span>
        <span className="ml-auto text-right">Total</span>
      </div>

      <div className="divide-y divide-border/50 px-5 pb-4">
        {sectors.map((s) => {
          const isAlert = s.total_pct >= ALERT_THRESHOLD;
          const directW = (s.direct_pct / maxPct) * 100;
          const indirectW = (s.indirect_pct / maxPct) * 100;
          return (
            <div key={s.sector} className="flex items-center gap-3 py-2.5">
              {/* Sector name */}
              <div className="w-36 shrink-0 flex items-center gap-1.5 min-w-0">
                <span
                  className="truncate text-xs font-medium text-foreground"
                  title={s.sector}
                >
                  {s.sector}
                </span>
                {isAlert && (
                  <AlertTriangle className="h-3 w-3 shrink-0 text-amber-400" />
                )}
              </div>

              {/* Stacked bar */}
              <div className="flex-1 flex h-5 rounded overflow-hidden bg-muted/30 min-w-0">
                {s.direct_pct > 0 && (
                  <div
                    className="flex items-center justify-end pr-1 transition-all duration-500"
                    style={{ width: `${directW}%`, background: DIRECT_COLOR }}
                  >
                    {directW > 12 && (
                      <span className="text-[10px] font-semibold text-black/60 tabular-nums leading-none">
                        {fmt(s.direct_pct)}
                      </span>
                    )}
                  </div>
                )}
                {s.indirect_pct > 0 && (
                  <div
                    className="flex items-center justify-end pr-1 transition-all duration-500"
                    style={{ width: `${indirectW}%`, background: INDIRECT_COLOR }}
                  >
                    {indirectW > 12 && (
                      <span className="text-[10px] font-semibold text-white/70 tabular-nums leading-none">
                        {fmt(s.indirect_pct)}
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Total % */}
              <div className="w-14 shrink-0 text-right">
                <span
                  className={`text-xs font-bold tabular-nums ${
                    isAlert ? "text-amber-400" : "text-foreground"
                  }`}
                >
                  {fmt(s.total_pct)}
                </span>
                {(s.direct_pct > 0 || s.indirect_pct > 0) && (
                  <div className="text-[10px] text-muted-foreground tabular-nums">
                    {s.direct_pct > 0 && (
                      <span style={{ color: DIRECT_COLOR }}>{s.direct_pct.toFixed(1)}</span>
                    )}
                    {s.direct_pct > 0 && s.indirect_pct > 0 && (
                      <span className="text-muted-foreground/50"> + </span>
                    )}
                    {s.indirect_pct > 0 && (
                      <span style={{ color: INDIRECT_COLOR }}>{s.indirect_pct.toFixed(1)}</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Company exposure row ──────────────────────────────────────────────────────

function StockRow({ stock, maxPct }: { stock: StockExposure; maxPct: number }) {
  const [open, setOpen] = useState(false);
  const isAlert = stock.total_pct >= ALERT_THRESHOLD;
  const directW = stock.total_pct > 0 ? (stock.direct_pct / stock.total_pct) * 100 : 0;
  const barW = (stock.total_pct / maxPct) * 100;

  return (
    <div className="border-b border-border/50 last:border-0">
      <button
        className="flex w-full items-center gap-3 px-5 py-2.5 text-left hover:bg-muted/30 transition-colors"
        onClick={() => setOpen((o) => !o)}
      >
        {/* Chevron */}
        <span className="shrink-0 text-muted-foreground/60">
          {open ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
        </span>

        {/* Name + sector */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="truncate text-xs font-semibold text-foreground">{stock.name}</span>
            {isAlert && <AlertTriangle className="h-3 w-3 shrink-0 text-amber-400" />}
          </div>
          <span className="text-[11px] text-muted-foreground">{stock.sector}</span>
        </div>

        {/* Scaled bar */}
        <div className="hidden w-32 md:flex items-center">
          <div className="w-full h-1.5 rounded-full bg-muted/40 overflow-hidden">
            <div
              className="h-full rounded-full overflow-hidden flex"
              style={{ width: `${barW}%` }}
            >
              <div style={{ width: `${directW}%`, background: DIRECT_COLOR }} />
              <div style={{ width: `${100 - directW}%`, background: INDIRECT_COLOR }} />
            </div>
          </div>
        </div>

        {/* Percentages */}
        <div className="shrink-0 text-right w-16">
          <div
            className={`text-xs font-bold tabular-nums ${
              isAlert ? "text-amber-400" : "text-foreground"
            }`}
          >
            {fmt(stock.total_pct)}
          </div>
          <div className="text-[10px] tabular-nums text-muted-foreground">
            {stock.direct_pct > 0 && (
              <span style={{ color: DIRECT_COLOR }}>{stock.direct_pct.toFixed(1)}</span>
            )}
            {stock.direct_pct > 0 && stock.indirect_pct > 0 && (
              <span className="text-muted-foreground/50"> + </span>
            )}
            {stock.indirect_pct > 0 && (
              <span style={{ color: INDIRECT_COLOR }}>{stock.indirect_pct.toFixed(1)}</span>
            )}
          </div>
        </div>
      </button>

      {/* Expanded source breakdown */}
      {open && (
        <div className="bg-muted/10 border-t border-border/30 px-12 py-2.5 space-y-1.5">
          {stock.sources.map((src, i) => (
            <div key={i} className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground truncate">{src.label}</span>
              <span
                className="ml-4 shrink-0 font-medium tabular-nums"
                style={{
                  color:
                    src.instrument_type === "stock" ? DIRECT_COLOR : INDIRECT_COLOR,
                }}
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

function CompanyExposurePanel({ stocks }: { stocks: StockExposure[] }) {
  const maxPct = useMemo(() => Math.max(...stocks.map((s) => s.total_pct), 1), [stocks]);
  const alertCount = stocks.filter((s) => s.total_pct >= ALERT_THRESHOLD).length;

  return (
    <div className="rounded-xl border border-border bg-card flex flex-col">
      <div className="border-b border-border px-5 py-4 flex items-start justify-between">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Company Exposure</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Click any row to see the breakdown by source
          </p>
        </div>
        {alertCount > 0 && (
          <span className="flex items-center gap-1.5 rounded-full bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 text-xs font-medium text-amber-400">
            <AlertTriangle className="h-3 w-3" />
            {alertCount} concentrated
          </span>
        )}
      </div>

      {/* Column headers */}
      <div className="flex items-center gap-3 border-b border-border/50 px-5 py-2 text-[11px] font-medium text-muted-foreground/70">
        <span className="w-3.5 shrink-0" />
        <span className="flex-1">Company / Sector</span>
        <span className="hidden w-32 text-left md:block">Scale</span>
        <span className="w-16 text-right">Total / Split</span>
      </div>

      <div className="overflow-y-auto max-h-[420px]">
        {stocks.map((s) => (
          <StockRow key={s.isin} stock={s} maxPct={maxPct} />
        ))}
      </div>
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

  useEffect(() => {
    load();
  }, []);

  const mfsWithData = data
    ? new Set(
        data.by_stock
          .flatMap((s) =>
            s.sources
              .filter((src) => src.instrument_type === "mutual_fund")
              .map((src) => src.label)
          )
      ).size
    : 0;

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto space-y-5">
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
              MF data:{" "}
              {new Date(data.last_composition_date).toLocaleDateString("en-IN", {
                month: "short",
                year: "numeric",
              })}
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
            <div className="rounded-lg border border-border bg-card px-4 py-2.5 text-center min-w-[80px]">
              <div className="text-lg font-bold text-foreground">{data.by_stock.length}</div>
              <div className="text-xs text-muted-foreground">companies</div>
            </div>
            <div className="rounded-lg border border-border bg-card px-4 py-2.5 text-center min-w-[80px]">
              <div className="text-lg font-bold text-foreground">{data.by_sector.length}</div>
              <div className="text-xs text-muted-foreground">sectors</div>
            </div>
            <div className="rounded-lg border border-border bg-card px-4 py-2.5 text-center min-w-[80px]">
              <div className="text-lg font-bold" style={{ color: INDIRECT_COLOR }}>
                {mfsWithData}
              </div>
              <div className="text-xs text-muted-foreground">MFs with look-through</div>
            </div>
            {data.mf_without_composition.length > 0 && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-2.5 text-center min-w-[80px]">
                <div className="text-lg font-bold text-amber-400">
                  {data.mf_without_composition.length}
                </div>
                <div className="text-xs text-amber-600 dark:text-amber-400/70">pending data</div>
              </div>
            )}
          </div>

          {/* No data */}
          {data.by_stock.length === 0 && data.by_sector.length === 0 && (
            <div className="rounded-xl border border-border bg-card p-8 text-center">
              <Info className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
              <p className="font-medium text-foreground">No exposure data yet</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Add stock holdings or import mutual funds to see your consolidated exposure.
              </p>
            </div>
          )}

          {/* Main panels — side by side on desktop */}
          {(data.by_sector.length > 0 || data.by_stock.length > 0) && (
            <div className="grid gap-5 lg:grid-cols-2 items-start">
              {data.by_sector.length > 0 && (
                <SectorExposurePanel sectors={data.by_sector} />
              )}
              {data.by_stock.length > 0 && (
                <CompanyExposurePanel stocks={data.by_stock} />
              )}
            </div>
          )}

          {/* MF without composition data */}
          {data.mf_without_composition.length > 0 && (
            <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground">
                    {data.mf_without_composition.length} mutual fund
                    {data.mf_without_composition.length > 1 ? "s" : ""} pending portfolio data
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    These funds represent{" "}
                    <span className="font-medium text-foreground">
                      {fmt(
                        data.mf_without_composition.reduce(
                          (s, f) => s + f.pct_of_portfolio,
                          0
                        )
                      )}
                    </span>{" "}
                    of your portfolio. Their underlying stocks are not yet included in the
                    look-through above. Click <strong>Refresh MF data</strong> to attempt
                    fetching the latest AMFI portfolio disclosures.
                  </p>
                  <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-1">
                    {data.mf_without_composition.map((f, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground truncate">{f.name}</span>
                        <span className="ml-4 shrink-0 font-medium text-amber-400">
                          {fmt(f.pct_of_portfolio)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
