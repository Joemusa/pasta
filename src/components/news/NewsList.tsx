import { ArrowUpRight } from "lucide-react";
import type { IntelligenceSignal } from "@/lib/types";
import { newsExcerpt, newsHref } from "@/lib/news";
import { analyseStory } from "@/lib/product-impact";
import { formatDate } from "@/lib/utils";

export function NewsList({
  items,
  emptyTitle = "No stories in this period.",
  emptyBody = "Adjust filters or run a scan to pull South African news.",
}: {
  items: IntelligenceSignal[];
  emptyTitle?: string;
  emptyBody?: string;
}) {
  if (items.length === 0) {
    return (
      <div className="border border-rule bg-white px-5 py-10 text-center">
        <p className="font-serif text-xl text-ink-text">{emptyTitle}</p>
        <p className="mt-2 text-sm text-muted">{emptyBody}</p>
      </div>
    );
  }

  return (
    <div className="border border-rule bg-white">
      {items.map((signal) => (
        <NewsItem key={signal.id} signal={signal} />
      ))}
    </div>
  );
}

export function NewsItem({ signal }: { signal: IntelligenceSignal }) {
  const href = newsHref(signal);
  const excerpt = newsExcerpt(signal);
  const analysis = analyseStory(signal);

  return (
    <article className="border-b border-rule px-5 py-5 last:border-b-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-teal">
          {signal.source}
        </p>
        <time className="text-xs text-muted" dateTime={signal.publishedAt}>
          {formatDate(signal.publishedAt)}
        </time>
      </div>
      {href ? (
        <a href={href} target="_blank" rel="noreferrer" className="group mt-1.5 block">
          <h2 className="font-serif text-xl text-ink-text group-hover:text-teal">{signal.title}</h2>
        </a>
      ) : (
        <h2 className="mt-1.5 font-serif text-xl text-ink-text">{signal.title}</h2>
      )}
      {excerpt ? <p className="mt-2 text-sm leading-relaxed text-muted">{excerpt}</p> : null}
      <div className="mt-3 border border-rule bg-paper-2/40 px-4 py-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-teal">
          What this means for Unilever
        </p>
        <dl className="mt-2 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-[11px] uppercase tracking-wider text-muted">Category</dt>
            <dd className="text-ink-text">{analysis.category}</dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wider text-muted">Brand</dt>
            <dd className="text-ink-text">{analysis.brand}</dd>
          </div>
          <div>
            <dt className="text-[11px] uppercase tracking-wider text-muted">Product</dt>
            <dd className="text-ink-text">{analysis.product}</dd>
          </div>
        </dl>
        <p className="mt-2 text-sm leading-relaxed text-ink-text">{analysis.meaning}</p>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-0.5 text-teal hover:underline"
          >
            Read at {signal.source}
            <ArrowUpRight size={12} />
          </a>
        ) : (
          <span>Source cited · no article URL</span>
        )}
      </div>
    </article>
  );
}
