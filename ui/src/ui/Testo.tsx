/**
 * Il testo della risposta: marcatori col loro verdetto, formule disegnate.
 *
 * **I marcatori sono inerti finche' `answer` non arriva**, ed e' una regola del
 * §3.5 e non una scelta grafica: mentre i token scorrono, `[2]` compare prima
 * che il suo verdetto esista, e prima ancora che il parser abbia potuto
 * normalizzarlo. Disegnarlo subito come un riferimento valido significherebbe
 * promettere qualcosa che nessuno ha ancora controllato — e per ~11 s.
 *
 * **Poi ognuno porta il proprio verdetto** (U-07): sostenuta, non sostenuta, non
 * verificata, ciascuna distinguibile dalle altre senza aprire niente, e nessuna
 * nascosta. Chi decide quale verdetto tocca a quale occorrenza e' `verdetti.ts`,
 * qui si disegna — l'ordine importa perche' quella decisione ha dei test e questo
 * file no.
 *
 * **La frase che non cita niente e' sottolineata dove sta**, non solo elencata
 * nel pannello. E' il denominatore nascosto della precisione: si alza citando di
 * meno, e vederla in mezzo alla risposta e' cio' che impedisce di scambiare la
 * reticenza per accuratezza.
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

import { marcatoriDelTesto, spanSenzaCitazione } from "../app/verdetti";
import type { Marcato, Span } from "../app/verdetti";
import type { Risposta } from "../app/conversazione";
import { perAnteprima, segmenta } from "./matematica";
import { Marcatore } from "./Verdetto";

const MARCATORE = /\[(\d+)\]/g;

/** I marcatori presenti nel testo, in ordine. Serve al pannello fonti per
 *  sapere quali schede sono state davvero citate. */
export function marcatoriCitati(testo: string): Set<number> {
  const trovati = new Set<number>();
  for (const m of testo.matchAll(MARCATORE)) trovati.add(Number(m[1]));
  return trovati;
}

export function Testo({ risposta }: { risposta: Risposta }) {
  // `segmenta` **prima**, e annotare dentro i suoi pezzi: al contrario, un
  // `$x[3]$` -- un indice fra quadre dentro una formula, che in un corpus di
  // paper esiste -- verrebbe spezzato a meta' e la formula non si comporrebbe
  // piu'. La matematica ha la precedenza perche' un suo errore rompe il disegno,
  // mentre un marcatore mancato resta leggibile.
  const { segmenti, annotazioni } = useMemo(() => {
    const marcati = marcatoriDelTesto(risposta);
    const scoperte = spanSenzaCitazione(risposta);
    return {
      segmenti: segmenta(risposta.testo),
      // Le due specie non si annidano mai: una frase «senza citazione» e' per
      // definizione una frase senza marcatori. Quindi una lista piatta, ordinata,
      // basta -- e non serve un albero di intervalli.
      annotazioni: ordina([
        ...marcati.map((m): Annotazione => ({
          da: m.indice,
          a: m.indice + m.lunghezza,
          marcato: m,
        })),
        ...scoperte.map((s): Annotazione => ({ ...s, marcato: null })),
      ]),
    };
  }, [risposta]);

  return (
    <div className="text-[13.5px] leading-[1.66] whitespace-pre-wrap text-ink">
      {segmenti.map((s, i) =>
        s.tipo === "testo" ? (
          <span key={i}>{annota(s.valore, s.da, annotazioni)}</span>
        ) : (
          <Formula key={i} tex={s.tex} blocco={s.tipo === "blocco"} />
        ),
      )}
    </div>
  );
}

/** Un tratto di testo che va disegnato diversamente. `marcato: null` = una frase
 *  che non cita niente. */
interface Annotazione extends Span {
  marcato: Marcato | null;
}

function ordina(a: Annotazione[]): Annotazione[] {
  return a.sort((x, y) => x.da - y.da);
}

/**
 * La prosa di un segmento, coi tratti annotati al loro posto.
 *
 * Gli intervalli si **ritagliano** sul segmento invece di essere scartati: una
 * frase scoperta che contiene una formula sta a cavallo di due segmenti, e
 * scartarla la lascerebbe senza sottolineatura proprio nella meta' che si legge.
 */
function annota(prosa: string, da: number, annotazioni: Annotazione[]): ReactNode[] {
  const fine = da + prosa.length;
  const pezzi: ReactNode[] = [];
  let i = da;

  for (const ann of annotazioni) {
    if (ann.a <= i || ann.da >= fine) continue;
    const inizio = Math.max(ann.da, i);
    const termine = Math.min(ann.a, fine);
    if (inizio > i) pezzi.push(prosa.slice(i - da, inizio - da));

    if (ann.marcato !== null) {
      pezzi.push(<Marcatore key={ann.da} marcato={ann.marcato} />);
    } else {
      pezzi.push(
        <span key={`s${ann.da}`} className="border-b-2 border-dotted border-warn pb-px">
          {prosa.slice(inizio - da, termine - da)}
        </span>,
      );
    }
    i = termine;
  }

  if (i < fine) pezzi.push(prosa.slice(i - da));
  return pezzi;
}

/**
 * L'estratto di un chunk nel pannello fonti: **stessa matematica, nessun
 * marcatore**.
 *
 * I `[12]` che compaiono qui sono i riferimenti bibliografici del documento —
 * il prompt del §3.2 avverte il modello di non copiarli — e accenderli come
 * citazioni direbbe che il documento cita se' stesso attraverso di noi.
 *
 * Il testo passa da `perAnteprima`, che toglie i cancelletti dei titoli e i tag
 * delle tabelle: **il 100%** dei chunk di `open_ragbench` comincia con un titolo
 * Markdown e **il 39%** di quelli di `ledger` porta HTML. E' una riduzione per
 * una scheda alta due righe, non una modifica del dato.
 */
export function Estratto({ testo }: { testo: string }) {
  return (
    <p className="line-clamp-2 text-[11px] leading-[1.5] text-ink-2">
      {segmenta(perAnteprima(testo)).map((s, i) =>
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
