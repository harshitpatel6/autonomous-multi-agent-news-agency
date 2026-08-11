import Link from "next/link";
import { ArticleSummary } from "@/lib/api";
import { Category } from "@/lib/categories";
import ArticleCard from "./ArticleCard";

type Props = {
  category: Category;
  articles: ArticleSummary[];
  max?: number;
};

export default function CategorySections({ category, articles, max = 3 }: Props) {
  if (articles.length === 0) return null;
  return (
    <section style={{ marginBottom: 48 }}>
      <div className="section-head">
        <div className="section-head-title">
          <span className="section-accent-dot" style={{ background: category.color }} />
          <h2>{category.label}</h2>
        </div>
        <Link href={`/category/${category.slug}`}>See all stories →</Link>
      </div>
      <div className="article-grid">
        {articles.slice(0, max).map((a) => (
          <ArticleCard key={a.id} article={a} />
        ))}
      </div>
    </section>
  );
}
