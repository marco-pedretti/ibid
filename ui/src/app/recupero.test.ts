import { describe, expect, it } from "vitest";

import type { ConfigView } from "../api/types";
import { spiegaPunteggio } from "./recupero";

function config(sopra: Partial<ConfigView>): ConfigView {
  return {
    top_k: 5,
    retrieval_mode: "dense",
    rerank: false,
    query_rewrite: false,
    filter_content_type: "",
    search_exact: false,
    hnsw_ef: null,
    model: "gemma4",
    temperature: 0,
    max_new_tokens: 512,
    reasoning_effort: "",
    rag: true,
    baseline_prompt: "",
    verify: true,
    entailment_threshold: 0.5,
    ...sopra,
  };
}

describe("spiegaPunteggio", () => {
  it("dense: una somiglianza fra 0 e 1", () => {
    expect(spiegaPunteggio(config({ retrieval_mode: "dense" }))).toBe("score.retrieval.dense");
  });

  it("sparse: un punteggio BM25", () => {
    expect(spiegaPunteggio(config({ retrieval_mode: "sparse" }))).toBe("score.retrieval.sparse");
  });

  it("hybrid: un punteggio RRF, che non e' una somiglianza", () => {
    // 0,875 in `dense` e 0,016 in `hybrid` sono due fonti ottime: chiamarli
    // entrambi «punteggio» e' vero e inutile.
    expect(spiegaPunteggio(config({ retrieval_mode: "hybrid" }))).toBe("score.retrieval.hybrid");
  });

  it("il reranker vince sul modo di recupero", () => {
    // Gira per ultimo e **sostituisce** il punteggio: dire «somiglianza densa»
    // descriverebbe uno stadio che c'e' stato ma che quel numero non porta piu'.
    expect(spiegaPunteggio(config({ retrieval_mode: "hybrid", rerank: true }))).toBe(
      "score.retrieval.rerank",
    );
  });

  it("un modo nuovo lato server ricade sul generico invece di rompere", () => {
    // `Capabilities.retrieval_modes` e' `string[]` proprio per questo.
    expect(spiegaPunteggio(config({ retrieval_mode: "colbert" }))).toBe("score.retrieval.unknown");
  });

  it("prima di `done` non si indovina il default del server", () => {
    expect(spiegaPunteggio(null)).toBe("score.retrieval.unknown");
  });
});
