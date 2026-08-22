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

/** Cercare fra i documenti del corpus (U-06). */
export function Lente(p: PropsIcona) {
  return (
    <Base {...p}>
      <circle cx="7" cy="7" r="4" />
      <path d="M10 10 L13.5 13.5" />
    </Base>
  );
}

/**
 * Il corpus e come e' stato spezzato: tre bande di larghezza diversa.
 *
 * Non una lente ne' una cartella. Cio' che quella schermata mostra e' **la
 * mappa** — le tessere di un documento, larghe in modo diverso a seconda di cosa
 * contengono — e l'icona e' quella mappa in piccolo: un documento tagliato in
 * pezzi disuguali, che e' l'unica cosa che una cartella non direbbe.
 */
export function Corpus(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M2.5 4 H13.5" />
      <path d="M2.5 8 H8.5" />
      <path d="M2.5 12 H11" />
    </Base>
  );
}

/**
 * La corsia, aperta o chiusa: un pannello con la sua striscia a sinistra.
 *
 * **La stessa forma per i due versi**, e non una freccia che cambia direzione.
 * Una freccia dice «di la'», e qui non si va da nessuna parte: si toglie e si
 * rimette una colonna. Il verso lo dice il nome del comando — «Comprimi la
 * corsia», «Apri la corsia» — che chi ascolta sente e chi guarda legge nel
 * suggerimento, mentre due frecce speculari costringerebbero a ricordare quale
 * significa cosa.
 */
export function Corsia(p: PropsIcona) {
  return (
    <Base {...p}>
      <rect x="2.5" y="3" width="11" height="10" rx="1.5" />
      <path d="M6.5 3 V13" />
    </Base>
  );
}

/**
 * La cronologia: cio' che si e' chiesto prima.
 *
 * Un orologio con le lancette in alto a destra, che e' il modo in cui «recente»
 * si disegna. Non una lista di righe: quella e' `Corpus`, e li' le righe
 * disuguali **sono** il significato — due icone di righe orizzontali a 13 px
 * sono la stessa icona.
 */
export function Orologio(p: PropsIcona) {
  return (
    <Base {...p}>
      <circle cx="8" cy="8" r="5.5" />
      <path d="M8 4.9 L8 8 L10.4 9.4" />
    </Base>
  );
}

/**
 * L'indice su cui si sta chiedendo: una pila.
 *
 * Un dataset qui e' una **collezione** — migliaia di chunk impilati e cercabili
 * — e la pila e' la forma che lo dice senza promettere altro. Una cartella
 * direbbe «file», un cilindro «database»: nessuno dei due e' cio' che c'e'
 * dentro.
 */
export function Indice(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M8 2.6 L14 5.9 L8 9.2 L2 5.9 Z" />
      <path d="M2.6 9.2 L8 12.2 L13.4 9.2" />
    </Base>
  );
}

/**
 * «Che cos'e' questo»: la i in un cerchio (U-19).
 *
 * E' il glifo che il progetto ha gia' — il marchio e' `ib`·`i`·`d` con la i di
 * mezzo in accento — e qui torna da solo. Un punto interrogativo avrebbe detto
 * «aiuto», che e' un'altra cosa: quella pagina non spiega come si usa
 * l'interfaccia, dice cos'e' il programma e cosa non e'.
 *
 * Il punto della i e' un segmento lungo un decimo di griglia: con le estremita'
 * tonde diventa un disco, e resta un tratto come tutto il resto invece di essere
 * l'unico riempimento del set.
 */
export function Informazioni(p: PropsIcona) {
  return (
    <Base {...p}>
      <circle cx="8" cy="8" r="5.8" />
      <path d="M8 4.6 L8 4.7" />
      <path d="M8 7.4 L8 11.2" />
    </Base>
  );
}

/**
 * Ferma cio' che sta arrivando: il quadrato.
 *
 * **Pieno, ed e' la seconda eccezione alla regola 2** — che dice «solo tratto».
 * La regola esiste per non dover scegliere un secondo colore che regga su carta
 * e su fondo scuro, e un riempimento in `currentColor` quel problema non ce
 * l'ha: e' la stessa deroga di `Sistema`, per la stessa ragione.
 *
 * Serve, perche' il quadrato vuoto e' gia' preso: `NonVerificata` e' una casella
 * vuota, e vuol dire «di questa frase non e' stato detto niente». Le due non si
 * incontrano mai — una sta nel campo di scrittura, l'altra sui marcatori dentro
 * una risposta — ma due quadrati di tratto con due significati diversi sarebbero
 * comunque due volte la stessa figura, e il pieno e' anche la forma con cui
 * «ferma» si scrive dappertutto.
 */
export function Ferma(p: PropsIcona) {
  return (
    <Base {...p}>
      <rect x="4" y="4" width="8" height="8" rx="1.6" fill="currentColor" stroke="none" />
    </Base>
  );
}

/** Si apre fuori da qui: una freccia che esce dal riquadro (U-06). */
export function Esterno(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M12.5 9.5 V13 a.5.5 0 0 1-.5.5 H3.5 a.5.5 0 0 1-.5-.5 V4.5 a.5.5 0 0 1 .5-.5 H7" />
      <path d="M10 2.5 H13.5 V6" />
      <path d="M13.5 2.5 L7.5 8.5" />
    </Base>
  );
}

/** Un passo in giu' su una manopola numerica. */
export function Meno(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M3.6 8 L12.4 8" />
    </Base>
  );
}

/** Rimette una manopola sul valore configurato: l'arco che torna al punto di
 *  partenza, e non una freccia, perche' non porta *indietro di uno*. */
export function Ritorno(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M3.4 8 A4.6 4.6 0 1 1 5.9 12.1" />
      <path d="M3.4 4.8 L3.4 8 L6.6 8" />
    </Base>
  );
}

/**
 * Chiude uno strato che si e' aperto sopra il lavoro (D-5).
 *
 * **Non e' `Indietro`**, ed e' la stessa distinzione che quel commento fa: una
 * freccia dice «torna da dove sei arrivato», cioe' promette una navigazione. Un
 * foglio non porta da nessuna parte -- si toglie di mezzo, e sotto c'e' quel
 * che c'era gia'. La croce e' la parola per «via», ed e' l'unica cosa che nella
 * grammatica delle icone non voglia dire nient'altro.
 */
export function Chiudi(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M4.2 4.2 L11.8 11.8" />
      <path d="M11.8 4.2 L4.2 11.8" />
    </Base>
  );
}

/** Torna da dove si era arrivati. Sul confronto, che e' l'unica schermata da
 *  cui si esce invece di cambiare pagina. */
export function Indietro(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M12.5 8 L4 8" />
      <path d="M8 4 L4 8 L8 12" />
    </Base>
  );
}

/** Le due risposte alla stessa domanda, una accanto all'altra. */
export function DueColonne(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M3 3.5 L3 12.5" />
      <path d="M8 2.5 L8 13.5" />
      <path d="M13 3.5 L13 12.5" />
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

/** Fa qualcosa di nuovo. Sulla voce «Nuova conversazione», dove distingue
 *  l'unica riga della corsia che **crea** da quelle che ci riportano. */
export function Piu(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M8 3.6 L8 12.4 M3.6 8 L12.4 8" />
    </Base>
  );
}

/**
 * Butta via. L'unico comando dell'interfaccia che distrugge, ed e' l'unico posto
 * dove il token `danger` compare.
 *
 * Tre tratti e non di piu': coperchio, presa, corpo. Le righine verticali che i
 * cestini disegnati in grande hanno dentro, a 12 px diventano un'ombra grigia —
 * e quello che deve arrivare a quella misura e' la sagoma.
 */
export function Cestino(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M3.2 5.2 L12.8 5.2" />
      <path d="M6.3 5.2 L6.3 3.3 L9.7 3.3 L9.7 5.2" />
      <path d="M4.7 5.2 L5.3 12.9 L10.7 12.9 L11.3 5.2" />
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

/**
 * I due verificatori non concordano: `≠`.
 *
 * Non e' un terzo verdetto, e' la dichiarazione che ce ne sono due e dicono cose
 * diverse — su una tabella l'NLI di C-03 sbaglia e il verificatore numerico di
 * C-09 no, ed e' esattamente perche' C-09 esiste. Un simbolo di disuguaglianza
 * dice quella cosa e nessun'altra.
 */
export function Discordi(p: PropsIcona) {
  return (
    <Base {...p}>
      <path d="M3.6 6.4 L12.4 6.4 M3.6 9.6 L12.4 9.6 M11 3.4 L5 12.6" />
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
