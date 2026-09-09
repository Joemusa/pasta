import { xInsights } from "@/lib/intelligence/x-insights";
import type { IntelligenceSignal } from "@/lib/types";

export function XInsights({ signals }: { signals: IntelligenceSignal[] }) {
  const report = xInsights(signals);
  if (report.posts === 0) return null;

  return (
    <section className="border border-rule bg-white p-5">
      <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-teal">X consumer voice</p>
      <h2 className="mt-1 font-serif text-xl text-ink-text">What shoppers are saying on X</h2>
      <p className="mt-2 text-sm text-muted">
        Social-media discussion, not verified facts. {report.posts} posts in this view.
      </p>
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-[11px] uppercase tracking-wider text-muted">Negative</dt>
          <dd className="text-ink-text">{report.sentiment.negative}</dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase tracking-wider text-muted">Neutral</dt>
          <dd className="text-ink-text">{report.sentiment.neutral}</dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase tracking-wider text-muted">Positive</dt>
          <dd className="text-ink-text">{report.sentiment.positive}</dd>
        </div>
      </dl>
      <p className="mt-3 text-sm leading-relaxed text-ink-text">{report.consumerVoice}</p>
      <p className="mt-2 text-sm leading-relaxed text-muted">{report.brandSentiment}</p>
      {report.productIssues.length > 0 ? (
        <p className="mt-2 text-sm">
          <span className="text-muted">Product issues: </span>
          {report.productIssues.join("; ")}
        </p>
      ) : null}
      {report.competitive.length > 0 ? (
        <p className="mt-2 text-sm">
          <span className="text-muted">Competitive: </span>
          {report.competitive.join("; ")}
        </p>
      ) : null}
      {report.important.length > 0 ? (
        <p className="mt-2 text-sm">
          <span className="text-muted">Important conversations: </span>
          {report.important.join("; ")}
        </p>
      ) : null}
      <p className="mt-3 text-sm leading-relaxed text-ink-text">{report.implication}</p>
    </section>
  );
}
