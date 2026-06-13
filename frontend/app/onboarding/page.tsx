"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { usePunji } from "@/store";

const RISK_OPTIONS = [
  {
    value: "sell_everything",
    emoji: "😰",
    title: "Sell everything",
    desc: "I can't handle seeing my portfolio drop that much",
    category: "Conservative",
  },
  {
    value: "hold",
    emoji: "🧘",
    title: "Hold and wait",
    desc: "Markets recover — I'll stay the course",
    category: "Moderate",
  },
  {
    value: "buy_more",
    emoji: "🚀",
    title: "Buy more",
    desc: "A 30% drop is a buying opportunity",
    category: "Aggressive",
  },
];

function stepFromOnboardingStep(onboardingStep: number): number {
  if (onboardingStep >= 2) return 2;
  return 1;
}

export default function OnboardingPage() {
  const router = useRouter();
  const { user, setUser } = usePunji();
  const [step, setStep] = useState(() => stepFromOnboardingStep(user?.onboarding_step ?? 0));
  const [loading, setLoading] = useState(false);

  async function selectRisk(value: string) {
    setLoading(true);
    try {
      await api.auth.setRiskProfile(value);
      // Update Zustand so AuthGuard sees the new step on next navigation
      if (user) setUser({ ...user, onboarding_step: 2 });
      setStep(2);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4">
      {/* Progress */}
      <div className="mb-10 flex gap-2">
        {[1, 2, 3].map((s) => (
          <div
            key={s}
            className="h-1.5 w-16 rounded-full transition-colors"
            style={{ background: s <= step ? "var(--punji-brand)" : "var(--border)" }}
          />
        ))}
      </div>

      {step === 1 && (
        <div className="w-full max-w-2xl space-y-8 text-center">
          <div>
            <p className="text-sm font-medium uppercase tracking-wider text-muted-foreground">Step 1 of 3</p>
            <h2 className="mt-3 text-2xl font-bold">
              If your portfolio dropped 30% tomorrow, what would you do?
            </h2>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            {RISK_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                disabled={loading}
                onClick={() => selectRisk(opt.value)}
                className="group flex flex-col gap-3 rounded-xl border border-border bg-card p-6 text-left transition-all hover:border-primary hover:shadow-lg disabled:opacity-50"
              >
                <span className="text-4xl">{opt.emoji}</span>
                <div>
                  <p className="font-semibold">{opt.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{opt.desc}</p>
                </div>
                <span className="mt-auto text-xs font-medium text-primary">{opt.category}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="w-full max-w-lg space-y-8 text-center">
          <div>
            <p className="text-sm font-medium uppercase tracking-wider text-muted-foreground">Step 2 of 3</p>
            <h2 className="mt-3 text-2xl font-bold">Add your first holding</h2>
          </div>

          <div className="space-y-3">
            <button
              onClick={() => router.push("/holdings?import=true")}
              className="w-full rounded-xl border-2 border-primary bg-primary/10 p-5 text-left transition hover:bg-primary/20"
            >
              <p className="font-semibold">📄 Import from file</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Fastest way — supports Zerodha, Groww, CAMS CAS
              </p>
              <span className="mt-2 inline-block text-xs font-medium text-primary">Recommended</span>
            </button>

            <button
              onClick={() => router.push("/holdings?add=true")}
              className="w-full rounded-xl border border-border bg-card p-5 text-left transition hover:border-primary"
            >
              <p className="font-semibold">✏️ Add manually</p>
              <p className="mt-1 text-sm text-muted-foreground">Enter one holding at a time</p>
            </button>

            <button
              disabled
              className="w-full cursor-not-allowed rounded-xl border border-border bg-card p-5 text-left opacity-50"
            >
              <p className="font-semibold">🔗 Connect broker</p>
              <p className="mt-1 text-sm text-muted-foreground">Auto-sync with your broker account</p>
              <span className="mt-2 inline-block text-xs text-muted-foreground">Coming soon</span>
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="w-full max-w-md space-y-8 text-center">
          <div>
            <span className="inline-block rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
              Optional
            </span>
            <h2 className="mt-4 text-2xl font-bold">Set a financial goal</h2>
            <p className="mt-2 text-muted-foreground">Goals help Punji track your progress and alert you when you&apos;re off track.</p>
          </div>

          <div className="flex flex-col gap-3">
            <button
              onClick={() => router.push("/goals?create=true")}
              className="rounded-xl border-2 border-primary bg-primary/10 px-6 py-3 font-semibold transition hover:bg-primary/20"
            >
              Set a goal
            </button>
            <button
              onClick={() => router.push("/dashboard")}
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Skip — I&apos;ll set goals later from the dashboard
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
