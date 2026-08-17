/**
 * I simboli dell'interfaccia, disegnati.
 *
 * **Perche' non i glifi.** `▾`, `↑`, `☾` sono caratteri dei font, e il §12
 * impone font di **sistema** (U-08 vuole il profilo demo senza rete): arrivano
 * sottili, piu' piccoli della loro dimensione nominale, e diversi su ogni
 * macchina. Un tratto disegnato ha lo spessore che gli si da', ed e' lo stesso
 * ovunque.
 *
 * **La direzione, e vale per tutta la UI.** Cinque regole, non di gusto ma di
 * coerenza — un'icona nuova che le rispetta appartiene all'insieme senza doverla
 * confrontare con le altre:
 *
 * 1. **una griglia sola**, `viewBox="0 0 16 16"`: le forme si assomigliano
 *    perche' sono disegnate nello stesso spazio, non perche' qualcuno le ha
 *    pareggiate a occhio;
 * 2. **solo tratto, mai riempimento** — un'icona piena avrebbe bisogno di un
 *    secondo colore per restare leggibile sui fondi chiari e su quelli scuri,
 *    e un colore in piu' e' una decisione in piu' per ogni tema. L'unica
 *    eccezione e' `Sistema`, dove il **contrasto fra pieno e vuoto e' proprio
 *    il significato**: «segui il sistema, che a volte e' chiaro e a volte
 *    scuro»;
 * 3. **spessore 2 sulla griglia**, che scala con la dimensione: a 12 px sono
 *    1,5 px reali, e a 14 px 1,75 — otticamente lo stesso segno;
 * 4. **estremita' e giunti tondi**, come le forme dell'interfaccia, che hanno
 *    raggi piccoli ma non angoli vivi;
 * 5. **`currentColor` sempre**: l'icona prende il colore del testo accanto a
 *    cui sta, quindi non esiste il caso di un'icona rimasta indietro di un
 *    token quando la palette cambia.
 *
 * Sono `aria-hidden` per costruzione: il significato sta nella parola accanto o
 * nell'`aria-label` del controllo che le contiene. Un'icona che *e'* l'unica
 * informazione e' un'icona che qualcuno non legge.
 */
import type { ReactNode } from "react";

function Base({
  size = 14,
  className = "",
  children,
}: {
  size?: number;
  className?: string;
  children: ReactNode;
}) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 16 16"
      width={size}
      height={size}
      className={`shrink-0 ${className}`}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {children}
    </svg>
  );
}

export interface PropsIcona {
  size?: number;
  className?: string;
}

/** Questo controllo apre un menu. */
export function Caret(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M4 6.5 L8 10.5 L12 6.5" />
    </Base>
  );
}

/** Manda la domanda. */
export function FrecciaSu(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M8 12.5 L8 4" />
      <path d="M4 8 L8 4 L12 8" />
    </Base>
  );
}

/* --- i tre temi ----------------------------------------------------------
   Tre forme che si distinguono **di silhouette** e non di dettaglio: a 12 px il
   dettaglio non arriva, e tre cerchi con dentro cose diverse sarebbero tre
   cerchi. */

export function Chiaro(p: PropsIcona) {
  return (
    <Base {...p}>
      <circle cx="8" cy="8" r="3" />
      <path d="M8 1.5 L8 2.8 M8 13.2 L8 14.5 M1.5 8 L2.8 8 M13.2 8 L14.5 8" />
      <path d="M3.4 3.4 L4.3 4.3 M11.7 11.7 L12.6 12.6 M12.6 3.4 L11.7 4.3 M4.3 11.7 L3.4 12.6" />
    </Base>
  );
}

export function Scuro(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M13 9.8 A5.6 5.6 0 1 1 6.2 3 A4.4 4.4 0 0 0 13 9.8 Z" />
    </Base>
  );
}

/**
 * «Segui il sistema». L'unica icona con un pieno, e il pieno **e'** il
 * significato: mezzo disco chiaro e mezzo scuro dice che il tema non e' stato
 * scelto, e' delegato.
 */
export function Sistema(p: PropsIcona) {
  return (
    <Base {...p}>
      <circle cx="8" cy="8" r="5.6" />
      <path d="M8 2.4 A5.6 5.6 0 0 1 8 13.6 Z" fill="currentColor" stroke="none" />
    </Base>
  );
}

/* --- i verdetti (U-07) ---------------------------------------------------
   Cinque forme per i cinque stati di una citazione, e si distinguono **di
   silhouette**: una spunta, una croce, una casella vuota, una linea, un punto.
   Il §12 chiede che un verdetto si legga da glifo, colore e parola insieme —
   queste sono il glifo, e nessuna delle cinque e' l'assenza di un'altra. */

/** Il chunk citato sostiene la frase. */
export function Sostiene(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M3.5 8.6 L6.4 11.5 L12.5 4.6" />
    </Base>
  );
}

/**
 * Il chunk citato **non** sostiene la frase.
 *
 * Una croce e non un triangolo d'allarme, e nel colore `warn` che non e' rosso:
 * U-07 dice che questa non e' una cosa andata storta da nascondere, e' il dato
 * che il progetto esiste per misurare. Un segno d'errore contraddirebbe il §0.
 */
export function NonSostiene(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M4.6 4.6 L11.4 11.4 M11.4 4.6 L4.6 11.4" />
    </Base>
  );
}

/**
 * Nessun verdetto per questa coppia: **la casella e' rimasta vuota.**
 *
 * L'unico rettangolo dell'insieme, e la ragione e' che deve essere impossibile
 * confonderlo con gli altri quattro: e' lo stato che il criterio di U-07 nomina
 * per nome, e leggerlo come «sostenuta» sarebbe l'errore peggiore possibile qui.
 */
export function NonVerificata(p: PropsIcona) {
  return (
    <Base {...p}>
      <rect x="3.4" y="3.4" width="9.2" height="9.2" rx="2.2" />
    </Base>
  );
}

/** Il recupero l'ha portata, la risposta non l'ha usata. Non e' un verdetto. */
export function NonCitata(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M4 8 L12 8" />
    </Base>
  );
}

/** La verifica sta girando: un punto, come il `·` del mockup. */
export function InAttesa(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M8 8 L8.01 8" />
    </Base>
  );
}

/* --- gli avvisi ---------------------------------------------------------- */

/** Astensione: non e' stato detto niente, e non e' un guasto. */
export function Astensione(p: PropsIcona) {
  return (
    <Base {...p}>
      <circle cx="8" cy="8" r="5.6" />
      <path d="M4 12 L12 4" />
    </Base>
  );
}

/** Troncato: il testo continuava e si e' fermato. */
export function Troncato(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M3 8 L3.01 8 M8 8 L8.01 8 M13 8 L13.01 8" />
    </Base>
  );
}

/** Qualcosa e' andato storto, e va letto. */
export function Avvertimento(p: PropsIcona) {
  return (
    <Base {...p}>
      <circle cx="8" cy="8" r="5.6" />
      <path d="M8 5 L8 8.6 M8 11 L8.01 11" />
    </Base>
  );
}
