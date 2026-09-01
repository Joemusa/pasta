import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatScanTime(iso: string, now = new Date()): string {
  const date = new Date(iso);
  const sameDay =
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate();
  const time = date.toLocaleTimeString("en-ZA", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  if (sameDay) return `Today, ${time}`;
  return `${date.toLocaleDateString("en-ZA", {
    day: "numeric",
    month: "short",
  })}, ${time}`;
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function deltaLabel(current: number, previous: number): {
  text: string;
  direction: "up" | "down" | "flat";
} {
  if (previous === 0 && current === 0) {
    return { text: "No change vs previous period", direction: "flat" };
  }
  if (previous === 0) {
    return { text: "New vs previous period", direction: "up" };
  }
  const pct = Math.round(((current - previous) / previous) * 100);
  if (pct === 0) {
    return { text: "No change vs previous period", direction: "flat" };
  }
  const arrow = pct > 0 ? "↑" : "↓";
  return {
    text: `${arrow} ${Math.abs(pct)}% vs previous period`,
    direction: pct > 0 ? "up" : "down",
  };
}
