/**
 * Keep only South African stories that can affect Unilever Home Care
 * categories: laundry detergent, laundry bars, dishwashing, toilet care,
 * fabric conditioner, hard-surface cleaners.
 */

const UNILEVER = /\bunilever\b/i;

const DISTINCT_BRANDS =
  /\b(domestos|handy andy|jik|maq|harpic|sta-?soft|britelite)\b/i;

const CATEGORY_TERMS =
  /\b(home care|homecare|detergents?|laundry detergents?|washing powder|laundry liquids?|laundry bars?|fabric conditioners?|fabric softeners?|dishwashing liquids?|dish liquids?|toilet cleaners?|household cleaners?|surface cleaners?|multipurpose cleaners?)\b/i;

const UNILEVER_HC_TERMS =
  /\b(home care|homecare|detergents?|laundry|washing powder|dishwashing)\b/i;

const SOUTH_AFRICA =
  /\b(south africa|south african|\bsa\b|gauteng|kwazulu-natal|\bkzn\b|western cape|eastern cape|limpopo|mpumalanga|free state|northern cape|north[- ]west|johannesburg|cape town|durban|pretoria|soweto|shoprite|checkers|usave|pick n pay|boxer)\b/i;

const SA_PUBLISHER =
  /\b(news24|iol|the citizen|moneyweb|sunday ?world|business ?tech|timeslive|times live|sowetan|daily maverick|ewn|jacaranda|capetalk|daily investor|the south african|businesstech|fin24|bizcommunity|engineering news|retailer news)\b/i;

const SA_HOST =
  /\.co\.za\b|news24\.com|dailymaverick\.co\.za|businesstech\.co\.za|moneyweb\.co\.za|thesouthafrican\.com/i;

const FOREIGN_MARKET =
  /\b(india|indian|mumbai|delhi|hindustan unilever|\bhul\b|australia|australian|sydney|melbourne|ireland|irish|korea|korean|nigeria|nigerian|kenya|kenyan|ghana|ghanaian|zimbabwe|zambia|namibia|botswana|united kingdom|\buk\b|britain|british|united states|\busa\b|america|american|mexico|mexican|brazil|brazilian|china|chinese|japan|japanese|france|french|germany|german|netherlands|europe|european|indonesia|pakistan|bangladesh)\b/i;

const FALSE_HOME_CARE =
  /\b(home[- ]based care|home care workers?|home care nurs(?:e|ing)|frail care|palliative)\b/i;

const FALSE_OMO =
  /\b(open market|omo auctions?|omo actions?|omo operations?|central bank|cbn|naira|money market|treasury bills?|omo oba|omo ologo)\b/i;

const FALSE_SURF =
  /\b(surfing|surfers?|surf ski|surf shop|surf contest|surf challenge|beach surf)\b/i;

const DENY =
  /\b(gepf|pension fund|sardines?|vida e caff|rugby|cricket|soccer|murder|homicide|celebrity|fintech|market size|industry report|fortune business insights|marketsandmarkets|comrades marathon)\b/i;

const UNILEVER_NOT_HOME_CARE =
  /\b(dove soap|ice cream|magnum|wall'?s|hellmann|knorr|lipton|colman'?s|mustard|beauty volume|personal care)\b/i;

function hasOmoBrand(text: string): boolean {
  if (!/\bomo\b/i.test(text) || FALSE_OMO.test(text)) return false;
  return /\b(unilever|detergent|laundry|washing powder|handwash|2-in-1)\b/i.test(text);
}

function hasSurfBrand(text: string): boolean {
  if (!/\bsurf\b/i.test(text) || FALSE_SURF.test(text)) return false;
  return /\b(detergent|laundry|washing powder|unilever|handwash|2-in-1)\b/i.test(text);
}

function hasSkipBrand(text: string): boolean {
  return /\bskip\b/i.test(text) && /\b(detergent|laundry|unilever|washing)\b/i.test(text);
}

function hasSunlightBrand(text: string): boolean {
  return (
    /\bsunlight\b/i.test(text) &&
    /\b(dish|laundry|bar|liquid|soap|unilever|detergent|washing)\b/i.test(text)
  );
}

function hasComfortBrand(text: string): boolean {
  return (
    /\bcomfort\b/i.test(text) &&
    /\b(fabric|conditioner|softener|unilever|sta-?soft)\b/i.test(text)
  );
}

function hasArielBrand(text: string): boolean {
  return /\bariel\b/i.test(text) && /\b(detergent|laundry|unilever|p&g|procter)\b/i.test(text);
}

function hasFinishBrand(text: string): boolean {
  return /\bfinish\b/i.test(text) && /\b(dish|dishwasher|reckitt)\b/i.test(text);
}

function hasNamedHomeCareBrand(text: string): boolean {
  return (
    DISTINCT_BRANDS.test(text) ||
    hasOmoBrand(text) ||
    hasSurfBrand(text) ||
    hasSkipBrand(text) ||
    hasSunlightBrand(text) ||
    hasComfortBrand(text) ||
    hasArielBrand(text) ||
    hasFinishBrand(text)
  );
}

function hasUnileverHomeCare(text: string): boolean {
  if (!UNILEVER.test(text)) return false;
  if (hasNamedHomeCareBrand(text) || UNILEVER_HC_TERMS.test(text)) return true;
  if (/\bliquids?\b/i.test(text) && /\bafrica/i.test(text)) return true;
  return false;
}

function isSouthAfricanStory(title: string, summary: string, source: string, url: string): boolean {
  const story = `${title} ${summary}`;
  if (FOREIGN_MARKET.test(story)) return false;
  if (SOUTH_AFRICA.test(story)) return true;
  if (SA_PUBLISHER.test(source) || SA_HOST.test(source) || SA_HOST.test(url)) return true;
  return false;
}

function isHomeCareTopic(text: string): boolean {
  if (UNILEVER_NOT_HOME_CARE.test(text) && !CATEGORY_TERMS.test(text) && !hasNamedHomeCareBrand(text)) {
    return false;
  }
  if (hasNamedHomeCareBrand(text) || hasUnileverHomeCare(text)) return true;
  return CATEGORY_TERMS.test(text);
}

export function isHomeCareRelevant(
  title: string,
  summary = "",
  source = "",
  url = "",
): boolean {
  const text = `${title} ${summary}`;
  if (!text.trim() || DENY.test(text) || FALSE_HOME_CARE.test(text)) return false;
  if (!isSouthAfricanStory(title, summary, source, url)) return false;
  return isHomeCareTopic(text);
}

export function signalIsHomeCareRelevant(signal: {
  title: string;
  summary?: string;
  source?: string;
  sourceUrl?: string | null;
}): boolean {
  return isHomeCareRelevant(
    signal.title,
    signal.summary ?? "",
    signal.source ?? "",
    signal.sourceUrl ?? "",
  );
}
