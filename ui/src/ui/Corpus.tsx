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
 * **La mappa e' il pezzo che non si poteva disegnare prima di U-05.** E' una
 * striscia continua, mandata a capo: ogni tratto e' un chunk, largo **quanto il
 * chunk e' grande davvero**. Guardare due documenti dello stesso corpus e vedere
 * due mappe diverse e' l'affermazione 2 del §0 senza una tabella di numeri —
 * e vedere che i pezzi sono disuguali e' meta' di cio' che la pipeline fa.
 *
 * **Niente pagina renderizzata, e non e' solo I-06.** Su nessuno dei due corpus
 * esiste un PDF: `open_ragbench` ha il JSON degli articoli, `ledger` il Markdown
 * di Mathpix. Si dichiara nella colonna di destra invece di disegnare un
 * riquadro grigio che promette qualcosa — «dichiararlo, non simularlo» sta nel
 * criterio.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import type { ChunkView } from "../api/types";
import { filtra, indirizzo } from "../app/corpus";
import { usaEsploratore } from "../app/esploratore";
import { usaDataset } from "../app/dataset";
import { nomeGenere, nomeTaglio, taglioPerGenere } from "../app/genere";
import { usaLingua } from "../app/i18n";
import { griglia, leggi, ridimensiona } from "./colonne";
import type { Larghezze } from "./colonne";
import { Etichetta } from "./Etichetta";
import { quanteRighe, righeMappa } from "./mappa";
import { Esterno, Indietro, Lente } from "./Icona";
import { Separatore } from "./Separatore";
import { Suggerimento } from "./Suggerimento";
import { pezzi } from "./tabellaHtml";
import type { Cella } from "./tabellaHtml";
import { Prosa } from "./Testo";

/** Dove si ricordano le larghezze. Una preferenza, come il tema — vedi `colonne.ts`. */
const DEPOSITO = "ibid.corpus.colonne";

export function Corpus() {
  const { t } = usaLingua();
  const { chiudi } = usaEsploratore();
  const { scelto: dataset } = usaDataset();
  const contenitore = useRef<HTMLDivElement>(null);
  const [larghezze, setLarghezze] = useState<Larghezze>(() => {
    try {
      return leggi(localStorage.getItem(DEPOSITO));
    } catch {
      // Deposito negato (modalita' privata, iframe): si parte dai predefiniti.
      return leggi(null);
    }
  });

  /** Le larghezze correnti, leggibili da un gestore che non si ri-crea. */
  const correnti = useRef(larghezze);
  useEffect(() => {
    correnti.current = larghezze;
  }, [larghezze]);

  /** Quelle di **quando il trascinamento e' cominciato**, o `null` se non e' in
   *  corso. Vedi la nota in testa a `Separatore`: e' cio' che impedisce al
   *  manico di ripartire appena il puntatore inverte, quando e' finito ben oltre
   *  il limite. */
  const partenza = useRef<Larghezze | null>(null);

  /** La larghezza che le tre colonne hanno insieme, **adesso**: la finestra puo'
   *  essere cambiata da quando la schermata si e' aperta, e un totale vecchio
   *  farebbe fermare i manici nel posto sbagliato. I 10 px sono i due manici. */
  const disponibile = useCallback(
    () => Math.max((contenitore.current?.clientWidth ?? 0) - 10, 0),
    [],
  );

  const inizia = useCallback(() => {
    partenza.current = correnti.current;
  }, []);
  const finisci = useCallback(() => {
    partenza.current = null;
  }, []);
  const sposta = useCallback(
    (quale: keyof Larghezze, delta: number) => {
      const da = partenza.current ?? correnti.current;
      setLarghezze(ridimensiona(da, quale, delta, disponibile()));
    },
    [disponibile],
  );

  // Si scrive **dopo** il trascinamento, non a ogni pixel: un `pointermove`
  // arriva decine di volte al secondo, e serializzare a ogni passaggio farebbe
  // pagare al deposito un movimento del mouse. La pausa e' la stessa idea del
  // ritardo di salvataggio della cronologia.
  useEffect(() => {
    const t = setTimeout(() => {
      try {
        localStorage.setItem(DEPOSITO, JSON.stringify(larghezze));
      } catch {
        // Le misure restano valide per questa sessione: non ricordarle e' meno
        // grave che rifiutare di cambiarle.
      }
    }, 300);
    return () => clearTimeout(t);
  }, [larghezze]);

  // La finestra si stringe: le colonne fisse restano, e la mappa puo' finire
  // sotto il proprio minimo. Un `ridimensiona` di zero le riporta dentro i
  // limiti senza spostare niente quando non serve.
  useEffect(() => {
    // Non passa da `sposta`: quello lavora sulla partenza di un trascinamento, e
    // qui non ce n'e' uno. Un delta di zero sulle larghezze **correnti** le
    // riporta dentro i limiti senza muovere niente quando non serve.
    const controlla = () => setLarghezze((l) => ridimensiona(l, "documenti", 0, disponibile()));
    window.addEventListener("resize", controlla, { passive: true });
    return () => window.removeEventListener("resize", controlla);
  }, [disponibile]);

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

      {/* Le tre colonne del mockup, con due manici in mezzo.
          `grid-rows-[minmax(0,1fr)]` per la ragione di sempre: senza una riga
          dichiarata quella implicita e' `auto`, e a scorrere sarebbe la pagina
          invece delle colonne.

          I bordi non sono piu' `divide-x`: adesso li fanno i manici, che sono
          una traccia della griglia. Due linee, una sola volta. */}
      <div
        ref={contenitore}
        style={{ gridTemplateColumns: griglia(larghezze) }}
        className="grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)] overflow-hidden"
      >
        <Documenti />
        <Separatore
          etichetta={t("corpus.resize.documents")}
          valore={larghezze.documenti}
          onInizio={inizia}
          onFine={finisci}
          onSposta={(d) => sposta("documenti", d)}
        />
        <Mappa />
        <Separatore
          etichetta={t("corpus.resize.detail")}
          valore={larghezze.dettaglio}
          onInizio={inizia}
          onFine={finisci}
          onSposta={(d) => sposta("dettaglio", d)}
        />
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
 * Com'e' stato spezzato: la striscia del documento, mandata a capo.
 *
 * **La larghezza e' la dimensione vera del pezzo.** Su `NYSE_SHW_2017` il chunk
 * piu' grande e' 6.302 caratteri e il piu' piccolo 19: con tessere tutte uguali
 * quella differenza spariva, ed era la cosa da mostrare — la pipeline esiste
 * perche' una tabella non si spezza, e il risultato e' un documento fatto di
 * pezzi molto diversi. Il conto sta in `mappa.ts`, provato a parte.
 *
 * **Il tipo e' una densita', non un colore.** Nel §12 l'accento vuol dire
 * «scelto»: usarlo per «tabella» faceva sembrare selezionate tutte le tabelle e
 * spente tutte le altre. Ora l'accento e' l'unica cosa colorata della mappa, ed
 * e' il tratto scelto — che la legenda dichiara invece di lasciarlo indovinare.
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

      <div className="flex flex-col gap-[3px]">
        {righeMappa(
          chunks.map((c) => c.text.length),
          // La scala viene dal pezzo piu' piccolo **con del testo** di questo
          // documento: il numero di righe segue da li'. Vedi `mappa.ts`.
          quanteRighe(chunks.map((c) => c.text)),
        ).map((riga, n) => (
          <div key={n} className="flex h-[18px] gap-[2px]">
            {riga.map((p, k) => (
              <Tratto
                key={`${p.indice}-${k}`}
                chunk={chunks[p.indice]}
                frazione={p.frazione}
                scelta={chunks[p.indice].chunk_id === scelto}
                estremi={{ apre: !p.continuazione, chiude: !p.spezzato }}
                onClick={() => scegliChunk(chunks[p.indice].chunk_id)}
              />
            ))}
            {/* L'ultima riga e' quasi sempre incompleta, e deve **restare**
                incompleta: con i soli tratti il flex distribuirebbe fra loro
                tutto lo spazio, e mezzo documento in fondo sembrerebbe una riga
                piena. Questo pezzo vuoto tiene il posto che manca. */}
            <Riempimento frazione={1 - riga.reduce((a, p) => a + p.frazione, 0)} />
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-3 font-mono text-[10px] text-muted">
        <Voce quadro="bg-surface-2">{t("corpus.legend.text")}</Voce>
        <Voce quadro="bg-line-2">
          {t(perGenere ? "corpus.legend.table.routed" : "corpus.legend.table")}
        </Voce>
        <Voce quadro="bg-accent">{t("corpus.legend.selected")}</Voce>
      </div>

      {primo !== undefined && <Spiegazione chunk={primo} />}
    </section>
  );
}

/**
 * Un tratto della striscia: un chunk, o la parte che ne entra in questa riga.
 *
 * **La larghezza e' la proporzione**, non una taglia in due misure. `flexGrow`
 * invece di una percentuale perche' fra un tratto e l'altro c'e' un pixel di
 * stacco: con le percentuali la riga sborderebbe della somma degli stacchi,
 * mentre `flex` distribuisce cio' che resta **dopo** averli tolti.
 *
 * `min-w-[3px]` e' l'unico punto in cui la proporzione viene tradita, e sta qui
 * e non nel conto: un chunk da 19 caratteri su 348.942 e' largo niente, ed e'
 * vero — ma un pezzo del documento che non si puo' cliccare e' un pezzo che non
 * esiste. Il conto resta esatto (`mappa.ts`), la bugia sta nel disegno e si
 * ferma a tre pixel.
 *
 * **Arrotondato come tutto il resto.** Tre pixel di raggio, gli stessi delle
 * pastiglie e delle schede: una fila di rettangoli vivi era l'unica cosa
 * dell'interfaccia con gli angoli a spigolo. E un pezzo andato a capo si
 * arrotonda **solo** dal lato in cui il chunk comincia o finisce davvero, cosi'
 * si legge come una cosa sola che continua invece che come due.
 *
 * **Il colore non usa l'accento per il tipo.** Nel §12 l'accento vuol dire
 * «questo e' scelto», e usarlo per «questa e' una tabella» faceva sembrare
 * selezionate tutte le tabelle e spente tutte le altre. Il tipo si legge come
 * densita' — un neutro chiaro e uno piu' fitto — e l'accento resta **solo** per
 * il tratto scelto, che cosi' e' l'unica cosa colorata della mappa.
 */
function Tratto({
  chunk,
  frazione,
  scelta,
  estremi,
  onClick,
}: {
  chunk: ChunkView;
  frazione: number;
  scelta: boolean;
  /** Da che parte il chunk **finisce davvero**: un pezzo andato a capo si
   *  arrotonda solo dal lato in cui comincia o in cui finisce, altrimenti due
   *  meta' dello stesso chunk sembrano due chunk. */
  estremi: { apre: boolean; chiude: boolean };
  onClick: () => void;
}) {
  const { t, lingua } = usaLingua();
  const tabella = chunk.content_type === "table" || chunk.content_type === "mixed";

  return (
    <Suggerimento
      dato
      fuoco={false}
      // Lo stile va sul **bersaglio**, che e' lo `span` di `Suggerimento`: e'
      // lui la voce del flex, e un `flexGrow` messo sul bottone dentro non
      // raggiunge nessuno. `× 1000` perche' quando la somma dei fattori di
      // crescita e' minore di uno il CSS distribuisce solo quella frazione dello
      // spazio libero: le frazioni di una riga sommano esattamente a uno, cioe'
      // proprio sul bordo, e un arrotondamento in meno lascerebbe la riga corta.
      stile={{ flexGrow: frazione * 1000, flexBasis: 0 }}
      className="h-full min-w-[3px]"
      testo={t("corpus.chunkHint", {
        id: chunk.chunk_id,
        tipo: chunk.content_type,
        caratteri: chunk.text.length.toLocaleString(lingua === "it" ? "it-IT" : "en-US"),
      })}
    >
      <button
        type="button"
        onClick={onClick}
        aria-label={chunk.chunk_id}
        aria-current={scelta}
        className={`block h-full w-full transition-colors ${
          estremi.apre ? "rounded-l-[3px]" : ""
        } ${estremi.chiude ? "rounded-r-[3px]" : ""} ${
          scelta
            ? "bg-accent"
            : tabella
              ? "bg-line-2 hover:bg-muted"
              : "bg-surface-2 hover:bg-line-2"
        }`}
      />
    </Suggerimento>
  );
}

/** Lo spazio che manca a una riga incompleta. Niente colore: e' documento che
 *  non c'e', non un pezzo vuoto. */
function Riempimento({ frazione }: { frazione: number }) {
  if (frazione <= 0.0005) return null;
  return <span aria-hidden="true" style={{ flexGrow: frazione * 1000, flexBasis: 0 }} />;
}

function Voce({ quadro, children }: { quadro: string; children: ReactNode }) {
  return (
    <span className="flex items-center gap-1.5">
      <i className={`inline-block h-[9px] w-[9px] rounded-[2px] ${quadro}`} />
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
