"use client";
import { useEffect, useState } from "react";
import { CheckCheck, ChevronDown, ChevronUp, ThumbsUp, ThumbsDown } from "lucide-react";
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
  opportunity: "Opportunity",
  tax: "Tax",
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
                <div className="border-t border-border px-4 pb-4 pt-3">
                  <p className="text-sm text-muted-foreground">{a.message}</p>
                  <div className="mt-3 flex items-center gap-2">
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
