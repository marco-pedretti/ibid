import { describe, expect, it } from "vitest";

import type { ConfigView } from "../api/types";
import {
  PERMISSIVO,
  SEVERO,
  bracci,
  braccioNudo,
  conBraccio,
  promptNudo,
  scelteDiPrompt,
} from "./confronto";
import type { Confronto } from "./confronto";
import { inizio } from "./conversazione";
import type { Risposta } from "./conversazione";

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
  baseline_prompt: SEVERO,
  verify: true,
  entailment_threshold: 0.5,
};

const conclusa = (config: ConfigView, testo: string): Risposta => ({
  ...inizio(),
  fase: "conclusa",
  testo,
  config,
});

/** Il caso normale: si e' chiesto con le fonti, e il braccio nudo e' quello
 *  che il confronto ha lanciato. */
const dallefonti = (): Confronto => ({
  domanda: "q",
  data: conclusa(CONFIG, "con"),
  nuova: conclusa({ ...CONFIG, rag: false }, "senza"),
  nudo: "nuova",
  promptChiesto: SEVERO,
});

/** L'altro verso: si e' chiesto **senza** fonti, quindi la colonna nuda e' la
 *  risposta gia' data e quella lanciata e' l'altra. */
const dalNudo = (): Confronto => ({
  domanda: "q",
  data: conclusa({ ...CONFIG, rag: false }, "senza"),
  nuova: conclusa(CONFIG, "con"),
  nudo: "data",
  promptChiesto: SEVERO,
});

describe("da che parte va ciascuna colonna", () => {
  it("la risposta di partenza sta dalla parte che il suo rag dice", () => {
    expect(braccioNudo(CONFIG)).toBe("nuova");
    expect(braccioNudo({ ...CONFIG, rag: false })).toBe("data");
  });

  it("le due colonne per nome, in tutti e due i versi", () => {
    expect(bracci(dallefonti()).conFonti.testo).toBe("con");
    expect(bracci(dallefonti()).senzaFonti.testo).toBe("senza");
    expect(bracci(dalNudo()).conFonti.testo).toBe("con");
    expect(bracci(dalNudo()).senzaFonti.testo).toBe("senza");
  });

  it("non si scambiano mentre la colonna nuda si rifa'", () => {
    // Il difetto vero, e il motivo per cui `nudo` e' un campo: rilanciando la
    // colonna nuda il suo `config` torna `null` fino a `done`. Ricavando la
    // posizione da li', per ~11 s le due colonne si sarebbero scambiate di
    // posto -- in una schermata il cui unico scopo e' dire quale ha visto le
    // fonti.
    const c = conBraccio(dalNudo(), "data", () => inizio());
    expect(c.data.config).toBeNull();
    expect(bracci(c).senzaFonti).toBe(c.data);
    expect(bracci(c).conFonti.testo).toBe("con");
  });
});

describe("riscrivere un braccio solo", () => {
  it("tocca quello chiesto e lascia l'altro identico", () => {
    const prima = dallefonti();
    const dopo = conBraccio(prima, "nuova", (r) => ({ ...r, testo: "rifatta" }));
    expect(dopo.nuova.testo).toBe("rifatta");
    expect(dopo.data).toBe(prima.data);
  });

  it("il braccio e' quello passato, non quello che lo stato dice adesso", () => {
    // Chi guida uno stream fissa il braccio quando parte. Se `conBraccio` lo
    // rileggesse da `c.nudo` i token finirebbero nella colonna sbagliata nel
    // momento in cui `nudo` cambiasse per qualunque motivo.
    const dopo = conBraccio(dallefonti(), "data", (r) => ({ ...r, testo: "altrove" }));
    expect(dopo.data.testo).toBe("altrove");
    expect(dopo.nuova.testo).toBe("senza");
  });
});

describe("i due capi dell'asse del prompt", () => {
  it("nell'ordine dell'asse, non in quello del server", () => {
    expect(scelteDiPrompt([SEVERO, PERMISSIVO])).toEqual([PERMISSIVO, SEVERO]);
  });

  it("con meno di due non c'e' niente da scegliere", () => {
    // Il controllo sparisce, come sparisce il ragionamento quando il server non
    // offre entrambi i capi: nessun comando che gira a vuoto.
    expect(scelteDiPrompt([SEVERO])).toHaveLength(1);
    expect(scelteDiPrompt([])).toEqual([]);
    expect(scelteDiPrompt(["qualcosaltro"])).toEqual([]);
  });
});

describe("con quale prompt sta rispondendo la colonna nuda", () => {
  it("quello che ha girato, quando si sa", () => {
    const c = dallefonti();
    c.nuova = conclusa({ ...CONFIG, rag: false, baseline_prompt: PERMISSIVO }, "senza");
    expect(promptNudo(c)).toBe(PERMISSIVO);
  });

  it("quello chiesto, finche' non si sa", () => {
    // Senza questo il selettore tornerebbe indietro da solo appena premuto, per
    // saltare al valore giusto ~11 s dopo.
    const c = { ...dallefonti(), nuova: inizio(), promptChiesto: PERMISSIVO };
    expect(promptNudo(c)).toBe(PERMISSIVO);
  });

  it("cio' che ha girato puo' smentire il controllo, ed e' quando deve", () => {
    const c = { ...dallefonti(), promptChiesto: PERMISSIVO };
    expect(promptNudo(c)).toBe(SEVERO);
  });
});
