import { describe, expect, it } from "vitest";

import { DISTANZA, MARGINE } from "./collocazione";
import type { Misura, Rettangolo } from "./collocazione";
import { RESPIRO, alone, collocaScheda } from "./riflettore";

/** Una finestra da portatile, quella su cui la demo si guarda. */
const FINESTRA: Misura = { larghezza: 1440, altezza: 900 };

/** La scheda dell'avvio guidato: la misura che ha davvero. */
const SCHEDA: Misura = { larghezza: 360, altezza: 150 };

/** Dentro la finestra per intero, margine compreso. */
function sta(posa: { x: number; y: number }, scheda: Misura, finestra: Misura): boolean {
  return (
    posa.x >= MARGINE &&
    posa.y >= MARGINE &&
    posa.x + scheda.larghezza <= finestra.larghezza - MARGINE &&
    posa.y + scheda.altezza <= finestra.altezza - MARGINE
  );
}

describe("l'alone", () => {
  it("circonda il bersaglio, staccato del respiro", () => {
    const b: Rettangolo = { x: 200, y: 100, larghezza: 300, altezza: 80 };
    expect(alone(b, FINESTRA)).toEqual({
      x: 200 - RESPIRO,
      y: 100 - RESPIRO,
      larghezza: 300 + 2 * RESPIRO,
      altezza: 80 + 2 * RESPIRO,
    });
  });

  it("contro un bordo chiude sul bordo, invece di uscire", () => {
    // La corsia parte da x=0: senza il ritaglio l'alone comincerebbe a -6, cioe'
    // un contorno disegnato dove lo schermo non c'e'.
    const a = alone({ x: 0, y: 0, larghezza: 200, altezza: 900 }, FINESTRA);
    expect(a.x).toBe(0);
    expect(a.y).toBe(0);
    expect(a.altezza).toBe(900);
  });

  it("un bersaglio interamente fuori non produce misure negative", () => {
    // Capita mentre una colonna scorre: meglio un alone vuoto che un rettangolo
    // con larghezza negativa, che il browser disegna a rovescio.
    const a = alone({ x: -400, y: -400, larghezza: 100, altezza: 100 }, FINESTRA);
    expect(a.larghezza).toBeGreaterThanOrEqual(0);
    expect(a.altezza).toBeGreaterThanOrEqual(0);
  });
});

describe("dove va la scheda", () => {
  it("accanto alla corsia va a destra, sopra la colonna che si sta guardando", () => {
    const zona = alone({ x: 0, y: 300, larghezza: 200, altezza: 60 }, FINESTRA);
    const p = collocaScheda(zona, SCHEDA, FINESTRA);
    expect(p.lato).toBe("destra");
    expect(p.x).toBe(zona.x + zona.larghezza + DISTANZA);
    expect(sta(p, SCHEDA, FINESTRA)).toBe(true);
  });

  it("accanto al pannello fonti ripiega a sinistra, perche' a destra non c'e' posto", () => {
    // Il pannello e' largo 272 px e sta incollato al bordo destro: e' lo stesso
    // caso concreto che ha fatto nascere `collocazione.ts`.
    const zona = alone({ x: 1168, y: 0, larghezza: 272, altezza: 900 }, FINESTRA);
    const p = collocaScheda(zona, SCHEDA, FINESTRA);
    expect(p.lato).toBe("sinistra");
    expect(p.x + SCHEDA.larghezza).toBe(zona.x - DISTANZA);
    expect(sta(p, SCHEDA, FINESTRA)).toBe(true);
  });

  it("una zona bassa e larga si spiega sotto", () => {
    const zona = alone({ x: 220, y: 40, larghezza: 900, altezza: 60 }, FINESTRA);
    const p = collocaScheda(zona, SCHEDA, { larghezza: 1200, altezza: 900 });
    expect(p.lato).toBe("sotto");
    expect(p.y).toBe(zona.y + zona.altezza + DISTANZA);
  });

  it("la colonna di mezzo non ha un accanto: la scheda va dentro, in basso", () => {
    // Alta quanto la finestra e larga quanto resta fra corsia e fonti: nessuno
    // dei quattro lati la contiene, e insistere metterebbe la scheda in una
    // striscia di venti pixel.
    const zona = alone({ x: 200, y: 0, larghezza: 968, altezza: 900 }, FINESTRA);
    const p = collocaScheda(zona, SCHEDA, FINESTRA);
    expect(p.lato).toBe("dentro");
    // In basso, non al centro: sopra c'e' cio' che l'alone sta indicando.
    expect(p.y + SCHEDA.altezza).toBe(zona.y + zona.altezza - MARGINE);
    expect(sta(p, SCHEDA, FINESTRA)).toBe(true);
  });

  it("non esce mai dalla finestra, dovunque sia il bersaglio", () => {
    for (const x of [0, 1, 400, 900, 1300, 1439]) {
      for (const y of [0, 1, 300, 700, 899]) {
        for (const l of [10, 200, 900]) {
          for (const a of [10, 200, 880]) {
            const zona = alone({ x, y, larghezza: l, altezza: a }, FINESTRA);
            expect(sta(collocaScheda(zona, SCHEDA, FINESTRA), SCHEDA, FINESTRA)).toBe(true);
          }
        }
      }
    }
  });

  it("in una finestra piu' piccola della scheda resta al margine invece di uscire dall'altro lato", () => {
    // `Math.max` dopo `Math.min`: l'errore che `collocazione.ts` aveva gia'
    // pagato una volta, e che qui tornerebbe identico.
    const piccola: Misura = { larghezza: 320, altezza: 240 };
    const zona = alone({ x: 100, y: 100, larghezza: 40, altezza: 40 }, piccola);
    const p = collocaScheda(zona, SCHEDA, piccola);
    expect(p.x).toBe(MARGINE);
    expect(p.y).toBe(MARGINE);
  });
});
