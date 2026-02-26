"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LayoutDashboard,
  MessageSquare,
  Users,
  Mail,
  MessageSquareReply,
  BarChart3,
  Settings,
  Bot,
  LogOut,
  Search,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/prospecting", label: "Prospecting", icon: Search },
  { href: "/chat", label: "AI Chat", icon: MessageSquare },
  { href: "/ai-agents", label: "AI Agents", icon: Bot },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/usage", label: "Usage", icon: BarChart3 },
  { href: "/campaigns", label: "Campaigns", icon: Mail },
  { href: "/responses", label: "Replies", icon: MessageSquareReply },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <aside className="w-64 border-r bg-card h-screen flex flex-col">
      <div className="p-6">
        <h2 className="text-lg font-semibold">Miriade</h2>
        <p className="text-xs text-muted-foreground mt-1">B2B Outreach Platform</p>
      </div>
      <nav className="flex-1 px-3">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors mb-1",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t">
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors w-full px-3 py-2 rounded-lg hover:bg-accent"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
        <p className="text-xs text-muted-foreground mt-2 px-3">v0.1.0</p>
      </div>
    </aside>
  );
}
