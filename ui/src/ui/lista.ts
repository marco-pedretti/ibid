/**
 * Come ci si muove dentro un elenco a scelta singola.
 *
 * Sta fuori dal componente perche' e' la parte che il `<select>` nativo faceva
 * gratis e che ora e' nostra: saltare le voci disabilitate, girare in fondo e
 * ricominciare, e non bloccarsi quando **tutte** sono disabilitate. Sono tre
 * casi che a mano non si riprovano mai piu' dopo la prima volta, e i test qui
 * girano senza DOM.
 */
import type { ReactNode } from "react";

export interface Voce<T extends string> {
  valore: T;
  testo: string;
  /** Il simbolo dell'insieme di `Icona.tsx`, quando la voce ne ha uno. Il
   *  `<select>` nativo accettava solo testo: era l'unico posto dell'interfaccia
   *  in cui il simbolo doveva restare un glifo. */
  icona?: ReactNode;
  /** Il dato che sta a destra, in mono: il conteggio dei chunk, non una
   *  seconda riga di prosa. Separato da `testo` perche' e' `testo` a dover
   *  troncare quando la corsia e' stretta -- un numero troncato non e' un
   *  numero. */
  dettaglio?: string;
  /** Visibile e leggibile, ma non scegliibile: uno stato da capire, non da
   *  indovinare. La tastiera la salta, come farebbe il controllo nativo. */
  disabilitata?: boolean;
}

/** L'indice di `valore`, o -1. */
export function indiceDi<T extends string>(voci: readonly Voce<T>[], valore: T): number {
  return voci.findIndex((v) => v.valore === valore);
}

/**
 * L'indice attivo dopo una freccia, saltando le disabilitate e girando in tondo.
 *
 * `-1` quando non c'e' nessuna voce scegliibile: il chiamante deve poter
 * distinguere «non mi sono mosso» da «non c'era dove muoversi», altrimenti il
 * ciclo che cerca la prossima voce non finisce mai.
 */
export function scorri<T extends string>(
  voci: readonly Voce<T>[],
  da: number,
  passo: 1 | -1,
): number {
  if (voci.length === 0) return -1;

  for (let n = 1; n <= voci.length; n += 1) {
    const i = (((da + passo * n) % voci.length) + voci.length) % voci.length;
    if (!voci[i].disabilitata) return i;
  }
  return -1;
}

/** La prima voce scegliibile dall'inizio (`1`) o dalla fine (`-1`). */
export function estremo<T extends string>(voci: readonly Voce<T>[], verso: 1 | -1): number {
  return scorri(voci, verso === 1 ? -1 : voci.length, verso);
}

/**
 * Da dove parte l'evidenziazione all'apertura: la voce corrente se e' ancora
 * scegliibile, altrimenti la prima che lo e'.
 *
 * Aprire su una voce disabilitata sembrerebbe una selezione, e il primo Invio
 * non farebbe niente senza spiegare perche'.
 */
export function allApertura<T extends string>(voci: readonly Voce<T>[], valore: T): number {
  const i = indiceDi(voci, valore);
  if (i !== -1 && !voci[i].disabilitata) return i;
  return estremo(voci, 1);
}
