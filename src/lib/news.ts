import type { IntelligenceSignal } from "./types";

const BOILERPLATE =
  /view full coverage on google news|this is an interpretation|this is an external south african|confirm with internal pos|demo scan:|suggested internal/i;

export function newsExcerpt(signal: IntelligenceSignal): string | null {
  if (signal.demo) return null;
  const title = signal.title.trim();
  let text = signal.summary
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!text || BOILERPLATE.test(text) || text.includes("<")) return null;
  if (title && text.toLowerCase().startsWith(title.toLowerCase())) {
    text = text.slice(title.length).replace(/^[\s:—–-]+/, "");
  }
  if (text.length < 48) return null;
  if (text.length > 220) {
    return `${text.slice(0, 217).replace(/\s+\S*$/, "")}…`;
  }
  return text;
}

export function newsHref(signal: IntelligenceSignal): string | null {
  if (!signal.sourceUrl) return null;
  try {
    const url = new URL(signal.sourceUrl);
    if (!/^https?:$/.test(url.protocol)) return null;
    return signal.sourceUrl;
  } catch {
    return null;
  }
}
