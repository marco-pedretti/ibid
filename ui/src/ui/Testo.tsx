/**
 * Il testo della risposta, coi marcatori riconosciuti.
 *
 * **I marcatori sono inerti finche' `answer` non arriva**, ed e' una regola del
 * §3.5 e non una scelta grafica: mentre i token scorrono, `[2]` compare prima
 * che il suo verdetto esista, e prima ancora che il parser abbia potuto
 * normalizzarlo. Disegnarlo subito come un riferimento valido significherebbe
 * promettere qualcosa che nessuno ha ancora controllato — e per ~11 s.
 *
 * Riconosce solo la forma contigua `[n]`, la stessa che il parser accetta: se
 * il modello scrive `[2, 3]` qui non si accende niente, esattamente come non si
 * accende nel backend. Un'interfaccia piu' generosa del contratto mostrerebbe
 * come citazione qualcosa che il contratto ha scartato.
 */
import type { ReactNode } from "react";

const MARCATORE = /\[(\d+)\]/g;

/** I marcatori presenti nel testo, in ordine. Serve al pannello fonti per
 *  sapere quali schede sono state davvero citate. */
export function marcatoriCitati(testo: string): Set<number> {
  const trovati = new Set<number>();
  for (const m of testo.matchAll(MARCATORE)) trovati.add(Number(m[1]));
  return trovati;
}

export function Testo({ testo, vivi }: { testo: string; vivi: boolean }) {
  return (
    <div className="text-[13.5px] leading-[1.66] text-ink">
      {testo.split(/\n{2,}/).map((paragrafo, i) => (
        <p key={i} className="mb-[9px] last:mb-0 whitespace-pre-wrap">
          {spezza(paragrafo, vivi)}
        </p>
      ))}
    </div>
  );
}

function spezza(paragrafo: string, vivi: boolean): ReactNode[] {
  const pezzi: ReactNode[] = [];
  let ultimo = 0;

  for (const m of paragrafo.matchAll(MARCATORE)) {
    const inizio = m.index;
    if (inizio > ultimo) pezzi.push(paragrafo.slice(ultimo, inizio));
    pezzi.push(
      <span
        key={`${inizio}`}
        className={
          vivi
            ? "rounded-[3px] border-b border-accent bg-accent-soft px-[3px] py-px align-[0.32em] font-mono text-[10px] text-accent"
            : "border-b border-dotted border-line-2 px-px align-[0.32em] font-mono text-[10px] text-muted"
        }
      >
        {m[0]}
      </span>,
    );
    ultimo = inizio + m[0].length;
  }

  if (ultimo < paragrafo.length) pezzi.push(paragrafo.slice(ultimo));
  return pezzi;
}
