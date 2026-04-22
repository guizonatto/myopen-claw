import test from "node:test";
import assert from "node:assert/strict";

import {
  buildUsageRouterRef,
  parseUsageRouterRef,
} from "../src/model-ref.js";

test("buildUsageRouterRef prefixes provider/model refs", () => {
  assert.equal(
    buildUsageRouterRef("groq/llama-3.1-8b-instant"),
    "usage-router/groq/llama-3.1-8b-instant",
  );
});

test("parseUsageRouterRef extracts provider and model", () => {
  assert.deepEqual(
    parseUsageRouterRef("usage-router/google/gemini-2.5-flash"),
    {
      provider: "google",
      model: "gemini-2.5-flash",
      modelRef: "google/gemini-2.5-flash",
    },
  );
});

