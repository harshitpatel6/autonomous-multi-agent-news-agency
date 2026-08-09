import Link from "next/link";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="layout admin-theme">
      <aside className="sidebar">
        <h1>🗞️ AI News Agency</h1>
        <div className="subtitle">Autonomous multi-agent dashboard</div>
        <nav>
          <Link href="/">🌐 View public site</Link>
          <Link href="/dashboard">Overview</Link>
          <Link href="/agents">Agent Performance</Link>
          <Link href="/digests">Recent Digests</Link>
          <Link href="/ceo">CEO Chat (ALEX)</Link>
          <Link href="/config">Configuration</Link>
        </nav>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
