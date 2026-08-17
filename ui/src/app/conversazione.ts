/**
 * Lo stream del §3.5 ridotto a uno stato disegnabile.
 *
 * Il protocollo manda sei eventi in un ordine che **e'** il contratto, e
 * l'interfaccia deve sapere cosa disegnare dopo ognuno — otto situazioni, non
 * due. Metterle in un reducer puro invece che dentro il componente non e'
 * eleganza: e' l'unico modo di provarle senza DOM, e sono proprio quelle che a
 * mano non si riescono a riprodurre (un token in ritardo, uno stream che cade
 * a meta', una verifica che non arriva mai).
 *
 * **`answer` sostituisce il testo, non lo continua.** Durante lo stream si
 * accumulano i token grezzi; `answer` porta il testo dopo la riparazione dei
 * marcatori, che e' quello che si deve leggere. Da li' in poi un token in
 * ritardo viene **ignorato**: appenderlo scriverebbe in coda a un testo gia'
 * definitivo, ed e' il tipo di guasto che si vede solo con una rete lenta.
 *
 * **Il parziale non si butta mai.** Su errore o su «Ferma» restano fonti e
 * testo ricevuti, marcati per quello che sono: una risposta interrotta e' un
 * dato, cancellarla e' perdere cio' che era gia' arrivato.
 */
import type { ChunkView, CitationView, ConfigView, SseEvent } from "../api/types";
import { ABSTENTION } from "../api/types";

/** Dove siamo, e con quale granularita' il §3.5 lo permette. */
export type Fase =
  /** Richiesta partita, nessun evento: il retrieval sta girando. */
  | "attesa"
  /** `chunks` — le fonti ci sono, il modello non ha ancora scritto niente. */
  | "fonti"
  /** `token` — il testo sta arrivando, i marcatori non sono ancora affidabili. */
  | "scrittura"
  /** `answer` — testo definitivo, verdetti non ancora. */
  | "risposta"
  /** `citations` — i verdetti ci sono. */
  | "citazioni"
  /** `done` — tempi e configurazione, cioe' la run e' raccontabile. */
  | "conclusa"
  | "errore"
  /** «Ferma»: l'ha deciso chi guarda, e non e' un guasto. */
  | "interrotta";

export interface Risposta {
  fase: Fase;
  chunks: ChunkView[];
  testo: string;
  /** Il testo e' quello di `answer` e non l'accumulo dei token. */
  definitivo: boolean;
  /** Il parser ha dovuto sistemare i marcatori (`text !== raw_text`). */
  riparato: boolean;
  troncato: boolean;
  /** `""` | `ABSTENTION.gate` | `ABSTENTION.modello`. */
  astensione: string;
  /** La verifica sta girando: testo si', verdetti non ancora. */
  verificaInCorso: boolean;
  citazioni: CitationView[];
  /** Le frasi verificabili che non citano niente: il costo nascosto della
   *  precisione, e si mostra invece di sparire. */
  senzaCitazione: string[];
  /** La verifica ha girato davvero. Distingue «nessuna citazione» da «verdetti
   *  non disponibili», che senza questo campo sono la stessa lista vuota. */
  verificate: boolean;
  tempi: Record<string, number>;
  config: ConfigView | null;
  errore: { message: string; stage: string } | null;
}

/**
 * Una domanda e la sua risposta.
 *
 * Sta qui e non nel provider perche' e' **un dato**, non uno stato di React: da
 * U-13 in poi va anche serializzato in `localStorage`, e il modulo che lo salva
 * non deve dipendere da un file `.tsx` per conoscerne la forma.
 */
export interface Scambio {
  id: string;
  domanda: string;
  risposta: Risposta;
}

export function inizio(): Risposta {
  return {
    fase: "attesa",
    chunks: [],
    testo: "",
    definitivo: false,
    riparato: false,
    troncato: false,
    astensione: ABSTENTION.nessuna,
    verificaInCorso: false,
    citazioni: [],
    senzaCitazione: [],
    verificate: false,
    tempi: {},
    config: null,
    errore: null,
  };
}

export function applica(r: Risposta, e: SseEvent): Risposta {
  switch (e.event) {
    case "chunks":
      return { ...r, fase: "fonti", chunks: e.data.chunks };

    case "token":
      // Dopo `answer` il testo e' quello riparato: un token in ritardo qui
      // scriverebbe in coda a una risposta gia' chiusa.
      if (r.definitivo) return r;
      return { ...r, fase: "scrittura", testo: r.testo + e.data.text };

    case "answer":
      return {
        ...r,
        fase: "risposta",
        testo: e.data.text,
        definitivo: true,
        riparato: e.data.repaired,
        troncato: e.data.truncated,
        astensione: e.data.abstention,
        verificaInCorso: e.data.verification_pending,
      };

    case "citations":
      return {
        ...r,
        fase: "citazioni",
        citazioni: e.data.citations,
        senzaCitazione: e.data.uncited_claims,
        verificaInCorso: false,
      };

    case "done":
      return {
        ...r,
        fase: "conclusa",
        astensione: e.data.abstention,
        verificate: e.data.verified,
        verificaInCorso: false,
        tempi: e.data.timings,
        config: e.data.config,
      };

    case "error":
      // Il parziale resta. Chi guarda deve poter vedere fin dove si era
      // arrivati, altrimenti «riprova» e' l'unica informazione disponibile.
      return { ...r, fase: "errore", verificaInCorso: false, errore: e.data };
  }
}

/**
 * Lo stream e' caduto senza un evento `error`: rete, processo morto, tab chiuso
 * dall'altra parte. Non e' la stessa cosa di un `error` del server — li' il
 * servizio ha detto **cosa** e' andato storto, qui nessuno l'ha detto — e
 * `stage` lo dichiara invece di lasciarlo indovinare.
 */
export function guasto(r: Risposta, messaggio: string): Risposta {
  return { ...r, fase: "errore", verificaInCorso: false, errore: { message: messaggio, stage: "trasporto" } };
}

/** «Ferma». Una decisione di chi guarda, e va distinta da un guasto. */
export function interrompi(r: Risposta): Risposta {
  if (r.fase === "conclusa" || r.fase === "errore") return r;
  return { ...r, fase: "interrotta", verificaInCorso: false };
}

/**
 * Lo stream sta ancora arrivando: e' cio' che decide se «Ferma» ha senso.
 *
 * Definito per esclusione — tutto cio' che non e' uno dei tre stati terminali —
 * e non elencando le fasi vive: aggiungendo una fase, il pulsante «Ferma»
 * comparirebbe da solo invece di sparire finche' qualcuno non se ne accorge.
 */
export function inCorso(r: Risposta): boolean {
  return r.fase !== "conclusa" && r.fase !== "errore" && r.fase !== "interrotta";
}

/** Chi si e' astenuto, o `null`. Due astensioni diverse, due frasi diverse. */
export function chiSiEAstenuto(r: Risposta): "gate" | "modello" | null {
  if (r.astensione === ABSTENTION.gate) return "gate";
  if (r.astensione === ABSTENTION.modello) return "modello";
  return null;
}
