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
import { CHIAVI, ricorda, ricordato } from "../app/deposito";
import { usaEsploratore } from "../app/esploratore";
import type { StatoDocumento } from "../app/esploratore";
import { usaDataset } from "../app/dataset";
import { nomeGenere, nomeTaglio, taglioPerGenere } from "../app/genere";
import { usaLingua } from "../app/i18n";
import { griglia, leggi, ridimensiona } from "./colonne";
import { Contenuto, Leggibile } from "./Leggibile";
import { Modo } from "./Modo";
import { Collegamento, Pagina, Ritorno } from "./Pagina";
import type { Larghezze } from "./colonne";
import { Etichetta } from "./Etichetta";
import { larghezzePixel, quanteRighe, righeMappa } from "./mappa";
import { Lente } from "./Icona";
import { usaForma } from "./Telaio";
import { Separatore } from "./Separatore";
import { Suggerimento } from "./Suggerimento";

export function Corpus() {
  const { t } = usaLingua();
  const { chiudi } = usaEsploratore();
  const { scelto: dataset } = usaDataset();
  const stretta = usaForma() === "stretta";
  const contenitore = useRef<HTMLDivElement>(null);
  // Una preferenza, come il tema: `leggi` fa ricadere sui predefiniti tutto cio'
  // che non e' un paio di larghezze valide, chiave assente compresa.
  const [larghezze, setLarghezze] = useState<Larghezze>(() => leggi(ricordato(CHIAVI.colonne)));

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
    const t = setTimeout(() => ricorda(CHIAVI.colonne, JSON.stringify(larghezze)), 300);
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
    <Pagina
      etichetta={t("corpus.title")}
      sottotitolo={t("corpus.subtitle", { dataset: dataset?.dataset_id ?? "—" })}
      indietro={t("corpus.back")}
      chiudi={chiudi}
    >
      {stretta ? (
        <Affondo />
      ) : (
        /* Le tre colonne del mockup, con due manici in mezzo.
           `grid-rows-[minmax(0,1fr)]` per la ragione di sempre: senza una riga
           dichiarata quella implicita e' `auto`, e a scorrere sarebbe la pagina
           invece delle colonne.

           I bordi non sono piu' `divide-x`: adesso li fanno i manici, che sono
           una traccia della griglia. Due linee, una sola volta. */
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
          <Centro />
          <Separatore
            etichetta={t("corpus.resize.detail")}
            valore={larghezze.dettaglio}
            onInizio={inizia}
            onFine={finisci}
            onSposta={(d) => sposta("dettaglio", d)}
          />
          <Dettaglio />
        </div>
      )}
    </Pagina>
  );
}

/**
 * A colonna sola le tre colonne diventano **due schermate in fila**: l'elenco,
 * e poi il documento scelto.
 *
 * **Un affondo e non tre riquadri impilati.** L'elenco dei documenti e' una
 * cosa che si interroga — 494 voci su `ledger` — e messo sopra la mappa
 * costringerebbe a scorrerlo tutto ogni volta per arrivare al documento che si
 * sta gia' leggendo. Le altre due invece si impilano davvero, perche' sono la
 * stessa cosa vista da due distanze: la mappa dice dove sono caduti i tagli, il
 * dettaglio dice cosa c'e' dentro quello scelto, e sceglierne uno sulla mappa
 * riempie il riquadro che gli sta appena sotto.
 *
 * **I manici non ci sono**, e non e' una perdita: servivano a spartire una
 * larghezza fra tre colonne, e qui di larghezza ce n'e' una sola da spartire con
 * nessuno. Le misure ricordate restano dove sono e tornano quando lo schermo
 * torna largo.
 *
 * Il nome del documento sta accanto al comando che risale, e non e' decorazione:
 * e' l'unica cosa che dice **da dove** si sta risalendo, visto che l'elenco —
 * dove il documento aperto e' marcato — adesso non e' sullo schermo.
 */
function Affondo() {
  const { t } = usaLingua();
  const { documento, lascia } = usaEsploratore();

  if (documento.stato === "nessuno") {
    // Una griglia di una riga sola, e non un `flex-1` sulla sezione: e' il modo
    // gia' usato qui e nel telaio per dare a un figlio l'altezza disponibile
    // senza che il suo scorrimento interno diventi lo scorrimento della pagina.
    return (
      <div className="grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)] overflow-hidden">
        <Documenti />
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center gap-2 border-b border-line px-[18px] py-2">
        <Ritorno onClick={lascia}>{t("corpus.documents")}</Ritorno>
        <span className="min-w-0 truncate font-mono text-[10.5px] text-muted">
          {documento.doc_id}
        </span>
      </div>

      <div className="flex min-h-0 flex-1 flex-col divide-y divide-line overflow-y-auto">
        <Centro impilato />
        <Dettaglio impilato />
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
/**
 * Lo stacco fra due tratti, e la larghezza sotto cui un tratto non si vede.
 * Interi, e sono l'unica misura del disegno che il conto deve sapere.
 *
 * **Dieci pixel violano la proporzione, e costa poco.** Misurato sui documenti
 * veri, contando quanti pezzi vengono gonfiati e quanti pixel bisogna togliere
 * agli altri per fargli posto:
 *
 *     NASDAQ_LOOP_2017 (261 chunk)   33 su 261 gonfiati, 1,1% della mappa
 *     NYSE_SHW_2017     (83 chunk)    2 su  83 gonfiati, 0,1% della mappa
 *     2401.02564v2      (15 chunk)    nessuno
 *     2401.03345v2      (29 chunk)    nessuno
 *
 * Cioe' il caso peggiore e' l'uno per cento su un documento di 261 pezzi, e sui
 * documenti normali non si paga niente. A tre pixel la proporzione era piu'
 * fedele e alcuni pezzi restavano invisibili — che e' il modo in cui una
 * proporzione fedele smette di essere utile.
 */
const STACCO = 2;
const MINIMO_TRATTO = 10;

/**
 * La colonna di mezzo: due viste dello stesso documento.
 *
 * **La mappa dice quanto sono grandi i pezzi, il testo dice cosa c'era nel punto
 * in cui uno e' stato tagliato.** Sono la stessa domanda — «com'e' stato
 * spezzato» — guardata da lontano e da vicino, e condividono la selezione:
 * scegliendo un tratto sulla mappa e passando al testo ci si ritrova li'.
 *
 * Il modo **non** si ricorda oltre la sessione, a differenza delle larghezze:
 * quelle sono una preferenza («voglio piu' spazio per leggere»), questo e' cosa
 * si sta guardando adesso.
 */
function Centro({ impilato = false }: { impilato?: boolean }) {
  const { t } = usaLingua();
  const { documento } = usaEsploratore();
  const [vista, setVista] = useState<"mappa" | "testo">("mappa");

  if (documento.stato === "nessuno") {
    return (
      <section className="flex min-h-0 flex-col justify-center px-[18px] py-4">
        <p className="text-center text-[12px] text-muted">{t("corpus.pickDocument")}</p>
      </section>
    );
  }

  return (
    <section
      className={`flex flex-col gap-3 px-[18px] py-4 ${impilato ? "" : "min-h-0 overflow-y-auto"}`}
    >
      <div className="flex items-center gap-1">
        <Modo attivo={vista === "mappa"} onClick={() => setVista("mappa")}>
          {t("corpus.howSplit")}
        </Modo>
        <Modo attivo={vista === "testo"} onClick={() => setVista("testo")}>
          {t("corpus.indexedText")}
        </Modo>
      </div>
      {vista === "mappa" ? <Mappa /> : <TestoIndicizzato />}
    </section>
  );
}

/**
 * Il documento in fila, con le cuciture visibili.
 *
 * **Non e' «il documento»**, ed e' la ragione per cui si chiama «il testo
 * indicizzato»: il PDF non ce l'abbiamo, e cio' che si puo' mettere in fila sono
 * i chunk. Oggi le due cose coincidono — misurato: nell'indice generico non c'e'
 * **nessuna** sovrapposizione fra chunk adiacenti, quindi i pezzi partizionano
 * il documento esattamente. In una collection instradata non sarebbe piu' vero:
 * un quarto delle coppie condivide fino a 586 caratteri, e la lettura continua
 * li mostrerebbe due volte. Sta in D-18, che e' il debito che renderebbe quelle
 * collection raggiungibili.
 *
 * **Le cuciture sono il contenuto, non un difetto.** Vedere dove un taglio e'
 * caduto — in mezzo a una frase, prima di una tabella, dopo un titolo — e' la
 * tesi del progetto applicata al corpus: la mappa dice che i pezzi sono
 * disuguali, questa dice cosa c'era nel punto in cui uno e' stato staccato.
 */
function TestoIndicizzato() {
  const { t } = usaLingua();
  const { documento, scelto, scegliChunk } = usaEsploratore();
  if (documento.stato !== "pronto") return <Attesa stato={documento} />;

  return (
    <div className="flex flex-col">
      {documento.chunks.map((c, i) => (
        <article key={c.chunk_id}>
          {/* La cucitura sta **sopra** il chunk e non fra due: cosi' porta il
              nome di quello che apre, e il primo taglio si vede come gli altri
              invece di essere l'unico senza riga. */}
          <button
            type="button"
            onClick={() => scegliChunk(c.chunk_id)}
            aria-current={c.chunk_id === scelto}
            className="group flex w-full items-center gap-2 py-1.5 text-left"
          >
            <span
              className={`font-mono text-[9.5px] tabular-nums transition-colors ${
                c.chunk_id === scelto ? "text-accent" : "text-muted group-hover:text-ink-2"
              }`}
            >
              {t("corpus.seam", { n: i + 1, caratteri: c.text.length })}
            </span>
            <span
              className={`h-px flex-1 transition-colors ${
                c.chunk_id === scelto ? "bg-accent" : "bg-line group-hover:bg-line-2"
              }`}
            />
          </button>
          <div
            className={`rounded-[7px] px-2.5 py-1.5 transition-colors ${
              c.chunk_id === scelto ? "bg-accent-soft" : ""
            }`}
          >
            <Leggibile testo={c.text} />
          </div>
        </article>
      ))}
    </div>
  );
}

/** Il caricamento e il guasto di un documento, che le due viste dividono. */
function Attesa({ stato }: { stato: StatoDocumento }) {
  const { t } = usaLingua();
  if (stato.stato === "caricamento") {
    return (
      <p className="font-mono text-[11px] text-muted">
        <span className="mr-2 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-accent align-middle" />
        {t("corpus.loading")}
      </p>
    );
  }
  if (stato.stato === "guasto") {
    return <p className="font-mono text-[10px] break-all text-warn">{stato.errore}</p>;
  }
  return null;
}

function Mappa() {
  const { t } = usaLingua();
  const { documento, scelto, scegliChunk } = usaEsploratore();
  const misura = useRef<HTMLDivElement>(null);
  const [larghezza, setLarghezza] = useState(0);

  // `ResizeObserver` e non una lettura sola: la colonna di mezzo si ridimensiona
  // col manico di U-06, e una larghezza presa all'apertura resterebbe quella.
  useEffect(() => {
    const nodo = misura.current;
    if (nodo === null) return;
    const osserva = new ResizeObserver(([voce]) =>
      setLarghezza(Math.floor(voce.contentRect.width)),
    );
    osserva.observe(nodo);
    return () => osserva.disconnect();
  }, [documento.stato]);

  if (documento.stato !== "pronto") return <Attesa stato={documento} />;

  const chunks = documento.chunks;
  // Genere e pipeline sono proprieta' del **documento**: il primo chunk le porta
  // come tutti gli altri, e leggerle da li' evita di ripetere la stessa domanda
  // duecentosessantuno volte.
  const primo = chunks[0];
  const perGenere = primo !== undefined && taglioPerGenere(primo.pipeline);

  return (
    <div className="flex flex-col gap-3.5">
      <p className="font-mono text-[10px] text-muted tabular-nums">
        {t("corpus.chunks", { n: chunks.length })}
      </p>

      {/* La larghezza vera serve al conto: le larghezze dei tratti sono in
          **pixel interi** perche' cosi' ogni stacco e' uguale, e per farli interi
          bisogna sapere quanti pixel ci sono. Si osserva invece di calcolarla:
          questa colonna e' ridimensionabile. */}
      <div ref={misura} className="flex flex-col gap-[3px]">
        {larghezza > 0 &&
          righeMappa(
            chunks.map((c) => c.text.length),
            // La scala viene dal pezzo piu' piccolo **con del testo** di questo
            // documento: il numero di righe segue da li'. Vedi `mappa.ts`.
            quanteRighe(chunks.map((c) => c.text)),
          ).map((riga, n) => {
            const px = larghezzePixel(
              riga.map((p) => p.frazione),
              larghezza,
              STACCO,
              MINIMO_TRATTO,
            );
            return (
              <div key={n} className="flex h-[18px]" style={{ gap: STACCO }}>
                {riga.map((p, k) => (
                  <Tratto
                    key={`${p.indice}-${k}`}
                    chunk={chunks[p.indice]}
                    larghezza={px[k]}
                    scelta={chunks[p.indice].chunk_id === scelto}
                    onClick={() => scegliChunk(chunks[p.indice].chunk_id)}
                  />
                ))}
              </div>
            );
          })}
      </div>

      <div className="flex flex-wrap gap-3 font-mono text-[10px] text-muted">
        <Voce quadro="bg-surface-2">{t("corpus.legend.text")}</Voce>
        <Voce quadro="bg-line-2">
          {t(perGenere ? "corpus.legend.table.routed" : "corpus.legend.table")}
        </Voce>
        <Voce quadro="bg-accent">{t("corpus.legend.selected")}</Voce>
      </div>

      {primo !== undefined && <Spiegazione chunk={primo} />}
    </div>
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
 * **La larghezza arriva in pixel interi**, e non e' un dettaglio: con misure
 * frazionarie ogni confine fra due tratti cadeva su un mezzo pixel e il browser
 * lo arrotondava, quindi lo stesso stacco da due pixel usciva ora due ora tre e
 * la fila sembrava spaziata a caso. Il conto sta in `larghezzePixel`.
 *
 * Il minimo e' l'unico punto in cui la proporzione viene tradita — un chunk da
 * 19 caratteri su 348.942 e' largo niente, ed e' vero, ma un pezzo del documento
 * che non si puo' vedere e' un pezzo che non esiste. Quanto costa esattamente
 * sta su `MINIMO_TRATTO`, misurato.
 *
 * **Arrotondato come tutto il resto.** Tre pixel di raggio, gli stessi delle
 * pastiglie e delle schede: una fila di rettangoli vivi era l'unica cosa
 * dell'interfaccia con gli angoli a spigolo. Tutti e quattro gli angoli, ora che
 * un pezzo non si spezza piu' a meta' riga: ogni tratto e' un chunk intero.
 *
 * **Il colore non usa l'accento per il tipo.** Nel §12 l'accento vuol dire
 * «questo e' scelto», e usarlo per «questa e' una tabella» faceva sembrare
 * selezionate tutte le tabelle e spente tutte le altre. Il tipo si legge come
 * densita' — un neutro chiaro e uno piu' fitto — e l'accento resta **solo** per
 * il tratto scelto, che cosi' e' l'unica cosa colorata della mappa.
 */
function Tratto({
  chunk,
  larghezza,
  scelta,
  onClick,
}: {
  chunk: ChunkView;
  /** In pixel **interi**: vedi `larghezzePixel`. */
  larghezza: number;
  scelta: boolean;
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
      stile={{ width: larghezza, flex: "none" }}
      className="h-full"
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
        className={`block h-full w-full rounded-[3px] transition-colors ${
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
function Dettaglio({ impilato = false }: { impilato?: boolean }) {
  const { t } = usaLingua();
  const { documento, scelto } = usaEsploratore();

  const chunk =
    documento.stato === "pronto"
      ? (documento.chunks.find((c) => c.chunk_id === scelto) ?? null)
      : null;

  if (chunk === null) {
    return (
      <aside className={`flex flex-col px-3 py-3.5 ${impilato ? "" : "min-h-0"}`}>
        <Etichetta>{t("corpus.selected")}</Etichetta>
      </aside>
    );
  }

  const href = indirizzo(chunk.source_uri);

  return (
    <aside
      className={`flex flex-col gap-2.5 px-3 py-3.5 ${impilato ? "" : "min-h-0 overflow-y-auto"}`}
    >
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
        <Collegamento href={href}>{t("corpus.open")}</Collegamento>
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
