"use client";
import { useTheme } from "next-themes";

export function useChartColors() {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme !== "light";

  return {
    grid: isDark ? "#1E1E2E" : "#E8E8F4",
    axis: isDark ? "#5A5A7A" : "#8A8AAA",
    tooltip: {
      bg: isDark ? "#1A1A24" : "#FFFFFF",
      border: isDark ? "#2A2A3E" : "#D4D4E8",
    },
    gain: isDark ? "#22C55E" : "#16A34A",
    loss: isDark ? "#EF4444" : "#DC2626",
    brand: isDark ? "#6366F1" : "#4F46E5",
    charts: [
      "#6366F1", "#22C55E", "#F59E0B", "#EC4899",
      "#14B8A6", "#F97316", "#A855F7", "#06B6D4",
    ],
  };
}
