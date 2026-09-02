"use client";

import type { IntelligenceSignal } from "@/lib/types";
import { AppProvider } from "../providers";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

export function AppShell({
  children,
  initialSignals,
  initialLastScanAt,
}: {
  children: React.ReactNode;
  initialSignals: IntelligenceSignal[];
  initialLastScanAt: string;
}) {
  return (
    <AppProvider initialSignals={initialSignals} initialLastScanAt={initialLastScanAt}>
      <div className="flex min-h-screen bg-paper">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Header />
          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">{children}</main>
        </div>
      </div>
    </AppProvider>
  );
}
