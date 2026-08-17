import { describe, expect, it } from "vitest";

import { colloca, DISTANZA, MARGINE } from "./collocazione";

const FINESTRA = { larghezza: 1280, altezza: 780 };
/** Una bolla di suggerimento vera: 240 px al massimo, due righe. */
const BOLLA = { larghezza: 240, altezza: 44 };

describe("in verticale", () => {
  it("sta sopra il bersaglio quando c'e' posto", () => {
    // Il puntatore arriva da sopra quasi sempre: una bolla sotto finisce dove la
    // mano sta andando.
    const p = colloca({ x: 600, y: 300, larghezza: 40, altezza: 14 }, BOLLA, FINESTRA);
    expect(p.verso).toBe("sopra");
    expect(p.y).toBe(300 - BOLLA.altezza - DISTANZA);
  });

  it("ripiega sotto quando il bersaglio e' in cima", () => {
    const p = colloca({ x: 600, y: 20, larghezza: 40, altezza: 14 }, BOLLA, FINESTRA);
    expect(p.verso).toBe("sotto");
    expect(p.y).toBe(20 + 14 + DISTANZA);
  });

  it("in una finestra troppo bassa sceglie il lato con piu' spazio", () => {
    const bassa = { larghezza: 1280, altezza: 100 };
    // Bersaglio in basso: sopra ci sono 70 px, sotto 16. Nessuno dei due basta a
    // una bolla di 44 + 8, e insistere su «sopra» per preferenza sarebbe giusto
    // per caso; qui e' giusto perche' e' il lato piu' capiente.
    const p = colloca({ x: 600, y: 70, larghezza: 40, altezza: 14 }, BOLLA, bassa);
    expect(p.verso).toBe("sopra");
  });

  it("bersaglio in cima e finestra bassa: va sotto, dove lo spazio c'e'", () => {
    const bassa = { larghezza: 1280, altezza: 100 };
    const p = colloca({ x: 600, y: 4, larghezza: 40, altezza: 14 }, BOLLA, bassa);
    expect(p.verso).toBe("sotto");
  });
});

describe("in orizzontale", () => {
  it("centra sul bersaglio quando ci sta", () => {
    const p = colloca({ x: 600, y: 300, larghezza: 40, altezza: 14 }, BOLLA, FINESTRA);
    expect(p.x).toBe(600 + 20 - 120);
  });

  it("si stringe al bordo destro invece di sporgere", () => {
    // **Il caso che rende necessario questo modulo.** Il pannello fonti e' largo
    // 272 px e sta incollato al bordo: un punteggio a 1.240 px con una bolla di
    // 240 centrata sporgerebbe di 100 px, cioe' il testo non si leggerebbe.
    const p = colloca({ x: 1235, y: 300, larghezza: 34, altezza: 14 }, BOLLA, FINESTRA);
    expect(p.x).toBe(FINESTRA.larghezza - BOLLA.larghezza - MARGINE);
    expect(p.x + BOLLA.larghezza).toBeLessThanOrEqual(FINESTRA.larghezza - MARGINE);
  });

  it("si stringe al bordo sinistro", () => {
    const p = colloca({ x: 12, y: 300, larghezza: 40, altezza: 14 }, BOLLA, FINESTRA);
    expect(p.x).toBe(MARGINE);
  });

  it("una bolla piu' larga della finestra parte dal margine, non da fuori", () => {
    // `Math.max` dopo `Math.min`: nell'ordine opposto il massimo sarebbe minore
    // del margine e si finirebbe a sinistra del bordo.
    const stretta = { larghezza: 200, altezza: 780 };
    const p = colloca({ x: 100, y: 300, larghezza: 40, altezza: 14 }, BOLLA, stretta);
    expect(p.x).toBe(MARGINE);
  });
});
