/**
 * Cosa e' cambiato fra una domanda e la successiva.
 *
 * **Il dato non e' nuovo.** `Risposta.config` porta il `ConfigView` che ha
 * davvero girato — non quello chiesto — ed e' li' dall'evento `done` del §3.5;
 * `cronologia.ts` lo scrive nel deposito da U-13 senza che nessuno l'avesse
 * pensato per questo. Qui non si aggiunge niente: si legge.
 *
 * **Si mostra la differenza, non la configurazione.** Quattordici campi
 * ripetuti sotto ogni domanda sarebbero un muro che nessuno legge, e cio' che
 * serve sapere e' *cosa e' cambiato da prima*. La prima riga di una
 * conversazione si confronta con i **predefiniti del servizio**, cosi' una
 * conversazione partita senza toccare niente lo dice in tre parole invece che
 * in quattordici.
 *
 * **Si copre tutto `ConfigView`, non i soli controlli della barra.** Un
 * parametro cambiato lato server fra due domande e' esattamente cio' che questa
 * riga esiste per non far sparire — e coprire tutto il contratto la rende
 * automatica: un campo aggiunto domani compare da solo, senza che nessuno debba
 * ricordarsi di aggiungerlo anche qui.
 */
import type { ConfigView } from "../api/types";

export interface Differenza {
  /** Il nome del campo **come lo chiama il server**. Tradurlo vorrebbe dire
   *  tenere un elenco di chiavi del backend nel frontend, e una chiave nuova
   *  comparirebbe senza nome: e' la scelta gia' presa per i tempi nella riga di
   *  stato. */
  campo: string;
  prima: unknown;
  dopo: unknown;
}

/**
 * I campi in cui `dopo` non concorda con `prima`.
 *
 * Le chiavi si prendono da **`dopo`**, cioe' dalla risposta che si sta
 * descrivendo: se il server ne aggiunge una, compare; se ne toglie una, sparisce
 * insieme al campo invece di restare come un confronto con `undefined`.
 */
export function differenze(prima: ConfigView | null, dopo: ConfigView): Differenza[] {
  const p = prima as unknown as Record<string, unknown> | null;
  const d = dopo as unknown as Record<string, unknown>;
  return Object.keys(d)
    .filter((k) => p === null || p[k] !== d[k])
    .map((k) => ({ campo: k, prima: p === null ? undefined : p[k], dopo: d[k] }));
}

/**
 * La configurazione di uno scambio, quando esiste.
 *
 * `null` mentre la risposta arriva, e su una interrotta o caduta: `config` viene
 * con `done`, che li' non e' mai arrivato. Chi legge deve saper distinguere «non
 * e' cambiato niente» da «non si sa cosa ha girato», e le due cose non possono
 * essere lo stesso valore.
 */
export function configDi(scambio: { risposta: { config: ConfigView | null } }): ConfigView | null {
  return scambio.risposta.config;
}

/**
 * L'ultima configurazione **conosciuta** prima dell'indice `i`.
 *
 * Si salta all'indietro sulle risposte senza `config` invece di trattarle come
 * una rottura: una generazione fermata a meta' non ha cambiato niente, e
 * mostrare «tutto cambiato» dopo un «Ferma» direbbe una cosa falsa su un gesto
 * che non ha toccato nessun parametro.
 */
export function configPrecedente(
  scambi: readonly { risposta: { config: ConfigView | null } }[],
  i: number,
): ConfigView | null {
  for (let k = i - 1; k >= 0; k -= 1) {
    const c = scambi[k].risposta.config;
    if (c !== null) return c;
  }
  return null;
}

/** Ogni campo e il suo valore, per il suggerimento: qui la configurazione si
 *  vuole **intera**, perche' e' il posto in cui la si va a cercare. */
export function intera(config: ConfigView): Differenza[] {
  const d = config as unknown as Record<string, unknown>;
  return Object.keys(d).map((k) => ({ campo: k, prima: undefined, dopo: d[k] }));
}
