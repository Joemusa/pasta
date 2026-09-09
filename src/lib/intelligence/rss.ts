export type RssItem = {
  title: string;
  link: string;
  pubDate: string;
  source: string;
  summary: string;
};

export function decodeXml(text: string): string {
  const withTags = text
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&");
  return withTags.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}

function tag(block: string, name: string): string {
  const cdata = block.match(new RegExp(`<${name}[^>]*>\\s*<!\\[CDATA\\[([\\s\\S]*?)\\]\\]>`, "i"));
  if (cdata) return decodeXml(cdata[1]);
  const plain = block.match(new RegExp(`<${name}[^>]*>([\\s\\S]*?)</${name}>`, "i"));
  return plain ? decodeXml(plain[1]) : "";
}

export function prettySource(publisher: string, feedName: string): string {
  const name = publisher.trim();
  if (name && !/^google news/i.test(name)) return name;
  if (feedName.startsWith("Google News")) return "Google News";
  return feedName;
}

export function cleanExcerpt(raw: string, title: string): string {
  let text = decodeXml(raw).replace(/View Full Coverage on Google News/gi, "").trim();
  if (title && text.toLowerCase().startsWith(title.toLowerCase())) {
    text = text.slice(title.length).replace(/^[\s:—–-]+/, "");
  }
  if (text.includes("<") || text.length < 48) return "";
  if (text.length > 400) return `${text.slice(0, 397).replace(/\s+\S*$/, "")}…`;
  return text;
}

export function parseRss(xml: string, feedName: string): RssItem[] {
  const chunks = xml.split(/<item[\s>]/i).slice(1);
  return chunks
    .map((chunk) => {
      const block = chunk.split(/<\/item>/i)[0] ?? "";
      const title = tag(block, "title");
      const link = tag(block, "link") || tag(block, "guid");
      const publisher =
        tag(block, "source") || (title.includes(" - ") ? title.split(" - ").slice(-1)[0] : "");
      const headline = title.replace(/\s+-\s+[^-]+$/, "").trim() || title;
      return {
        title: headline,
        link,
        pubDate: tag(block, "pubDate") || tag(block, "published"),
        source: prettySource(publisher, feedName),
        summary: cleanExcerpt(tag(block, "description"), headline),
      };
    })
    .filter((item) => item.title && item.link);
}
