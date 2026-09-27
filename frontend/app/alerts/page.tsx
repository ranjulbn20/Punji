"use client";
import { useEffect, useState } from "react";
import { CheckCheck, ChevronDown, ChevronUp, ExternalLink, ThumbsUp, ThumbsDown } from "lucide-react";
import { api, type Alert } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const SEV: Record<string, "destructive" | "warning" | "success" | "default"> = {
  critical: "destructive",
  warning: "warning",
  info: "default",
  success: "success",
};

const TYPE_LABEL: Record<string, string> = {
  rebalance: "Rebalance",
  goal_drift: "Goal Drift",
  market_event: "Market Event",
  signal_opportunity: "Recommendation",
  opportunity: "Opportunity",
  tax: "Tax",
};

const CRITIQUE_LABEL: Record<string, string> = {
  critical: "Critical concern",
  moderate: "Worth weighing",
  minor: "Minor note",
};

function timeAgo(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [feedbackId, setFeedbackId] = useState<string | null>(null);

  async function loadAlerts() {
    try {
      const data = await api.alerts.list();
      setAlerts(data as Alert[]);
    } catch {}
    finally { setLoading(false); }
  }

  useEffect(() => { loadAlerts(); }, []);

  async function markRead(id: string) {
    try {
      await api.alerts.markRead(id);
      setAlerts((prev) => prev.map((a) => a.id === id ? { ...a, is_read: true } : a));
    } catch {}
  }

  async function markAllRead() {
    try {
      await api.alerts.markAllRead();
      setAlerts((prev) => prev.map((a) => ({ ...a, is_read: true })));
    } catch {}
  }

  async function sendFeedback(id: string, feedback: "helpful" | "not_helpful") {
    try {
      await api.alerts.feedback(id, feedback);
      setFeedbackId(id);
    } catch {}
  }

  const unread = alerts.filter((a) => !a.is_read).length;

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Alerts</h1>
          {unread > 0 && (
            <p className="mt-0.5 text-sm text-muted-foreground">{unread} unread</p>
          )}
        </div>
        {unread > 0 && (
          <Button variant="outline" size="sm" onClick={markAllRead}>
            <CheckCheck className="h-4 w-4" />
            Mark all read
          </Button>
        )}
      </div>

      {loading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
        </div>
      ) : alerts.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-20 text-center">
          <CheckCheck className="h-12 w-12 text-muted-foreground" />
          <p className="font-medium">All clear</p>
          <p className="text-sm text-muted-foreground">No alerts right now. Punji will notify you when something needs your attention.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {alerts.map((a) => (
            <div
              key={a.id}
              className={cn(
                "rounded-xl border transition-all",
                a.is_read ? "border-border bg-card" : "border-primary/30 bg-primary/5"
              )}
            >
              <button
                className="flex w-full items-start gap-3 p-4 text-left"
                onClick={() => {
                  setExpanded(expanded === a.id ? null : a.id);
                  if (!a.is_read) markRead(a.id);
                }}
              >
                <div className="mt-0.5">
                  <Badge variant={SEV[a.severity] ?? "default"} className="capitalize">
                    {a.severity}
                  </Badge>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className={cn("truncate text-sm font-medium", !a.is_read && "text-foreground")}>
                      {a.title}
                    </p>
                    <div className="flex items-center gap-2 shrink-0">
                      {TYPE_LABEL[a.alert_type] && (
                        <span className="hidden text-xs text-muted-foreground sm:block">
                          {TYPE_LABEL[a.alert_type]}
                        </span>
                      )}
                      <span className="text-xs text-muted-foreground">{timeAgo(a.created_at)}</span>
                      {expanded === a.id
                        ? <ChevronUp className="h-4 w-4 text-muted-foreground" />
                        : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                    </div>
                  </div>
                  {expanded !== a.id && (
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">{a.message}</p>
                  )}
                </div>
              </button>

              {expanded === a.id && (
                <div className="border-t border-border px-4 pb-4 pt-3 space-y-3">
                  <p className="text-sm text-muted-foreground">{a.message}</p>

                  {a.alert_type === "market_event" && a.metadata && (
                    <div className="grid grid-cols-2 gap-x-4 gap-y-2 rounded-lg border border-border bg-muted/30 p-3 text-xs sm:grid-cols-3">
                      {a.metadata.change_1d_pct != null && (
                        <div>
                          <span className="text-muted-foreground">1-day move</span>
                          <p className="font-medium">{a.metadata.change_1d_pct > 0 ? "+" : ""}{a.metadata.change_1d_pct.toFixed(2)}%</p>
                        </div>
                      )}
                      {a.metadata.change_5d_pct != null && (
                        <div>
                          <span className="text-muted-foreground">5-day trend</span>
                          <p className="font-medium">{a.metadata.change_5d_pct > 0 ? "+" : ""}{a.metadata.change_5d_pct.toFixed(2)}%</p>
                        </div>
                      )}
                      {a.metadata.benchmark?.market_relative_pct != null && (
                        <div>
                          <span className="text-muted-foreground">vs NIFTY 50</span>
                          <p className="font-medium">{a.metadata.benchmark.market_relative_pct > 0 ? "+" : ""}{a.metadata.benchmark.market_relative_pct.toFixed(2)}%</p>
                        </div>
                      )}
                      {a.metadata.benchmark?.industry_relative_pct != null && (
                        <div>
                          <span className="text-muted-foreground">vs {a.metadata.benchmark.industry} index</span>
                          <p className="font-medium">{a.metadata.benchmark.industry_relative_pct > 0 ? "+" : ""}{a.metadata.benchmark.industry_relative_pct.toFixed(2)}%</p>
                        </div>
                      )}
                      {a.metadata.portfolio_weight_pct != null && (
                        <div>
                          <span className="text-muted-foreground">Portfolio weight</span>
                          <p className="font-medium">{a.metadata.portfolio_weight_pct.toFixed(1)}%</p>
                        </div>
                      )}
                      {a.metadata.confidence != null && (
                        <div>
                          <span className="text-muted-foreground">Confidence</span>
                          <p className="font-medium">{Math.round(a.metadata.confidence * 100)}%</p>
                        </div>
                      )}
                      {a.metadata.market_context && (
                        <div className="col-span-full border-t border-border pt-2">
                          <span className="text-muted-foreground">Assessment: </span>
                          <span className="font-medium">
                            {a.metadata.market_context === "broad_based" ? "Broad market/sector move" : "Company-specific"}
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {a.alert_type === "signal_opportunity" && a.metadata?.proposal && (
                    <div className="space-y-3 rounded-lg border border-border bg-muted/30 p-3 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold uppercase tracking-wide text-muted-foreground">
                          Proposal — not financial advice
                        </span>
                        <Badge variant={a.metadata.proposal.action === "sell" || a.metadata.proposal.action === "trim" ? "destructive" : "success"}>
                          {a.metadata.proposal.action}
                        </Badge>
                      </div>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
                        <div>
                          <span className="text-muted-foreground">Amount</span>
                          <p className="font-medium">₹{a.metadata.proposal.amount_inr.toLocaleString("en-IN")}</p>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Timeline</span>
                          <p className="font-medium capitalize">{a.metadata.proposal.timeline.replace(/_/g, " ")}</p>
                        </div>
                      </div>
                      <p className="text-muted-foreground">{a.metadata.proposal.reasoning}</p>
                      {a.metadata.proposal.tax_note && (
                        <p className="text-muted-foreground"><span className="font-medium text-foreground">Tax note: </span>{a.metadata.proposal.tax_note}</p>
                      )}

                      {a.metadata.critique && (
                        <div className="border-t border-border pt-2">
                          <p className="font-semibold uppercase tracking-wide text-muted-foreground">
                            Devil&apos;s advocate — {CRITIQUE_LABEL[a.metadata.critique.overall] ?? a.metadata.critique.overall}
                          </p>
                          <p className="mt-1 text-muted-foreground">{a.metadata.critique.strongest_concern}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {a.reasoning && (
                    <p className="text-xs text-muted-foreground">{a.reasoning}</p>
                  )}

                  {a.metadata?.news_link && (
                    <a
                      href={a.metadata.news_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      Read the source article <ExternalLink className="h-3 w-3" />
                    </a>
                  )}

                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Was this helpful?</span>
                    <button
                      onClick={() => sendFeedback(a.id, "helpful")}
                      className={cn(
                        "rounded p-1 text-muted-foreground transition-colors hover:text-green-400",
                        feedbackId === a.id && "text-green-400"
                      )}
                    >
                      <ThumbsUp className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => sendFeedback(a.id, "not_helpful")}
                      className={cn(
                        "rounded p-1 text-muted-foreground transition-colors hover:text-red-400",
                        feedbackId === a.id && "text-muted-foreground"
                      )}
                    >
                      <ThumbsDown className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
