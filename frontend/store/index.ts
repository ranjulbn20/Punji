import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User, PortfolioSummary, Alert } from "@/lib/api";

interface PunjiStore {
  // Auth
  user: User | null;
  accessToken: string | null;
  setAuth: (user: User, accessToken: string, refreshToken: string) => void;
  setUser: (user: User) => void;
  clearAuth: () => void;

  // Portfolio
  portfolioSummary: PortfolioSummary | null;
  setPortfolioSummary: (s: PortfolioSummary) => void;

  // Alerts (live push)
  liveAlerts: Alert[];
  pushAlert: (a: Alert) => void;
  clearLiveAlerts: () => void;

  // Theme
  theme: "dark" | "light" | "system";
  setTheme: (t: "dark" | "light" | "system") => void;
}

export const usePunji = create<PunjiStore>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      setAuth: (user, accessToken, refreshToken) => {
        localStorage.setItem("punji_access_token", accessToken);
        localStorage.setItem("punji_refresh_token", refreshToken);
        set({ user, accessToken });
      },
      setUser: (user) => set({ user }),
      clearAuth: () => {
        localStorage.removeItem("punji_access_token");
        localStorage.removeItem("punji_refresh_token");
        set({ user: null, accessToken: null });
      },

      portfolioSummary: null,
      setPortfolioSummary: (s) => set({ portfolioSummary: s }),

      liveAlerts: [],
      pushAlert: (a) => set((s) => ({ liveAlerts: [a, ...s.liveAlerts].slice(0, 20) })),
      clearLiveAlerts: () => set({ liveAlerts: [] }),

      theme: "dark",
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: "punji-store",
      partialize: (s) => ({ user: s.user, accessToken: s.accessToken, theme: s.theme }),
    }
  )
);
