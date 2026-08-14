/**
 * Il testo della risposta: marcatori riconosciuti, formule disegnate.
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
 *
 * **Le formule si disegnano con KaTeX** (MIT, in `STACK.md`). Il corpus dei
 * paper ne e' pieno: 452 formule su 2000 risposte di riferimento. La divisione
 * fra prosa e TeX sta in `matematica.ts`, provata a parte, perche' e' la parte
 * che puo' sbagliare — e sbagliare significa scambiare due prezzi per una
 * formula.
 *
 * Niente `<p>`: i paragrafi vengono da `whitespace-pre-wrap`. Con blocchi e
 * formule mescolati, avvolgere la prosa in paragrafi lascerebbe le formule
 * *fuori* dal paragrafo, cioe' spezzerebbe la riga dove il testo non va a capo.
 */
import katex from "katex";
import "katex/dist/katex.min.css";
import { useMemo } from "react";
import type { ReactNode } from "react";

import { segmenta } from "./matematica";

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
    <div className="text-[13.5px] leading-[1.66] whitespace-pre-wrap text-ink">
      {segmenta(testo).map((s, i) =>
        s.tipo === "testo" ? (
          <span key={i}>{conMarcatori(s.valore, vivi)}</span>
        ) : (
          <Formula key={i} tex={s.tex} blocco={s.tipo === "blocco"} />
        ),
      )}
    </div>
  );
}

/**
 * L'estratto di un chunk nel pannello fonti: **stessa matematica, nessun
 * marcatore**.
 *
 * I `[12]` che compaiono qui sono i riferimenti bibliografici del documento —
 * il prompt del §3.2 avverte il modello di non copiarli — e accenderli come
 * citazioni direbbe che il documento cita se' stesso attraverso di noi.
 */
export function Estratto({ testo }: { testo: string }) {
  return (
    <p className="line-clamp-2 text-[11px] leading-[1.5] text-ink-2">
      {segmenta(testo).map((s, i) =>
        s.tipo === "testo" ? (
          <span key={i}>{s.valore}</span>
        ) : (
          // Anche una formula in display resta in linea: la scheda e' tagliata a
          // due righe, e un blocco centrato le farebbe saltare entrambe.
          <Formula key={i} tex={s.tex} blocco={false} />
        ),
      )}
    </p>
  );
}

function Formula({ tex, blocco }: { tex: string; blocco: boolean }) {
  const html = useMemo(
    () =>
      katex.renderToString(tex, {
        displayMode: blocco,
        // Non solleva: una formula che KaTeX non capisce si disegna in colore
        // d'avviso col suo sorgente, che e' l'unica cosa onesta da mostrare —
        // il testo c'era, non siamo riusciti a comporlo.
        throwOnError: false,
        // `trust: false` e' il default e resta: senza, `\href` e `\htmlClass`
        // permetterebbero a un testo **generato dal modello** di iniettare
        // markup nella pagina.
        trust: false,
        strict: false,
      }),
    [tex, blocco],
  );

  return (
    <span
      className={blocco ? "my-1 block overflow-x-auto" : ""}
      // L'HTML e' prodotto da KaTeX con `trust: false`, non dal modello.
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function conMarcatori(prosa: string, vivi: boolean): ReactNode[] {
  const pezzi: ReactNode[] = [];
  let ultimo = 0;

  for (const m of prosa.matchAll(MARCATORE)) {
    const inizio = m.index;
    if (inizio > ultimo) pezzi.push(prosa.slice(ultimo, inizio));
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

  if (ultimo < prosa.length) pezzi.push(prosa.slice(ultimo));
  return pezzi;
}
