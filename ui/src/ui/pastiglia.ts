/**
 * La pastiglia del mockup (`.tg`): pillola, bordo sottile, 11 px.
 *
 * Stava dentro `Barra.tsx`, dov'e' nata, e da U-04 non e' piu' solo della barra:
 * il selettore del prompt nella colonna nuda e' un comando come quelli sotto il
 * campo, e disegnarselo per conto suo era il difetto gia' visto col caret —
 * stessa forma presa da un'altra misura, che diverge alla prima correzione.
 *
 * Il passaggio del mouse porta l'accento in **tutti** gli stati: un comando che
 * si illumina solo quando e' gia' acceso non dice a chi non l'ha mai toccato che
 * si puo' toccare. E' la correzione che U-13 ha imposto sul pulsante della
 * cronologia.
 */

/** Solo la pillola, senza margini interni: serve a chi ne ha di propri (il
 *  numero a passi ha quelli dei bottoncini che contiene). */
export const FORMA = "inline-flex items-center rounded-full border text-[11px] transition-colors";
export const PASTIGLIA = `${FORMA} gap-1.5 py-1 pr-2.5 pl-[7px]`;
export const RIPOSO = "border-line-2 bg-surface text-ink-2 hover:border-accent-2 hover:text-ink";
export const MOSSA = "border-accent bg-accent-soft text-accent hover:border-accent-2";
