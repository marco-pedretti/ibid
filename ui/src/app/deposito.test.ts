/**
 * Cosa deve reggere il deposito, e cosa non deve mai fare.
 *
 * Prima di Q-07 questi casi erano provabili in **un** modulo su sei —
 * `cronologia.ts`, l'unico che prendeva il deposito per parametro. Gli altri
 * cinque chiamavano il globale dentro un componente, dove nessun test arriva:
 * il caso «finestra privata» era coperto da cinque `try/catch` scritti a mano e
 * da nessuna verifica.
 *
 * Il caso piu' importante e' l'ultimo: che le chiavi siano **tutte qui** e
 * distinte. Era un invariante affidato a un commento, e il commento lo
 * dichiarava elencando a mano le chiavi degli altri file.
 */
import { describe, expect, it } from "vitest";

import { CHIAVI, ricorda, ricordato } from "./deposito";
import type { Deposito } from "./deposito";

/** Un deposito finto. `capienza` a 0 rifiuta ogni scrittura, come un'origine
 *  piena; `negato` solleva anche in lettura, come una finestra privata. */
function finto({ capienza = Infinity, negato = false } = {}) {
  const dati = new Map<string, string>();
  const d: Deposito = {
    getItem: (k) => {
      if (negato) throw new Error("negato");
      return dati.get(k) ?? null;
    },
    setItem: (k, v) => {
      if (negato) throw new Error("negato");
      if (dati.size >= capienza && !dati.has(k)) throw new Error("pieno");
      dati.set(k, v);
    },
    removeItem: (k) => {
      if (negato) throw new Error("negato");
      dati.delete(k);
    },
  };
  return { d, dati };
}

describe("ricordato / ricorda", () => {
  it("cio' che si ricorda si rilegge", () => {
    const { d } = finto();
    ricorda(CHIAVI.tema, "dark", d);
    expect(ricordato(CHIAVI.tema, d)).toBe("dark");
  });

  it("una chiave mai scritta e' `null`, non una stringa vuota", () => {
    expect(ricordato(CHIAVI.lingua, finto().d)).toBeNull();
  });

  it("`null` toglie la chiave invece di scrivere la parola «null»", () => {
    const { d, dati } = finto();
    ricorda(CHIAVI.tema, "dark", d);
    ricorda(CHIAVI.tema, null, d);
    expect(dati.has(CHIAVI.tema)).toBe(false);
    expect(ricordato(CHIAVI.tema, d)).toBeNull();
  });

  it("senza deposito si legge `null` e si scrive senza sollevare", () => {
    expect(ricordato(CHIAVI.corsia, null)).toBeNull();
    expect(() => ricorda(CHIAVI.corsia, "chiusa", null)).not.toThrow();
  });

  it("un deposito che solleva in lettura vale come vuoto", () => {
    expect(ricordato(CHIAVI.avvio, finto({ negato: true }).d)).toBeNull();
  });

  it("un deposito pieno non fa cadere chi scrive", () => {
    // Il caso vero: `QuotaExceededError`. Chi cambia tema non deve vedere un
    // guasto perche' l'origine e' satura di cronologia.
    const { d, dati } = finto({ capienza: 0 });
    expect(() => ricorda(CHIAVI.tema, "dark", d)).not.toThrow();
    expect(dati.size).toBe(0);
  });

  it("un deposito negato non fa cadere nemmeno chi cancella", () => {
    expect(() => ricorda(CHIAVI.tema, null, finto({ negato: true }).d)).not.toThrow();
  });
});

describe("il registro delle chiavi", () => {
  const chiavi = Object.values(CHIAVI);

  it("hanno tutte il prefisso del progetto", () => {
    // Il deposito e' per **origine**: in sviluppo `localhost:5173` ospita anche
    // altro, e `theme` senza prefisso e' un nome che chiunque puo' aver preso.
    for (const c of chiavi) expect(c.startsWith("ibid.")).toBe(true);
  });

  it("sono distinte", () => {
    // L'invariante che prima stava in due commenti, ognuno dei quali elencava a
    // mano le chiavi degli altri file. Due voci con lo stesso valore vorrebbero
    // dire che una preferenza ne sovrascrive un'altra, e si vedrebbe solo dopo.
    expect(new Set(chiavi).size).toBe(chiavi.length);
  });

  it("`tema` e' quella che legge anche `index.html`", () => {
    // L'unica che esiste in due linguaggi: lo script in testa alla pagina la
    // legge per dipingere il fondo prima che React parta. Cambiarla qui e non
    // li' fa ricomparire il lampo bianco all'avvio in tema scuro, che e' un
    // difetto che nessun test di questa cartella vedrebbe.
    expect(CHIAVI.tema).toBe("ibid.theme");
  });
});
