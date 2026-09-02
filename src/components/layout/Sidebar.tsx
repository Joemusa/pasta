"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronLeft, ChevronRight, LayoutDashboard, Radio, Settings } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppState } from "../providers";

const NAV = [
  { href: "/", label: "Home", icon: LayoutDashboard },
  { href: "/intelligence", label: "Intelligence Feed", icon: Radio },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { collapsed, setCollapsed, mobileNav, setMobileNav } = useAppState();

  const content = (
    <aside
      className={cn(
        "flex h-full flex-col bg-ink text-[13px] text-white/80",
        collapsed ? "w-[72px]" : "w-[240px]",
      )}
    >
      <div className={cn("flex items-center gap-2 border-b border-white/10 px-4 py-5", collapsed && "justify-center px-2")}>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center bg-teal text-[11px] font-semibold tracking-wide text-white">
          SA
        </div>
        {!collapsed ? (
          <div className="min-w-0">
            <p className="truncate text-[11px] font-semibold uppercase tracking-[0.14em] text-white">
              Home Care
            </p>
            <p className="truncate text-[10px] uppercase tracking-wider text-white/45">
              Intelligence
            </p>
          </div>
        ) : null}
      </div>
      <nav className="flex-1 overflow-y-auto py-3">
        {NAV.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMobileNav(false)}
              title={item.label}
              className={cn(
                "mx-2 mb-0.5 flex items-center gap-3 rounded-sm px-3 py-2.5 transition-colors",
                collapsed && "justify-center px-0",
                active
                  ? "bg-white/10 text-white"
                  : "text-white/60 hover:bg-white/5 hover:text-white",
              )}
            >
              <Icon size={16} strokeWidth={1.75} />
              {!collapsed ? <span>{item.label}</span> : null}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-white/10 p-2">
        <button
          type="button"
          onClick={() => setCollapsed((c: boolean) => !c)}
          className="flex w-full items-center justify-center gap-2 rounded-sm px-2 py-2 text-white/50 hover:bg-white/5 hover:text-white"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight size={16} /> : <><ChevronLeft size={16} /><span className="text-xs">Collapse</span></>}
        </button>
      </div>
    </aside>
  );

  return (
    <>
      <div className="hidden h-screen sticky top-0 lg:block">{content}</div>
      {mobileNav ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            className="absolute inset-0 bg-ink/50"
            aria-label="Close menu"
            onClick={() => setMobileNav(false)}
          />
          <div className="relative h-full w-[240px]">{content}</div>
        </div>
      ) : null}
    </>
  );
}
