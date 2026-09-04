import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Geist, Geist_Mono, Source_Serif_4 } from "next/font/google";
import { connection } from "next/server";
import { AppShell } from "@/components/layout/AppShell";
import { loadInitialNews } from "@/lib/intelligence/bootstrap";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin"],
  weight: ["400", "600", "700"],
});

export const metadata: Metadata = {
  title: "SA Home Care Intelligence",
  description:
    "South African Home Care news for Unilever.",
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  await connection();
  const initial = await loadInitialNews();
  return (
    <html
      lang="en-ZA"
      className={`${geistSans.variable} ${geistMono.variable} ${sourceSerif.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <AppShell initialSignals={initial.signals} initialLastScanAt={initial.lastScanAt}>
          {children}
        </AppShell>
      </body>
    </html>
  );
}
