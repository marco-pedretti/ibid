import { describe, expect, it } from "vitest";

import { DISTANZA, MARGINE } from "./collocazione";
import type { Misura, Rettangolo } from "./collocazione";
import { FUORI, RESPIRO, VERTICI, alone, buco, collocaScheda } from "./riflettore";

/** Una finestra da portatile, quella su cui la demo si guarda. */
const FINESTRA: Misura = { larghezza: 1440, altezza: 900 };

/** La scheda dell'avvio guidato: la misura che ha davvero. */
const SCHEDA: Misura = { larghezza: 360, altezza: 150 };

/** La stessa finestra con lo `zoom` della radice a 1,25: e' quella in cui la
 *  colonna delle risposte non ha piu' spazio ai fianchi per una scheda intera. */
const STRETTA: Misura = { larghezza: 1152, altezza: 720 };

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

describe("il ritaglio del velo", () => {
  /** I vertici del poligono, come coppie di numeri. */
  function vertici(clip: string): [number, number][] {
    const dentro = clip.slice(clip.indexOf("(") + 1, clip.lastIndexOf(")"));
    return dentro
      .split(",")
      .slice(1) // la regola di riempimento, non un punto
      .map((p) => {
        const [x, y] = p.trim().split(/\s+/);
        return [Number.parseFloat(x), Number.parseFloat(y)] as [number, number];
      });
  }

  const CONTORNO: Rettangolo = { x: 200, y: 300, larghezza: 400, altezza: 120 };

  it("e' la finestra intera meno la zona, con la regola che fa il buco", () => {
    const clip = buco(CONTORNO, FINESTRA);
    expect(clip.startsWith("polygon(evenodd,")).toBe(true);

    const p = vertici(clip);
    // Il perimetro esterno: i quattro angoli della finestra.
    expect(p.slice(0, 4)).toEqual([
      [0, 0],
      [FINESTRA.larghezza, 0],
      [FINESTRA.larghezza, FINESTRA.altezza],
      [0, FINESTRA.altezza],
    ]);
    // Il buco: i quattro angoli della zona.
    expect(p.slice(5, 9)).toEqual([
      [200, 300],
      [200, 420],
      [600, 420],
      [600, 300],
    ]);
  });

  it("ha sempre lo stesso numero di vertici, ed e' cio' che rende il movimento continuo", () => {
    // Una transizione su `clip-path` interpola solo fra poligoni con lo stesso
    // numero di punti: se il ritaglio ne cambiasse toccando un bordo, il velo
    // salterebbe proprio quando la zona attraversa lo schermo.
    for (const zona of [
      CONTORNO,
      { x: 0, y: 0, larghezza: 200, altezza: 900 },
      { x: 1168, y: 0, larghezza: 272, altezza: 900 },
      { x: 0, y: 0, larghezza: FINESTRA.larghezza, altezza: FINESTRA.altezza },
      { x: 700, y: 400, larghezza: 0, altezza: 0 },
    ]) {
      expect(vertici(buco(zona, FINESTRA)).length).toBe(VERTICI);
    }
  });

  it("una zona che sporge viene ritagliata invece di portare i vertici fuori", () => {
    const p = vertici(buco({ x: -100, y: -50, larghezza: 4000, altezza: 4000 }, FINESTRA));
    for (const [x, y] of p) {
      expect(x).toBeGreaterThanOrEqual(0);
      expect(y).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThanOrEqual(FINESTRA.larghezza);
      expect(y).toBeLessThanOrEqual(FINESTRA.altezza);
    }
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

  it("la colonna delle risposte: si accosta al bordo invece di entrarci", () => {
    // Alta quanto la finestra e larga quanto la misura di lettura: sopra e sotto
    // non c'e' niente, e ai fianchi c'e' meno di quanto la scheda chiede. Prima
    // finiva `dentro`, cioe' con la spiegazione appoggiata sopra la cosa
    // spiegata — che e' il difetto che questo modulo esiste per non avere.
    const zona = alone({ x: 260, y: 0, larghezza: 560, altezza: 900 }, STRETTA);
    const p = collocaScheda(zona, SCHEDA, STRETTA);

    expect(p.lato).toBe("destra");
    // Accostata al bordo: e' li' che finisce quando non ci sta per intero.
    expect(p.x).toBe(STRETTA.larghezza - SCHEDA.larghezza - MARGINE);
    // E quel che copre della zona e' meno della meta' di se stessa: un bordo,
    // non il mezzo.
    const dentro = zona.x + zona.larghezza - p.x;
    expect(dentro).toBeLessThanOrEqual(SCHEDA.larghezza * FUORI);
  });

  it("una zona grande quanto la finestra non ha nemmeno un bordo: dentro, in alto", () => {
    // Un bersaglio che riempie lo schermo: nessun lato ha spazio, nemmeno per
    // meta' scheda. E' il caso del telefono, dove la zona che finisce `dentro`
    // e' la colonna di lavoro intera — e in fondo a quella c'e' il campo.
    const zona = { x: 0, y: 0, larghezza: FINESTRA.larghezza, altezza: FINESTRA.altezza };
    const p = collocaScheda(zona, SCHEDA, FINESTRA);
    expect(p.lato).toBe("dentro");
    expect(p.y).toBe(zona.y + MARGINE);
    expect(sta(p, SCHEDA, FINESTRA)).toBe(true);
  });

  it("dentro un telefono la scheda non arriva mai sul campo in cui si scrive", () => {
    // 390 px: la colonna di lavoro e' tutto lo schermo, nessun lato ha spazio e
    // la scheda finisce per forza dentro la zona. Che non tocchi la meta' bassa
    // e' cio' che rende ancora vero il criterio di U-20 — «non impedisce di fare
    // la prima domanda» — sull'unico schermo su cui U-21 si misura.
    const telefono: Misura = { larghezza: 390, altezza: 844 };
    const zona = alone({ x: 0, y: 44, larghezza: 390, altezza: 700 }, telefono);
    const p = collocaScheda(zona, SCHEDA, telefono);
    expect(p.lato).toBe("dentro");
    expect(p.y + SCHEDA.altezza).toBeLessThan(telefono.altezza / 2);
    expect(sta(p, SCHEDA, telefono)).toBe(true);
  });

  it("senza bersaglio va in alto, dove non c'e' il campo in cui si scrive", () => {
    // A colonna sola due dei cinque passi parlano di cose che stanno nel
    // cassetto della corsia, e per loro l'alone non si disegna. In basso la
    // scheda coprirebbe il campo, e il criterio di U-20 dice che la prima
    // domanda si deve poter fare con la guida aperta.
    const p = collocaScheda(null, SCHEDA, FINESTRA);
    expect(p.lato).toBe("dentro");
    expect(p.y).toBe(MARGINE);
    expect(p.x).toBe(FINESTRA.larghezza / 2 - SCHEDA.larghezza / 2);
    expect(sta(p, SCHEDA, FINESTRA)).toBe(true);
  });

  it("senza bersaglio, su uno schermo stretto, resta al margine", () => {
    // Uno schermo largo quanto la scheda: la centratura la mette a zero, e i due
    // limiti si incrociano — il massimo (-8) e' minore del minimo (8). Nell'ordine
    // sbagliato la scheda uscirebbe a sinistra, che e' l'errore gia' pagato una
    // volta da `collocazione.ts`.
    const telefono: Misura = { larghezza: 360, altezza: 780 };
    const p = collocaScheda(null, SCHEDA, telefono);
    expect(p.x).toBe(MARGINE);
    expect(p.y).toBe(MARGINE);
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
    // pagato una volta, e che qui tornerebbe identico. Con una scheda piu' larga
    // della finestra il massimo e' minore del minimo, e nell'ordine sbagliato la
    // scheda uscirebbe a sinistra invece di restare dentro.
    const piccola: Misura = { larghezza: 320, altezza: 240 };
    const zona = alone({ x: 100, y: 100, larghezza: 40, altezza: 40 }, piccola);
    const p = collocaScheda(zona, SCHEDA, piccola);
    expect(p.x).toBe(MARGINE);
    expect(p.y).toBeGreaterThanOrEqual(MARGINE);
    expect(p.y + SCHEDA.altezza).toBeLessThanOrEqual(piccola.altezza - MARGINE);
  });
});
