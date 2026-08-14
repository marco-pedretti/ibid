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
 * Targhette `pipeline`/`doc_genre` e verdetti di citazione non sono qui: sono
 * U-05 e U-07, e ognuno arriva col proprio criterio. Metterli ora significa
 * consegnarli senza il test che li verifica.
 */
import { usaChat } from "../app/chat";
import { usaLingua } from "../app/i18n";
import type { ChunkView } from "../api/types";
import { Etichetta } from "./Etichetta";
import { Estratto, marcatoriCitati } from "./Testo";

export function PannelloFonti() {
  const { t } = usaLingua();
  const { scambi } = usaChat();

  // L'ultimo scambio: le fonti riguardano la risposta che si sta guardando, e
  // quella e' sempre l'ultima. Una cronologia di pannelli sarebbe una seconda
  // navigazione dentro la stessa colonna.
  const ultimo = scambi[scambi.length - 1] ?? null;
  const r = ultimo?.risposta ?? null;
  const chunks = r?.chunks ?? [];
  const citati = marcatoriCitati(r?.testo ?? "");

  return (
    <aside className="flex h-full min-h-0 flex-col gap-[11px] overflow-y-auto border-l border-line bg-surface px-3 py-3.5">
      <div className="flex items-baseline justify-between">
        <Etichetta>{t("sources.title")}</Etichetta>
        {chunks.length > 0 && (
          <span className="font-mono text-[10px] text-muted tabular-nums">{chunks.length}</span>
        )}
      </div>

      {chunks.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line-2 px-3 py-4 text-center text-[11px] leading-[1.5] text-muted">
          {/* Due frasi diverse: «non ho ancora cercato» non e' «ho cercato e non
              c'e' niente». La seconda e' un risultato, e va detta come tale. */}
          {r !== null && !inAttesa(r.fase) ? t("sources.none") : t("sources.waiting")}
        </p>
      ) : (
        <div className="flex flex-col gap-[11px]">
          {chunks.map((c) => (
            <Scheda key={c.chunk_id} chunk={c} citata={citati.has(c.marker)} />
          ))}
        </div>
      )}

      {r !== null && r.senzaCitazione.length > 0 && (
        <div className="mt-1 flex flex-col gap-1.5">
          <Etichetta>{t("sources.uncited")}</Etichetta>
          {/* Il costo nascosto della precisione: la si alza citando di meno, e
              queste sono le frasi che nessuna fonte sostiene. Mostrarle e' cio'
              che impedisce di scambiare la reticenza per accuratezza. */}
          <ul className="flex flex-col gap-1.5">
            {r.senzaCitazione.map((frase, i) => (
              <li
                key={i}
                className="border-b-2 border-dotted border-warn pb-px text-[11px] leading-[1.5] text-ink-2"
              >
                {frase}
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}

function inAttesa(fase: string): boolean {
  return fase === "attesa";
}

function Scheda({ chunk, citata }: { chunk: ChunkView; citata: boolean }) {
  return (
    <article
      className={`flex flex-col gap-1.5 rounded-lg border px-2.5 py-2.5 ${
        citata ? "border-accent bg-accent-soft" : "border-line bg-surface"
      }`}
    >
      <div className="flex items-center gap-1.5">
        <span
          className={`rounded font-mono text-[10px] font-semibold tabular-nums ${
            citata ? "bg-accent text-accent-ink" : "bg-ink text-paper"
          } px-[5px] py-px`}
        >
          {chunk.marker}
        </span>
        <span className="truncate text-[11px] font-medium text-ink" title={chunk.doc_id}>
          {chunk.doc_id}
        </span>
        <span className="ml-auto font-mono text-[10px] text-muted tabular-nums">
          {chunk.score.toFixed(3)}
        </span>
      </div>

      {chunk.section_path !== "" && (
        <p className="truncate font-mono text-[9.5px] text-muted" title={chunk.section_path}>
          {chunk.section_path}
        </p>
      )}

      <Estratto testo={chunk.text} />
    </article>
  );
}
