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
};

const DATASET: DatasetView = {
  dataset_id: "ledger",
  collection: "ledger",
  ready: true,
  n_chunks: 228331,
};

const nomi = (config: ConfigView | null, dataset: DatasetView | null) =>
  scheda(config, dataset).map((v) => v.nome);

describe("scheda", () => {
  it("dice chi risponde e su quale corpus, coi valori del servizio", () => {
    expect(scheda(CONFIG, DATASET)).toContainEqual({
      nome: "about.now.model",
      dato: "gemma4:e4b",
    });
    expect(scheda(CONFIG, DATASET)).toContainEqual({
      nome: "about.now.corpus",
      dato: "ledger",
    });
  });

  it("senza risposta dal servizio non inventa niente", () => {
    expect(scheda(null, DATASET)).toEqual([]);
  });

  // A-07: quando non si sa chi risponde, non lo si dice. Una riga col trattino
  // sarebbe la stessa affermazione mancata, scritta piu' piano.
  it("non fa una riga per un campo che il servizio ha lasciato vuoto", () => {
    expect(nomi({ ...CONFIG, model: "" }, DATASET)).not.toContain("about.now.model");
    expect(nomi(CONFIG, null)).not.toContain("about.now.corpus");
    expect(nomi({ ...CONFIG, retrieval_mode: "" }, DATASET)).not.toContain("about.now.mode");
  });

  // Gli interruttori invece ci sono sempre: `false` e' uno stato, non un'assenza,
  // e «ricerca esatta: spento» e' proprio la cosa che questa pagina deve dire.
  it("gli interruttori restano anche da spenti", () => {
    const spenti = { ...CONFIG, rerank: false, search_exact: false, verify: false };
    expect(scheda(spenti, DATASET)).toContainEqual({
      nome: "about.now.exact",
      testo: "bar.advanced.off",
    });
    expect(nomi(spenti, DATASET)).toEqual(nomi(CONFIG, DATASET));
  });
});
