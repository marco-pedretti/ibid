import type { ReactNode } from "react";

import { Etichetta } from "./Etichetta";
import { Esterno, Indietro } from "./Icona";

/**
 * Una pagina che si apre **sopra** la conversazione, e si chiude tornando la'.
 *
 * Sono due — l'esploratore del corpus (§12) e «Che cos'e'» (U-19) — e prima di
 * Q-07 erano due volte le stesse quaranta righe: stesso contenitore alto quanto
 * la colonna, stessa testata con etichetta e sottotitolo, stesso bottone
 * «indietro» con la stessa stringa di classi lunga ottantuno caratteri. Erano
 * identiche **oggi**; il difetto e' quello che `pastiglia.ts` chiama per nome,
 * *stessa forma presa da un'altra misura*, e si vede alla prima correzione: chi
 * ritocca il bordo della testata ne ritocca una, e l'altra resta indietro senza
 * che nessuno se ne accorga finche' non si aprono in fila.
 *
 * **La testata non e' un `<header>`.** Questa pagina vive dentro la colonna di
 * lavoro, che ha gia' la sua testata a colonna sola (`Telaio`): due `header`
 * annidati direbbero a chi legge con la voce che ce ne sono due, e la seconda
 * non e' l'intestazione del documento — e' il titolo di una vista.
 *
 * Cio' che cambia fra le due sta tutto negli argomenti, e nel corpo.
 */
export function Pagina({
  etichetta,
  sottotitolo,
  indietro,
  chiudi,
  children,
}: {
  etichetta: string;
  sottotitolo: ReactNode;
  /** La parola sul bottone: «Torna alla conversazione», «Chiudi». Non e' la
   *  stessa nelle due pagine, e non deve diventarlo — dice dove si torna. */
  indietro: string;
  chiudi: () => void;
  children: ReactNode;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col bg-paper">
      <div className="flex shrink-0 items-start gap-3 border-b border-line px-[22px] py-3">
        <div className="min-w-0 flex-1">
          <Etichetta>{etichetta}</Etichetta>
          <p className="mt-1 text-[13px] text-ink">{sottotitolo}</p>
        </div>
        <Ritorno onClick={chiudi}>{indietro}</Ritorno>
      </div>
      {children}
    </div>
  );
}

/** La forma di cio' che porta via da qui — indietro, o fuori dall'applicazione:
 *  bordo sottile, testo attenuato, accento al passaggio del mouse. */
const FUORI =
  "rounded-md border border-line-2 px-[9px] py-[5px] text-[11px] text-ink-2 transition-colors hover:border-accent-2 hover:text-ink";

/**
 * Il bottone che torna indietro, con la sua freccia.
 *
 * Lo usano la testata qui sopra e l'affondo dell'esploratore, che a colonna
 * sola torna dal documento all'elenco: due testate diverse, lo stesso gesto e
 * la stessa forma. La parola la sceglie chi chiama, perche' dice **dove** si
 * torna e non sono lo stesso posto.
 */
export function Ritorno({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex shrink-0 items-center gap-1.5 ${FUORI}`}
    >
      <Indietro size={12} />
      {children}
    </button>
  );
}

/**
 * Un collegamento che esce dall'applicazione.
 *
 * Ha la forma del bottone «indietro» perche' fa la stessa cosa vista da qui —
 * si va altrove — e la scriveva a mano tutte e due le volte: il documento
 * originale nell'esploratore, il repository in «Che cos'e'».
 *
 * `rel="noreferrer noopener"` non e' cerimonia: senza `noopener` la pagina che
 * si apre puo' riscrivere l'indirizzo di questa attraverso `window.opener`.
 */
export function Collegamento({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className={`flex items-center gap-1.5 self-start ${FUORI}`}
    >
      <Esterno size={12} />
      {children}
    </a>
  );
}
