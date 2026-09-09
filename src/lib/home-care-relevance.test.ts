import assert from "node:assert/strict";
import { test } from "node:test";
import { isHomeCareRelevant } from "./home-care-relevance.ts";

test("Takealot product URLs count as South African", () => {
  assert.equal(
    isHomeCareRelevant(
      "Takealot: OMO 15% off",
      "Live Takealot promotion for laundry detergent.",
      "takealot.com",
      "https://www.takealot.com/omo-auto-washing-powder/PLID1",
    ),
    true,
  );
});

test("Indian Unilever stories are dropped", () => {
  assert.equal(
    isHomeCareRelevant(
      "Hindustan Unilever detergent launch in Mumbai",
      "HUL expands laundry in India",
      "Times of India",
      "https://timesofindia.indiatimes.com/x",
    ),
    false,
  );
});
