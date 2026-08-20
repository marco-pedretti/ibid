import { describe, expect, it } from "vitest";

import { haContenuto, larghezzePixel, quanteRighe, righeMappa } from "./mappa";

/** Le frazioni di una riga, arrotondate: le somme in virgola mobile non tornano
 *  a 1 esatto e non e' quello che si sta verificando. */
const frazioni = (riga: { frazione: number }[]) => riga.map((p) => Number(p.frazione.toFixed(6)));

/** `n` testi da `car` caratteri, pieni di roba da leggere. */
const testi = (...car: number[]) => car.map((n) => "x".repeat(n));

describe("quante righe: la scala viene dal pezzo piu' piccolo", () => {
  it("piu' e' piccolo il minimo rispetto al totale, piu' righe servono", () => {
    // `NYSE_SHW_2017`: il piu' piccolo con del testo e' 127 caratteri su
    // 348.942, e la regola chiede 22 righe. Le ottiene.
    expect(quanteRighe(testi(127, 348942 - 127))).toBe(22);
  });

  it("un documento di pezzi simili non ha bisogno di righe, e prende il minimo", () => {
    // `2401.02564v2`: 15 chunk, il piu' piccolo e' 1/18 del piu' grande. La
    // regola chiederebbe **una** riga: vera, e una striscia sottile in cima a
    // una colonna vuota non si legge come un documento.
    expect(quanteRighe(testi(257, 25862 - 257))).toBe(6);
  });

  it("oltre il tetto ci si ferma, e i pezzi piu' piccoli scendono sotto la misura", () => {
    // `NASDAQ_LOOP_2017` ne chiederebbe 37: diventerebbe una parete da scorrere
    // invece di un colpo d'occhio.
    expect(quanteRighe(testi(100, 457565 - 100))).toBe(24);
  });

  it("nessun pezzo, nessuna riga", () => {
    expect(quanteRighe([])).toBe(0);
  });
});

describe("quale pezzo detta la scala", () => {
  it("una filigrana non la detta", () => {
    // Misurato: l'1,13% dei chunk di `ledger` sta in 60 caratteri, e i piu'
    // frequenti sono `Powered by TCPDF (www.tcpdf.org)` e «pagina lasciata
    // intenzionalmente bianca». Lasciando che sia una di quelle a fissare la
    // misura minima, `NYSE_SHW_2017` passava da 22 righe a 147.
    expect(haContenuto("Powered by TCPDF (www.tcpdf.org)")).toBe(false);
    expect(haContenuto("This page intentionally left blank")).toBe(false);
    expect(haContenuto("![](images/0_0.jpg)")).toBe(false);
  });

  it("un pezzo corto ma vero si', ed e' il caso che la soglia deve lasciar passare", () => {
    // L'indirizzo in fondo al bilancio di Sherwin-Williams: 127 caratteri, ed e'
    // lui che detta la scala di quel documento.
    expect(haContenuto("The Sherwin-Williams Company, 101 W. Prospect Avenue, Cleveland")).toBe(
      true,
    );
  });

  it("un'immagine con una didascalia vera conta per la didascalia", () => {
    expect(
      haContenuto("![](images/3_1.jpg)\n\nFigura 3: la distribuzione delle cellule attive"),
    ).toBe(true);
  });

  it("se **tutti** sono filigrane, la scala la detta comunque qualcuno", () => {
    // Nessun pezzo con del testo: si ripiega su tutti invece di restare senza
    // base e dividere per un minimo che non esiste.
    expect(quanteRighe(["![](a.jpg)", "![](b.jpg)"])).toBe(6);
  });
});

describe("la striscia, mandata a capo", () => {
  it("pezzi uguali riempiono le righe in parti uguali", () => {
    const r = righeMappa([10, 10, 10, 10], 2);
    expect(r).toHaveLength(2);
    expect(frazioni(r[0])).toEqual([0.5, 0.5]);
    expect(frazioni(r[1])).toEqual([0.5, 0.5]);
  });

  it("nessuna riga sborda, e nessun pezzo si perde", () => {
    // Non «somma a uno»: le righe restano corte, ed e' il punto. Cio' che deve
    // valere e' che nessuna sfori e che i pezzi ci siano tutti.
    const lunghezze = [19, 4821, 6302, 1775, 32, 5119];
    const r = righeMappa(lunghezze, 3);
    expect(r.flat().map((p) => p.indice)).toEqual(lunghezze.map((_, i) => i));
    for (const riga of r) {
      expect(riga.reduce((a, p) => a + p.frazione, 0)).toBeLessThanOrEqual(1 + 1e-9);
    }
  });

  it("le proporzioni sono quelle vere, non appianate", () => {
    // Il punto del modulo: su un documento vero il pezzo piu' grande e' 330
    // volte il piu' piccolo, e con tessere uguali quella differenza spariva.
    const r = righeMappa([90, 10], 1);
    expect(frazioni(r[0])).toEqual([0.9, 0.1]);
  });
});

describe("un pezzo che non entra va a capo intero", () => {
  it("non si spezza: la riga resta corta", () => {
    // Un chunk e' l'unita' di cui la mappa parla, e mostrarne meta' di qua e
    // meta' di la' fa contare due volte una cosa sola. Il bordo frastagliato e'
    // dove i pezzi sono finiti, non un buco da riempire.
    const r = righeMappa([30, 70], 2);
    expect(r.map((riga) => riga.map((p) => p.indice))).toEqual([[0], [1]]);
  });

  it("riempie una riga finche' ci sta, poi va a capo", () => {
    const r = righeMappa([40, 40, 40, 40], 2);
    expect(r.map((riga) => riga.map((p) => p.indice))).toEqual([
      [0, 1],
      [2, 3],
    ]);
  });

  it("il pezzo piu' grande occupa esattamente una riga piena", () => {
    // La capacita' di una riga e' **almeno** il pezzo piu' grande: senza,
    // un chunk piu' lungo di `totale / righe` non entrerebbe da nessuna parte.
    // Le righe vengono un po' meno cariche e nessuna proporzione si muove.
    const r = righeMappa([100, 10, 10], 3);
    expect(frazioni(r[0])).toEqual([1]);
    expect(frazioni(r[1])).toEqual([0.1, 0.1]);
  });

  it("un resto da un milionesimo di riga non apre una riga in piu'", () => {
    // `somma / righe` non torna esatta in virgola mobile: senza margine
    // l'ultimo pezzo di una riga piena andava a capo per un nulla, aprendo una
    // riga con dentro un filo largo due pixel.
    const lunghezze = [4821, 6302, 1775, 5119, 19, 3333, 2222, 1111];
    const r = righeMappa(lunghezze, 3);
    expect(r.flat()).toHaveLength(lunghezze.length);
    expect(r.length).toBeLessThanOrEqual(4);
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

describe("le larghezze in pixel interi", () => {
  it("sono intere, ed e' tutto il punto", () => {
    // Con larghezze frazionarie ogni confine cade su un mezzo pixel e il browser
    // lo arrotonda: lo stesso stacco da due pixel veniva fuori ora due ora tre.
    const px = larghezzePixel([0.5, 0.3, 0.2], 302, 2, 3);
    expect(px.every(Number.isInteger)).toBe(true);
  });

  it("stanno in proporzione, tolti gli stacchi", () => {
    // 302 px meno due stacchi da 2 = 298 utili.
    expect(larghezzePixel([0.5, 0.3, 0.2], 302, 2, 3)).toEqual([149, 89, 60]);
  });

  it("una riga corta resta corta", () => {
    // Le frazioni non sommano a uno: un pezzo che non entrava e' gia' andato a
    // capo, e la riga deve restare frastagliata.
    const px = larghezzePixel([0.5, 0.2], 302, 2, 3);
    expect(px.reduce((a, b) => a + b, 0) + 2).toBeLessThan(302);
  });

  it("un pezzo minuscolo prende il minimo invece di sparire", () => {
    const px = larghezzePixel([0.999, 0.001], 302, 2, 3);
    expect(px[1]).toBe(3);
  });

  it("se i minimi sforano la riga, si toglie dai piu' larghi", () => {
    // Venti pezzi minuscoli in una riga da 50 px: il minimo li gonfia oltre la
    // larghezza, e a cedere un pixel devono essere quelli che possono.
    const frazioni = Array.from({ length: 20 }, (_, i) => (i === 0 ? 0.9 : 0.005));
    const px = larghezzePixel(frazioni, 100, 2, 3);
    expect(px.every((v) => v >= 3)).toBe(true);
    expect(Math.min(...px)).toBe(3);
  });

  it("nessun pezzo, nessuna larghezza", () => {
    expect(larghezzePixel([], 300, 2, 3)).toEqual([]);
  });
});
