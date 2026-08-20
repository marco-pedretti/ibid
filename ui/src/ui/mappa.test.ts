import { describe, expect, it } from "vitest";

import { quanteRighe, righeMappa } from "./mappa";

/** Le frazioni di una riga, arrotondate: le somme in virgola mobile non tornano
 *  a 1 esatto e non e' quello che si sta verificando. */
const frazioni = (riga: { frazione: number }[]) => riga.map((p) => Number(p.frazione.toFixed(6)));

describe("quante righe", () => {
  it("crescono col numero di pezzi, fra tre e dodici", () => {
    expect(quanteRighe(10)).toBe(3);
    expect(quanteRighe(83)).toBe(5);
    expect(quanteRighe(261)).toBe(12);
    expect(quanteRighe(9999)).toBe(12);
  });

  it("nessun pezzo, nessuna riga", () => {
    expect(quanteRighe(0)).toBe(0);
  });
});

describe("la striscia, mandata a capo", () => {
  it("pezzi uguali riempiono le righe in parti uguali", () => {
    const r = righeMappa([10, 10, 10, 10], 2);
    expect(r).toHaveLength(2);
    expect(frazioni(r[0])).toEqual([0.5, 0.5]);
    expect(frazioni(r[1])).toEqual([0.5, 0.5]);
  });

  it("ogni riga si riempie: le frazioni sommano a uno", () => {
    for (const riga of righeMappa([19, 4821, 6302, 1775, 32, 5119], 3)) {
      const somma = riga.reduce((a, p) => a + p.frazione, 0);
      expect(somma).toBeCloseTo(1, 9);
    }
  });

  it("le proporzioni sono quelle vere, non appianate", () => {
    // Il punto del modulo: su un documento vero il pezzo piu' grande e' 330
    // volte il piu' piccolo, e con tessere uguali quella differenza spariva.
    const r = righeMappa([90, 10], 1);
    expect(frazioni(r[0])).toEqual([0.9, 0.1]);
  });
});

describe("un pezzo che non entra va a capo", () => {
  it("si spezza invece di essere spostato intero", () => {
    // Spostarlo lascerebbe un buco a fine riga, e in una mappa di proporzioni un
    // buco si legge come «qui non c'e' niente».
    const r = righeMappa([30, 70], 2);
    expect(r).toHaveLength(2);
    expect(r[0].map((p) => p.indice)).toEqual([0, 1]);
    expect(r[1].map((p) => p.indice)).toEqual([1]);
    expect(frazioni(r[0])).toEqual([0.6, 0.4]);
    expect(frazioni(r[1])).toEqual([1]);
  });

  it("e dice di essere spezzato, cosi' chi disegna non lo chiude a destra", () => {
    const r = righeMappa([30, 70], 2);
    expect(r[0][1].spezzato).toBe(true);
    expect(r[1][0].spezzato).toBe(false);
    expect(r[0][0].spezzato).toBe(false);
  });

  it("un pezzo piu' lungo di una riga ne attraversa piu' di una", () => {
    const r = righeMappa([300], 3);
    expect(r).toHaveLength(3);
    expect(r.every((riga) => riga.length === 1 && riga[0].indice === 0)).toBe(true);
  });
});

describe("i casi che fanno dividere per zero", () => {
  it("nessun chunk, nessuna riga", () => {
    expect(righeMappa([], 5)).toEqual([]);
    expect(righeMappa([1, 2], 0)).toEqual([]);
  });

  it("tutti i chunk vuoti: pezzi uguali invece di NaN", () => {
    const r = righeMappa([0, 0, 0, 0], 2);
    expect(r.flat().map((p) => p.frazione)).toEqual([0.5, 0.5, 0.5, 0.5]);
  });

  it("un chunk vuoto in mezzo compare lo stesso, largo niente", () => {
    // La mappa dice **quanti** pezzi ci sono: toglierne uno perche' non si vede
    // sarebbe far decidere alla larghezza cosa esiste.
    const indici = righeMappa([50, 0, 50], 1)
      .flat()
      .map((p) => p.indice);
    expect(indici).toEqual([0, 1, 2]);
  });
});
