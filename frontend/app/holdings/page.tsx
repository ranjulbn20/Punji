"use client";
import React, { useEffect, useState, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { RefreshCw, Plus, Upload, Trash2, ChevronDown, ChevronUp, ArrowLeft, ArrowUp, ArrowDown, ArrowUpDown } from "lucide-react";
import { api, type Holding, type HoldingsSummary, type HoldingTypeSummary } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const TABS = ["Mutual Fund", "Stock", "Fixed Deposit", "PPF", "NPS"] as const;
type Tab = (typeof TABS)[number];

const TAB_FILTER: Record<Tab, string> = {
  "Mutual Fund": "mutual_fund",
  Stock: "stock",
  "Fixed Deposit": "fixed_deposit",
  PPF: "ppf",
  NPS: "nps",
};

type SortKey = "display_name" | "invested_amount" | "current_value" | "unrealised_pnl" | "xirr";

const COLUMNS: { key: SortKey; label: string; className?: string }[] = [
  { key: "display_name", label: "Name" },
  { key: "invested_amount", label: "Invested", className: "text-right" },
  { key: "current_value", label: "Current", className: "text-right" },
  { key: "unrealised_pnl", label: "P&L", className: "text-right hidden sm:table-cell" },
  { key: "xirr", label: "XIRR", className: "text-right hidden lg:table-cell" },
];

function fmt(n: number) {
  if (n >= 1_00_00_000) return `₹${(n / 1_00_00_000).toFixed(2)} Cr`;
  if (n >= 1_00_000) return `₹${(n / 1_00_000).toFixed(2)} L`;
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

// ── Platform configuration ────────────────────────────────────────────────────

interface PlatformConfig {
  id: string;
  name: string;
  tag: string;
  hint: string;
  acceptsPdf: boolean;
  acceptsXlsx: boolean;
}

const MF_PLATFORMS: PlatformConfig[] = [
  {
    id: "cams_cas",
    name: "CAMS / KFintech CAS",
    tag: "All AMCs",
    hint: "Password-protected PDF from mycams.com or kfintech.com — password is your PAN (e.g. ABCDE1234F)",
    acceptsPdf: true,
    acceptsXlsx: false,
  },
  {
    id: "groww_mf",
    name: "Groww",
    tag: "Groww MF",
    hint: "Holdings CSV: groww.in → Portfolio → Mutual Funds → Download",
    acceptsPdf: false,
    acceptsXlsx: false,
  },
  {
    id: "kuvera",
    name: "Kuvera",
    tag: "Kuvera MF",
    hint: "Holdings CSV: kuvera.in → Portfolio → Current Holdings → Export CSV",
    acceptsPdf: false,
    acceptsXlsx: false,
  },
];

const STOCK_PLATFORMS: PlatformConfig[] = [
  {
    id: "zerodha_holdings",
    name: "Zerodha Holdings",
    tag: "Snapshot",
    hint: "Holdings CSV or XLSX: console.zerodha.com → Portfolio → Holdings → ↓ Download",
    acceptsPdf: false,
    acceptsXlsx: true,
  },
  {
    id: "zerodha_tradebook",
    name: "Zerodha Tradebook",
    tag: "Full history",
    hint: "For accurate XIRR: console.zerodha.com → Reports → Tradebook → Download (CSV or XLSX)",
    acceptsPdf: false,
    acceptsXlsx: true,
  },
  {
    id: "groww_stocks",
    name: "Groww",
    tag: "Groww Stocks",
    hint: "Holdings CSV: groww.in → Portfolio → Stocks → Download",
    acceptsPdf: false,
    acceptsXlsx: false,
  },
];

// ── Step type ─────────────────────────────────────────────────────────────────

type ImportStep =
  | "idle"
  | "select_type"
  | "select_platform"
  | "uploading"
  | "password"
  | "preview"
  | "confirming"
  | "done";

interface PreviewData {
  job_id: string;
  holdings: Holding[];
  transactions: number;
  duplicates: unknown[];
}

// ── Page component ────────────────────────────────────────────────────────────

export default function HoldingsPage() {
  const searchParams = useSearchParams();
  const [tab, setTab] = useState<Tab>("Mutual Fund");
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<HoldingsSummary | null>(null);
  const [refreshing, setRefreshing] = useState<string | null>(null);
  const [importStep, setImportStep] = useState<ImportStep>(
    searchParams.get("import") === "true" ? "select_type" : "idle"
  );
  const [selectedType, setSelectedType] = useState<"mf" | "stocks" | null>(null);
  const [selectedPlatform, setSelectedPlatform] = useState<PlatformConfig | null>(null);
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pdfPassword, setPdfPassword] = useState("");
  const [passwordError, setPasswordError] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function loadHoldings(instrumentType?: string) {
    setLoading(true);
    try {
      const data = await api.holdings.list(instrumentType ? { instrument_type: instrumentType } : undefined);
      setHoldings(data.items);
    } catch {}
    finally { setLoading(false); }
  }

  async function loadSummary() {
    try { setSummary(await api.holdings.summary()); } catch {}
  }

  useEffect(() => {
    loadHoldings(TAB_FILTER[tab]);
  }, [tab]);

  useEffect(() => {
    loadSummary();
  }, []);

  async function refreshHolding(id: string) {
    setRefreshing(id);
    try { await api.holdings.refresh(id); await loadHoldings(TAB_FILTER[tab]); await loadSummary(); }
    catch {}
    finally { setRefreshing(null); }
  }

  async function deleteHolding(id: string) {
    if (!confirm("Remove this holding?")) return;
    try { await api.holdings.delete(id); setHoldings((h) => h.filter((x) => x.id !== id)); await loadSummary(); }
    catch {}
  }

  function resetImport() {
    setImportStep("idle");
    setSelectedType(null);
    setSelectedPlatform(null);
    setPendingFile(null);
    setPdfPassword("");
    setPasswordError(false);
    setPreview(null);
  }

  function handleFileSelect(file: File) {
    setPdfPassword("");
    setPasswordError(false);
    if (file.name.toLowerCase().endsWith(".pdf")) {
      setPendingFile(file);
      setImportStep("password");
    } else {
      setPendingFile(null);
      doUpload(file, "");
    }
  }

  async function doUpload(file: File, password: string) {
    setImportStep("uploading");
    try {
      const platformId = selectedPlatform?.id ?? "generic";
      const job = await api.imports.upload(file, platformId, password || undefined);
      if (job.status === "failed") {
        setPasswordError(true);
        setPendingFile(file);
        setImportStep("password");
        return;
      }
      const jobId = job.import_job_id ?? job.job_id;
      const prev = await api.imports.preview(jobId) as Omit<PreviewData, "job_id">;
      setPreview({ ...(prev as object), job_id: jobId } as PreviewData);
      setImportStep("preview");
    } catch { resetImport(); }
  }

  async function confirmImport() {
    if (!preview) return;
    setImportStep("confirming");
    try {
      await api.imports.confirm(preview.job_id, { confirmed: true });
      setImportStep("done");
      await loadHoldings(TAB_FILTER[tab]);
      await loadSummary();
    } catch { setImportStep("preview"); }
  }

  const filtered = holdings;

  const currentSummary: HoldingTypeSummary | undefined = summary?.by_type.find(
    (s) => s.instrument_type === TAB_FILTER[tab]
  );

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  const sorted = React.useMemo(() => {
    if (!sortKey) return filtered;
    const dir = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      // Nulls (e.g. missing XIRR) always sort last, regardless of direction.
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "string" || typeof bv === "string") {
        return String(av).localeCompare(String(bv)) * dir;
      }
      return ((av as number) - (bv as number)) * dir;
    });
  }, [filtered, sortKey, sortDir]);

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Holdings</h1>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setImportStep("select_type")}>
            <Upload className="h-4 w-4" />
            Import
          </Button>
          <Button size="sm" onClick={() => alert("Manual add coming soon")}>
            <Plus className="h-4 w-4" />
            Add
          </Button>
        </div>
      </div>

      {/* ── Import panel ── */}
      {importStep !== "idle" && importStep !== "done" && (
        <Card className="mb-6 border-primary/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {importStep !== "select_type" && (
                <button
                  onClick={() => {
                    if (importStep === "select_platform") setImportStep("select_type");
                    else if (importStep === "uploading") setImportStep("select_platform");
                    else if (importStep === "password") { setPendingFile(null); setImportStep("uploading"); }
                    else if (importStep === "preview") setImportStep("uploading");
                  }}
                  className="rounded p-0.5 text-muted-foreground hover:text-foreground"
                  aria-label="Back"
                >
                  <ArrowLeft className="h-4 w-4" />
                </button>
              )}
              Import Holdings
              {selectedType && (
                <span className="text-sm font-normal text-muted-foreground">
                  — {selectedType === "mf" ? "Mutual Funds" : "Stocks"}
                  {selectedPlatform && ` › ${selectedPlatform.name}`}
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>

            {/* Step 1: Select asset type */}
            {importStep === "select_type" && (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">What would you like to import?</p>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { key: "mf" as const, label: "Mutual Funds", desc: "CAMS CAS, Groww, Kuvera" },
                    { key: "stocks" as const, label: "Stocks", desc: "Zerodha, Groww" },
                  ].map(({ key, label, desc }) => (
                    <button
                      key={key}
                      onClick={() => { setSelectedType(key); setImportStep("select_platform"); }}
                      className="rounded-xl border border-border p-4 text-left hover:border-primary/60 hover:bg-primary/5 transition-colors"
                    >
                      <p className="font-medium">{label}</p>
                      <p className="mt-0.5 text-xs text-muted-foreground">{desc}</p>
                    </button>
                  ))}
                </div>
                <Button variant="ghost" size="sm" onClick={resetImport}>Cancel</Button>
              </div>
            )}

            {/* Step 2: Select platform */}
            {importStep === "select_platform" && selectedType && (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">Which platform is your data from?</p>
                <div className="grid gap-2">
                  {(selectedType === "mf" ? MF_PLATFORMS : STOCK_PLATFORMS).map((p) => (
                    <button
                      key={p.id}
                      onClick={() => { setSelectedPlatform(p); setImportStep("uploading"); }}
                      className="flex items-start justify-between rounded-xl border border-border px-4 py-3 text-left hover:border-primary/60 hover:bg-primary/5 transition-colors"
                    >
                      <div>
                        <p className="font-medium">{p.name}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">{p.hint}</p>
                      </div>
                      <Badge variant="outline" className="ml-3 mt-0.5 shrink-0 text-xs">
                        {p.tag}
                      </Badge>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Step 3: Upload drop zone */}
            {importStep === "uploading" && selectedPlatform && (
              <div
                className="flex flex-col items-center gap-4 rounded-xl border-2 border-dashed border-border py-10 text-center"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  const file = e.dataTransfer.files[0];
                  if (file) handleFileSelect(file);
                }}
              >
                <Upload className="h-10 w-10 text-muted-foreground" />
                <div>
                  <p className="font-medium">Drag & drop your {selectedPlatform.name} file here</p>
                  <p className="mt-1 text-sm text-muted-foreground max-w-sm">{selectedPlatform.hint}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Accepts: {selectedPlatform.acceptsPdf ? "CSV or PDF" : selectedPlatform.acceptsXlsx ? "CSV or XLSX" : "CSV"}
                  </p>
                </div>
                <Button variant="outline" onClick={() => fileRef.current?.click()}>Browse file</Button>
                <input
                  ref={fileRef}
                  type="file"
                  accept={selectedPlatform.acceptsPdf ? ".csv,.pdf" : selectedPlatform.acceptsXlsx ? ".csv,.xlsx" : ".csv"}
                  className="hidden"
                  onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFileSelect(f); }}
                />
              </div>
            )}

            {/* Step 3b: PDF password */}
            {importStep === "password" && pendingFile && selectedPlatform && (
              <div className="flex flex-col gap-4 max-w-sm">
                <p className="text-sm font-medium">{pendingFile.name}</p>
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">
                    Document password{" "}
                    <span className="text-muted-foreground/60">(usually your PAN number in uppercase)</span>
                  </label>
                  <input
                    type="password"
                    placeholder="e.g. ABCDE1234F"
                    value={pdfPassword}
                    onChange={(e) => { setPdfPassword(e.target.value); setPasswordError(false); }}
                    className={`w-full rounded-md border px-3 py-2 text-sm bg-background outline-none focus:ring-1 focus:ring-primary ${
                      passwordError ? "border-red-500" : "border-border"
                    }`}
                    autoFocus
                    onKeyDown={(e) => { if (e.key === "Enter") doUpload(pendingFile, pdfPassword); }}
                  />
                  {passwordError && (
                    <p className="text-xs text-red-400">Incorrect password — please try again.</p>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button onClick={() => doUpload(pendingFile, pdfPassword)}>Upload</Button>
                  <Button variant="outline" onClick={() => { setPendingFile(null); setPdfPassword(""); setPasswordError(false); setImportStep("uploading"); }}>
                    Back
                  </Button>
                </div>
              </div>
            )}

            {/* Step 4: Preview */}
            {importStep === "preview" && preview && (
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  Found <strong>{preview.holdings?.length ?? 0}</strong> holdings and{" "}
                  <strong>{preview.transactions ?? 0}</strong> transactions.
                  {(preview.duplicates?.length ?? 0) > 0 && (
                    <span className="ml-1 text-yellow-400">
                      {preview.duplicates.length} duplicates will be skipped.
                    </span>
                  )}
                </p>
                <div className="max-h-48 overflow-y-auto rounded-lg border border-border">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-card">
                      <tr className="border-b border-border text-left text-muted-foreground">
                        <th className="px-3 py-2">Name</th>
                        <th className="px-3 py-2">Type</th>
                        <th className="px-3 py-2 text-right">Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(preview.holdings ?? []).map((h, i) => (
                        <tr key={i} className="border-b border-border/50 last:border-0">
                          <td className="px-3 py-2">{h.display_name}</td>
                          <td className="px-3 py-2 capitalize">{h.instrument_type?.replace(/_/g, " ")}</td>
                          <td className="px-3 py-2 text-right">{fmt(h.current_value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex gap-2">
                  <Button onClick={confirmImport}>Confirm Import</Button>
                  <Button variant="outline" onClick={resetImport}>Cancel</Button>
                </div>
              </div>
            )}

            {/* Uploading spinner (shown while file is being processed) */}
            {importStep === "confirming" && (
              <div className="flex items-center gap-3 py-4">
                <RefreshCw className="h-5 w-5 animate-spin text-primary" />
                <span className="text-sm">Importing holdings…</span>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {importStep === "done" && (
        <div className="mb-6 rounded-xl bg-green-500/10 border border-green-500/30 px-4 py-3 text-sm text-green-400">
          Import complete! Your holdings have been updated.
          <button className="ml-2 underline" onClick={resetImport}>Dismiss</button>
        </div>
      )}

      {/* ── Tabs ── */}
      <div className="mb-4 flex gap-1 overflow-x-auto">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              "shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
              tab === t ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground"
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {/* ── Section summary ── */}
      {currentSummary && currentSummary.count > 0 && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
          <div className="rounded-xl border border-border bg-card px-4 py-3">
            <p className="text-xs text-muted-foreground">Holdings</p>
            <p className="mt-0.5 text-lg font-semibold tabular-nums">{currentSummary.count}</p>
          </div>
          <div className="rounded-xl border border-border bg-card px-4 py-3">
            <p className="text-xs text-muted-foreground">Invested</p>
            <p className="mt-0.5 text-lg font-semibold tabular-nums">{fmt(currentSummary.invested_amount)}</p>
          </div>
          <div className="rounded-xl border border-border bg-card px-4 py-3">
            <p className="text-xs text-muted-foreground">Current Value</p>
            <p className="mt-0.5 text-lg font-semibold tabular-nums">{fmt(currentSummary.current_value)}</p>
          </div>
          <div className="rounded-xl border border-border bg-card px-4 py-3">
            <p className="text-xs text-muted-foreground">P&amp;L</p>
            <p className={cn(
              "mt-0.5 text-lg font-semibold tabular-nums",
              currentSummary.unrealised_pnl >= 0 ? "text-green-400" : "text-red-400"
            )}>
              {currentSummary.unrealised_pnl >= 0 ? "+" : ""}{fmt(currentSummary.unrealised_pnl)}
              {currentSummary.invested_amount > 0 && (
                <span className="ml-1 text-sm font-normal">
                  ({((currentSummary.unrealised_pnl / currentSummary.invested_amount) * 100).toFixed(1)}%)
                </span>
              )}
            </p>
          </div>
          <div className="rounded-xl border border-border bg-card px-4 py-3">
            <p className="text-xs text-muted-foreground">XIRR</p>
            <p className={cn(
              "mt-0.5 text-lg font-semibold tabular-nums",
              currentSummary.xirr == null ? "" : currentSummary.xirr >= 0 ? "text-green-400" : "text-red-400"
            )}>
              {currentSummary.xirr != null ? `${currentSummary.xirr >= 0 ? "+" : ""}${currentSummary.xirr.toFixed(1)}%` : "—"}
            </p>
          </div>
        </div>
      )}

      {/* ── Holdings table ── */}
      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-16 rounded-xl" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <p className="text-muted-foreground">No holdings yet</p>
          <Button onClick={() => setImportStep("select_type")}>
            <Upload className="h-4 w-4" />
            Import from file
          </Button>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-card text-left text-xs text-muted-foreground">
                {COLUMNS.map((col) => (
                  <th key={col.key} className={cn("px-4 py-3", col.className)}>
                    <button
                      onClick={() => toggleSort(col.key)}
                      className={cn(
                        "inline-flex items-center gap-1 hover:text-foreground",
                        col.className?.includes("text-right") && "flex-row-reverse"
                      )}
                    >
                      {col.label}
                      {sortKey === col.key ? (
                        sortDir === "asc" ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
                      ) : (
                        <ArrowUpDown className="h-3 w-3 opacity-40" />
                      )}
                    </button>
                  </th>
                ))}
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {sorted.map((h) => {
                const gain = h.unrealised_pnl >= 0;
                const pnlPct = h.invested_amount > 0 ? (h.unrealised_pnl / h.invested_amount) * 100 : 0;
                return (
                  <React.Fragment key={h.id}>
                    <tr
                      className="border-b border-border/50 bg-card transition-colors hover:bg-muted/30 cursor-pointer"
                      onClick={() => setExpandedId(expandedId === h.id ? null : h.id)}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          {expandedId === h.id
                            ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
                            : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                          }
                          <span className="font-medium">{h.display_name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">{fmt(h.invested_amount)}</td>
                      <td className="px-4 py-3 text-right tabular-nums font-medium">{fmt(h.current_value)}</td>
                      <td className="px-4 py-3 text-right hidden sm:table-cell">
                        <span className={cn("tabular-nums text-xs font-medium", gain ? "text-green-400" : "text-red-400")}>
                          {gain ? "+" : ""}{fmt(h.unrealised_pnl)} ({pnlPct.toFixed(1)}%)
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right hidden lg:table-cell">
                        {h.xirr != null ? (
                          <span className={cn("tabular-nums text-xs", h.xirr >= 0 ? "text-green-400" : "text-red-400")}>
                            {h.xirr >= 0 ? "+" : ""}{h.xirr.toFixed(1)}%
                          </span>
                        ) : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => refreshHolding(h.id)}
                            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                            title="Refresh price"
                          >
                            <RefreshCw className={cn("h-3.5 w-3.5", refreshing === h.id && "animate-spin")} />
                          </button>
                          <button
                            onClick={() => deleteHolding(h.id)}
                            className="rounded p-1 text-muted-foreground hover:bg-destructive/20 hover:text-destructive"
                            title="Remove"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                    {expandedId === h.id && (
                      <tr key={`${h.id}-exp`} className="bg-muted/20">
                        <td colSpan={6} className="px-8 py-4">
                          <div className="grid gap-3 text-xs sm:grid-cols-2 md:grid-cols-3">
                            <div>
                              <p className="text-muted-foreground">Asset Class</p>
                              <p className="mt-0.5 font-medium capitalize">{h.asset_class}</p>
                            </div>
                            {Object.entries(h.metadata_ ?? {}).slice(0, 6).map(([k, v]) => (
                              <div key={k}>
                                <p className="capitalize text-muted-foreground">{k.replace(/_/g, " ")}</p>
                                <p className="mt-0.5 font-medium">{String(v)}</p>
                              </div>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
