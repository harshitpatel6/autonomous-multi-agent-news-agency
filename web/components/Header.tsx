import Link from "next/link";
import { CATEGORIES } from "@/lib/categories";

export default function Header() {
  return (
    <header className="site-header">
      <div className="site-header-top">
        <Link href="/" className="site-logo">
          AI <span>Daily</span>
        </Link>
        <Link href="/articles" className="site-header-cta">
          Newsroom
        </Link>
      </div>
      <nav className="site-nav">
        <Link href="/">Home</Link>
        {CATEGORIES.map((c) => (
          <Link key={c.slug} href={`/category/${c.slug}`}>
            {c.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
