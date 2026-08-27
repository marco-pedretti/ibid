import { describe, expect, it } from "vitest";

import type { DatasetView } from "../api/types";
import { interrogabili, sceltaIniziale } from "./scelta-dataset";

function ds(dataset_id: string, n_chunks: number, ready = n_chunks > 0): DatasetView {
  return { dataset_id, collection: `${dataset_id}_c`, ready, n_chunks, ridotto: false };
}

const PRONTI = [ds("open_ragbench", 18840), ds("ledger", 47110)];

describe("interrogabili", () => {
  it("tiene solo i dataset con un indice non vuoto", () => {
    const lista = [ds("open_ragbench", 18840), ds("demo", 0), ds("ledger", 47110)];
    expect(interrogabili(lista).map((d) => d.dataset_id)).toEqual(["open_ragbench", "ledger"]);
  });

  it("scarta anche `ready: true` con zero chunk", () => {
    // La collection esiste ma non contiene niente: `ready` da solo direbbe di
    // si', e ogni domanda tornerebbe un'astensione che si legge come un guasto
    // del modello invece che come un indice vuoto.
    expect(interrogabili([ds("vuoto", 0, true)])).toEqual([]);
  });
});

describe("sceltaIniziale", () => {
  it("senza niente di ricordato prende il primo interrogabile", () => {
    expect(sceltaIniziale(PRONTI, null)).toBe("open_ragbench");
  });

  it("rispetta l'ordine del server, non l'alfabeto", () => {
    // `ledger` prima significa che il server lo dichiara prima: il frontend non
    // sa quale sia «il principale», e non deve deciderlo per conto suo.
    expect(sceltaIniziale([...PRONTI].reverse(), null)).toBe("ledger");
  });

  it("ripristina la scelta ricordata", () => {
    expect(sceltaIniziale(PRONTI, "ledger")).toBe("ledger");
  });

  it("butta l'id ricordato se il server non lo elenca piu'", () => {
    expect(sceltaIniziale(PRONTI, "un_dataset_di_marzo")).toBe("open_ragbench");
  });

  it("butta l'id ricordato se quel dataset non e' piu' interrogabile", () => {
    // Reingestione in corso, collection svuotata: la scelta di ieri manderebbe
    // ogni domanda contro un indice vuoto.
    const lista = [ds("open_ragbench", 18840), ds("ledger", 0)];
    expect(sceltaIniziale(lista, "ledger")).toBe("open_ragbench");
  });

  it("e' `null` quando nessun indice e' pronto", () => {
    // La condizione di chi ha appena clonato il repo. Fingere una selezione
    // manderebbe query contro una collection che non esiste.
    expect(sceltaIniziale([ds("open_ragbench", 0), ds("ledger", 0)], "ledger")).toBeNull();
  });

  it("e' `null` anche con la lista vuota", () => {
    expect(sceltaIniziale([], null)).toBeNull();
  });
});
