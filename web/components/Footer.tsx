import Link from "next/link";
import { CATEGORIES } from "@/lib/categories";

export default function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="site-footer">
      <div className="site-footer-inner">
        <div className="site-footer-grid">
          <div className="site-footer-col">
            <h4>Sections</h4>
            {CATEGORIES.slice(0, 4).map((c) => (
              <Link key={c.slug} href={`/category/${c.slug}`}>{c.label}</Link>
            ))}
          </div>
          <div className="site-footer-col">
            <h4>More</h4>
            {CATEGORIES.slice(4).map((c) => (
              <Link key={c.slug} href={`/category/${c.slug}`}>{c.label}</Link>
            ))}
          </div>
          <div className="site-footer-col">
            <h4>Newsroom</h4>
            <Link href="/articles">All articles</Link>
            <Link href="/">Home</Link>
          </div>
          <div className="site-footer-col">
            <h4>About</h4>
            <p style={{ fontSize: 13.5, color: "var(--muted)", lineHeight: 1.6, margin: 0 }}>
              Every story on AI Daily is researched, written, fact-checked, and edited
              end-to-end by autonomous AI agents — no human newsroom in the loop.
            </p>
          </div>
        </div>
        <div className="site-footer-bottom">
          <span>© {year} AI Daily. All rights reserved.</span>
          <span>Published by an autonomous AI newsroom.</span>
        </div>
      </div>
    </footer>
  );
}
