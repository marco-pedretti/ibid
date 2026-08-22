import { describe, expect, it } from "vitest";

import type { ConfigView, DatasetView } from "../api/types";
import { scheda } from "./scheda";

const CONFIG: ConfigView = {
  top_k: 5,
  retrieval_mode: "hybrid",
  rerank: true,
  query_rewrite: false,
  filter_content_type: "",
  search_exact: true,
  hnsw_ef: null,
  model: "gemma4:e4b",
  temperature: 0,
  max_new_tokens: 1024,
  reasoning_effort: "none",
  rag: true,
  baseline_prompt: "strict",
  verify: true,
  entailment_threshold: 0.5,
};

const DATASET: DatasetView = {
  dataset_id: "ledger",
  collection: "ledger",
  ready: true,
  n_chunks: 228331,
};

describe("scheda", () => {
  it("dice chi risponde e su quale corpus, coi valori del servizio", () => {
    expect(scheda(CONFIG, DATASET)).toEqual({
      noti: true,
      modello: "gemma4:e4b",
      corpus: "ledger",
    });
  });

  // A-07: quando non si sa chi risponde, non lo si dice. Una frase col trattino
  // al posto del nome sarebbe la stessa affermazione mancata, scritta piu' piano
  // — e siccome la frase e' una sola, basta che ne manchi una perche' cada.
  it("se ne manca una non ne afferma nessuna", () => {
    expect(scheda(null, DATASET)).toEqual({ noti: false });
    expect(scheda({ ...CONFIG, model: "" }, DATASET)).toEqual({ noti: false });
    expect(scheda(CONFIG, null)).toEqual({ noti: false });
  });
});
