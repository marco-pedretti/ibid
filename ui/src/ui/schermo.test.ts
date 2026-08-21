import { describe, expect, it } from "vitest";

import { APERTA, CHIUSA, FIANCO, griglia } from "./corsia";
import { SOGLIA, TELEFONO, colonne, forma } from "./schermo";

/** Le tracce della griglia, come le legge il browser. */
const tracce = (s: string) => s.split(" ").filter((t) => t !== "");

describe("la forma del telaio", () => {
  it("il telefono del criterio non e' largo abbastanza per le colonne", () => {
    expect(forma(TELEFONO)).toBe("stretta");
  });

  it("la soglia e' inclusa: e' la prima larghezza che le colonne reggono", () => {
    expect(forma(SOGLIA)).toBe("larga");
    expect(forma(SOGLIA - 1)).toBe("stretta");
  });

  it("finche' e' larga, la colonna di lavoro non riceve meno di un telefono", () => {
    // E' la definizione della soglia, e vale la pena provarla come invariante e
    // non come numero: cambiando una delle due colonne laterali il numero
    // cambia da solo, e questo test resta quello che dice cosa si e' voluto.
    for (let l = SOGLIA; l <= 3000; l += 7) {
      expect(l - APERTA - FIANCO).toBeGreaterThanOrEqual(TELEFONO);
    }
  });

  it("la soglia sta sotto il primo scalino dello zoom", () => {
    // `index.css` non scala niente sotto i 1.400 px, quindi in tutta la banda in
    // cui questa decisione si prende px di finestra e px di disegno sono la
    // stessa cosa. La conversione si fa lo stesso (regola di `scala.ts`), ma
    // dimenticarla non puo' cambiare la forma del telaio.
    expect(SOGLIA).toBeLessThan(1400);
  });
});

describe("le tracce della griglia", () => {
  it("larga, sono quelle di sempre: la corsia non e' cambiata", () => {
    for (const chiusa of [false, true]) {
      for (const fianco of [false, true]) {
        expect(colonne("larga", chiusa, fianco)).toBe(griglia(chiusa, fianco));
      }
    }
  });

  it("stretta, la traccia e' una sola e non ha misura", () => {
    // Le colonne laterali non sono nascoste, non ci sono: una traccia a
    // larghezza zero lascerebbe la riga in tre pezzi di cui due vuoti, ed e' lo
    // stesso difetto che `corsia.ts` evita chiudendo la corsia a 48 e non a 0.
    for (const chiusa of [false, true]) {
      for (const fianco of [false, true]) {
        const g = colonne("stretta", chiusa, fianco);
        expect(tracce(g).length).toBe(1);
        expect(g).not.toContain("px");
      }
    }
  });

  it("a un telefono non resta addosso nessuna misura fissa", () => {
    // Il criterio di U-21 e' «senza scorrimento orizzontale», e la somma delle
    // tracce fisse e' il primo modo di romperlo: 200 + 272 sono gia' 472 dentro
    // 390.
    const g = colonne(forma(TELEFONO), false, true);
    expect(g).not.toContain(`${APERTA}px`);
    expect(g).not.toContain(`${CHIUSA}px`);
    expect(g).not.toContain(`${FIANCO}px`);
  });
});
