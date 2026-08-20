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
import { analizza, stiliIn, visibili } from "./markdown";
import type { Blocco as BloccoMd, Nascosto, Stile } from "./markdown";
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
  const { blocchi, annotazioni, stili, nascosti } = useMemo(() => {
    const marcati = marcatoriDelTesto(risposta);
    // **Senza fonti recuperate non c'e' niente da sottolineare.** «Questa frase
    // non cita nessuna fonte» e' un rilievo quando le fonti c'erano e la frase
    // non le ha usate; col RAG spento — e in un'astensione del gate — non ce
    // n'era nessuna, quindi la frase e' vera di ogni riga e non dice niente di
    // nessuna. Sottolineare tutta la colonna la fa anche sembrare *analizzata*,
    // che e' l'opposto di cio' che quella meta' del confronto merita: li' non
    // c'e' un verdetto piu' severo, non c'e' proprio niente da verificare, e a
    // dirlo basta l'avviso — una volta.
    const scoperte = risposta.chunks.length === 0 ? [] : spanSenzaCitazione(risposta);
    const md = analizza(risposta.testo);
    return {
      ...md,
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

  const contesto: Contesto = { testo: risposta.testo, annotazioni, stili, nascosti };

  // I blocchi si raggruppano solo per disegnare `<ul>`/`<ol>`: voci consecutive
  // stanno in un elenco, e senza il raggruppamento sarebbero N elenchi da una
  // voce -- che i lettori di schermo annunciano uno per uno.
  return (
    <div className="flex flex-col gap-2 text-[13.5px] leading-[1.66] text-ink">
      {raggruppa(blocchi).map((g, i) =>
        g.tipo === "elenco" ? (
          <Elenco key={i} voci={g.blocchi} contesto={contesto} />
        ) : (
          <Blocco key={i} blocco={g.blocchi[0]} contesto={contesto} />
        ),
      )}
    </div>
  );
}

/**
 * Del testo qualunque, disegnato come la risposta ma **senza niente sopra**.
 *
 * Serve all'esploratore di U-06: un chunk del corpus ha titoli, elenchi, enfasi
 * e formule esattamente come una risposta, e non ha ne' marcatori di citazione
 * ne' verdetti — perche' nessuno lo ha ancora citato ne' controllato.
 *
 * **Riusa `Testo` invece di rifarlo** passando `annotazioni: []`. Le annotazioni
 * sono l'unica cosa che lega quella macchina alle risposte; tutto il resto —
 * blocchi, tabelle Markdown, matematica, sintassi nascosta — vale per qualunque
 * testo. Una seconda composizione scritta accanto sarebbe divergente al primo
 * caso di bordo, e i casi di bordo qui sono la ragione per cui il modulo esiste.
 */
export function Prosa({ testo }: { testo: string }) {
  const { blocchi, stili, nascosti } = useMemo(() => analizza(testo), [testo]);
  const contesto: Contesto = { testo, annotazioni: [], stili, nascosti };

  return (
    <div className="flex flex-col gap-2">
      {raggruppa(blocchi).map((g, i) =>
        g.tipo === "elenco" ? (
          <Elenco key={i} voci={g.blocchi} contesto={contesto} />
        ) : (
          <Blocco key={i} blocco={g.blocchi[0]} contesto={contesto} />
        ),
      )}
    </div>
  );
}

/** Cio' che serve a ogni pezzo per disegnarsi: il testo grezzo e i quattro
 *  elenchi di intervalli che ci stanno sopra. */
interface Contesto {
  testo: string;
  annotazioni: Annotazione[];
  stili: Stile[];
  nascosti: Nascosto[];
}

type Gruppo = { tipo: "elenco" | "solo"; blocchi: BloccoMd[] };

function raggruppa(blocchi: readonly BloccoMd[]): Gruppo[] {
  const fuori: Gruppo[] = [];
  for (const b of blocchi) {
    const ultimo = fuori[fuori.length - 1];
    if (b.tipo === "voce" && ultimo?.tipo === "elenco") ultimo.blocchi.push(b);
    else fuori.push({ tipo: b.tipo === "voce" ? "elenco" : "solo", blocchi: [b] });
  }
  return fuori;
}

/**
 * I titoli non crescono di corpo, e non e' una svista.
 *
 * Un `##` reso come un titolo grande darebbe alla risposta **senza fonti** una
 * gerarchia visiva che quella con le fonti non ha — e il confronto di U-03
 * esiste per mettere in dubbio proprio quella colonna. Qui un titolo si legge
 * come un titolo (peso, spaziatura, un filo di colore) senza guadagnare
 * autorita' tipografica.
 */
const TITOLO = "font-semibold text-ink";

function Blocco({ blocco, contesto }: { blocco: BloccoMd; contesto: Contesto }) {
  if (blocco.tipo === "tabella") return <Tabella blocco={blocco} contesto={contesto} />;

  const dentro = <Tratto da={blocco.da} a={blocco.a} contesto={contesto} />;
  if (blocco.tipo === "titolo") {
    return <p className={`${TITOLO} ${(blocco.livello ?? 1) <= 2 ? "mt-1" : ""}`}>{dentro}</p>;
  }
  // **Niente `whitespace-pre-wrap`, e non e' una svista.** Prima serviva: senza
  // struttura, gli a capo del modello erano l'unica cosa che separava un
  // paragrafo dal successivo. Ora i paragrafi sono blocchi, e tenere anche i
  // ritorni a capo del sorgente li conta due volte — il testo si spezzava dove
  // il modello era andato a capo per la larghezza della sua riga, non del
  // nostro riquadro, e la colonna veniva fuori sfrangiata accanto a una fatta
  // di elenchi. E' la regola del Markdown: dentro un paragrafo un a capo
  // singolo e' uno spazio; a separare e' la riga vuota, che qui e' gia'
  // diventata un blocco.
  return <p>{dentro}</p>;
}

function Elenco({ voci, contesto }: { voci: BloccoMd[]; contesto: Contesto }) {
  const Tag = voci[0].numerata === true ? "ol" : "ul";
  return (
    <Tag
      className={`flex flex-col gap-1 pl-5 ${
        Tag === "ol" ? "list-decimal" : "list-disc"
      } marker:text-muted`}
    >
      {voci.map((v) => (
        <li key={v.da}>
          <Tratto da={v.da} a={v.a} contesto={contesto} />
        </li>
      ))}
    </Tag>
  );
}

/**
 * Una tabella, e le celle sono intervalli.
 *
 * Un verdetto che attraversa due celle si ritaglia su ciascuna, come gia' fa una
 * frase scoperta a cavallo di due segmenti di formula: e' la stessa scelta, e
 * per la stessa ragione — meta' sottolineatura e' leggibile, nessuna no.
 */
function Tabella({ blocco, contesto }: { blocco: BloccoMd; contesto: Contesto }) {
  const [intestazione, ...corpo] = blocco.righe ?? [];
  if (intestazione === undefined) return null;

  return (
    // Scorre per conto suo: una tabella larga non deve far scorrere la colonna
    // della risposta, che porterebbe via con se' anche il testo.
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[12.5px]">
        <thead>
          <tr>
            {intestazione.map((c) => (
              <th
                key={c.da}
                className="border-b border-line-2 px-2 py-1 text-left font-semibold text-ink"
              >
                <Tratto da={c.da} a={c.a} contesto={contesto} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {corpo.map((riga, i) => (
            <tr key={i}>
              {riga.map((c) => (
                <td key={c.da} className="border-b border-line px-2 py-1 align-top text-ink-2">
                  <Tratto da={c.da} a={c.a} contesto={contesto} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Un tratto di testo grezzo, disegnato con tutto cio' che gli sta sopra.
 *
 * L'ordine e' obbligato. `segmenta` **prima**, e annotare dentro i suoi pezzi:
 * al contrario, un `$x[3]$` — un indice fra quadre dentro una formula, che in un
 * corpus di paper esiste — verrebbe spezzato a meta' e la formula non si
 * comporrebbe piu'. La matematica ha la precedenza perche' un suo errore rompe
 * il disegno, mentre un marcatore mancato resta leggibile.
 */
function Tratto({ da, a, contesto }: { da: number; a: number; contesto: Contesto }) {
  // `segmenta` lavora sulla stringa che riceve, quindi i suoi `da` sono relativi:
  // si riportano sul grezzo sommando `da`. Meglio che aggiungere un parametro a
  // una funzione che ha gia' i suoi test e che qui non deve cambiare.
  const grezzo = contesto.testo.slice(da, a);
  return (
    <>
      {segmenta(grezzo).map((s, i) =>
        s.tipo === "testo" ? (
          <span key={i}>{conStile(s.valore, da + s.da, contesto)}</span>
        ) : (
          <Formula key={i} tex={s.tex} blocco={s.tipo === "blocco"} />
        ),
      )}
    </>
  );
}

/**
 * La prosa di un segmento: prima si tolgono i caratteri di sintassi, poi si
 * spezza per enfasi, e dentro ogni pezzo vanno marcatori e sottolineature.
 *
 * I nascosti si saltano **qui** e non in `analizza` per la ragione di tutto il
 * modulo: togliere caratteri prima sposterebbe gli offset di tutti gli altri
 * intervalli.
 */
function conStile(prosa: string, da: number, contesto: Contesto): ReactNode[] {
  const fine = da + prosa.length;
  const stili = stiliIn(contesto.stili, da, fine);

  // I confini che contano: inizio, fine, e ogni estremo di stile. Fra due
  // confini consecutivi lo stile e' uno solo, perche' `analizza` prende ogni
  // carattere una volta sola -- quindi gli stili non si annidano e un taglio
  // secco basta. Con l'annidamento servirebbe un albero, e non e' il caso.
  const confini = [...new Set([da, fine, ...stili.flatMap((s) => [s.da, s.a])])].sort(
    (x, y) => x - y,
  );

  const pezzi: ReactNode[] = [];
  for (let k = 0; k + 1 < confini.length; k += 1) {
    const [inizio, termine] = [confini[k], confini[k + 1]];
    const dentro = visibili(inizio, termine, contesto.nascosti).flatMap((v) =>
      annota(contesto.testo.slice(v.da, v.a), v.da, contesto.annotazioni),
    );
    if (dentro.length === 0) continue;

    const stile = stili.find((s) => s.da <= inizio && s.a >= termine);
    pezzi.push(
      stile === undefined ? (
        <span key={inizio}>{dentro}</span>
      ) : (
        <span key={inizio} className={VESTE_STILE[stile.tipo]}>
          {dentro}
        </span>
      ),
    );
  }
  return pezzi;
}

const VESTE_STILE: Record<Stile["tipo"], string> = {
  forte: "font-semibold text-ink",
  enfasi: "italic",
  // In mono e su fondo, come ogni altro dato di questa interfaccia (§12).
  codice: "rounded bg-surface-2 px-1 py-px font-mono text-[11.5px]",
};

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
