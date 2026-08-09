import Link from "next/link";
import { ArticleSummary } from "@/lib/api";
import { Category } from "@/lib/categories";
import ArticleCard from "./ArticleCard";

type Props = {
  category: Category;
  articles: ArticleSummary[];
  max?: number;
};

/** One homepage row: "<Category> — See all →" heading + a grid of its top stories. */
export default function CategorySections({ category, articles, max = 3 }: Props) {
  if (articles.length === 0) return null;
  return (
    <section className="category-section">
      <div className="category-section-head">
        <h2>{category.label}</h2>
        <Link href={`/category/${category.slug}`}>See all →</Link>
      </div>
      <div className="article-grid">
        {articles.slice(0, max).map((a) => (
          <ArticleCard key={a.id} article={a} />
        ))}
      </div>
    </section>
  );
}
