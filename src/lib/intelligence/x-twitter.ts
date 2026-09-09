import { xPostToSignal } from "./x-analyze";
import { getXBearerToken, getXSettings, xTokenConfigured } from "./x-config";
import { defaultXQueries, xSearchParams } from "./x-queries";
import {
  passesRelevanceThreshold,
  scoreXPost,
  type XPost,
} from "./x-relevance";
import type { IntelligenceSignal } from "../types";

type ScanFeedError = { feed: string; error: string };

type TwitterUser = { id: string; name?: string; username?: string; location?: string };
type TwitterMedia = { media_key: string; type?: string };
type TwitterTweet = {
  id: string;
  text?: string;
  created_at?: string;
  author_id?: string;
  conversation_id?: string;
  public_metrics?: { like_count?: number; reply_count?: number; retweet_count?: number };
  entities?: { hashtags?: { tag?: string }[]; urls?: { expanded_url?: string }[] };
  attachments?: { media_keys?: string[] };
};

const API = "https://api.twitter.com/2/tweets/search/recent";
const FETCH_MS = 12000;

function normalizeText(text: string): string {
  return text
    .toLowerCase()
    .replace(/https?:\/\/\S+/g, "")
    .replace(/@\w+/g, "")
    .replace(/#/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 120);
}

async function searchRecent(query: string, token: string, settings: ReturnType<typeof getXSettings>): Promise<{
  tweets: TwitterTweet[];
  users: TwitterUser[];
  media: TwitterMedia[];
}> {
  const url = `${API}?${xSearchParams(query, settings).toString()}`;
  const res = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
    signal: AbortSignal.timeout(FETCH_MS),
    cache: "no-store",
  });
  if (res.status === 429) {
    const err = new Error("X API rate limited");
    (err as Error & { code: number }).code = 429;
    throw err;
  }
  if (res.status === 401 || res.status === 403) {
    throw new Error("X API authentication failed");
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`X API HTTP ${res.status}${body ? `: ${body.slice(0, 180)}` : ""}`);
  }
  const json = (await res.json()) as {
    data?: TwitterTweet[];
    includes?: { users?: TwitterUser[]; media?: TwitterMedia[] };
  };
  return {
    tweets: json.data ?? [],
    users: json.includes?.users ?? [],
    media: json.includes?.media ?? [],
  };
}

export function tweetToPost(
  tweet: TwitterTweet,
  users: Map<string, TwitterUser>,
  media: Map<string, TwitterMedia>,
  query: string,
): XPost | null {
  const text = (tweet.text ?? "").trim();
  if (!text || !tweet.id) return null;
  const user = tweet.author_id ? users.get(tweet.author_id) : undefined;
  const handle = user?.username;
  const mediaType = tweet.attachments?.media_keys
    ?.map((key) => media.get(key)?.type)
    .find(Boolean);
  return {
    id: tweet.id,
    text,
    createdAt: tweet.created_at ? new Date(tweet.created_at).toISOString() : new Date().toISOString(),
    url: handle ? `https://x.com/${handle}/status/${tweet.id}` : `https://x.com/i/web/status/${tweet.id}`,
    author: user?.name,
    authorHandle: handle,
    location: user?.location,
    likes: tweet.public_metrics?.like_count ?? 0,
    replies: tweet.public_metrics?.reply_count ?? 0,
    reposts: tweet.public_metrics?.retweet_count ?? 0,
    hashtags: (tweet.entities?.hashtags ?? []).map((h) => h.tag).filter((tag): tag is string => Boolean(tag)),
    mediaType,
    query,
  };
}

export function selectXSignals(
  posts: XPost[],
  fetchedAt: string,
  threshold: number,
  cap: number,
): IntelligenceSignal[] {
  const seenIds = new Set<string>();
  const seenText = new Set<string>();
  const selected: IntelligenceSignal[] = [];
  const ranked = posts
    .map((post) => ({ post, relevance: scoreXPost(post) }))
    .filter((row) => passesRelevanceThreshold(row.relevance, threshold))
    .sort((a, b) => b.relevance.score - a.relevance.score);

  for (const { post, relevance } of ranked) {
    if (seenIds.has(post.id)) continue;
    const textKey = normalizeText(post.text);
    if (textKey && seenText.has(textKey)) continue;
    seenIds.add(post.id);
    if (textKey) seenText.add(textKey);
    selected.push(xPostToSignal(post, relevance, fetchedAt));
    if (selected.length >= cap) break;
  }
  return selected;
}

export async function runXScan(fetchedAt: string): Promise<{
  signals: IntelligenceSignal[];
  errors: ScanFeedError[];
  feedsAttempted: number;
}> {
  try {
    const settings = getXSettings();
    if (!settings.enabled) {
      return { signals: [], errors: [], feedsAttempted: 0 };
    }
    if (!xTokenConfigured()) {
      return {
        signals: [],
        errors: [
          {
            feed: "X",
            error: "X agent skipped: set X_BEARER_TOKEN (X API v2 recent search) on the server.",
          },
        ],
        feedsAttempted: 0,
      };
    }

    const token = getXBearerToken();
    const queries = defaultXQueries(settings.extraQuery);
    const posts: XPost[] = [];
    const errors: ScanFeedError[] = [];
    const users = new Map<string, TwitterUser>();
    const media = new Map<string, TwitterMedia>();

    for (const feed of queries) {
      try {
        const page = await searchRecent(feed.query, token, settings);
        for (const user of page.users) users.set(user.id, user);
        for (const item of page.media) media.set(item.media_key, item);
        for (const tweet of page.tweets) {
          const post = tweetToPost(tweet, users, media, feed.name);
          if (post) posts.push(post);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        errors.push({ feed: feed.name, error: message });
        if (message.includes("rate limited") || message.includes("authentication")) break;
      }
    }

    return {
      signals: selectXSignals(posts, fetchedAt, settings.relevanceThreshold, settings.maxPosts),
      errors,
      feedsAttempted: queries.length,
    };
  } catch (error) {
    return {
      signals: [],
      errors: [
        {
          feed: "X",
          error: error instanceof Error ? error.message : String(error),
        },
      ],
      feedsAttempted: 0,
    };
  }
}
