import { describe, expect, it } from "vitest";

import { ESEMPI, esempiDi } from "./esempi";

/**
 * **Questi test non verificano il recupero** — quello lo fa
 * `scripts/verify_esempi.py`, che ha bisogno di Qdrant e dell'indice vero e
 * quindi non gira qui. Verificano la **forma** dell'elenco, che e' l'altra meta'
 * del difetto di D-17: una lista d'esempi si puo' rompere in due modi, e uno dei
 * due si vede senza accendere niente.
 */
describe("la forma dell'elenco", () => {
  it("ogni dataset ha tre esempi", () => {
    for (const [dataset, esempi] of Object.entries(ESEMPI)) {
      expect(esempi, dataset).toHaveLength(3);
    }
  });

  it("esattamente uno per dataset e' fuori corpus", () => {
    // Zero renderebbe la demo una pubblicita' — nasconderebbe l'astensione, che
    // e' meta' della dimostrazione. Due toglierebbero un esempio che risponde,
    // e il primo clic di chi prova il progetto conta piu' del secondo.
    for (const [dataset, esempi] of Object.entries(ESEMPI)) {
      const assenti = esempi.filter((e) => e.atteso.esito === "si astiene");
      expect(assenti, dataset).toHaveLength(1);
    }
  });

  it("l'esempio fuori corpus e' l'ultimo", () => {
    // Non e' estetica: `Avvio.tsx` li disegna nell'ordine dell'array, e
    // l'astensione va guardata dopo aver visto due risposte, non prima.
    for (const [dataset, esempi] of Object.entries(ESEMPI)) {
      expect(esempi[esempi.length - 1].atteso.esito, dataset).toBe("si astiene");
    }
  });
});

describe("cosa dichiara ogni esempio", () => {
  it("chi risponde dichiara un chunk del proprio dataset e una posizione dentro top_k", () => {
    for (const [dataset, esempi] of Object.entries(ESEMPI)) {
      for (const e of esempi) {
        if (e.atteso.esito !== "risponde") continue;
        // Il `chunk_id` porta il `dataset_id` come primo campo (§3). Un chunk
        // di un altro corpus qui sarebbe un copia-incolla che lo script
        // scoprirebbe solo col database acceso.
        expect(e.atteso.chunk.startsWith(`${dataset}:`), e.query).toBe(true);
        expect(e.atteso.posizione).toBeGreaterThanOrEqual(1);
        expect(e.atteso.posizione).toBeLessThanOrEqual(5);
      }
    }
  });

  it("chi si astiene dichiara un margine positivo", () => {
    // Un margine zero o negativo vorrebbe dire che il gate **non** si chiude, e
    // che il numero e' stato copiato senza guardarlo.
    for (const esempi of Object.values(ESEMPI)) {
      for (const e of esempi) {
        if (e.atteso.esito !== "si astiene") continue;
        expect(e.atteso.margine, e.query).toBeGreaterThan(0);
      }
    }
  });
});

describe("i testi", () => {
  it("la versione inglese coincide con la query che parte", () => {
    // I due testi stanno uno sopra l'altro nello stato vuoto: se differissero,
    // chi legge in inglese vedrebbe una domanda e ne manderebbe un'altra.
    for (const esempi of Object.values(ESEMPI)) {
      for (const e of esempi) {
        expect(e.testo.en).toBe(e.query);
      }
    }
  });

  it("la versione italiana esiste ed e' diversa", () => {
    for (const esempi of Object.values(ESEMPI)) {
      for (const e of esempi) {
        expect(e.testo.it.length, e.query).toBeGreaterThan(0);
        expect(e.testo.it).not.toBe(e.query);
      }
    }
  });
});

describe("esempiDi", () => {
  it("senza dataset non propone niente", () => {
    expect(esempiDi(null)).toEqual([]);
  });

  it("un dataset che non ne ha non ne inventa", () => {
    expect(esempiDi("ledger_routed")).toEqual([]);
  });

  it("restituisce quelli del dataset chiesto", () => {
    expect(esempiDi("ledger")).toBe(ESEMPI.ledger);
  });
});
