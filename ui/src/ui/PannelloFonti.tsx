/**
 * Le fonti. **Sempre visibili, senza interazione** — e' il criterio di U-02.
 *
 * Non e' un pannello che si apre: e' una colonna che c'e' in ogni stato, anche
 * prima della prima domanda, dove dice cosa comparira'. Un pannello da aprire
 * renderebbe le fonti una funzione avanzata, quando sono la tesi del progetto.
 *
 * **Si riempie su `chunks`, non a risposta finita.** Il §3.5 manda le fonti
 * prima del primo token: misurate a caldo, 0,27 s contro 3,01 s. L'attesa si
 * riempie invece di premiare, e si vede da dove nasce la risposta mentre nasce.
 *
 * **Ogni scheda porta il proprio verdetto e nessuna viene toccata** (U-07). Una
 * fonte che non sostiene quello che le e' stato attribuito resta al suo posto,
 * marcata: togliere le non sostenute porterebbe la precisione apparente al 100%
 * per costruzione, proprio nel punto in cui il progetto vuole essere misurato.
 *
 * **Le frasi senza citazione sono uscite da qui** e sono tornate dove stanno:
 * sottolineate nella risposta. U-02 le aveva messe in fondo al pannello perche'
 * non c'era un altro posto, ma una frase che non cita niente non e' una fonte, e
 * in una colonna larga 272 px prendeva lo spazio delle fonti vere. Nel testo si
 * legge *dove* manca la citazione, che e' l'unica cosa che serve saperne.
 *
 * **Come il documento e' stato spezzato sta sulla scheda** (U-05), sotto la
 * testata e nel posto in cui stava `section_path`: e' una proprieta' del
 * documento da cui la fonte viene, non un giudizio su di essa, quindi non va in
 * fondo accanto ai verdetti. Si legge in mono e attenuata come tutto cio' che e'
 * un dato, e prende l'accento **solo quando una pipeline e' stata scelta per il
 * genere** — cioe' quando c'e' un routing da vedere.
 */
import { usaChat } from "../app/chat";
import { usaEsploratore } from "../app/esploratore";
import { nomeGenere, nomeTaglio, taglioPerGenere } from "../app/genere";
import { usaLingua } from "../app/i18n";
import { spiegaPunteggio } from "../app/recupero";
import { esitoDellaScheda, esitoNumericoDellaScheda } from "../app/verdetti";
import type { Risposta } from "../app/conversazione";
import type { ChunkView } from "../api/types";
import { zona } from "./Avvio";
import { Etichetta } from "./Etichetta";
import { Suggerimento } from "./Suggerimento";
import { Estratto, marcatoriCitati } from "./Testo";
import { Verdetto, VerdettoNumerico } from "./Verdetto";

/**
 * La risposta di cui le fonti parlano: sempre l'ultima.
 *
 * Le fonti riguardano la risposta che si sta guardando, e quella e' sempre
 * l'ultima. Una cronologia di pannelli sarebbe una seconda navigazione dentro
 * la stessa colonna.
 *
 * E' un hook esportato perche' da U-21 la stessa domanda se la fa anche la
 * testata a colonna sola, che sul proprio comando mostra **quante** fonti sono
 * arrivate. Due volte «l'ultimo scambio» scritto a mano sono due posti che
 * divergono il giorno in cui l'ultimo non e' piu' quello giusto.
 */
export function usaUltimaRisposta(): Risposta | null {
  const { scambi } = usaChat();
  return scambi[scambi.length - 1]?.risposta ?? null;
}

export function PannelloFonti() {
  const { t } = usaLingua();
  const r = usaUltimaRisposta();

  return (
    <aside
      {...zona("fonti")}
      className="flex h-full min-h-0 flex-col gap-[11px] overflow-y-auto border-l border-line bg-surface px-3 py-3.5"
    >
      <div className="flex items-baseline justify-between">
        <Etichetta>{t("sources.title")}</Etichetta>
        {(r?.chunks.length ?? 0) > 0 && (
          <Suggerimento
            dato
            testo={t("sources.count")}
            className="font-mono text-[10px] text-muted tabular-nums"
          >
            {r?.chunks.length}
          </Suggerimento>
        )}
      </div>

      <Schede risposta={r} />
    </aside>
  );
}

/**
 * Le schede delle fonti di **una** risposta, senza la cornice del pannello.
 *
 * Separata perche' le fonti compaiono in due posti: qui nella colonna di
 * fianco, e dentro la colonna «con le fonti» del confronto, dove il pannello
 * laterale non c'e' — e' proprio la loro presenza da una parte e la loro assenza
 * dall'altra a essere l'argomento di quella schermata.
 */
export function Schede({ risposta: r }: { risposta: Risposta | null }) {
  const { t } = usaLingua();
  const chunks = r?.chunks ?? [];
  const citati = marcatoriCitati(r?.testo ?? "");

  if (chunks.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-line-2 px-3 py-4 text-center text-[11px] leading-[1.5] text-muted">
        {/* Due frasi diverse: «non ho ancora cercato» non e' «ho cercato e non
            c'e' niente». La seconda e' un risultato, e va detta come tale. */}
        {r !== null && !inAttesa(r.fase) ? t("sources.none") : t("sources.waiting")}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-[11px]">
      {chunks.map((c) => (
        <Scheda key={c.chunk_id} chunk={c} citata={citati.has(c.marker)} risposta={r} />
      ))}
    </div>
  );
}

function inAttesa(fase: string): boolean {
  return fase === "attesa";
}

/**
 * Riconosciuto come X, tagliato Y — la decisione di routing, sulla fonte.
 *
 * **Le due meta' insieme.** La pipeline da sola non dice in base a cosa e' stata
 * scelta, e il genere da solo non dice cosa se n'e' fatto. Il criterio di U-05 e'
 * «rende visibile il routing», e il routing e' la freccia fra i due.
 *
 * **L'accento solo quando c'e' un routing da vedere.** Con l'indice generico
 * ogni documento riceve lo stesso taglio, e una targhetta accesa cinque volte
 * uguale su cinque schede smetterebbe di essere letta — e' la regola del
 * riepilogo dei verdetti e della riga dei parametri. Il genere invece cambia
 * scheda per scheda anche li': su `open_ragbench` un documento su nove e' fatto
 * di tabelle, e vederlo accanto a quattro paper e' meta' della domanda che
 * questo progetto misura.
 *
 * Un valore che non conosciamo si mostra com'e' e senza spiegazione: tradurre un
 * genere aggiunto domani direbbe una cosa che nessuno ha verificato.
 */
function Taglio({ chunk }: { chunk: ChunkView }) {
  const { t } = usaLingua();
  const genere = nomeGenere(chunk.doc_genre);
  const taglio = nomeTaglio(chunk.pipeline);
  if (chunk.doc_genre === "" && chunk.pipeline === "") return null;

  const scelto = taglioPerGenere(chunk.pipeline);
  const parole = {
    genere: genere === null ? chunk.doc_genre : t(genere),
    taglio: taglio === null ? chunk.pipeline : t(taglio),
  };

  return (
    <p className="min-w-0">
      <Suggerimento
        dato
        testo={`${t("source.pipeline.hint", parole)} ${t(
          scelto ? "source.pipeline.routed" : "source.pipeline.generic",
        )}`}
        className={`block truncate font-mono text-[9.5px] ${scelto ? "text-accent" : "text-muted"}`}
      >
        {parole.genere} → {parole.taglio}
      </Suggerimento>
    </p>
  );
}

function Scheda({
  chunk,
  citata,
  risposta,
}: {
  chunk: ChunkView;
  citata: boolean;
  risposta: Risposta | null;
}) {
  const { t } = usaLingua();
  const { apri: apriNelCorpus } = usaEsploratore();
  const numerico = risposta === null ? null : esitoNumericoDellaScheda(risposta, chunk.marker);

  return (
    <article
      className={`flex flex-col gap-1.5 rounded-lg border px-2.5 py-2.5 ${
        citata ? "border-accent bg-accent-soft" : "border-line bg-surface"
      }`}
    >
      <div className="flex items-center gap-1.5">
        <Suggerimento
          dato
          testo={t("score.marker", { marker: chunk.marker })}
          className={`rounded font-mono text-[10px] font-semibold tabular-nums ${
            citata ? "bg-accent text-accent-ink" : "bg-ink text-paper"
          } px-[5px] py-px`}
        >
          {chunk.marker}
        </Suggerimento>
        {/* Il nome del documento e' **troncato** in 272 px, ed e' il posto dove
            un suggerimento serve piu' che altrove: qui non spiega, mostra cio'
            che il taglio ha nascosto.

            Da U-06 e' anche il modo di arrivare alla fonte intera: la scheda ne
            mostra due righe, e il chunk citato puo' essere lungo seimila
            caratteri. Il nome del documento e' il posto giusto perche' e' gia'
            cio' che si guarda per sapere da dove viene — non serve un comando
            in piu' su una colonna larga 272 px. */}
        <Suggerimento
          dato
          fuoco={false}
          testo={`${chunk.doc_id} — ${t("corpus.fromCitation")}`}
          className="min-w-0"
        >
          <button
            type="button"
            onClick={() => apriNelCorpus(chunk.doc_id, chunk.chunk_id)}
            className="block w-full truncate text-left text-[11px] font-medium text-ink transition-colors hover:text-accent"
          >
            {chunk.doc_id}
          </button>
        </Suggerimento>
        {/* Cosa sia questo numero **dipende dalla configurazione che ha girato**:
            una somiglianza in `dense`, un punteggio di posizione in `hybrid`, il
            giudizio di un cross-encoder col rerank. Un'etichetta sola sarebbe vera
            e inutile — 0,875 e 0,016 possono essere due fonti ottime. */}
        <Suggerimento
          dato
          testo={t(spiegaPunteggio(risposta?.config ?? null))}
          className="ml-auto font-mono text-[10px] text-muted tabular-nums"
        >
          {chunk.score.toFixed(3)}
        </Suggerimento>
      </div>

      <Taglio chunk={chunk} />

      {chunk.section_path !== "" && (
        <p className="min-w-0">
          <Suggerimento
            dato
            testo={chunk.section_path}
            className="block truncate font-mono text-[9.5px] text-muted"
          >
            {chunk.section_path}
          </Suggerimento>
        </p>
      )}

      <Estratto testo={chunk.text} />

      {/* Il verdetto sta **in fondo** e non nella testata: la testata dice quale
          fonte e' (marcatore, documento, punteggio di recupero), il verdetto dice
          cosa se n'e' fatto. Sopra l'estratto sembrerebbe un giudizio sul chunk;
          sotto e' quello che e', un giudizio sulla frase che lo cita. */}
      {risposta !== null && (
        <div className="flex flex-wrap gap-1.5">
          <Verdetto esito={esitoDellaScheda(risposta, chunk.marker)} />
          {/* Il verdetto numerico di C-09 **accanto** e non al posto dell'altro:
              e' additivo per contratto (`schema.py`), e su un corpus di tabelle
              e' quello che sa giudicare. Compare solo quando ha giudicato. */}
          {numerico !== null && <VerdettoNumerico esito={numerico} />}
        </div>
      )}
    </article>
  );
}
