import { describe, expect, it } from "vitest";

import { allApertura, estremo, indiceDi, scorri } from "./lista";
import type { Voce } from "./lista";

const VOCI: Voce<string>[] = [
  { valore: "a", testo: "A" },
  { valore: "b", testo: "B", disabilitata: true },
  { valore: "c", testo: "C" },
];

describe("scorri", () => {
  it("va alla prossima voce", () => {
    expect(scorri(VOCI, 0, 1)).toBe(2); // salta `b`
  });

  it("salta le disabilitate anche all'indietro", () => {
    expect(scorri(VOCI, 2, -1)).toBe(0);
  });

  it("gira in tondo", () => {
    expect(scorri(VOCI, 2, 1)).toBe(0);
    expect(scorri(VOCI, 0, -1)).toBe(2);
  });

  it("resta dov'è se è l'unica scegliibile", () => {
    const sole = [{ valore: "a", testo: "A" }, { valore: "b", testo: "B", disabilitata: true }];
    expect(scorri(sole, 0, 1)).toBe(0);
  });

  it("è -1 quando nessuna è scegliibile", () => {
    // Il chiamante deve distinguere «non mi sono mosso» da «non c'era dove
    // muoversi»: senza, il ciclo che cerca la prossima non finisce.
    const tutte = VOCI.map((v) => ({ ...v, disabilitata: true }));
    expect(scorri(tutte, 0, 1)).toBe(-1);
  });

  it("è -1 sull'elenco vuoto", () => {
    expect(scorri([], 0, 1)).toBe(-1);
  });
});

describe("estremo", () => {
  it("trova la prima e l'ultima scegliibile", () => {
    expect(estremo(VOCI, 1)).toBe(0);
    expect(estremo(VOCI, -1)).toBe(2);
  });

  it("salta le disabilitate ai bordi", () => {
    const bordi: Voce<string>[] = [
      { valore: "a", testo: "A", disabilitata: true },
      { valore: "b", testo: "B" },
      { valore: "c", testo: "C", disabilitata: true },
    ];
    expect(estremo(bordi, 1)).toBe(1);
    expect(estremo(bordi, -1)).toBe(1);
  });
});

describe("allApertura", () => {
  it("parte dalla voce corrente", () => {
    expect(allApertura(VOCI, "c")).toBe(2);
  });

  it("non parte da una voce disabilitata", () => {
    // Sembrerebbe una selezione, e il primo Invio non farebbe niente senza
    // spiegare perche'.
    expect(allApertura(VOCI, "b")).toBe(0);
  });

  it("ripiega sulla prima scegliibile se il valore non c'è", () => {
    expect(allApertura(VOCI, "zzz")).toBe(0);
  });
});

describe("indiceDi", () => {
  it("trova il valore", () => {
    expect(indiceDi(VOCI, "b")).toBe(1);
  });

  it("è -1 se non c'è", () => {
    expect(indiceDi(VOCI, "zzz")).toBe(-1);
  });
});
