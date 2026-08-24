/**
 * Il testo della risposta: marcatori col loro verdetto, formule disegnate.
 *
 * **Qui si disegna soltanto.** Quali pezzi ci sono, in che ordine e con che
 * veste lo decide `composizione.ts`, che non produce nodi e quindi ha dei test
 * (D-8): questo file prende quella lista e le mette addosso delle classi. La
 * separazione non e' formale — l'incrocio fra markdown, matematica, marcatori e
 * verdetti e' la parte che si puo' sbagliare senza che si veda, e finche' e'
 * stata scritta in JSX si e' potuta verificare solo a schermo.
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
 * qui si disegna.
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

import type { Risposta } from "../app/conversazione";
import { annotazioni, componi, raggruppa } from "./composizione";
import type { Contesto, Pezzo } from "./composizione";
import { analizza } from "./markdown";
import type { Blocco as BloccoMd, Stile } from "./markdown";
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
  const { blocchi, contesto } = useMemo(() => {
    const md = analizza(risposta.testo);
    const contesto: Contesto = {
      testo: risposta.testo,
      annotazioni: annotazioni(risposta),
      stili: md.stili,
      nascosti: md.nascosti,
    };
    return { blocchi: md.blocchi, contesto };
  }, [risposta]);

  return <Composto blocchi={blocchi} contesto={contesto} spaziata />;
}

/**
 * Del testo qualunque, disegnato come la risposta ma **senza niente sopra**.
 *
 * Serve all'esploratore di U-06: un chunk del corpus ha titoli, elenchi, enfasi
 * e formule esattamente come una risposta, e non ha ne' marcatori di citazione
 * ne' verdetti — perche' nessuno lo ha ancora citato ne' controllato.
 *
 * **Riusa la stessa macchina invece di rifarla** passando `annotazioni: []`. Le
 * annotazioni sono l'unica cosa che lega quella macchina alle risposte; tutto il
 * resto — blocchi, tabelle Markdown, matematica, sintassi nascosta — vale per
 * qualunque testo. Una seconda composizione scritta accanto sarebbe divergente
 * al primo caso di bordo, e i casi di bordo qui sono la ragione per cui il
 * modulo esiste.
 */
export function Prosa({ testo }: { testo: string }) {
  const { blocchi, contesto } = useMemo(() => {
    const md = analizza(testo);
    const contesto: Contesto = {
      testo,
      annotazioni: [],
      stili: md.stili,
      nascosti: md.nascosti,
    };
    return { blocchi: md.blocchi, contesto };
  }, [testo]);

  return <Composto blocchi={blocchi} contesto={contesto} spaziata={false} />;
}

/** I blocchi, disegnati. `spaziata` distingue la colonna di una risposta — che
 *  ha il proprio corpo e la propria interlinea — dal testo di un chunk, che
 *  eredita quelli di chi lo ospita. */
function Composto({
  blocchi,
  contesto,
  spaziata,
}: {
  blocchi: readonly BloccoMd[];
  contesto: Contesto;
  spaziata: boolean;
}) {
  return (
    <div
      className={`flex flex-col gap-2 ${spaziata ? "text-[13.5px] leading-[1.66] text-ink" : ""}`}
    >
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

  const dentro = <Pezzi da={blocco.da} a={blocco.a} contesto={contesto} />;
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
          <Pezzi da={v.da} a={v.a} contesto={contesto} />
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
                <Pezzi da={c.da} a={c.a} contesto={contesto} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {corpo.map((riga, i) => (
            <tr key={i}>
              {riga.map((c) => (
                <td key={c.da} className="border-b border-line px-2 py-1 align-top text-ink-2">
                  <Pezzi da={c.da} a={c.a} contesto={contesto} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Un tratto di testo grezzo, coi suoi pezzi al loro posto. */
function Pezzi({ da, a, contesto }: { da: number; a: number; contesto: Contesto }) {
  return (
    <>
      {componi(da, a, contesto).map((p) => (
        <Disegno key={`${p.tipo}-${p.da}`} pezzo={p} />
      ))}
    </>
  );
}

const VESTE_STILE: Record<Stile["tipo"], string> = {
  forte: "font-semibold text-ink",
  enfasi: "italic",
  // In mono e su fondo, come ogni altro dato di questa interfaccia (§12).
  codice: "rounded bg-surface-2 px-1 py-px font-mono text-[11.5px]",
};

/** La frase che non cita nessuna fonte. Punteggiata e in colore d'avviso: non e'
 *  un errore, e' un tratto di risposta che nessuno ha potuto verificare. */
const SCOPERTO = "border-b-2 border-dotted border-warn pb-px";

function Disegno({ pezzo }: { pezzo: Pezzo }) {
  if (pezzo.tipo === "formula") return <Formula tex={pezzo.tex} blocco={pezzo.blocco} />;

  const veste = pezzo.veste === null ? "" : VESTE_STILE[pezzo.veste];
  if (pezzo.tipo === "marcatore") {
    return (
      <span className={veste}>
        <Marcatore marcato={pezzo.marcato} />
      </span>
    );
  }
  const classi = `${veste} ${pezzo.scoperto ? SCOPERTO : ""}`.trim();
  return <span className={classi}>{pezzo.testo}</span>;
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
