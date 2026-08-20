/**
 * Le due colonne: chi e' chi, e l'unica cosa che si puo' cambiare dentro.
 *
 * Sta accanto a `chat.tsx` come `conversazione.ts` sta accanto a `Chat`: li' lo
 * stream e l'`AbortController`, qui le regole che si possono provare senza un
 * browser. Sono poche e valgono tutte per lo stesso motivo — **la coppia deve
 * restare la stessa coppia** mentre una delle due si rifa'.
 *
 * ## Perche' il braccio nudo e' un campo e non un calcolo
 *
 * Prima si ricavava dalla risposta: `data.config.rag` falso vuol dire che la
 * colonna nuda e' quella gia' data. Funziona finche' nessuno la rifa'. Da U-04
 * la colonna nuda si rilancia col prompt cambiato, e mentre arriva il suo
 * `config` e' `null` — cioe' proprio il dato da cui si ricavava la posizione.
 * Le due colonne si sarebbero **scambiate di posto a meta' generazione**, che
 * e' il difetto peggiore possibile in una schermata il cui unico scopo e' dire
 * quale delle due ha visto le fonti.
 *
 * Quindi si decide una volta, all'apertura, e non si ricalcola piu'.
 */
import type { ConfigView } from "../api/types";
import type { Risposta } from "./conversazione";

/** Quale delle due risposte e' il braccio senza fonti. */
export type Braccio = "data" | "nuova";

/**
 * Le due risposte alla stessa domanda, e null quando non se ne sta guardando
 * nessuna.
 *
 * **Non e' uno scambio della conversazione.** Il §12 dice che «affiancate, dalla
 * stessa query, nella stessa sessione» non si ottiene con due messaggi
 * consecutivi: il braccio nudo dentro il filo sarebbe una seconda risposta alla
 * stessa domanda, e nella cronologia diventerebbe una conversazione che si
 * contraddice da sola. Vive accanto al filo, e chiudendolo sparisce.
 */
export interface Confronto {
  domanda: string;
  /** Quella gia' data, da cui si e' partiti. */
  data: Risposta;
  /** La stessa domanda col solo RAG invertito. */
  nuova: Risposta;
  /** Quale delle due e' senza fonti. Deciso all'apertura — vedi la nota in
   *  testa al file. */
  nudo: Braccio;
  /**
   * Con quale prompt e' stata **chiesta** la colonna nuda.
   *
   * Cosa ha girato lo dice il suo `ConfigView`, che pero' arriva con `done`:
   * per gli ~11 s in cui la risposta si sta rifacendo non c'e'. Senza questo
   * campo il selettore tornerebbe indietro da solo appena premuto, per poi
   * saltare al valore giusto a generazione finita. E' la stessa coppia
   * chiesto/girato di U-15, e si legge con la stessa regola — vedi `promptNudo`.
   */
  promptChiesto: string;
}

/** Da che parte va ciascuna, all'apertura: la risposta di partenza sta dalla
 *  parte che il suo `rag` dice, e l'altra e' quella che si sta chiedendo. */
export function braccioNudo(partenza: ConfigView): Braccio {
  return partenza.rag ? "nuova" : "data";
}

/** Le due colonne per nome. */
export function bracci(c: Confronto): { conFonti: Risposta; senzaFonti: Risposta } {
  return c.nudo === "data"
    ? { conFonti: c.nuova, senzaFonti: c.data }
    : { conFonti: c.data, senzaFonti: c.nuova };
}

/**
 * La stessa coppia con **un** braccio riscritto.
 *
 * `quale` e' un argomento e non `c.nudo`: chi guida uno stream lo ha fissato
 * quando e' partito, e leggerlo dallo stato a ogni token significherebbe
 * rileggere un campo che quello stesso stream sta cambiando.
 */
export function conBraccio(c: Confronto, quale: Braccio, f: (r: Risposta) => Risposta): Confronto {
  return quale === "data" ? { ...c, data: f(c.data) } : { ...c, nuova: f(c.nuova) };
}

/**
 * I due capi dell'asse che E-04 ed E-05 hanno misurato: rispondi comunque,
 * oppure astieniti se non sei certo.
 *
 * I valori sono quelli del server, scritti qui, ed e' il motivo di
 * `scelteDiPrompt`: sono due nomi in una copia, con la verifica accanto.
 */
export const PERMISSIVO = "permissive";
export const SEVERO = "strict";

/**
 * Quali dei due il servizio offre davvero, nell'ordine dell'asse.
 *
 * Con meno di due non c'e' niente da scegliere e il controllo sparisce: e' la
 * stessa regola di `ragionamentoDisponibile`, cioe' nessun comando che gira a
 * vuoto. E l'ordine e' quello, sempre — permissivo a sinistra, severo a destra —
 * perche' e' un asse e non un elenco: se cambiasse posto a seconda di come il
 * server elenca i valori, «l'altro capo» smetterebbe di essere un posto.
 */
export function scelteDiPrompt(offerti: readonly string[]): string[] {
  return [PERMISSIVO, SEVERO].filter((p) => offerti.includes(p));
}

/**
 * Con quale prompt sta rispondendo la colonna nuda.
 *
 * Cio' che ha girato quando si sa, cio' che e' stato chiesto mentre non si sa
 * ancora: la stessa regola di `configDi` in `parametri.ts`. Il verso conta —
 * `config` per primo — perche' e' l'unico dei due che puo' smentire il
 * controllo, ed e' esattamente quando deve farlo.
 */
export function promptNudo(c: Confronto): string {
  return bracci(c).senzaFonti.config?.baseline_prompt ?? c.promptChiesto;
}
