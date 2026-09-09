import {
  COMPETITOR_HOME_CARE,
  CONSUMER_VOICE_TERMS,
  SA_MARKET_TERMS,
  TREND_TERMS,
  UNILEVER_HOME_CARE,
  brandSearchTerms,
  orClause,
} from "../home-care-catalog";
import type { XAgentSettings } from "./x-config";

const SA = orClause(SA_MARKET_TERMS);
const LANG = "lang:en -is:retweet -is:reply";

function clampQuery(query: string): string {
  const text = query.replace(/\s+/g, " ").trim();
  return text.length <= 512 ? text : text.slice(0, 512);
}

export function defaultXQueries(extraQuery = ""): { name: string; query: string }[] {
  const unilever = orClause(UNILEVER_HOME_CARE.flatMap(brandSearchTerms));
  const competitors = orClause(COMPETITOR_HOME_CARE.flatMap(brandSearchTerms));
  const extra = extraQuery.trim();
  const extraAnd = extra ? ` (${extra})` : "";
  return [
    {
      name: "X · Unilever Home Care SA",
      query: clampQuery(`${unilever} ${SA} (detergent OR laundry OR dish OR bleach OR cleaner OR fabric OR Unilever)${extraAnd} ${LANG}`),
    },
    {
      name: "X · competitor Home Care SA",
      query: clampQuery(`${competitors} ${SA} (laundry OR detergent OR toilet OR dish OR fabric OR Unilever OR OMO)${extraAnd} ${LANG}`),
    },
    {
      name: "X · consumer voice",
      query: clampQuery(
        `${orClause(["OMO", "Sunlight", "Domestos", "Handy Andy", "Comfort"])} ${orClause(CONSUMER_VOICE_TERMS.slice(0, 10))} ${SA}${extraAnd} ${LANG}`,
      ),
    },
    {
      name: "X · Home Care trends",
      query: clampQuery(
        `${orClause(["washing powder", "dishwashing liquid", "laundry liquid", "fabric softener"])} ${orClause(TREND_TERMS.slice(0, 6))} ${SA}${extraAnd} ${LANG}`,
      ),
    },
  ];
}

export function xStartTime(lookbackHours: number, now = new Date()): string {
  const hours = Math.max(1, Math.min(168, lookbackHours));
  const start = new Date(now.getTime() - hours * 60 * 60 * 1000);
  return start.toISOString();
}

export function xSearchParams(query: string, settings: XAgentSettings, now = new Date()): URLSearchParams {
  const max = Math.max(10, Math.min(25, settings.maxPosts));
  return new URLSearchParams({
    query,
    max_results: String(max),
    start_time: xStartTime(settings.lookbackHours, now),
    "tweet.fields": "created_at,public_metrics,entities,lang,possibly_sensitive,conversation_id",
    "user.fields": "username,name,location",
    expansions: "author_id,attachments.media_keys",
    "media.fields": "type",
  });
}
