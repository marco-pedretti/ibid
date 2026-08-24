import { describe, expect, it } from "vitest";

import type { ChunkView, CitationView } from "../api/types";
import { inizio } from "../app/conversazione";
import type { Risposta } from "../app/conversazione";
import { annotazioni, componi, raggruppa } from "./composizione";
import type { Annotazione, Contesto, Pezzo } from "./composizione";
import { analizza } from "./markdown";

/**
 * **E' l'incrocio che qui si prova, non le parti.** `markdown.ts`,
 * `matematica.ts` e `verdetti.ts` hanno gia' i loro test e non si ripetono:
 * quello che non ne aveva — e che D-8 ha registrato come debito — e' cosa
 * succede quando i loro intervalli si sovrappongono sullo stesso testo. Ogni
 * caso qui sotto e' una sovrapposizione, e ognuna aveva una risposta scritta in
 * un commento e verificata solo a schermo.
 */

/** Il contesto come lo costruisce `Testo`: l'analisi del markdown piu' cio' che
 *  sta sopra. */
function contesto(testo: string, ann: Annotazione[] = []): Contesto {
  const md = analizza(testo);
  return { testo, annotazioni: ann, stili: md.stili, nascosti: md.nascosti };
}

/** Tutti i pezzi di un testo, blocco per blocco: e' cio' che finisce a schermo. */
function pezzi(testo: string, ann: Annotazione[] = []): Pezzo[] {
  const c = contesto(testo, ann);
  return analizza(testo).blocchi.flatMap((b) =>
    b.tipo === "tabella"
      ? (b.righe ?? []).flat().flatMap((cella) => componi(cella.da, cella.a, c))
      : componi(b.da, b.a, c),
  );
}

/** Solo cio' che si legge, in fila. Serve a dire «i caratteri di sintassi non
 *  sono arrivati» senza elencare i pezzi uno per uno. */
function letto(p: readonly Pezzo[]): string {
  return p.map((x) => (x.tipo === "testo" ? x.testo : "")).join("");
}

/** Un marcatore annotato, come lo produce `verdetti.ts` per l'occorrenza in
 *  posizione `indice`. Il verdetto non conta: qui si prova dove finisce, non
 *  come si colora. */
function marcatore(indice: number, marker: number): Annotazione {
  const scritto = `[${marker}]`;
  return {
    da: indice,
    a: indice + scritto.length,
    marcato: {
      indice,
      lunghezza: scritto.length,
      marker,
      esito: "sostenuta",
      citazione: null,
    },
  };
}

/** Una frase che non cita niente. */
function scoperta(da: number, a: number): Annotazione {
  return { da, a, marcato: null };
}

describe("componi: prosa, enfasi, e cio' che non si deve leggere", () => {
  it("la prosa nuda e' un pezzo solo, e sa da dove viene", () => {
    expect(pezzi("Il valore massimo e' 400ms.")).toEqual([
      { tipo: "testo", testo: "Il valore massimo e' 400ms.", da: 0, veste: null, scoperto: false },
    ]);
  });

  it("il grassetto veste il suo tratto, e gli asterischi non arrivano", () => {
    const p = pezzi("Il valore **massimo** e' 400ms.");
    expect(letto(p)).toBe("Il valore massimo e' 400ms.");
    expect(p.map((x) => (x.tipo === "testo" ? x.veste : "?"))).toEqual([null, "forte", null]);
  });

  it("i cancelletti di un titolo spariscono e il testo resta dov'era", () => {
    // **Dov'era** e' la meta' che conta: se il titolo si spostasse, ogni
    // annotazione a valle finirebbe su un'altra frase. E' la ragione per cui
    // `markdown.ts` restituisce intervalli invece di testo ripulito.
    expect(pezzi("## Risultati")).toEqual([
      { tipo: "testo", testo: "Risultati", da: 3, veste: null, scoperto: false },
    ]);
  });

  it("il trattino di una voce d'elenco non e' testo", () => {
    expect(letto(pezzi("- primo\n- secondo"))).toBe("primosecondo");
  });
});

describe("componi: un marcatore prende il posto del proprio testo", () => {
  it("il `[2]` scritto dal modello diventa un pezzo, e non resta anche scritto", () => {
    const testo = "Il massimo e' 400ms [2].";
    const p = pezzi(testo, [marcatore(20, 2)]);
    expect(p).toEqual([
      { tipo: "testo", testo: "Il massimo e' 400ms ", da: 0, veste: null, scoperto: false },
      { tipo: "marcatore", marcato: expect.objectContaining({ marker: 2 }), da: 20, veste: null },
      { tipo: "testo", testo: ".", da: 23, veste: null, scoperto: false },
    ]);
    expect(letto(p)).not.toContain("[2]");
  });

  it("dentro il grassetto porta la veste del grassetto", () => {
    // Il marcatore e' disegnato da un componente suo, ma vive dentro il tratto
    // in grassetto: se perdesse la veste, un `[2]` in mezzo a un titolo in
    // grassetto si vedrebbe piu' leggero del testo che lo circonda.
    const p = pezzi("**Il massimo e' 400ms [2].**", [marcatore(22, 2)]);
    expect(p.map((x) => x.tipo === "marcatore")).toContain(true);
    expect(p.every((x) => x.tipo !== "formula" && x.veste === "forte")).toBe(true);
  });
});

describe("componi: la matematica ha la precedenza", () => {
  it("un indice fra quadre dentro una formula resta formula", () => {
    // `$x[3]$` in un corpus di paper esiste. Annotare prima di segmentare lo
    // spezzerebbe a meta' e la formula non si comporrebbe piu': un errore di
    // matematica rompe il disegno, un marcatore mancato resta leggibile.
    const p = pezzi("La derivata $x[3]$ e' nulla.", [marcatore(14, 3)]);
    expect(p.filter((x) => x.tipo === "formula")).toEqual([
      { tipo: "formula", tex: "x[3]", da: 12, blocco: false },
    ]);
    expect(p.some((x) => x.tipo === "marcatore")).toBe(false);
  });

  it("i delimitatori della formula non sono testo", () => {
    expect(letto(pezzi("La derivata $x[3]$ e' nulla."))).toBe("La derivata  e' nulla.");
  });
});

describe("componi: gli intervalli si ritagliano, non si scartano", () => {
  it("una frase scoperta a cavallo di una formula resta segnata in tutte e due le meta'", () => {
    // Scartare l'annotazione che non sta dentro un solo segmento la
    // toglierebbe proprio dalla meta' che si legge. Meta' sottolineatura e'
    // leggibile, nessuna no.
    const testo = "Il tasso e' $\\alpha$ ogni anno.";
    const p = pezzi(testo, [scoperta(0, testo.length)]);
    const scoperti = p.filter((x) => x.tipo === "testo" && x.scoperto);
    expect(scoperti.map((x) => (x.tipo === "testo" ? x.testo : ""))).toEqual([
      "Il tasso e' ",
      " ogni anno.",
    ]);
  });

  it("un tratto in grassetto e scoperto porta tutte e due le cose", () => {
    const testo = "Il **massimo** non e' citato.";
    const p = pezzi(testo, [scoperta(0, testo.length)]);
    expect(p.filter((x) => x.tipo === "testo" && x.veste === "forte" && x.scoperto)).toHaveLength(
      1,
    );
    expect(p.every((x) => x.tipo !== "testo" || x.scoperto)).toBe(true);
  });
});

describe("componi: una tabella e' fatta di celle", () => {
  const TABELLA = "| Anno | Ricavo |\n|---|---|\n| 2018 | 400 |";

  it("le righe di trattini non si leggono", () => {
    expect(letto(pezzi(TABELLA))).toBe("AnnoRicavo2018400");
  });

  it("un'annotazione a cavallo di due celle si ritaglia su ciascuna", () => {
    // Stessa scelta della formula, e per la stessa ragione: il verdetto vale
    // per la frase, e la frase qui attraversa una pipe che non si legge.
    const da = TABELLA.indexOf("2018");
    const p = pezzi(TABELLA, [scoperta(da, TABELLA.indexOf("400") + 3)]);
    const scoperti = p.filter((x) => x.tipo === "testo" && x.scoperto);
    expect(scoperti.map((x) => (x.tipo === "testo" ? x.testo : ""))).toEqual(["2018", "400"]);
  });
});

/** Una citazione come la manda l'API: `claim` e' la frase **senza** marcatori. */
function cit(marker: number, claim: string, supported = true): CitationView {
  return {
    marker,
    chunk_id: `d:${marker}`,
    claim,
    supported,
    score: 0.9,
    threshold: 0.5,
    numeric: "not_applicable",
  };
}

function chunk(): ChunkView {
  return {
    marker: 1,
    score: 0.9,
    chunk_id: "d:1",
    dataset_id: "ledger",
    doc_id: "d",
    doc_genre: "table_heavy",
    pipeline: "generic",
    section_path: "",
    page: 1,
    bbox: null,
    content_type: "text",
    text: "…",
    source_uri: "",
  };
}

function verificata(testo: string, senzaCitazione: string[], chunks: ChunkView[]): Risposta {
  return {
    ...inizio(),
    fase: "conclusa",
    testo,
    definitivo: true,
    chunks,
    citazioni: [cit(1, "Beta cita.")],
    senzaCitazione,
    verificate: true,
  };
}

describe("annotazioni: cosa si segna sopra una risposta", () => {
  const TESTO = "Alfa non cita. Beta cita [1].";

  it("marcatori e frasi scoperte arrivano insieme, in ordine di posizione", () => {
    // L'ordine non e' estetica: `componi` scorre le annotazioni una volta sola
    // col cursore che avanza, e una fuori posto verrebbe saltata.
    const a = annotazioni(verificata(TESTO, ["Alfa non cita."], [chunk()]));
    expect(a.map((x) => [x.da, x.marcato === null])).toEqual([
      [0, true],
      [25, false],
    ]);
  });

  it("senza fonti recuperate non c'e' niente da sottolineare", () => {
    // Col RAG spento — e in un'astensione del gate — non c'era nessuna fonte:
    // «questa frase non cita niente» sarebbe vero di ogni riga, e sottolineare
    // tutta la colonna la farebbe anche sembrare analizzata.
    const a = annotazioni(verificata(TESTO, ["Alfa non cita."], []));
    expect(a.every((x) => x.marcato !== null)).toBe(true);
  });

  it("i marcatori restano anche quando le fonti non ci sono", () => {
    const a = annotazioni(verificata(TESTO, ["Alfa non cita."], []));
    expect(a).toHaveLength(1);
    expect(a[0].da).toBe(25);
  });
});

describe("raggruppa: gli elenchi si ricompongono", () => {
  const gruppi = (testo: string) =>
    raggruppa(analizza(testo).blocchi).map((g) => [g.tipo, g.blocchi.length]);

  it("voci consecutive stanno in un elenco solo", () => {
    // N elenchi da una voce sono la stessa cosa a vedersi e una cosa diversa a
    // sentirsi: un lettore di schermo li annuncia uno per uno.
    expect(gruppi("- primo\n- secondo\n- terzo")).toEqual([["elenco", 3]]);
  });

  it("un paragrafo in mezzo spezza l'elenco in due", () => {
    expect(gruppi("- primo\n\nUna frase.\n\n- secondo")).toEqual([
      ["elenco", 1],
      ["solo", 1],
      ["elenco", 1],
    ]);
  });

  it("i blocchi che non sono voci restano ognuno per se'", () => {
    expect(gruppi("## Titolo\n\nUna frase.")).toEqual([
      ["solo", 1],
      ["solo", 1],
    ]);
  });
});
