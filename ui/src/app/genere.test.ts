import { describe, expect, it } from "vitest";

import { nomeGenere, nomeTaglio, taglioPerGenere } from "./genere";

describe("i due vocabolari sono due", () => {
  it("`table_heavy` vuol dire due cose diverse a seconda del campo", () => {
    // Come genere: «questo documento e' fatto di tabelle». Come pipeline: «e'
    // stato spezzato tenendo le tabelle intere». Che il routing mandi il primo
    // sulla seconda e' la decisione, non un'identita' — e su open_ragbench un
    // documento `table_heavy` finisce su `continuous_text`.
    expect(nomeGenere("table_heavy")).toBe("source.genre.tables");
    expect(nomeTaglio("table_heavy")).toBe("source.cut.tables");
    expect(nomeGenere("table_heavy")).not.toBe(nomeTaglio("table_heavy"));
  });

  it("un nome vale in un campo e non nell'altro", () => {
    // `structured_hierarchical` e' solo una pipeline, `academic_pdf` solo un
    // genere: una mappa condivisa li avrebbe accettati tutti e due ovunque.
    expect(nomeGenere("structured_hierarchical")).toBeNull();
    expect(nomeTaglio("academic_pdf")).toBeNull();
  });

  it("quello che non conosciamo non si traduce", () => {
    // La regola dei modelli fuori catalogo di U-16: `null` dice a chi disegna di
    // mostrare il valore com'e', invece di inventargli un nome.
    expect(nomeGenere("qualcosa_di_nuovo")).toBeNull();
    expect(nomeTaglio("qualcosa_di_nuovo")).toBeNull();
    expect(nomeGenere("")).toBeNull();
  });
});

describe("il taglio e' stato scelto in base al genere?", () => {
  it("si', per le tre pipeline vere", () => {
    expect(taglioPerGenere("structured_hierarchical")).toBe(true);
    expect(taglioPerGenere("table_heavy")).toBe(true);
    expect(taglioPerGenere("continuous_text")).toBe(true);
  });

  it("no per `generic`, che pero' e' un valore vero", () => {
    // E' il termine di paragone di R-07: l'unita' che il documento offriva gia'.
    // Fino a U-05 questo campo diceva il nome di una pipeline che non aveva
    // girato, e la targhetta avrebbe mostrato un routing inesistente.
    expect(taglioPerGenere("generic")).toBe(false);
    expect(nomeTaglio("generic")).toBe("source.cut.generic");
  });

  it("no anche per la stringa vuota, e non e' la stessa ragione", () => {
    // Un chunk indicizzato prima che il campo esistesse non porta niente: «non
    // lo so» non e' «e' stata scelta», e nemmeno «e' stato generico».
    expect(taglioPerGenere("")).toBe(false);
    expect(nomeTaglio("")).toBeNull();
  });
});
