import { describe, expect, it } from "vitest";

import { APERTA, CHIUSA, FIANCO, griglia, leggi } from "./corsia";

/** Le tracce della griglia, come le legge il browser. */
const tracce = (s: string) => s.split(" ");

/** I pixel che le colonne di misura fissa si prendono: il resto va al lavoro. */
const fisse = (s: string) =>
  tracce(s)
    .filter((t) => t.endsWith("px"))
    .reduce((a, t) => a + parseInt(t, 10), 0);

describe("la griglia del telaio", () => {
  it("aperta e' quella di sempre: 200 px di corsia, e 272 di fonti quando ci sono", () => {
    expect(griglia(false, false)).toBe("200px 1fr");
    expect(griglia(false, true)).toBe("200px 1fr 272px");
  });

  it("chiusa, la corsia e' una striscia e non un bordo", () => {
    expect(tracce(griglia(true, false))[0]).toBe(`${CHIUSA}px`);
    // Zero sarebbe «sparita»: il comando per riaprirla non avrebbe piu' dove
    // stare, ed e' il modo in cui una corsia comprimibile si rompe.
    expect(CHIUSA).toBeGreaterThan(0);
  });

  it("chiudendola la colonna di lavoro guadagna **tutto** lo spazio, non una parte", () => {
    // E' il criterio di U-18, ed e' una somma: le tracce restano le stesse, una
    // sola cambia di misura, e il resto e' `1fr`. Con una traccia in piu' — una
    // colonna nascosta lasciata li' a larghezza zero, o un `visibility` — la
    // differenza fra le fisse non farebbe piu' i 152 px.
    for (const fianco of [false, true]) {
      const aperta = griglia(false, fianco);
      const chiusa = griglia(true, fianco);
      expect(tracce(chiusa).length).toBe(tracce(aperta).length);
      expect(fisse(aperta) - fisse(chiusa)).toBe(APERTA - CHIUSA);
    }
  });

  it("la colonna di mezzo e' il resto, in tutte e quattro le combinazioni", () => {
    for (const chiusa of [false, true]) {
      for (const fianco of [false, true]) {
        expect(tracce(griglia(chiusa, fianco))[1]).toBe("1fr");
      }
    }
  });

  it("il pannello fonti e' la terza traccia, e non tocca la corsia", () => {
    expect(tracce(griglia(true, true))).toEqual([`${CHIUSA}px`, "1fr", `${FIANCO}px`]);
  });
});

describe("la scelta ricordata", () => {
  it("chi non ha mai scelto trova la corsia aperta", () => {
    // Chi arriva la prima volta non sa che esistono il dataset, la cronologia e
    // l'esploratore: una striscia di glifi non glielo dice.
    expect(leggi(null)).toBe(false);
  });

  it("solo la parola esatta chiude", () => {
    expect(leggi("chiusa")).toBe(true);
    expect(leggi("aperta")).toBe(false);
  });

  it("qualunque cosa di storto nel deposito riapre invece di rompere", () => {
    for (const g of ["", "true", "1", "{}", "Chiusa", "chiusa "]) {
      expect(leggi(g)).toBe(false);
    }
  });
});
