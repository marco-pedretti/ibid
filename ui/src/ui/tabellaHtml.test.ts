import { describe, expect, it } from "vitest";

import { pezzi, testoSemplice } from "./tabellaHtml";

const TAB = "<table><tr><td>Lease cost</td><td>$ 8,733,000</td></tr></table>";

describe("dividere prosa e tabelle", () => {
  it("prosa prima, tabella, prosa dopo — con gli offset del grezzo", () => {
    const testo = `Prima.\n${TAB}\nDopo.`;
    const p = pezzi(testo);
    expect(p.map((x) => x.tipo)).toEqual(["testo", "tabella", "testo"]);
    // Gli offset sono quelli del testo di partenza, come in `matematica.ts`:
    // chi disegna la prosa la passa ad `analizza`, che lavora in coordinate del
    // grezzo, e senza `da` quel conto andrebbe rifatto sommando lunghezze.
    expect(testo.slice(p[0].da, p[0].a)).toBe("Prima.\n");
    expect(testo.slice(p[1].da, p[1].a)).toBe(TAB);
    expect(testo.slice(p[2].da, p[2].a)).toBe("\nDopo.");
  });

  it("un testo senza tabelle e' un pezzo solo", () => {
    expect(pezzi("solo prosa")).toEqual([{ tipo: "testo", da: 0, a: 10 }]);
  });

  it("un testo vuoto non e' un pezzo vuoto", () => {
    expect(pezzi("")).toEqual([]);
  });

  it("piu' tabelle di fila, senza prosa in mezzo", () => {
    expect(pezzi(TAB + TAB).map((x) => x.tipo)).toEqual(["tabella", "tabella"]);
  });
});

describe("cosa NON si parsa", () => {
  it("una tabella senza chiusura resta testo", () => {
    // Un chunk puo' finire a meta' di una tabella, perche' e' cosi' che e' stato
    // spezzato: chiuderla noi disegnerebbe una griglia che nel documento non
    // finisce li'.
    const testo = "<table><tr><td>a</td></tr>";
    expect(pezzi(testo)).toEqual([{ tipo: "testo", da: 0, a: testo.length }]);
  });

  it("una tabella senza celle riconoscibili resta testo, e non ferma le altre", () => {
    const testo = `<table></table>${TAB}`;
    const p = pezzi(testo);
    expect(p.map((x) => x.tipo)).toEqual(["testo", "tabella"]);
    expect(testo.slice(p[0].da, p[0].a)).toBe("<table></table>");
  });
});

describe("le celle", () => {
  it("il testo, ripulito", () => {
    const p = pezzi(TAB);
    expect(p[0].tipo === "tabella" && p[0].righe).toEqual([
      [
        { testo: "Lease cost", colspan: 1, rowspan: 1, intestazione: false },
        { testo: "$ 8,733,000", colspan: 1, rowspan: 1, intestazione: false },
      ],
    ]);
  });

  it("le celle unite restano unite", () => {
    // Qui sta la differenza voluta con `parse_html_table` in Python, che le
    // **espande** ripetendo il valore: quella serve a cercare, questa a mostrare
    // — e a mostrare ci pensa il browser con `colSpan`/`rowSpan`.
    const t = '<table><tr><td rowspan="2"></td><td colspan="2">Year Ended</td></tr></table>';
    const p = pezzi(t);
    expect(p[0].tipo === "tabella" && p[0].righe[0]).toEqual([
      { testo: "", colspan: 1, rowspan: 2, intestazione: false },
      { testo: "Year Ended", colspan: 2, rowspan: 1, intestazione: false },
    ]);
  });

  it("uno span assurdo si riporta dentro un limite invece di far sparire la cella", () => {
    const p = pezzi('<table><tr><td colspan="9999">x</td></tr></table>');
    expect(p[0].tipo === "tabella" && p[0].righe[0][0].colspan).toBe(64);
  });

  it("`<th>` e' un'intestazione dichiarata, non dedotta dalla posizione", () => {
    // Nel corpus non compare mai — misurato su 2.758 tabelle — ma se comparisse
    // sarebbe un dato del documento, e dedurre l'intestazione dalla prima riga
    // sarebbe indovinarla.
    const p = pezzi("<table><tr><th>Voce</th></tr></table>");
    expect(p[0].tipo === "tabella" && p[0].righe[0][0].intestazione).toBe(true);
  });

  it("i tag dentro una cella si buttano e il testo si tiene", () => {
    const p = pezzi("<table><tr><td>a<br/>b</td></tr></table>");
    expect(p[0].tipo === "tabella" && p[0].righe[0][0].testo).toBe("a b");
  });
});

describe("le entita'", () => {
  it("quelle che l'OCR produce", () => {
    expect(testoSemplice("AT&amp;T &lt;x&gt;")).toBe("AT&T <x>");
  });

  it("le numeriche, decimali ed esadecimali", () => {
    expect(testoSemplice("&#8212;&#x2014;")).toBe("——");
  });

  it("quello che non si riconosce resta scritto", () => {
    // Meglio un `&xyz;` a vista di un carattere inventato: il primo si vede ed
    // e' un difetto noto, il secondo e' un dato falso.
    expect(testoSemplice("&xyz; &#999999999;")).toBe("&xyz; &#999999999;");
  });
});
