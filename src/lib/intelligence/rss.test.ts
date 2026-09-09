import assert from "node:assert/strict";
import { test } from "node:test";
import { parseRss } from "./rss.ts";

const SAMPLE = `<?xml version="1.0"?>
<rss><channel>
<item>
  <title><![CDATA[OMO washing powder special - News24]]></title>
  <link>https://news.google.com/articles/abc</link>
  <pubDate>Tue, 08 Sep 2026 09:00:00 GMT</pubDate>
  <source>News24</source>
  <description><![CDATA[OMO washing powder special Shoprite has a South Africa laundry promotion this week.]]></description>
</item>
<item>
  <title></title>
  <link></link>
</item>
</channel></rss>`;

test("parseRss extracts headline, publisher and excerpt", () => {
  const items = parseRss(SAMPLE, "Google News · Unilever Home Care SA");
  assert.equal(items.length, 1);
  assert.equal(items[0].title, "OMO washing powder special");
  assert.equal(items[0].source, "News24");
  assert.match(items[0].summary, /Shoprite/);
  assert.equal(items[0].link, "https://news.google.com/articles/abc");
});
