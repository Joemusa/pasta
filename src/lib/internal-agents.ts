import type { InternalAgent } from "./types";

export const INTERNAL_AGENTS: InternalAgent[] = [
  {
    id: "shares-growth",
    name: "Shares & Growth Expert",
    expertise: "Value and volume share, growth, switching direction by retailer and province",
  },
  {
    id: "price",
    name: "Price Expert",
    expertise: "Average selling price, price gaps, pack architecture",
  },
  {
    id: "distribution",
    name: "Distribution Expert",
    expertise: "Numeric distribution, listing gaps, store expansion catch-up",
  },
  {
    id: "promotion",
    name: "Promotion Expert",
    expertise: "Promo intensity, feature slots, grant-week timing",
  },
  {
    id: "category",
    name: "Category Expert",
    expertise: "Home Care pool size, tier mix, channel roles",
  },
  {
    id: "opportunity",
    name: "Opportunity Expert",
    expertise: "Ranked commercial actions from the Commercial Brain",
  },
];
