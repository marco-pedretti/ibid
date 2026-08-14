/**
 * Un `<select>` nativo reso trasparente sopra un disegno nostro.
 *
 * E' il modo di avere la forma decisa in `docs/ui-mockup.html` senza riscrivere
 * a mano tastiera, ruolo ARIA, chiusura al clic fuori, voci disabilitate e
 * comportamento su schermo tattile — le cinque cose che un menu fatto in casa
 * sbaglia quasi sempre, e che non costerebbero un componente ma un difetto di
 * accessibilita'. Il mockup non disegna mai una lista aperta, quindi lasciarla
 * al sistema non tradisce nessuna decisione presa.
 *
 * **I colori sono dichiarati su un elemento invisibile, e non e' un residuo.**
 * La tendina e' un widget nativo a parte: l'`opacity: 0` non la tocca. Senza
 * colori espliciti eredita il testo (`--ink`, quasi bianco nel tema scuro) e
 * dipinge il fondo col default dell'agente utente, che resta chiaro — bianco su
 * bianco per ogni voce tranne quella sotto l'evidenziazione di sistema. Vanno
 * ripetuti su ogni `<option>` perche' Chromium dipinge le voci col loro stile e
 * non con quello del controllo.
 *
 * Il disegno passa come `children` ed e' nascosto agli assistivi: il `<select>`
 * dice gia' le stesse cose, e sentirle due volte e' peggio che non vederle.
 */
import type { ReactNode } from "react";

export interface Voce<T extends string> {
  valore: T;
  testo: string;
  /** Resta visibile e leggibile, in `muted`: uno stato da capire, non da
   *  indovinare. Toglierla direbbe che non esiste. */
  disabilitata?: boolean;
}

export function SelettoreNativo<T extends string>({
  etichetta,
  valore,
  voci,
  onCambia,
  className = "",
  children,
}: {
  etichetta: string;
  valore: T;
  voci: readonly Voce<T>[];
  onCambia: (valore: T) => void;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div
      className={`relative focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent ${className}`}
    >
      <span aria-hidden="true" className="contents">
        {children}
      </span>

      {/* Il caret lo mette il componente, non il chiamante. Nel mockup e' il
          segno che distingue una pastiglia che **apre** (`.tg.menu`) da una che
          commuta e basta: e' una proprieta' del controllo, e lasciarla al
          disegno significa che il prossimo selettore se la dimentica.

          Disegnato invece di scritto come `▾`: quel carattere e' un glifo del
          font, e nei font di sistema — che il §12 impone, per U-08 senza rete —
          arriva sottile e piu' piccolo della sua dimensione nominale, al punto
          da non vedersi. Un tratto ha lo spessore che gli si da'. */}
      <svg
        aria-hidden="true"
        viewBox="0 0 12 12"
        className="h-3 w-3 shrink-0 text-ink-2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M3 4.75 L6 7.75 L9 4.75" />
      </svg>

      <select
        aria-label={etichetta}
        value={valore}
        onChange={(e) => onCambia(e.target.value as T)}
        className="absolute inset-0 w-full cursor-pointer bg-surface text-ink opacity-0"
      >
        {voci.map((v) => (
          <option
            key={v.valore}
            value={v.valore}
            disabled={v.disabilitata}
            className={v.disabilitata ? "bg-surface text-muted" : "bg-surface text-ink"}
          >
            {v.testo}
          </option>
        ))}
      </select>
    </div>
  );
}
