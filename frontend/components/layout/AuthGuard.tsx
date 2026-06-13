"use client";
import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useSession } from "next-auth/react";
import { usePunji } from "@/store";
import AppShell from "@/components/layout/AppShell";

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, setAuth } = usePunji();
  const { data: session, status } = useSession();

  const backendToken = (session?.user as any)?.backendAccessToken;
  const backendRefreshToken = (session?.user as any)?.backendRefreshToken;
  const backendUser = (session?.user as any)?.backendUser;

  useEffect(() => {
    if (status === "loading") return;

    if (backendToken && backendUser) {
      // Always sync the latest token from NextAuth session — guards against stale Zustand persist
      const storedToken = typeof window !== "undefined" ? localStorage.getItem("punji_access_token") : null;
      if (storedToken !== backendToken || !user) {
        setAuth(backendUser, backendToken, backendRefreshToken ?? "");
      }
      // Prefer live Zustand step (updated after API calls) over frozen session value
      const currentStep = user?.onboarding_step ?? backendUser.onboarding_step ?? 0;
      const onboardingDone = currentStep >= 2;
      if (!onboardingDone && pathname !== "/onboarding") {
        router.replace("/onboarding");
      }
      return;
    }

    if (!user) router.replace("/login");
  }, [user, backendToken, backendRefreshToken, backendUser, status, router, pathname, setAuth]);

  // Wait while NextAuth is loading or we're mid-sync (no Zustand user yet)
  if (status === "loading" || (!user && backendToken)) return null;

  if (!user) return null;

  return <AppShell>{children}</AppShell>;
}
