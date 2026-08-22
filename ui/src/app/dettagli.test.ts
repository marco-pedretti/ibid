import { describe, expect, it } from "vitest";

import type { CollectionView, ConfigView } from "../api/types";
import { CAMPI_MOSTRATI, gruppiDellaRun, indiceDi } from "./dettagli";

const CONFIG: ConfigView = {
  top_k: 5,
  retrieval_mode: "dense",
  rerank: false,
  query_rewrite: false,
  filter_content_type: "",
  search_exact: false,
  hnsw_ef: null,
  model: "gemma4:latest",
  temperature: 0,
  max_new_tokens: 1024,
  reasoning_effort: "none",
  rag: true,
  baseline_prompt: "strict",
  verify: true,
  entailment_threshold: 0.5,
};

const INDICE: CollectionView = {
  name: "ledger",
  points: 47110,
  dense_size: 1024,
  has_sparse: true,
};

describe("i campi mostrati", () => {
  it("ogni campo di ConfigView compare esattamente una volta", () => {
    // **E' la rete di D-5.** Un campo aggiunto al contratto e non aggiunto qui
    // sparirebbe dal foglio in silenzio, e il foglio esiste proprio perche' «la
    // configurazione che ha girato non sia mai un mistero» (§12). Un buco non
    // si vede: si vede un'interfaccia che sembra completa.
    expect([...CAMPI_MOSTRATI].sort()).toEqual(Object.keys(CONFIG).sort());
  });

  it("nessun campo compare due volte", () => {
    expect(new Set(CAMPI_MOSTRATI).size).toBe(CAMPI_MOSTRATI.length);
  });
});

describe("i gruppi", () => {
  it("con l'indice sono tre, e il primo dice dove ha cercato", () => {
    const g = gruppiDellaRun(CONFIG, "ledger", INDICE);
    expect(g.map((x) => x.nome)).toEqual(["indice", "recupero", "generazione"]);
    expect(g[0].righe).toEqual([
      { nome: "collection", valore: "ledger" },
      { nome: "points", valore: 47110 },
      { nome: "dense_size", valore: 1024 },
      { nome: "has_sparse", valore: true },
    ]);
  });

  it("senza indice la sezione non si disegna, invece di disegnarsi vuota", () => {
    // Una collection scritta senza i suoi numeri si legge come un indice vuoto,
    // che e' un'affermazione — e falsa. Tacere no.
    expect(gruppiDellaRun(CONFIG, "ledger", null).map((x) => x.nome)).toEqual([
      "recupero",
      "generazione",
    ]);
    expect(gruppiDellaRun(CONFIG, "", INDICE).map((x) => x.nome)).toEqual([
      "recupero",
      "generazione",
    ]);
  });

  it("i valori arrivano come sono sul filo, non gia' scritti", () => {
    // `hnsw_ef: null` deve restare `null` fin qui: e' chi disegna a sapere che
    // in italiano si dice «predefinito» e in inglese «default», e una stringa
    // decisa qui sarebbe una traduzione nascosta in un modulo che non traduce.
    const recupero = gruppiDellaRun(CONFIG, "", null)[0];
    expect(recupero.righe).toContainEqual({ nome: "hnsw_ef", valore: null });
    expect(recupero.righe).toContainEqual({ nome: "rerank", valore: false });
  });
});

describe("trovare l'indice della risposta", () => {
  it("lo cerca per nome fra quelli pubblicati", () => {
    expect(indiceDi("ledger", [INDICE])).toBe(INDICE);
  });

  it("una risposta che non dice dove ha cercato non ne ha uno", () => {
    // Le risposte salvate prima di D-5: `collection` vale `""`. Ripiegare sul
    // dataset indovinerebbe giusto quasi sempre, ed e' il modo in cui un
    // difetto del genere sopravvive.
    expect(indiceDi("", [INDICE])).toBeNull();
  });

  it("una collection che il backend non pubblica piu' non si inventa", () => {
    expect(indiceDi("ledger_routed", [INDICE])).toBeNull();
  });
});
