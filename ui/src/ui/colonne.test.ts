import { describe, expect, it } from "vitest";

import { MINIME, PREDEFINITE, griglia, leggi, ridimensiona } from "./colonne";

/** Una finestra larga: 1400 px per le tre colonne. */
const TOT = 1400;
const l = () => ({ ...PREDEFINITE });

describe("trascinare un manico", () => {
  it("quello di sinistra allarga i documenti", () => {
    expect(ridimensiona(l(), "documenti", 40, TOT).documenti).toBe(250);
    expect(ridimensiona(l(), "documenti", -40, TOT).documenti).toBe(170);
  });

  it("quello di destra va **verso** la colonna, non al contrario", () => {
    // Tirando a sinistra (`delta` negativo) la colonna di destra si allarga:
    // e' il manico che sta al suo bordo sinistro. Col segno sbagliato andrebbe
    // dalla parte opposta al dito, che e' il difetto piu' fastidioso possibile
    // in un ridimensionamento.
    expect(ridimensiona(l(), "dettaglio", -60, TOT).dettaglio).toBe(500);
    expect(ridimensiona(l(), "dettaglio", 60, TOT).dettaglio).toBe(380);
  });

  it("tocca una colonna sola: l'altra non si muove", () => {
    const dopo = ridimensiona(l(), "documenti", 40, TOT);
    expect(dopo.dettaglio).toBe(PREDEFINITE.dettaglio);
  });
});

describe("i limiti, che sono la parte che conta", () => {
  it("nessuna colonna scende sotto il proprio minimo", () => {
    expect(ridimensiona(l(), "documenti", -9999, TOT).documenti).toBe(MINIME.documenti);
    expect(ridimensiona(l(), "dettaglio", 9999, TOT).dettaglio).toBe(MINIME.dettaglio);
  });

  it("nemmeno quella di mezzo, che nessuno sta trascinando", () => {
    // Il difetto vero: tirando il manico di destra verso sinistra si spinge la
    // mappa, non la colonna di destra. Senza questo limite la si farebbe sparire
    // tirando abbastanza — e per riaprirla servirebbe un manico che non si vede
    // piu'.
    const largo = ridimensiona(l(), "dettaglio", -9999, TOT);
    expect(largo.dettaglio).toBe(TOT - PREDEFINITE.documenti - MINIME.mappa);
    const mappa = TOT - largo.documenti - largo.dettaglio;
    expect(mappa).toBe(MINIME.mappa);
  });

  it("lo stesso tirando l'altro manico", () => {
    const largo = ridimensiona(l(), "documenti", 9999, TOT);
    expect(TOT - largo.documenti - largo.dettaglio).toBe(MINIME.mappa);
  });

  it("una finestra troppo stretta per i tre minimi non solleva niente", () => {
    // Non e' un errore, e' una finestra piccola: si va ai minimi e la pagina
    // scorrera'. Meglio tre colonne che sporgono di tre schiacciate a niente.
    const stretta = 300;
    const dopo = ridimensiona(l(), "documenti", 9999, stretta);
    expect(dopo.documenti).toBe(MINIME.documenti);
  });
});

describe("cosa finisce in `grid-template-columns`", () => {
  it("due misure, il resto alla mappa, e i due manici", () => {
    // `minmax(0, 1fr)` e non `1fr`: senza il minimo a zero la traccia implicita
    // e' larga quanto il contenuto, ed e' lo stesso difetto delle righe che ha
    // gia' morso due volte in questo repo.
    expect(griglia({ documenti: 210, dettaglio: 440 })).toBe("210px 5px minmax(0, 1fr) 5px 440px");
  });
});

describe("le misure ricordate", () => {
  it("senza niente nel deposito si parte dai predefiniti", () => {
    expect(leggi(null)).toEqual(PREDEFINITE);
  });

  it("si rileggono quelle salvate", () => {
    expect(leggi('{"documenti":300,"dettaglio":500}')).toEqual({
      documenti: 300,
      dettaglio: 500,
    });
  });

  it("qualunque cosa di storto ricade sui predefiniti", () => {
    // Un numero fuori scala scritto a mano nel deposito non deve poter lasciare
    // una colonna invisibile al ricaricamento successivo.
    expect(leggi("non json")).toEqual(PREDEFINITE);
    expect(leggi("null")).toEqual(PREDEFINITE);
    expect(leggi('{"documenti":-40}')).toEqual(PREDEFINITE);
    expect(leggi('{"documenti":"molto"}')).toEqual(PREDEFINITE);
    expect(leggi('{"dettaglio":10}').dettaglio).toBe(PREDEFINITE.dettaglio);
  });

  it("una sola delle due salvate non butta via l'altra", () => {
    expect(leggi('{"documenti":300}')).toEqual({
      documenti: 300,
      dettaglio: PREDEFINITE.dettaglio,
    });
  });
});
