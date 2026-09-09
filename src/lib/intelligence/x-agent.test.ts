import assert from "node:assert/strict";
import { test } from "node:test";
import { matchCatalogBrands } from "../home-care-catalog.ts";
import { inferSentiment, inferTopic, xPostToSignal } from "./x-analyze.ts";
import { defaultXQueries } from "./x-queries.ts";
import { xInsights } from "./x-insights.ts";
import { passesRelevanceThreshold, scoreXPost, type XPost } from "./x-relevance.ts";
import { selectXSignals, tweetToPost } from "./x-twitter.ts";

function post(partial: Partial<XPost> & Pick<XPost, "id" | "text">): XPost {
  return {
    createdAt: "2026-09-09T08:00:00.000Z",
    url: "https://x.com/shopper/status/1",
    likes: 0,
    replies: 0,
    reposts: 0,
    hashtags: [],
    query: "X · Unilever Home Care SA",
    location: "Johannesburg, South Africa",
    ...partial,
  };
}

test("catalog does not treat comfortable as Comfort", () => {
  assert.equal(matchCatalogBrands("this sofa is comfortable").length, 0);
  assert.ok(matchCatalogBrands("Comfort fabric conditioner in Shoprite").some((b) => b.name === "Comfort"));
});

test("high relevance Unilever complaint stays in the feed", () => {
  const relevance = scoreXPost(
    post({
      id: "1",
      text: "OMO washing powder in South Africa doesn't work and smells cheap. Switching to MAQ.",
      likes: 80,
      reposts: 12,
    }),
  );
  assert.equal(relevance.band, "high");
  assert.ok(passesRelevanceThreshold(relevance, 40));
  assert.ok(relevance.brands.some((b) => b.name === "OMO"));
});

test("unrelated Unilever divisions and spam are dropped", () => {
  assert.equal(scoreXPost(post({ id: "2", text: "Love Dove soap and TRESemmé in Sandton" })).band, "drop");
  assert.equal(scoreXPost(post({ id: "3", text: "OMO crypto giveaway click here" })).band, "drop");
});

test("low generic mentions miss the default threshold", () => {
  const relevance = scoreXPost(post({ id: "4", text: "Unilever share price today", location: "" }));
  assert.equal(passesRelevanceThreshold(relevance, 40), false);
});

test("sentiment and topic stay inside the post text", () => {
  assert.equal(inferSentiment("OMO doesn't work and I'm disappointed"), "negative");
  assert.equal(inferSentiment("I love Sunlight liquid, best dish soap"), "positive");
  assert.equal(inferTopic("out of stock at Shoprite"), "availability");
});

test("selectXSignals dedupes the same tweet id and near-copy text", () => {
  const fetchedAt = "2026-09-09T09:00:00.000Z";
  const a = post({
    id: "10",
    text: "Sunlight dishwashing liquid is too expensive in South Africa Shoprite",
    likes: 20,
  });
  const copy = post({
    id: "11",
    text: "Sunlight dishwashing liquid is too expensive in South Africa Shoprite https://t.co/abc",
  });
  const sameId = post({
    id: "10",
    text: "Sunlight dishwashing liquid is too expensive in South Africa Shoprite extra",
  });
  const signals = selectXSignals([a, copy, sameId], fetchedAt, 40, 12);
  assert.equal(signals.length, 1);
  assert.equal(signals[0].source, "X");
  assert.equal(signals[0].sourceType, "social_media");
  assert.match(signals[0].fact, /On X/);
  assert.match(signals[0].interpretation, /not a verified fact/i);
});

test("tweetToPost maps public X API fields without inventing a handle", () => {
  const mapped = tweetToPost(
    {
      id: "99",
      text: "Domestos is out of stock",
      created_at: "2026-09-09T07:00:00.000Z",
      author_id: "u1",
      public_metrics: { like_count: 3, reply_count: 1, retweet_count: 0 },
      entities: { hashtags: [{ tag: "Domestos" }] },
    },
    new Map([["u1", { id: "u1", name: "Thandi", username: "thandi_sa", location: "Durban" }]]),
    new Map(),
    "X · consumer voice",
  );
  assert.ok(mapped);
  assert.equal(mapped.url, "https://x.com/thandi_sa/status/99");
  assert.equal(mapped.authorHandle, "thandi_sa");
  assert.deepEqual(mapped.hashtags, ["Domestos"]);
});

test("X insights summarise only X posts", () => {
  const x = xPostToSignal(
    post({
      id: "21",
      text: "OMO laundry detergent in Cape Town is a waste, doesn't work",
      likes: 60,
    }),
    scoreXPost(
      post({
        id: "21",
        text: "OMO laundry detergent in Cape Town is a waste, doesn't work",
        likes: 60,
      }),
    ),
    "2026-09-09T09:00:00.000Z",
  );
  const report = xInsights([
    x,
    {
      ...x,
      id: "news-1",
      source: "News24",
      sourceType: "news",
      title: "Sunlight Liquid gets more time",
    },
  ]);
  assert.equal(report.posts, 1);
  assert.ok(report.sentiment.negative >= 1);
  assert.match(report.implication, /HelloPeter/);
});

test("default X queries stay within the 512 character API limit", () => {
  for (const feed of defaultXQueries()) {
    assert.ok(feed.query.length <= 512, `${feed.name} is ${feed.query.length}`);
  }
});
