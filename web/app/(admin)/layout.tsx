"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "@/components/ThemeToggle";

const LINKS = [
  { href: "/dashboard", label: "Overview", icon: "📊" },
  { href: "/seo", label: "SEO", icon: "🔍" },
  { href: "/history", label: "Article History", icon: "🗂️" },
  { href: "/agents", label: "Agent Performance", icon: "🤖" },
  { href: "/digests", label: "Recent Digests", icon: "📬" },
  { href: "/ceo", label: "CEO Chat (ALEX)", icon: "💬" },
  { href: "/config", label: "Configuration", icon: "⚙️" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="layout admin-theme">
      <aside className="sidebar">
        <h1>🗞️ AI News Agency</h1>
        <div className="subtitle">Autonomous multi-agent dashboard</div>
        <ThemeToggle />
        <nav>
          <Link href="/">🌐 View public site</Link>
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className={pathname === l.href ? "active" : undefined}>
              {l.icon} {l.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
