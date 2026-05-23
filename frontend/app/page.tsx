"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { usePunji } from "@/store";

export default function Home() {
  const { user } = usePunji();
  const router = useRouter();
  const [hydrated, setHydrated] = useState(false);

  // Wait one tick for Zustand persist to rehydrate from localStorage before redirecting
  useEffect(() => { setHydrated(true); }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (user) {
      router.replace(user.onboarding_step >= 3 ? "/dashboard" : "/onboarding");
    } else {
      router.replace("/login");
    }
  }, [hydrated, user, router]);

  return (
    <div className="flex h-screen items-center justify-center">
      <div className="text-muted-foreground text-sm">Loading…</div>
    </div>
  );
}
