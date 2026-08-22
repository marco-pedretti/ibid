/**
 * Cosa c'e' dentro «Dettagli della run» (D-5), e in che ordine.
 *
 * **Sta qui e non nel componente perche' e' una decisione, non un disegno.**
 * Quali campi si mostrano, come si raggruppano e cosa vuol dire un valore
 * assente sono cose che si possono sbagliare senza che nessuno se ne accorga
 * guardando lo schermo: un campo dimenticato non lascia un buco, lascia
 * un'interfaccia che sembra completa. Qui invece un test li conta.
 *
 * **I gruppi non sono estetica.** Sono le tre domande che uno si fa guardando
 * una risposta e non fidandosi: *dove ha cercato*, *come ha cercato*, *chi ha
 * scritto*. La verifica sta col resto della generazione perche' e' l'ultimo
 * passo di quel percorso, non un quarto argomento.
 *
 * **L'elenco e' esplicito e non `Object.keys(config)`.** Un ciclo sulle chiavi
 * darebbe righe nuove da solo appena il contratto cresce — con l'etichetta
 * mancante e il valore grezzo — cioe' inventerebbe interfaccia. La rete e' il
 * test `ogni campo di ConfigView compare esattamente una volta`: aggiungere un
 * campo al contratto rompe il test invece di riempire in silenzio una tabella.
 */
import type { CollectionView, ConfigView } from "../api/types";

/** Un valore com'e' sul filo. Chi disegna decide come si scrive. */
export type Valore = string | number | boolean | null;

export interface Riga {
  /** La chiave della stringa che lo nomina: `run.campo.<nome>`. */
  nome: string;
  valore: Valore;
}

export interface Gruppo {
  /** La chiave della stringa che intitola: `run.gruppo.<nome>`. */
  nome: "indice" | "recupero" | "generazione";
  righe: Riga[];
}

/** I campi di `ConfigView` che riguardano il recupero, nell'ordine in cui si
 *  leggono: prima cosa fa, poi quanto, poi le manopole fini. */
const RECUPERO = [
  "retrieval_mode",
  "top_k",
  "rerank",
  "query_rewrite",
  "filter_content_type",
  "search_exact",
  "hnsw_ef",
] as const satisfies readonly (keyof ConfigView)[];

/** Quelli della generazione, verifica compresa: e' l'ultimo passo di quel
 *  percorso e non un terzo argomento. */
const GENERAZIONE = [
  "model",
  "rag",
  "baseline_prompt",
  "reasoning_effort",
  "temperature",
  "max_new_tokens",
  "verify",
  "entailment_threshold",
] as const satisfies readonly (keyof ConfigView)[];

/**
 * Le righe del foglio, o `null` dove il dato non c'e'.
 *
 * **`indice` e' facoltativo e il resto no**, e la differenza e' reale: la
 * configurazione viaggia con la risposta, la forma dell'indice viene da
 * `/datasets` e puo' mancare per due motivi diversi — la risposta e' vecchia e
 * non dice su quale collection ha cercato (D-5 e' arrivato dopo), oppure il
 * backend non pubblica piu' quella collection. In tutti e due i casi
 * l'onesta' e' non disegnare la sezione: una collection scritta senza i suoi
 * numeri sembrerebbe un indice vuoto invece di un dato mancante.
 */
export function gruppiDellaRun(
  config: ConfigView,
  collection: string,
  indice: CollectionView | null,
): Gruppo[] {
  const fuori: Gruppo[] = [];
  if (collection !== "" && indice !== null) {
    fuori.push({
      nome: "indice",
      righe: [
        { nome: "collection", valore: indice.name },
        { nome: "points", valore: indice.points },
        { nome: "dense_size", valore: indice.dense_size },
        { nome: "has_sparse", valore: indice.has_sparse },
      ],
    });
  }
  fuori.push({ nome: "recupero", righe: RECUPERO.map((k) => ({ nome: k, valore: config[k] })) });
  fuori.push({
    nome: "generazione",
    righe: GENERAZIONE.map((k) => ({ nome: k, valore: config[k] })),
  });
  return fuori;
}

/** La collection su cui la risposta ha cercato, fra quelle che il backend
 *  pubblica. `null` quando non si sa o non c'e' piu': due casi diversi che si
 *  disegnano uguale, perche' l'unica cosa onesta da fare e' tacere. */
export function indiceDi(
  collection: string,
  collections: readonly CollectionView[],
): CollectionView | null {
  if (collection === "") return null;
  return collections.find((c) => c.name === collection) ?? null;
}

/** Ogni campo del contratto che il foglio mostra. Serve al test che conta. */
export const CAMPI_MOSTRATI = [...RECUPERO, ...GENERAZIONE] as const;
