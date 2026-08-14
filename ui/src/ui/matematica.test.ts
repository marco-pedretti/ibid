import { describe, expect, it } from "vitest";

import { segmenta } from "./matematica";

const testo = (v: string) => ({ tipo: "testo", valore: v });
const inline = (tex: string) => ({ tipo: "inline", tex });
const blocco = (tex: string) => ({ tipo: "blocco", tex });

describe("i delimitatori non ambigui", () => {
  it("riconosce `\\(…\\)` come inline", () => {
    expect(segmenta("il valore \\(x^2\\) cresce")).toEqual([
      testo("il valore "),
      inline("x^2"),
      testo(" cresce"),
    ]);
  });

  it("riconosce `\\[…\\]` come blocco", () => {
    expect(segmenta("quindi \\[E = mc^2\\]")).toEqual([testo("quindi "), blocco("E = mc^2")]);
  });

  it("`$$` prima di `$`, altrimenti diventa una formula vuota", () => {
    expect(segmenta("$$a+b$$")).toEqual([blocco("a+b")]);
  });
});

describe("il `$` singolo", () => {
  it("accetta una formula con comandi", () => {
    const s = segmenta("non esclude $\\frac{\\partial x}{\\partial t}$ qui");
    expect(s).toEqual([
      testo("non esclude "),
      inline("\\frac{\\partial x}{\\partial t}"),
      testo(" qui"),
    ]);
  });

  it("accetta una variabile sola", () => {
    // Le 125 coppie su 452 senza nessun segnale LaTeX: `$o$`, `$n$`, `$p(y, o, u)$`.
    // Chiedere un backslash butterebbe via un quarto della matematica vera.
    expect(segmenta("dove $o$ è un oggetto")).toEqual([
      testo("dove "),
      inline("o"),
      testo(" è un oggetto"),
    ]);
  });

  it("non scambia due importi per una formula", () => {
    const s = segmenta("da $1,2 mln a $3,4 mln");
    expect(s).toEqual([testo("da $1,2 mln a $3,4 mln")]);
  });

  it("non apre su uno spazio", () => {
    expect(segmenta("costa $ 5 e $ 7")).toEqual([testo("costa $ 5 e $ 7")]);
  });

  it("non chiude su uno spazio", () => {
    expect(segmenta("fra $5 e $7 dollari")).toEqual([testo("fra $5 e $7 dollari")]);
  });

  it("un `$` orfano resta testo", () => {
    expect(segmenta("il prezzo è $5 e basta")).toEqual([testo("il prezzo è $5 e basta")]);
  });

  it("una formula non attraversa un paragrafo", () => {
    // Senza questo, un `$` orfano si mangerebbe meta' risposta fino al prossimo.
    const s = segmenta("prezzo $5\n\naltro paragrafo $x$ qui");
    expect(s).toEqual([testo("prezzo $5\n\naltro paragrafo "), inline("x"), testo(" qui")]);
  });
});

describe("mentre lo stream arriva", () => {
  it("una formula incompleta resta testo", () => {
    // `$\frac{a}` non ha ancora la chiusura: trattarla come TeX disegnerebbe un
    // errore rosso per mezzo secondo a ogni formula che si sta scrivendo.
    expect(segmenta("il valore $\\frac{a}")).toEqual([testo("il valore $\\frac{a}")]);
  });

  it("un blocco incompleto resta testo", () => {
    expect(segmenta("quindi $$a+b")).toEqual([testo("quindi $$a+b")]);
  });

  it("appena la chiusura arriva, diventa formula", () => {
    expect(segmenta("il valore $\\frac{a}{b}$")).toEqual([
      testo("il valore "),
      inline("\\frac{a}{b}"),
    ]);
  });
});

describe("prosa senza matematica", () => {
  it("resta un segmento solo", () => {
    const t = "The MLMM approach allows for the direct modeling of the squared error [1].";
    expect(segmenta(t)).toEqual([testo(t)]);
  });

  it("il testo vuoto non produce segmenti", () => {
    expect(segmenta("")).toEqual([]);
  });
});
