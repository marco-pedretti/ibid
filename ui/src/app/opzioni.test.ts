import { describe, expect, it } from "vitest";

import type { ConfigView } from "../api/types";
import {
  SFORZO,
  avanzateToccate,
  campiRichiesta,
  modelloInstallato,
  opzioniDa,
  ragionamentoDisponibile,
  sforzoAcceso,
  stessaConfigurazione,
} from "./opzioni";

const SFORZI = ["none", "low", "medium", "high", "max"];

/** I default veri di questo deployment, come li restituisce `GET /config`. */
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

describe("i controlli si aprono su cio' che e' in vigore", () => {
  it("ogni voce viene dai predefiniti del servizio, nessuna e' decisa qui", () => {
    // Era una costante scritta a mano, e diceva «non lo so» con una voce «come
    // configurato» in ogni menu. `/config` lo dice, bastava chiederlo.
    expect(opzioniDa(CONFIG)).toEqual({
      rag: true,
      ragionamento: false,
      modello: "gemma4:latest",
      retrieval_mode: "dense",
      rerank: false,
      top_k: 5,
      hnsw_ef: null,
    });
  });

  it("il ragionamento e' acceso se il livello configurato non e' «spento»", () => {
    expect(opzioniDa({ ...CONFIG, reasoning_effort: "medium" }).ragionamento).toBe(true);
  });

  it("appena aperti, nessun controllo risulta mosso", () => {
    expect(avanzateToccate(opzioniDa(CONFIG), CONFIG)).toBe(false);
    expect(avanzateToccate({ ...opzioniDa(CONFIG), top_k: 12 }, CONFIG)).toBe(true);
    // Il modello non sta sotto «Avanzate»: la sua pastiglia si accende da sola.
    expect(avanzateToccate({ ...opzioniDa(CONFIG), modello: "altro" }, CONFIG)).toBe(false);
  });
});

describe("cosa parte nella richiesta", () => {
  it("tutto, esplicito, anche quando coincide col predefinito", () => {
    // Una richiesta che tace lascerebbe decidere al server una cosa che sullo
    // schermo appare gia' decisa — e ora sullo schermo c'e' scritto quale.
    expect(campiRichiesta(opzioniDa(CONFIG), CONFIG)).toEqual({
      rag: true,
      reasoning_effort: "none",
      model: "gemma4:latest",
      retrieval_mode: "dense",
      rerank: false,
      top_k: 5,
      hnsw_ef: null,
    });
  });

  it("acceso vuol dire il capo di C-07, o il livello del servizio se ne ha uno", () => {
    // Il suggerimento porta i numeri di quella misura: mandare un livello
    // diverso li farebbe descrivere un'altra cosa. Ma se il deployment ragiona
    // gia', «acceso» deve tornare al **suo**, altrimenti il predefinito marcato
    // nel menu e il valore che parte non sarebbero lo stesso.
    expect([SFORZO.spento, SFORZO.acceso]).toEqual(["none", "high"]);
    expect(sforzoAcceso(CONFIG)).toBe("high");
    expect(sforzoAcceso({ ...CONFIG, reasoning_effort: "medium" })).toBe("medium");

    const acceso = campiRichiesta({ ...opzioniDa(CONFIG), ragionamento: true }, CONFIG);
    expect(acceso.reasoning_effort).toBe("high");
  });

  it("il predefinito puo' non essere installato, e allora non si manda niente", () => {
    // `/config` dice come il servizio e' configurato, non cosa e' stato
    // scaricato. Senza questo controllo la domanda partirebbe lo stesso, per
    // fallire dopo l'attesa con un errore del modello.
    expect(modelloInstallato("gemma4:latest", ["qwen3.5:latest"])).toBe(false);
    expect(modelloInstallato("gemma4:latest", ["gemma4:latest", "qwen3.5:latest"])).toBe(true);
  });

  it("elenco vuoto vuol dire «non si sa», non «assente»", () => {
    // L'endpoint dei modelli non ha risposto: dichiarare assente cio' che non
    // si e' potuto verificare e' lo stesso errore che `catalog.models()` evita.
    expect(modelloInstallato("gemma4:latest", [])).toBe(true);
  });

  it("senza tutti e due i capi il controllo sparisce invece di mandare un 422", () => {
    expect(ragionamentoDisponibile(SFORZI)).toBe(true);
    expect(ragionamentoDisponibile(["none", "low"])).toBe(false);
    expect(ragionamentoDisponibile([])).toBe(false);
  });
});

describe("il confronto riparte da cio' che ha girato", () => {
  it("copia ogni campo della configurazione, e il test lo conta", () => {
    // E' la rete: un campo aggiunto a `ConfigView` e non aggiunto li' uscirebbe
    // dal confronto **in silenzio**, cioe' diventerebbe la seconda variabile che
    // `stessaConfigurazione` esiste per impedire (§15).
    expect(Object.keys(stessaConfigurazione(CONFIG)).sort()).toEqual(Object.keys(CONFIG).sort());
    expect(stessaConfigurazione(CONFIG)).toEqual(CONFIG);
  });

  it("invertire il RAG cambia una cosa sola", () => {
    const rilancio = { ...stessaConfigurazione(CONFIG), rag: !CONFIG.rag };
    const diversi = Object.keys(CONFIG).filter(
      (k) => rilancio[k as keyof ConfigView] !== CONFIG[k as keyof ConfigView],
    );
    expect(diversi).toEqual(["rag"]);
  });
});
