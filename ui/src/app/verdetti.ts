/**
 * Quale verdetto tocca a quale marcatore (U-07).
 *
 * Il criterio dice che una citazione **non verificata da C-03 deve essere
 * distinguibile da una verificata senza aprire nulla, e nessuna delle due
 * nascosta**. Ne segue una domanda che sembra banale e non lo e': dato il `[3]`
 * che sta in mezzo alla risposta, di quale verdetto si tratta?
 *
 * Perche' l'unita' che C-03 misura non e' il marcatore, e' la **coppia (frase,
 * chunk citato)**. Lo stesso `[3]` puo' comparire in tre frasi e reggerne due:
 * un verdetto per marcatore aggregherebbe proprio la granularita' che
 * l'affermazione 1 del §0 esiste per misurare. Quindi ogni **occorrenza** nel
 * testo porta il verdetto della frase in cui sta.
 *
 * **Le frasi non si ritagliano qui, si ritrovano.** La tentazione e' riscrivere
 * `split_claims` in TypeScript — dieci righe, una regex — ed e' esattamente cio'
 * che U-00 vieta: la seconda copia di una regola del backend diverge in silenzio,
 * perche' nessun test Python guarda dentro `ui/`. L'API manda gia' le frasi
 * (`citations[].claim`, `uncited_claims`), quindi qui si cerca **dove stanno**,
 * non dove andrebbero tagliate. Se il backend cambia il modo di spezzare, questo
 * modulo continua a dire il vero senza sapere che e' cambiato.
 *
 * Il solo dettaglio che serve conoscere e' che quelle frasi arrivano **senza i
 * marcatori** (`strip_markers`: il modello NLI non ha mai visto degli indici fra
 * quadre, e non fanno parte di cio' che la frase afferma). Percio' la ricerca
 * avviene su una copia del testo a cui i marcatori sono stati tolti, tenendo una
 * mappa verso le posizioni vere.
 */
import type { CitationView } from "../api/types";
import type { Risposta } from "./conversazione";

/** Un tratto di testo, in coordinate del testo di partenza. Fine esclusa. */
export interface Span {
  da: number;
  a: number;
}

/**
 * Cosa si sa di una citazione **in questo momento**. Cinque valori, e nessuno e'
 * l'assenza di un altro: e' la lezione del §3.5 sui tre significati di una lista
 * vuota, applicata al singolo marcatore.
 */
export type Esito =
  /** `answer` non e' arrivato: il marcatore non e' ancora un riferimento (§3.5). */
  | "inerte"
  /** Testo definitivo, la verifica sta girando. */
  | "attesa"
  /** Il chunk citato sostiene la frase. */
  | "sostenuta"
  /** Il chunk citato non la sostiene. **Non e' un errore da nascondere.** */
  | "nonSostiene"
  /** Nessun verdetto per questa coppia: la verifica non ha girato, o la frase
   *  era troppo corta perche' «il chunk la sostiene?» avesse una risposta. */
  | "nonVerificata";

/** Un'occorrenza di marcatore nel testo, e cio' che si sa di lei. */
export interface Marcato {
  /** L'indice della `[` nel testo. E' la chiave: due `[3]` sono due citazioni. */
  indice: number;
  lunghezza: number;
  marker: number;
  esito: Esito;
  citazione: CitationView | null;
}

/** Lo stato della verifica per l'intera risposta. */
export type StatoVerifica = "inerte" | "attesa" | "assente" | "fatta";

/**
 * `citazioni` vuoto non basta a dire cosa e' successo, ed e' lo stesso motivo per
 * cui il §3.5 ha dovuto aggiungere `verification_pending`: la lista vuota copre
 * «verifica non chiesta», «verifica fatta e niente da giudicare» e «verdetti in
 * arrivo». Qui le tre diventano tre valori.
 */
export function statoVerifica(r: Risposta): StatoVerifica {
  if (!r.definitivo) return "inerte";
  if (r.verificaInCorso) return "attesa";
  // `verificate` arriva con `done`, cioe' **dopo** `citations`: fra i due eventi
  // l'unica prova che la verifica ha girato sono i verdetti stessi.
  if (r.citazioni.length > 0 || r.verificate) return "fatta";
  return "assente";
}

const MARCATORE = /\[(\d+)\]/g;
/** Il marcatore col bianco che lo precede: e' cio' che `strip_markers` toglie. */
const MARCATORE_E_BIANCO = /[ \t]*\[\d+\]/g;
/** Marcatori in coda a una frase **senza terminatore**: l'ultima di un testo
 *  troncato. Fuori dal testo nudo per costruzione, quindi fuori dallo span. */
const CODA = /^(?:[ \t]*\[\d+\])+/;

interface Nudo {
  testo: string;
  /** `origine[i]` = dov'era, nel testo vero, il carattere `i` del testo nudo. */
  origine: number[];
}

function senzaMarcatori(testo: string): Nudo {
  const pezzi: string[] = [];
  const origine: number[] = [];
  let da = 0;

  const copia = (fino: number) => {
    for (let j = da; j < fino; j += 1) origine.push(j);
    pezzi.push(testo.slice(da, fino));
  };

  for (const m of testo.matchAll(MARCATORE_E_BIANCO)) {
    copia(m.index);
    da = m.index + m[0].length;
  }
  copia(testo.length);
  return { testo: pezzi.join(""), origine };
}

/**
 * Dove stanno, nel testo, le frasi che l'API ha mandato. `null` per quelle che
 * non si ritrovano — e non si inventa una posizione: un verdetto posato sulla
 * frase sbagliata e' peggio di un verdetto che resta solo nel pannello.
 *
 * Il cursore avanza perche' le frasi arrivano nell'ordine del testo (il backend
 * itera i claim in sequenza) e la stessa frase puo' comparire due volte. Se
 * l'ordine non tiene, si ricerca da capo: un posto giusto fuori ordine vale piu'
 * di nessun posto.
 */
export function localizza(testo: string, frasi: readonly string[]): (Span | null)[] {
  const nudo = senzaMarcatori(testo);
  let cursore = 0;

  return frasi.map((frase) => {
    if (frase === "") return null;
    let pos = nudo.testo.indexOf(frase, cursore);
    if (pos === -1) pos = nudo.testo.indexOf(frase);
    if (pos === -1) return null;
    cursore = pos + frase.length;

    const da = nudo.origine[pos];
    let a = nudo.origine[pos + frase.length - 1] + 1;
    // `Il valore e' 400ms [2]` senza punto finale: nel testo nudo la frase
    // termina su `s`, e il `[2]` resterebbe fuori dalla propria frase.
    const coda = CODA.exec(testo.slice(a));
    if (coda) a += coda[0].length;
    return { da, a };
  });
}

/** Le frasi che non citano niente, dove stanno nel testo. */
export function spanSenzaCitazione(r: Risposta): Span[] {
  if (r.senzaCitazione.length === 0) return [];
  return localizza(r.testo, r.senzaCitazione).filter((s): s is Span => s !== null);
}

/** Le citazioni raggruppate per frase, nell'ordine in cui sono arrivate. */
function perFrase(citazioni: readonly CitationView[]): Map<string, CitationView[]> {
  const gruppi = new Map<string, CitationView[]>();
  for (const c of citazioni) {
    const gia = gruppi.get(c.claim);
    if (gia) gia.push(c);
    else gruppi.set(c.claim, [c]);
  }
  return gruppi;
}

/**
 * Ogni occorrenza di marcatore nel testo, col verdetto che le tocca.
 *
 * **A quale frase appartiene un marcatore.** Dentro `[da, a)` della frase, il
 * caso normale. Fuori, in un buco fra due frasi, appartiene alla **seguente**:
 * il backend spezza sul bianco *dopo* il terminatore, quindi un `[2]` scritto
 * dopo il punto apre la frase successiva invece di chiudere la precedente. Oltre
 * l'ultima frase appartiene all'ultima. Le tre regole sono una sola riga —
 * «la prima frase che finisce dopo di lui» — e non un albero di casi.
 */
export function marcatoriDelTesto(r: Risposta): Marcato[] {
  const stato = statoVerifica(r);
  const occorrenze = [...r.testo.matchAll(MARCATORE)].map((m) => ({
    indice: m.index,
    lunghezza: m[0].length,
    marker: Number(m[1]),
  }));

  if (stato !== "fatta") {
    const esito: Esito =
      stato === "inerte" ? "inerte" : stato === "attesa" ? "attesa" : "nonVerificata";
    return occorrenze.map((o) => ({ ...o, esito, citazione: null }));
  }

  const gruppi = [...perFrase(r.citazioni)];
  const spans = localizza(
    r.testo,
    gruppi.map(([frase]) => frase),
  );

  const ultima = spans.reduce((v, s, i) => (s !== null ? i : v), -1);

  return occorrenze.map((o) => {
    const i = spans.findIndex((s) => s !== null && s.a > o.indice);
    const gruppo = i !== -1 ? gruppi[i][1] : ultima !== -1 ? gruppi[ultima][1] : null;
    const citazione = gruppo?.find((c) => c.marker === o.marker) ?? null;
    return {
      ...o,
      citazione,
      esito:
        citazione === null ? "nonVerificata" : citazione.supported ? "sostenuta" : "nonSostiene",
    };
  });
}

/**
 * Il verdetto di una scheda del pannello fonti.
 *
 * «Non citata» non e' un verdetto e non va colorata come tale: e' un chunk che il
 * recupero ha portato e che la risposta non ha usato. Resta nel pannello — U-02
 * vuole le fonti visibili in ogni stato — ma dire «sostiene» o «non sostiene» di
 * qualcosa che nessuno ha affermato sarebbe inventare un giudizio.
 */
export type EsitoScheda =
  | { tipo: "nonCitata" }
  | { tipo: "attesa" }
  | { tipo: "nonVerificata" }
  | { tipo: "sostiene"; punteggio: number; su: number }
  | { tipo: "nonSostiene"; punteggio: number; su: number }
  | { tipo: "misto"; nonSostengono: number; su: number };

export function esitoDellaScheda(r: Risposta, marker: number): EsitoScheda {
  const stato = statoVerifica(r);
  const marcati = marcatoriDelTesto(r).filter((m) => m.marker === marker);
  if (marcati.length === 0) return { tipo: "nonCitata" };
  if (stato === "inerte" || stato === "attesa") return { tipo: "attesa" };

  const verdetti = marcati.map((m) => m.citazione).filter((c): c is CitationView => c !== null);
  if (verdetti.length === 0) return { tipo: "nonVerificata" };
  return riassumi(verdetti.map((c) => ({ sostenuta: c.supported, punteggio: c.score })));
}

/**
 * Da piu' verdetti sulla stessa fonte a uno, o alla dichiarazione che non
 * concordano.
 *
 * Il punteggio mostrato e' quello della citazione **piu' vicina alla linea**: il
 * minimo fra le sostenute (quella che quasi non ce la faceva), il massimo fra le
 * contrarie (quella che quasi ce la faceva). In entrambi i casi e' il numero che
 * dice qualcosa; una media di verdetti opposti non direbbe niente.
 */
function riassumi(
  coppie: readonly { sostenuta: boolean; punteggio: number }[],
):
  | { tipo: "sostiene" | "nonSostiene"; punteggio: number; su: number }
  | { tipo: "misto"; nonSostengono: number; su: number } {
  const contrarie = coppie.filter((c) => !c.sostenuta);
  if (contrarie.length === 0) {
    return {
      tipo: "sostiene",
      punteggio: Math.min(...coppie.map((c) => c.punteggio)),
      su: coppie.length,
    };
  }
  if (contrarie.length === coppie.length) {
    return {
      tipo: "nonSostiene",
      punteggio: Math.max(...coppie.map((c) => c.punteggio)),
      su: coppie.length,
    };
  }
  return { tipo: "misto", nonSostengono: contrarie.length, su: coppie.length };
}

/** Il verdetto del verificatore numerico di C-09, quando ha giudicato. */
export type EsitoNumerico =
  | { tipo: "sostiene"; su: number }
  | { tipo: "nonSostiene"; su: number }
  | { tipo: "misto"; nonSostengono: number; su: number };

/** I due esiti che il verificatore numerico produce quando sa giudicare. Fuori
 *  da questi c'e' `not_applicable`, che non e' un verdetto: e' «non c'era una
 *  tabella, o non c'erano numeri». */
const GIUDICATO = new Set(["supported", "unsupported"]);

/**
 * Il verdetto **numerico** di una scheda, e perche' non sostituisce l'altro.
 *
 * C-09 esiste per una ragione misurata: su `ledger` **il 96,7% dei claim e'
 * numerico**, e un modello NLI addestrato su prosa non verifica un'asserzione
 * numerica contro una tabella. Visto dal vivo il 17 agosto: alla domanda sul
 * capex di Sherwin-Williams l'NLI dava `non sostiene` a 0,208 mentre il
 * verificatore numerico trovava il 222,8 **dentro la tabella citata**.
 *
 * Mostrare solo il primo darebbe per verdetto cio' che il progetto stesso
 * documenta come debole li'. Mostrare solo il secondo perderebbe le citazioni di
 * prosa. Quindi si mostrano **entrambi**, che e' anche cio' che `schema.py`
 * dichiara del campo: additivo, non sostituisce `supported`.
 *
 * `null` quando il verificatore numerico non ha giudicato niente qui — e non si
 * disegna una pastiglia per dirlo: «non applicabile» e' il caso normale su un
 * corpus di paper, e un'etichetta che compare quasi sempre non informa.
 */
export function esitoNumericoDellaScheda(r: Risposta, marker: number): EsitoNumerico | null {
  if (statoVerifica(r) !== "fatta") return null;
  const giudizi = marcatoriDelTesto(r)
    .filter((m) => m.marker === marker && m.citazione !== null)
    .map((m) => m.citazione as CitationView)
    .filter((c) => GIUDICATO.has(c.numeric));
  if (giudizi.length === 0) return null;

  const riassunto = riassumi(
    giudizi.map((c) => ({ sostenuta: c.numeric === "supported", punteggio: 0 })),
  );
  // Il verificatore numerico non produce un punteggio: e' un confronto fra
  // numeri, non una probabilita'. Portarlo a 0 e mostrarlo direbbe il falso.
  return riassunto.tipo === "misto" ? riassunto : { tipo: riassunto.tipo, su: riassunto.su };
}

/**
 * Cosa c'e' da dire sotto la risposta, in parole.
 *
 * Il §12 chiede che un verdetto si legga da **glifo, colore e parola insieme**.
 * Sul marcatore in mezzo alla prosa ci stanno i primi due; la parola sta qui, e
 * per questo non e' un ornamento: e' il terzo terzo della regola.
 *
 * `null` quando tutto regge — un avviso che compare sempre smette di essere
 * letto, ed e' lo stesso motivo per cui `dev.py` non stampa un errore a ogni
 * uscita.
 */
export interface Riepilogo {
  /** I marcatori che non reggono, in ordine, una volta ciascuno. */
  nonSostengono: number[];
  /** Quante **occorrenze** hanno verdetto NLI negativo. Non e' la lunghezza di
   *  `nonSostengono`: quello e' l'elenco dei marcatori, deduplicato. */
  nonSostenute: number;
  /**
   * Di quelle, quante il verificatore numerico di C-09 **conferma invece**.
   *
   * E' il dato che decide come si intitola il riepilogo: se tutte le non
   * sostenute sono confermate dal numerico, «non tutte le citazioni reggono» e'
   * la frase sbagliata — non e' la citazione a non reggere, sono i due
   * verificatori a non concordare, e su una tabella quello giusto e' il secondo.
   */
  discordanti: number;
  /** Quante frasi non citano niente: il denominatore nascosto della precisione. */
  senzaCitazione: number;
  /** Quante occorrenze sono rimaste senza verdetto. */
  nonVerificate: number;
}

export function riepilogo(r: Risposta): Riepilogo | null {
  if (statoVerifica(r) !== "fatta") return null;

  const marcati = marcatoriDelTesto(r);
  const contrarie = marcati.filter((m) => m.esito === "nonSostiene");
  const nonSostengono = [...new Set(contrarie.map((m) => m.marker))];
  const discordanti = contrarie.filter((m) => m.citazione?.numeric === "supported").length;
  const nonVerificate = marcati.filter((m) => m.esito === "nonVerificata").length;
  const senzaCitazione = r.senzaCitazione.length;

  if (contrarie.length === 0 && nonVerificate === 0 && senzaCitazione === 0) return null;
  return {
    nonSostengono,
    nonSostenute: contrarie.length,
    discordanti,
    senzaCitazione,
    nonVerificate,
  };
}
