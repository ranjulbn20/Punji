"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Send, Bot, User, ChevronDown, ChevronRight, MessageSquare } from "lucide-react";
import { streamChat, api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant";
  content: string;
  trace?: string[];
  streaming?: boolean;
}

interface Conversation {
  id: string;
  title?: string;
  created_at: string;
}

export default function ChatPage() {
  const searchParams = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState(searchParams.get("q") ?? "");
  const [convId, setConvId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(false);
  const [traceOpen, setTraceOpen] = useState<number | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api.agent.conversations().then((data) => setConversations(data as Conversation[])).catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-submit if ?q= param is present
  useEffect(() => {
    const q = searchParams.get("q");
    if (q) send(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const send = useCallback(
    (text?: string) => {
      const msg = (text ?? input).trim();
      if (!msg || loading) return;
      setInput("");
      setLoading(true);

      const userMsg: Message = { role: "user", content: msg };
      const assistantMsg: Message = { role: "assistant", content: "", streaming: true };
      setMessages((prev) => [...prev, userMsg, assistantMsg]);

      let idx: number;
      setMessages((prev) => {
        idx = prev.length - 1;
        return prev;
      });

      streamChat(
        msg,
        convId,
        (token) => {
          setMessages((prev) =>
            prev.map((m, i) => (i === prev.length - 1 ? { ...m, content: m.content + token } : m))
          );
        },
        (trace) => {
          setMessages((prev) =>
            prev.map((m, i) => (i === prev.length - 1 ? { ...m, trace } : m))
          );
        },
        (newConvId) => {
          setConvId(newConvId);
          setLoading(false);
          setMessages((prev) =>
            prev.map((m, i) => (i === prev.length - 1 ? { ...m, streaming: false } : m))
          );
          api.agent.conversations().then((data) => setConversations(data as Conversation[])).catch(() => {});
        },
        (err) => {
          setLoading(false);
          setMessages((prev) =>
            prev.map((m, i) =>
              i === prev.length - 1 ? { ...m, content: `Error: ${err}`, streaming: false } : m
            )
          );
        }
      );
    },
    [input, loading, convId]
  );

  function loadConversation(id: string) {
    setConvId(id);
    setMessages([]);
    setSidebarOpen(false);
    api.agent
      .conversation(id)
      .then((data: unknown) => {
        const msgs = (data as { messages: { role: "user" | "assistant"; content: string }[] }).messages ?? [];
        setMessages(msgs.map((m) => ({ role: m.role, content: m.content })));
      })
      .catch(() => {});
  }

  function newChat() {
    setConvId(null);
    setMessages([]);
    setSidebarOpen(false);
  }

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  return (
    <div className="flex h-[calc(100vh-56px)] overflow-hidden">
      {/* History sidebar */}
      <aside
        className={cn(
          "flex w-64 shrink-0 flex-col border-r border-border bg-card transition-all duration-200",
          "hidden md:flex"
        )}
      >
        <div className="flex items-center justify-between border-b border-border p-3">
          <span className="text-sm font-semibold">History</span>
          <button
            onClick={newChat}
            className="rounded-lg px-2 py-1 text-xs text-primary hover:bg-primary/10"
          >
            + New
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {conversations.length === 0 ? (
            <p className="px-2 py-3 text-xs text-muted-foreground">No past conversations</p>
          ) : (
            conversations.map((c) => (
              <button
                key={c.id}
                onClick={() => loadConversation(c.id)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs transition-colors hover:bg-muted",
                  convId === c.id && "bg-primary/10 text-primary"
                )}
              >
                <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{c.title ?? new Date(c.created_at).toLocaleDateString("en-IN")}</span>
              </button>
            ))
          )}
        </div>
      </aside>

      {/* Chat area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center gap-6 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                <Bot className="h-8 w-8 text-primary" />
              </div>
              <div>
                <h2 className="text-xl font-semibold">Ask Punji anything</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Your AI-powered finance agent for Indian markets
                </p>
              </div>
              <div className="grid max-w-md gap-2 text-left">
                {[
                  "How is my portfolio performing vs Nifty 50?",
                  "Am I on track for my retirement goal?",
                  "Where am I overexposed to a single business group?",
                  "What should I do with my HDFC Bank SIP?",
                ].map((q) => (
                  <button
                    key={q}
                    onClick={() => { setInput(q); textareaRef.current?.focus(); }}
                    className="rounded-xl border border-border bg-card px-4 py-3 text-left text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="mx-auto max-w-3xl space-y-6">
            {messages.map((m, i) => (
              <div key={i} className={cn("flex gap-3", m.role === "user" && "justify-end")}>
                {m.role === "assistant" && (
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 mt-1">
                    <Bot className="h-4 w-4 text-primary" />
                  </div>
                )}
                <div className={cn("max-w-[85%] space-y-2", m.role === "user" && "items-end")}>
                  <div
                    className={cn(
                      "rounded-2xl px-4 py-3 text-sm leading-relaxed",
                      m.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-foreground"
                    )}
                  >
                    {m.content || (m.streaming && (
                      <span className="inline-flex gap-1">
                        <span className="animate-bounce delay-0 h-1.5 w-1.5 rounded-full bg-muted-foreground" />
                        <span className="animate-bounce delay-150 h-1.5 w-1.5 rounded-full bg-muted-foreground" />
                        <span className="animate-bounce delay-300 h-1.5 w-1.5 rounded-full bg-muted-foreground" />
                      </span>
                    ))}
                  </div>

                  {/* Reasoning trace */}
                  {m.role === "assistant" && m.trace && m.trace.length > 0 && (
                    <div className="text-xs">
                      <button
                        onClick={() => setTraceOpen(traceOpen === i ? null : i)}
                        className="flex items-center gap-1 text-muted-foreground hover:text-foreground"
                      >
                        {traceOpen === i ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                        Reasoning trace ({m.trace.length} steps)
                      </button>
                      {traceOpen === i && (
                        <div className="mt-2 space-y-1 rounded-lg border border-border bg-card p-3">
                          {m.trace.map((t, j) => (
                            <div key={j} className="flex gap-2 text-muted-foreground">
                              <span className="shrink-0 font-mono text-primary">{j + 1}.</span>
                              <span>{t}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {m.role === "user" && (
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted mt-1">
                    <User className="h-4 w-4 text-muted-foreground" />
                  </div>
                )}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* Input */}
        <div className="border-t border-border bg-background p-4">
          <div className="mx-auto max-w-3xl">
            <div className="flex items-end gap-3 rounded-2xl border border-input bg-background px-4 py-3 focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/30">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKey}
                placeholder="Ask about your portfolio, goals, market events…"
                rows={1}
                className="max-h-40 flex-1 resize-none bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                style={{ height: "auto" }}
                onInput={(e) => {
                  const el = e.currentTarget;
                  el.style.height = "auto";
                  el.style.height = `${el.scrollHeight}px`;
                }}
              />
              <button
                onClick={() => send()}
                disabled={loading || !input.trim()}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground transition-opacity hover:bg-primary/90 disabled:opacity-40"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
            <p className="mt-2 text-center text-xs text-muted-foreground">
              Punji uses AI — verify important financial decisions with a SEBI-registered advisor
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
