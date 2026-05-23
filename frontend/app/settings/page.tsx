"use client";
import { useEffect, useState } from "react";
import { Trash2, Sun, Moon, Monitor } from "lucide-react";
import { api } from "@/lib/api";
import { usePunji } from "@/store";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface Memory { id: string; memory_type: string; content: string; created_at: string; }
interface ImportJob { id: string; source_platform: string; status: string; created_at: string; holdings_imported: number; }

const THEMES = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
] as const;

export default function SettingsPage() {
  const { user, theme, setTheme } = usePunji();
  const [memories, setMemories] = useState<Memory[]>([]);
  const [imports, setImports] = useState<ImportJob[]>([]);
  const [loadingMem, setLoadingMem] = useState(true);
  const [loadingImp, setLoadingImp] = useState(true);
  const [deletingMem, setDeletingMem] = useState<string | null>(null);

  useEffect(() => {
    api.agent.memories()
      .then((d) => setMemories(d as Memory[]))
      .catch(() => {})
      .finally(() => setLoadingMem(false));
    api.imports.history()
      .then((d) => setImports(d as ImportJob[]))
      .catch(() => {})
      .finally(() => setLoadingImp(false));
  }, []);

  async function deleteMemory(id: string) {
    setDeletingMem(id);
    try {
      await api.agent.deleteMemory(id);
      setMemories((m) => m.filter((x) => x.id !== id));
    } catch {}
    finally { setDeletingMem(null); }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <h1 className="text-xl font-semibold">Settings</h1>

      {/* Profile */}
      <Card>
        <CardHeader><CardTitle>Profile</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Name</span>
            <span className="font-medium">{user?.full_name ?? "—"}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Email</span>
            <span className="font-medium">{user?.email}</span>
          </div>
        </CardContent>
      </Card>

      {/* Theme */}
      <Card>
        <CardHeader><CardTitle>Appearance</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-2">
            {THEMES.map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                onClick={() => setTheme(value)}
                className={cn(
                  "flex flex-1 flex-col items-center gap-1.5 rounded-xl border py-3 text-xs font-medium transition-colors",
                  theme === value
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground"
                )}
              >
                <Icon className="h-5 w-5" />
                {label}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Agent Memory */}
      <Card>
        <CardHeader>
          <CardTitle>Agent Memory</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 text-xs text-muted-foreground">
            Punji stores context from your conversations to personalise future responses.
            You can delete individual memories.
          </p>
          {loadingMem ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}
            </div>
          ) : memories.length === 0 ? (
            <p className="text-sm text-muted-foreground">No memories stored yet.</p>
          ) : (
            <div className="space-y-2">
              {memories.map((m) => (
                <div key={m.id} className="flex items-start gap-3 rounded-lg border border-border bg-muted/30 p-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className="text-xs capitalize">{m.memory_type}</Badge>
                      <span className="text-xs text-muted-foreground">
                        {new Date(m.created_at).toLocaleDateString("en-IN")}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{m.content}</p>
                  </div>
                  <button
                    onClick={() => deleteMemory(m.id)}
                    disabled={deletingMem === m.id}
                    className="shrink-0 rounded p-1 text-muted-foreground hover:bg-destructive/20 hover:text-destructive disabled:opacity-50"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Import History */}
      <Card>
        <CardHeader><CardTitle>Import History</CardTitle></CardHeader>
        <CardContent>
          {loadingImp ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-10 rounded-lg" />)}
            </div>
          ) : imports.length === 0 ? (
            <p className="text-sm text-muted-foreground">No imports yet.</p>
          ) : (
            <div className="overflow-hidden rounded-lg border border-border">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border bg-muted/30 text-left text-muted-foreground">
                    <th className="px-3 py-2">Platform</th>
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2 text-center">Holdings</th>
                    <th className="px-3 py-2 text-right">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {imports.map((j) => (
                    <tr key={j.id} className="border-b border-border/50 last:border-0">
                      <td className="px-3 py-2 capitalize font-medium">{j.source_platform}</td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {new Date(j.created_at).toLocaleDateString("en-IN")}
                      </td>
                      <td className="px-3 py-2 text-center">{j.holdings_imported ?? 0}</td>
                      <td className="px-3 py-2 text-right">
                        <Badge
                          variant={j.status === "completed" ? "success" : j.status === "failed" ? "destructive" : "default"}
                          className="capitalize"
                        >
                          {j.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Danger zone */}
      <Card className="border-destructive/30">
        <CardHeader><CardTitle className="text-destructive">Danger Zone</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">Delete all agent memories</p>
              <p className="text-xs text-muted-foreground">Punji will lose all context about you</p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={async () => {
                if (!confirm("Delete all agent memories? This cannot be undone.")) return;
                for (const m of memories) { await api.agent.deleteMemory(m.id).catch(() => {}); }
                setMemories([]);
              }}
            >
              Clear All
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
