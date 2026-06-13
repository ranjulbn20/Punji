"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { usePunji } from "@/store";

export default function Home() {
  const { user } = usePunji();
  const { status } = useSession();
  const router = useRouter();
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => { setHydrated(true); }, []);

  useEffect(() => {
    if (!hydrated || status === "loading") return;
    if (user) {
      router.replace(user.onboarding_step >= 2 ? "/dashboard" : "/onboarding");
    } else if (status === "authenticated") {
      // Session exists but Zustand not yet synced — go to dashboard, AuthGuard will sync
      router.replace("/dashboard");
    } else {
      router.replace("/login");
    }
  }, [hydrated, user, status, router]);

  return (
    <div className="flex h-screen items-center justify-center">
      <div className="text-muted-foreground text-sm">Loading…</div>
    </div>
  );
}
