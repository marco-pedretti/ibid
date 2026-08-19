import { describe, expect, it } from "vitest";

import { analizza, stiliIn, unisci } from "./markdown";

/** Cio' che si legge una volta tolti i caratteri di sintassi. Non esiste nel
 *  programma — la' non si toglie niente — ma qui rende leggibile l'asserzione
 *  che conta: **gli offset non si spostano**. */
function visibile(testo: string): string {
  const { nascosti } = analizza(testo);
  let fuori = "";
  let i = 0;
  for (const n of nascosti) {
    fuori += testo.slice(i, n.da);
    i = n.a;
  }
  return fuori + testo.slice(i);
}

/** Il tratto di testo grezzo che uno stile copre. */
function coperto(testo: string, i: number): string {
  const s = analizza(testo).stili[i];
  return testo.slice(s.da, s.a);
}

describe("gli offset restano quelli del testo grezzo", () => {
  it("uno stile punta al testo dentro i delimitatori, non al testo ripulito", () => {
    // E' la proprieta' su cui poggia tutto: i verdetti per frase arrivano dal
    // backend come posizioni dentro **questo** testo, e un parser che
    // restituisse una stringa pulita le sposterebbe tutte.
    const t = "Il valore è **0,0226** secondo la tabella.";
    expect(coperto(t, 0)).toBe("0,0226");
    expect(t.slice(analizza(t).stili[0].da, analizza(t).stili[0].a)).toBe("0,0226");
  });

  it("i caratteri nascosti sono solo la sintassi", () => {
    expect(visibile("Il valore è **0,0226**.")).toBe("Il valore è 0,0226.");
    expect(visibile("## Risultati")).toBe("Risultati");
    expect(visibile("- primo\n- secondo")).toBe("primo\nsecondo");
  });
});

describe("enfasi", () => {
  it("grassetto, corsivo e codice", () => {
    const { stili } = analizza("**forte** e *lieve* e `codice`");
    expect(stili.map((s) => s.tipo)).toEqual(["forte", "enfasi", "codice"]);
  });

  it("dentro il codice gli asterischi restano asterischi", () => {
    // Il codice si prende per primo: `a*b*c` e' un identificatore, non un corsivo.
    const { stili } = analizza("la variabile `a*b*c` vale 1");
    expect(stili).toHaveLength(1);
    expect(stili[0].tipo).toBe("codice");
  });

  it("snake_case non e' un corsivo", () => {
    // In un corpus di paper e bilanci gli identificatori con underscore ci sono
    // davvero, e trasformarli in corsivo mangerebbe i loro underscore.
    expect(analizza("il campo dataset_id di chunk_view").stili).toEqual([]);
    expect(visibile("il campo dataset_id di chunk_view")).toBe("il campo dataset_id di chunk_view");
  });

  it("un marcatore di citazione sopravvive all'enfasi", () => {
    // §3.2: i marcatori sono la prima affermazione del §0, e il grassetto non
    // deve nasconderli. `**[2]**` lascia `[2]` intatto nel visibile.
    expect(visibile("Il massimo è 400ms **[2]**.")).toBe("Il massimo è 400ms [2].");
  });
});

describe("blocchi", () => {
  it("titolo, con il livello e senza i cancelletti", () => {
    const { blocchi } = analizza("### Metodo");
    expect(blocchi).toHaveLength(1);
    expect(blocchi[0].tipo).toBe("titolo");
    expect(blocchi[0].livello).toBe(3);
  });

  it("elenco puntato e numerato si distinguono", () => {
    const { blocchi } = analizza("- primo\n2. secondo");
    expect(blocchi.map((b) => b.tipo)).toEqual(["voce", "voce"]);
    expect(blocchi.map((b) => b.numerata === true)).toEqual([false, true]);
  });

  it("un paragrafo non si mangia l'elenco che lo segue", () => {
    const { blocchi } = analizza("Ecco i risultati:\n- primo\n- secondo");
    expect(blocchi.map((b) => b.tipo)).toEqual(["paragrafo", "voce", "voce"]);
  });

  it("le righe di un paragrafo restano insieme", () => {
    const { blocchi } = analizza("una riga\nche continua\n\nun altro blocco");
    expect(blocchi).toHaveLength(2);
    expect(blocchi[0].tipo).toBe("paragrafo");
  });
});

describe("tabelle", () => {
  const T = "| voce | 2017 |\n|---|---|\n| ricavi | 400 |\n| costi | 250 |";

  it("intestazione e righe, con le celle come intervalli", () => {
    const b = analizza(T).blocchi;
    expect(b).toHaveLength(1);
    expect(b[0].tipo).toBe("tabella");
    const righe = b[0].righe!;
    expect(righe).toHaveLength(3);
    expect(righe.map((r) => r.length)).toEqual([2, 2, 2]);
    expect(T.slice(righe[0][0].da, righe[0][0].a)).toBe("voce");
    expect(T.slice(righe[2][1].da, righe[2][1].a)).toBe("250");
  });

  it("senza la riga di trattini non e' una tabella", () => {
    // Due frasi che contengono un `|` non devono diventare una griglia.
    const { blocchi } = analizza("a | b\nc | d");
    expect(blocchi.every((b) => b.tipo === "paragrafo")).toBe(true);
  });

  it("una cella vuota in mezzo resta, quelle di bordo no", () => {
    // Un dato mancante e' un'informazione; una pipe di bordo e' punteggiatura.
    const t = "| a |  | c |\n|---|---|---|";
    const righe = analizza(t).blocchi[0].righe!;
    expect(righe[0]).toHaveLength(3);
    expect(t.slice(righe[0][1].da, righe[0][1].a)).toBe("");
  });
});

describe("comporre con chi disegna", () => {
  it("gli intervalli nascosti si uniscono e si ordinano", () => {
    expect(
      unisci([
        { da: 5, a: 7 },
        { da: 0, a: 2 },
        { da: 6, a: 9 },
      ]),
    ).toEqual([
      { da: 0, a: 2 },
      { da: 5, a: 9 },
    ]);
  });

  it("gli stili si ritagliano sul pezzo che li contiene", () => {
    // Serve perche' la matematica ha gia' spezzato il testo in segmenti: uno
    // stile a cavallo di due segmenti deve comparire in tutti e due, tagliato.
    const stili = [{ da: 2, a: 10, tipo: "forte" as const }];
    expect(stiliIn(stili, 0, 6)).toEqual([{ da: 2, a: 6, tipo: "forte" }]);
    expect(stiliIn(stili, 6, 20)).toEqual([{ da: 6, a: 10, tipo: "forte" }]);
    expect(stiliIn(stili, 12, 20)).toEqual([]);
  });
});
