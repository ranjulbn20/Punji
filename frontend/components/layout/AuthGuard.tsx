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

  useEffect(() => {
    if (status === "loading") return;

    // Bridge NextAuth Google session → Zustand store on first sign-in
    if (!user && session?.backendAccessToken && session.backendUser) {
      setAuth(session.backendUser as any, session.backendAccessToken, "");
      // Redirect new users to onboarding, returning users stay where they are
      const onboardingDone = (session.backendUser.onboarding_step ?? 0) >= 3;
      if (!onboardingDone && pathname !== "/onboarding") {
        router.replace("/onboarding");
      }
      return;
    }

    if (!user) router.replace("/login");
  }, [user, session, status, router, pathname, setAuth]);

  // Wait while NextAuth is loading or we're mid-sync
  if (status === "loading" || (!user && session?.backendAccessToken)) return null;

  if (!user) return null;

  return <AppShell>{children}</AppShell>;
}
