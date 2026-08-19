import { describe, expect, it } from "vitest";

import type { ConfigView } from "../api/types";
import { configDi, configPrecedente, differenze, intera } from "./parametri";

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
};

const scambio = (config: ConfigView | null, chiesto: ConfigView | null = null) => ({
  risposta: { config },
  chiesto,
});

describe("cosa e' cambiato", () => {
  it("niente, se la configurazione e' la stessa", () => {
    expect(differenze(CONFIG, { ...CONFIG })).toEqual([]);
  });

  it("solo i campi che non concordano", () => {
    const dopo = { ...CONFIG, rag: false, top_k: 12 };
    expect(differenze(CONFIG, dopo)).toEqual([
      { campo: "top_k", prima: 5, dopo: 12 },
      { campo: "rag", prima: true, dopo: false },
    ]);
  });

  it("senza un prima, tutto e' cambiato", () => {
    // E' il caso della prima risposta di una conversazione riletta dal deposito,
    // dove il confronto lo fa chi chiama contro i predefiniti del servizio.
    expect(differenze(null, CONFIG)).toHaveLength(Object.keys(CONFIG).length);
  });

  it("copre tutto il contratto, non i soli controlli della barra", () => {
    // Un parametro cambiato lato server e' esattamente cio' che questa riga
    // esiste per non far sparire, e prendere le chiavi da `dopo` la rende
    // automatica: un campo aggiunto domani compare da solo.
    expect(differenze(CONFIG, { ...CONFIG, temperature: 0.7 })).toEqual([
      { campo: "temperature", prima: 0, dopo: 0.7 },
    ]);
    expect(intera(CONFIG).map((d) => d.campo)).toEqual(Object.keys(CONFIG));
  });
});

describe("cosa mostrare, e quando", () => {
  it("cosa ha girato batte cosa era stato chiesto", () => {
    // `config` e' la verita' del server, `chiesto` cio' che avevamo mandato.
    // Quando non coincidono, quella che conta e' la prima.
    const girato = { ...CONFIG, top_k: 3 };
    expect(configDi(scambio(girato, CONFIG))).toBe(girato);
  });

  it("finche' `done` non arriva si mostra cio' che era stato chiesto", () => {
    // Senza questo la riga comparirebbe solo a generazione finita, cioe'
    // direbbe cosa e' cambiato **dopo** che la risposta l'ha gia' subito.
    expect(configDi(scambio(null, CONFIG))).toBe(CONFIG);
  });

  it("null solo quando non si sa nessuna delle due", () => {
    // Uno scambio riletto da un deposito scritto prima di U-15. Li' la riga
    // tace, perche' «non si sa» non e' «non e' cambiato niente».
    expect(configDi(scambio(null, null))).toBeNull();
  });
});

describe("l'ultima configurazione conosciuta", () => {
  it("salta le risposte che non ne hanno una", () => {
    // Una generazione fermata a meta' non ha `config`, e non ha cambiato
    // niente: mostrare «tutto cambiato» dopo un «Ferma» direbbe una cosa falsa
    // su un gesto che non ha toccato nessun parametro.
    const cambiata = { ...CONFIG, rag: false };
    const scambi = [scambio(CONFIG), scambio(null), scambio(cambiata)];
    expect(configPrecedente(scambi, 2)).toBe(CONFIG);
    expect(differenze(configPrecedente(scambi, 2), cambiata)).toEqual([
      { campo: "rag", prima: true, dopo: false },
    ]);
  });

  it("null quando prima non ce n'e' nessuna", () => {
    expect(configPrecedente([scambio(null)], 1)).toBeNull();
    expect(configPrecedente([], 0)).toBeNull();
  });
});
