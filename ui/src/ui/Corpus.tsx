/**
 * L'esploratore del corpus: quali documenti ci sono, e come sono stati spezzati.
 *
 * **Non e' la dashboard**, e la didascalia del mockup lo dice meglio di
 * qualunque parafrasi: qui non si confrontano configurazioni, si guarda il
 * corpus — cioe' si rende visibile il routing a chi non sa cosa sia un nDCG.
 *
 * Tre colonne, dal mockup: i documenti, com'e' stato spezzato quello aperto, e
 * il chunk scelto **per intero**. L'ultima e' la ragione per cui U-06 esiste: la
 * scheda del pannello fonti mostra due righe, e il chunk che risponde alla
 * domanda sui crediti di Sherwin-Williams e' lungo 6.302 caratteri. Verificare
 * una citazione vuol dire leggerli tutti.
 *
 * **La mappa e' il pezzo che non si poteva disegnare prima di U-05.** Ogni
 * tessera e' un chunk, e la sua larghezza dice cosa contiene: una tabella non
 * viene mai spezzata, quindi occupa il doppio. Guardare due documenti dello
 * stesso corpus e vedere due mappe diverse e' l'affermazione 2 del §0 senza una
 * tabella di numeri.
 *
 * **Niente pagina renderizzata, e non e' solo I-06.** Su nessuno dei due corpus
 * esiste un PDF: `open_ragbench` ha il JSON degli articoli, `ledger` il Markdown
 * di Mathpix. Si dichiara nella colonna di destra invece di disegnare un
 * riquadro grigio che promette qualcosa — «dichiararlo, non simularlo» sta nel
 * criterio.
 */
import { useMemo, useState } from "react";
import type { ReactNode } from "react";

import type { ChunkView } from "../api/types";
import { filtra, indirizzo } from "../app/corpus";
import { usaEsploratore } from "../app/esploratore";
import { usaDataset } from "../app/dataset";
import { nomeGenere, nomeTaglio, taglioPerGenere } from "../app/genere";
import { usaLingua } from "../app/i18n";
import { Etichetta } from "./Etichetta";
import { Esterno, Indietro, Lente } from "./Icona";
import { Suggerimento } from "./Suggerimento";
import { pezzi } from "./tabellaHtml";
import type { Cella } from "./tabellaHtml";
import { Prosa } from "./Testo";

export function Corpus() {
  const { t } = usaLingua();
  const { chiudi } = usaEsploratore();
  const { scelto: dataset } = usaDataset();

  return (
    <div className="flex h-full min-h-0 flex-col bg-paper">
      <div className="flex shrink-0 items-start gap-3 border-b border-line px-[22px] py-3">
        <div className="min-w-0 flex-1">
          <Etichetta>{t("corpus.title")}</Etichetta>
          <p className="mt-1 text-[13px] text-ink">
            {t("corpus.subtitle", { dataset: dataset?.dataset_id ?? "—" })}
          </p>
        </div>
        <button
          type="button"
          onClick={chiudi}
          className="flex shrink-0 items-center gap-1.5 rounded-md border border-line-2 px-[9px] py-[5px] text-[11px] text-ink-2 transition-colors hover:border-accent-2 hover:text-ink"
        >
          <Indietro size={12} />
          {t("corpus.back")}
        </button>
      </div>

      {/* Le tre colonne del mockup. `grid-rows-[minmax(0,1fr)]` per la ragione
          di sempre: senza una riga dichiarata quella implicita e' `auto`, e a
          scorrere sarebbe la pagina invece delle colonne. */}
      <div className="grid min-h-0 flex-1 grid-cols-[210px_1fr_290px] grid-rows-[minmax(0,1fr)] divide-x divide-line overflow-hidden">
        <Documenti />
        <Mappa />
        <Dettaglio />
      </div>
    </div>
  );
}

/** L'elenco dei documenti, con la ricerca sopra: 494 su `ledger`, e un elenco
 *  cosi' non si scorre, si interroga. */
function Documenti() {
  const { t } = usaLingua();
  const { elenco, documento, apri } = usaEsploratore();
  const [cerca, setCerca] = useState("");

  const visibili = useMemo(
    () => (elenco.stato === "pronto" ? filtra(elenco.documenti, cerca) : []),
    [elenco, cerca],
  );
  const apertoOra = documento.stato === "nessuno" ? null : documento.doc_id;

  return (
    <section className="flex min-h-0 flex-col gap-2.5 px-3 py-3.5">
      <Etichetta>{t("corpus.documents")}</Etichetta>

      <label className="flex items-center gap-2 rounded-lg border border-line-2 bg-surface px-2.5 py-1.5">
        <Lente size={12} className="text-muted" />
        <input
          value={cerca}
          onChange={(e) => setCerca(e.target.value)}
          placeholder={t("corpus.search")}
          className="min-w-0 flex-1 bg-transparent text-[11.5px] text-ink outline-none placeholder:text-muted"
        />
      </label>

      {elenco.stato === "caricamento" && (
        <p className="font-mono text-[10px] text-muted">{t("corpus.loading")}</p>
      )}
      {elenco.stato === "guasto" && (
        <p className="font-mono text-[10px] break-all text-warn">{elenco.errore}</p>
      )}

      {elenco.stato === "pronto" && (
        <>
          {/* Quanti se ne stanno vedendo, e su quanti. Senza, filtrando si perde
              la misura del corpus — che e' meta' di cio' che si e' venuti a
              guardare. */}
          <p className="font-mono text-[9.5px] text-muted tabular-nums">
            {t("corpus.count", { visti: visibili.length, tutti: elenco.documenti.length })}
          </p>
          <div className="-mx-1 min-h-0 flex-1 overflow-y-auto px-1">
            {visibili.map((d) => (
              <button
                key={d.doc_id}
                type="button"
                onClick={() => apri(d.doc_id)}
                aria-current={d.doc_id === apertoOra}
                className={`flex w-full flex-col gap-[3px] rounded-[7px] border px-2 py-[7px] text-left transition-colors ${
                  d.doc_id === apertoOra
                    ? "border-accent bg-accent-soft"
                    : "border-transparent hover:border-line-2"
                }`}
              >
                <b className="truncate text-[11.5px] font-medium text-ink">{d.doc_id}</b>
                <span className="font-mono text-[10px] text-muted tabular-nums">
                  {t("corpus.chunks", { n: d.n_chunks })}
                </span>
              </button>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

/**
 * Com'e' stato spezzato: una tessera per chunk.
 *
 * **La larghezza porta l'informazione**, non solo il colore: una tabella non
 * viene mai spezzata e occupa il doppio. Il colore da solo si perderebbe per chi
 * non lo distingue, ed e' la stessa regola dei verdetti in U-07 — glifo, colore
 * e parola insieme, mai uno solo.
 */
function Mappa() {
  const { t } = usaLingua();
  const { documento, scelto, scegliChunk } = usaEsploratore();

  if (documento.stato === "nessuno") {
    return (
      <section className="flex min-h-0 flex-col justify-center px-[18px] py-4">
        <p className="text-center text-[12px] text-muted">{t("corpus.pickDocument")}</p>
      </section>
    );
  }

  if (documento.stato !== "pronto") {
    return (
      <section className="flex min-h-0 flex-col gap-3 px-[18px] py-4">
        <Etichetta>{t("corpus.howSplit")}</Etichetta>
        {documento.stato === "caricamento" ? (
          <p className="font-mono text-[11px] text-muted">
            <span className="mr-2 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-accent align-middle" />
            {t("corpus.loading")}
          </p>
        ) : (
          <p className="font-mono text-[10px] break-all text-warn">{documento.errore}</p>
        )}
      </section>
    );
  }

  const chunks = documento.chunks;
  // Genere e pipeline sono proprieta' del **documento**: il primo chunk le porta
  // come tutti gli altri, e leggerle da li' evita di ripetere la stessa domanda
  // duecentosessantuno volte.
  const primo = chunks[0];
  const perGenere = primo !== undefined && taglioPerGenere(primo.pipeline);

  return (
    <section className="flex min-h-0 flex-col gap-3.5 overflow-y-auto px-[18px] py-4">
      <div>
        <Etichetta>{t("corpus.howSplit")}</Etichetta>
        <p className="mt-1 font-mono text-[10px] text-muted tabular-nums">
          {t("corpus.chunks", { n: chunks.length })}
        </p>
      </div>

      <div className="flex flex-wrap gap-[3px]">
        {chunks.map((c) => (
          <Tessera
            key={c.chunk_id}
            chunk={c}
            scelta={c.chunk_id === scelto}
            onClick={() => scegliChunk(c.chunk_id)}
          />
        ))}
      </div>

      <div className="flex gap-3 font-mono text-[10px] text-muted">
        <Voce quadro="border-line-2 bg-surface-2">{t("corpus.legend.text")}</Voce>
        <Voce quadro="border-accent-2 bg-accent-soft">
          {t(perGenere ? "corpus.legend.table.routed" : "corpus.legend.table")}
        </Voce>
      </div>

      {primo !== undefined && <Spiegazione chunk={primo} />}
    </section>
  );
}

/** Una tessera: un chunk, largo il doppio se contiene una tabella. */
function Tessera({
  chunk,
  scelta,
  onClick,
}: {
  chunk: ChunkView;
  scelta: boolean;
  onClick: () => void;
}) {
  const tabella = chunk.content_type === "table" || chunk.content_type === "mixed";

  return (
    <Suggerimento dato testo={`${chunk.chunk_id} · ${chunk.content_type}`} fuoco={false}>
      <button
        type="button"
        onClick={onClick}
        aria-label={chunk.chunk_id}
        aria-current={scelta}
        className={`h-[22px] rounded-[3px] border transition-colors ${
          tabella
            ? "w-[26px] border-accent-2 bg-accent-soft"
            : "w-[13px] border-line-2 bg-surface-2"
        } ${scelta ? "outline-2 outline-offset-1 outline-accent" : "hover:border-accent"}`}
      />
    </Suggerimento>
  );
}

function Voce({ quadro, children }: { quadro: string; children: ReactNode }) {
  return (
    <span className="flex items-center gap-1.5">
      <i className={`inline-block h-[9px] w-[9px] rounded-[2px] border ${quadro}`} />
      {children}
    </span>
  );
}

/** Perche' questo documento e' stato spezzato cosi'. Il riquadro neutro del
 *  mockup, con le parole di U-05 invece dei nomi interni. */
function Spiegazione({ chunk }: { chunk: ChunkView }) {
  const { t } = usaLingua();
  const genere = nomeGenere(chunk.doc_genre);
  const taglio = nomeTaglio(chunk.pipeline);
  const scelto = taglioPerGenere(chunk.pipeline);

  return (
    <div className="rounded-[7px] border border-line-2 bg-surface px-3 py-2.5">
      <p className="mb-[3px] text-[12px] font-semibold text-ink">
        {t("corpus.split.title", {
          genere: genere === null ? chunk.doc_genre : t(genere),
          taglio: taglio === null ? chunk.pipeline : t(taglio),
        })}
      </p>
      <p className="text-[11.5px] leading-[1.5] text-ink-2">
        {t(scelto ? "corpus.split.routed" : "corpus.split.generic")}
      </p>
    </div>
  );
}

/** Il chunk scelto, **intero**: e' cio' che U-06 chiede. */
function Dettaglio() {
  const { t } = usaLingua();
  const { documento, scelto } = usaEsploratore();

  const chunk =
    documento.stato === "pronto"
      ? (documento.chunks.find((c) => c.chunk_id === scelto) ?? null)
      : null;

  if (chunk === null) {
    return (
      <aside className="flex min-h-0 flex-col px-3 py-3.5">
        <Etichetta>{t("corpus.selected")}</Etichetta>
      </aside>
    );
  }

  const href = indirizzo(chunk.source_uri);

  return (
    <aside className="flex min-h-0 flex-col gap-2.5 overflow-y-auto px-3 py-3.5">
      <Etichetta>{t("corpus.selected")}</Etichetta>

      <div className="flex flex-wrap gap-1">
        <Targa accento>{chunk.pipeline}</Targa>
        <Targa>{chunk.content_type}</Targa>
        {/* La pagina solo dove **e'** una pagina: su `open_ragbench` vale 0 per
            ogni chunk, perche' li' il documento e' JSON per sezioni e una pagina
            non esiste. Mostrare «p. 0» su tutto sarebbe un dato inventato. */}
        {chunk.page > 0 && <Targa>{t("corpus.page", { n: chunk.page })}</Targa>}
      </div>

      {chunk.section_path !== "" && (
        <p className="font-mono text-[9.5px] break-words text-muted">{chunk.section_path}</p>
      )}

      <Contenuto testo={chunk.text} />

      <div className="flex flex-wrap gap-1">
        <Targa>{chunk.chunk_id}</Targa>
      </div>

      {href !== null ? (
        <a
          href={href}
          target="_blank"
          rel="noreferrer noopener"
          className="flex items-center gap-1.5 self-start rounded-md border border-line-2 px-[9px] py-[5px] text-[11px] text-ink-2 transition-colors hover:border-accent-2 hover:text-ink"
        >
          <Esterno size={12} />
          {t("corpus.open")}
        </a>
      ) : (
        <p className="font-mono text-[9.5px] break-all text-muted">{chunk.source_uri}</p>
      )}

      {/* Dichiarata, non simulata: il criterio di U-06 lo chiede con queste
          parole. E il motivo e' piu' largo di I-06 — un PDF non c'e' proprio. */}
      <p className="rounded-[7px] border border-line-2 bg-surface px-3 py-2.5 text-[11px] leading-[1.5] text-muted">
        {t("corpus.noPdf")}
      </p>
    </aside>
  );
}

/**
 * Il chunk, in due modi: come lo si legge e com'e' nell'indice.
 *
 * **Tutti e due servono, e per ragioni diverse.** Leggibile e' il modo di
 * controllare cosa dice una fonte: `## Table of Contents` e' un titolo, e
 * `<table><tr><td>` e' una tabella con dentro dei numeri incolonnati. Grezzo e'
 * cio' che sta davvero nell'indice — la stessa stringa che il modello ha ricevuto
 * in contesto e che il verificatore ha giudicato. In un progetto la cui tesi e'
 * che si controlla cio' che il sistema fa, il secondo non e' una modalita' di
 * ripiego: e' il dato.
 *
 * Si parte da **leggibile** perche' la domanda frequente e' «cosa dice questa
 * fonte», e un muro di `</td><td>` non risponde. Il grezzo resta a un clic, e la
 * pastiglia dice quale dei due si sta guardando invece di chiederlo.
 */
function Contenuto({ testo }: { testo: string }) {
  const { t } = usaLingua();
  const [grezzo, setGrezzo] = useState(false);
  const parti = useMemo(() => pezzi(testo), [testo]);

  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <div className="flex items-center gap-1">
        <Modo attivo={!grezzo} onClick={() => setGrezzo(false)}>
          {t("corpus.readable")}
        </Modo>
        <Modo attivo={grezzo} onClick={() => setGrezzo(true)}>
          {t("corpus.raw")}
        </Modo>
      </div>

      {grezzo ? (
        <p className="min-w-0 rounded-[7px] border border-line-2 bg-surface px-2.5 py-2 font-mono text-[10.5px] leading-[1.55] break-words whitespace-pre-wrap text-ink-2">
          {testo}
        </p>
      ) : (
        <div className="flex min-w-0 flex-col gap-2 rounded-[7px] border border-line-2 bg-surface px-2.5 py-2 text-[12px] leading-[1.55] text-ink-2">
          {parti.map((p) =>
            p.tipo === "tabella" ? (
              <TabellaHtml key={p.da} righe={p.righe} />
            ) : (
              <Prosa key={p.da} testo={testo.slice(p.da, p.a)} />
            ),
          )}
        </div>
      )}
    </div>
  );
}

function Modo({
  attivo,
  onClick,
  children,
}: {
  attivo: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={attivo}
      onClick={onClick}
      className={`rounded-full border px-2 py-[3px] text-[10px] transition-colors ${
        attivo
          ? "border-accent bg-accent-soft text-accent"
          : "border-line-2 text-muted hover:border-accent-2 hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

/**
 * Una tabella dei bilanci, costruita da noi con del testo.
 *
 * `colSpan`/`rowSpan` passano al browser invece di essere espansi: e' la
 * differenza dichiarata con `parse_html_table` in Python, che le espande perche'
 * serve a cercare. Qui serve a mostrare, e a mostrare ci pensa il browser.
 *
 * **Nessuna riga e' promossa a intestazione per posizione.** L'OCR di `ledger`
 * non produce `<th>` — misurato su 2.758 tabelle — e la prima riga di una
 * tabella di bilancio spesso e' un'etichetta di periodo che copre due colonne,
 * non un'intestazione. Indovinarla la farebbe sembrare un dato del documento.
 */
function TabellaHtml({ righe }: { righe: Cella[][] }) {
  return (
    // Scorre per conto suo: una tabella larga non deve far scorrere la colonna,
    // che porterebbe via anche il resto del chunk.
    <div className="-mx-1 overflow-x-auto px-1">
      <table className="w-full border-collapse font-mono text-[10.5px] tabular-nums">
        <tbody>
          {righe.map((riga, i) => (
            <tr key={i}>
              {riga.map((c, j) => (
                <td
                  key={j}
                  colSpan={c.colspan}
                  rowSpan={c.rowspan}
                  className={`border border-line px-1.5 py-[3px] align-top ${
                    c.intestazione ? "font-semibold text-ink" : "text-ink-2"
                  }`}
                >
                  {c.testo}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Targa({ accento = false, children }: { accento?: boolean; children: string }) {
  return (
    <span
      className={`rounded-[4px] border px-[5px] py-px font-mono text-[9px] tracking-[0.03em] break-all ${
        accento ? "border-accent-2 text-accent" : "border-line-2 text-muted"
      }`}
    >
      {children}
    </span>
  );
}
