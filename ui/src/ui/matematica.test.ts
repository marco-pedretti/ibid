import { describe, expect, it } from "vitest";

import { perAnteprima, segmenta } from "./matematica";

// `da` non ha un default: e' la posizione del segmento nel testo di partenza, e
// un default la renderebbe l'unica asserzione che passa anche quando e' sbagliata.
const testo = (v: string, da: number) => ({ tipo: "testo", valore: v, da });
const inline = (tex: string, da: number) => ({ tipo: "inline", tex, da });
const blocco = (tex: string, da: number) => ({ tipo: "blocco", tex, da });

describe("i delimitatori non ambigui", () => {
  it("riconosce `\\(…\\)` come inline", () => {
    expect(segmenta("il valore \\(x^2\\) cresce")).toEqual([
      testo("il valore ", 0),
      inline("x^2", 10),
      testo(" cresce", 17),
    ]);
  });

  it("riconosce `\\[…\\]` come blocco", () => {
    expect(segmenta("quindi \\[E = mc^2\\]")).toEqual([testo("quindi ", 0), blocco("E = mc^2", 7)]);
  });

  it("`$$` prima di `$`, altrimenti diventa una formula vuota", () => {
    expect(segmenta("$$a+b$$")).toEqual([blocco("a+b", 0)]);
  });
});

describe("il `$` singolo", () => {
  it("accetta una formula con comandi", () => {
    const s = segmenta("non esclude $\\frac{\\partial x}{\\partial t}$ qui");
    expect(s).toEqual([
      testo("non esclude ", 0),
      inline("\\frac{\\partial x}{\\partial t}", 12),
      testo(" qui", 43),
    ]);
  });

  it("accetta una variabile sola", () => {
    // Le 125 coppie su 452 senza nessun segnale LaTeX: `$o$`, `$n$`, `$p(y, o, u)$`.
    // Chiedere un backslash butterebbe via un quarto della matematica vera.
    expect(segmenta("dove $o$ è un oggetto")).toEqual([
      testo("dove ", 0),
      inline("o", 5),
      testo(" è un oggetto", 8),
    ]);
  });

  it("non scambia due importi per una formula", () => {
    const s = segmenta("da $1,2 mln a $3,4 mln");
    expect(s).toEqual([testo("da $1,2 mln a $3,4 mln", 0)]);
  });

  it("non apre su uno spazio", () => {
    expect(segmenta("costa $ 5 e $ 7")).toEqual([testo("costa $ 5 e $ 7", 0)]);
  });

  it("non chiude su uno spazio", () => {
    expect(segmenta("fra $5 e $7 dollari")).toEqual([testo("fra $5 e $7 dollari", 0)]);
  });

  it("un `$` orfano resta testo", () => {
    expect(segmenta("il prezzo è $5 e basta")).toEqual([testo("il prezzo è $5 e basta", 0)]);
  });

  it("una formula non attraversa un paragrafo", () => {
    // Senza questo, un `$` orfano si mangerebbe meta' risposta fino al prossimo.
    const s = segmenta("prezzo $5\n\naltro paragrafo $x$ qui");
    expect(s).toEqual([
      testo("prezzo $5\n\naltro paragrafo ", 0),
      inline("x", 27),
      testo(" qui", 30),
    ]);
  });
});

describe("le tabelle HTML di `ledger`", () => {
  it("due importi in celle diverse non sono una formula", () => {
    // Misurato su 600 chunk: 49 spans accettati dalla sola regola stretta, tutti
    // falsi, tutti cosi'. La guardia sui tag li toglie tutti e 49 senza togliere
    // nessuna delle 22.150 formule vere di `open_ragbench`.
    const t = "<tr><td>$2,389,000</td><td>$548,000</td></tr>";
    expect(segmenta(t)).toEqual([testo(t, 0)]);
  });

  it("ma `$a < b$` resta matematica", () => {
    // La guardia riconosce un **tag**, non un `<` qualunque.
    expect(segmenta("se $a < b$ allora")).toEqual([
      testo("se ", 0),
      inline("a < b", 3),
      testo(" allora", 10),
    ]);
  });
});

describe("mentre lo stream arriva", () => {
  it("una formula incompleta resta testo", () => {
    // `$\frac{a}` non ha ancora la chiusura: trattarla come TeX disegnerebbe un
    // errore rosso per mezzo secondo a ogni formula che si sta scrivendo.
    expect(segmenta("il valore $\\frac{a}")).toEqual([testo("il valore $\\frac{a}", 0)]);
  });

  it("un blocco incompleto resta testo", () => {
    expect(segmenta("quindi $$a+b")).toEqual([testo("quindi $$a+b", 0)]);
  });

  it("appena la chiusura arriva, diventa formula", () => {
    expect(segmenta("il valore $\\frac{a}{b}$")).toEqual([
      testo("il valore ", 0),
      inline("\\frac{a}{b}", 10),
    ]);
  });
});

describe("prosa senza matematica", () => {
  it("resta un segmento solo", () => {
    const t = "The MLMM approach allows for the direct modeling of the squared error [1].";
    expect(segmenta(t)).toEqual([testo(t, 0)]);
  });

  it("il testo vuoto non produce segmenti", () => {
    expect(segmenta("")).toEqual([]);
  });
});

describe("perAnteprima", () => {
  it("toglie i cancelletti del titolo", () => {
    // Il 100% dei chunk di `open_ragbench` comincia cosi': e' la pipeline
    // gerarchica a mettere la sezione in testa al testo.
    expect(perAnteprima("#### Abstract\nWe show that...")).toBe("Abstract We show that...");
  });

  it("toglie i tag delle tabelle di `ledger`", () => {
    expect(perAnteprima("<tr><td>Cash</td><td>10,055</td></tr>")).toBe("Cash 10,055");
  });

  it("riduce a una riga sola", () => {
    expect(perAnteprima("prima\n\n  seconda\triga  ")).toBe("prima seconda riga");
  });

  it("non tocca la matematica", () => {
    expect(perAnteprima("il valore $\\frac{a}{b}$ cresce")).toBe("il valore $\\frac{a}{b}$ cresce");
  });
});
