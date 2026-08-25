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

/**
 * Solo la pillola, senza margini interni: serve a chi ne ha di propri (il
 * numero a passi ha quelli dei bottoncini che contiene).
 *
 * **L'altezza e' dichiarata, non dedotta dal contenuto**, ed e' la stessa
 * lezione che `Telaio.tsx` ha imparato sulle celle della corsia: *due controlli
 * affiancati che differiscono di due pixel non si leggono come due misure, si
 * leggono come un errore*. Qui la differenza c'era e valeva 2,5 px — un menu
 * era alto quanto la sua riga di testo (11 px per l'interlinea 1,5, piu' i
 * margini), il numero a passi quanto i suoi bottoncini da 18 — e nel pannello
 * «Avanzate», che allinea le colonne in basso, quei 2,5 px diventavano due
 * altezze di etichetta.
 *
 * Ventisei perche' e' cio' che i menu erano gia': i sei controlli della barra
 * non si muovono di mezzo pixel, e a salire sono i due numeri.
 *
 * Da qui in poi **nessuna pastiglia ha margini verticali**: con l'altezza
 * dichiarata non decidono piu' niente, e un riquadro che porta tutt'e due
 * costringe chi legge a stabilire quale dei due vince.
 */
export const FORMA =
  "inline-flex h-[26px] items-center rounded-full border text-[11px] transition-colors";

/**
 * La pillola **con un glifo davanti al testo**, e oggi ne resta uno solo: gli
 * interruttori della barra, che portano un pallino acceso o spento.
 *
 * Il `pl-[7px]` e' quello: un pallino da 6 px non ha bisogno dei 10 px che il
 * testo chiede dall'altro lato, e con margini uguali sembrerebbe staccato. Su
 * una pillola **senza** glifo lo stesso margine la rende storta di tre pixel, ed
 * e' quello che facevano il menu del modello, «Avanzate» e i due menu del
 * pannello — che infatti adesso prendono `FORMA` con `px-2.5`, come il
 * selettore del prompt e come `Modo`.
 */
export const PASTIGLIA = `${FORMA} gap-1.5 pr-2.5 pl-[7px]`;
export const RIPOSO = "border-line-2 bg-surface text-ink-2 hover:border-accent-2 hover:text-ink";
export const MOSSA = "border-accent bg-accent-soft text-accent hover:border-accent-2";
