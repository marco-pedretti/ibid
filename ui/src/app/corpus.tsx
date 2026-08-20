/**
 * L'esploratore: quale documento si sta guardando, e quale chunk.
 *
 * Sta accanto a `corpus.ts` come `chat.tsx` sta accanto a `conversazione.ts` —
 * li' le regole, provate senza browser, qui lo stato di React e le due chiamate.
 *
 * **Due caricamenti separati e non uno.** L'elenco dei documenti dipende dal
 * dataset e si chiede una volta per dataset (494 documenti di `ledger`: 21 KB,
 * 0,35 s); i chunk dipendono dal documento aperto e si chiedono a ogni apertura
 * (il piu' grande: 261 chunk, 523 KB, 0,46 s). Tenerli in un caricamento solo
 * avrebbe rifatto l'elenco a ogni clic su un documento.
 *
 * **Si chiude senza dimenticare.** Tornando alla chat e riaprendo l'esploratore
 * si ritrova il documento che si stava leggendo: chi apre una fonte, torna a
 * guardare la risposta e riapre, sta continuando la stessa verifica. Lo stato
 * vive quanto la scheda e non oltre — come la barra di U-03, e per la stessa
 * ragione: e' un'esplorazione, non una preferenza.
 *
 * Cambiando dataset l'elenco si rifa' e il documento aperto si lascia: apparteneva
 * a un altro corpus, e mostrarne i chunk sotto un altro nome sarebbe la cosa
 * peggiore che questa schermata possa fare.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { api } from "../api/client";
import type { ChunkView, DocumentView } from "../api/types";
import { chunkIniziale } from "./corpus";
import { usaDataset } from "./dataset";

export type StatoElenco =
  | { stato: "caricamento" }
  | { stato: "pronto"; documenti: DocumentView[] }
  | { stato: "guasto"; errore: string };

export type StatoDocumento =
  | { stato: "nessuno" }
  | { stato: "caricamento"; doc_id: string }
  | { stato: "pronto"; doc_id: string; chunks: ChunkView[] }
  | { stato: "guasto"; doc_id: string; errore: string };

interface Corpus {
  /** L'esploratore e' sullo schermo. */
  aperto: boolean;
  elenco: StatoElenco;
  documento: StatoDocumento;
  /** Il `chunk_id` selezionato, o `null` finche' non ce n'e' uno. */
  scelto: string | null;
  /** Apre l'esploratore. Con un documento, ci va sopra; con un chunk, lo
   *  seleziona — e' la strada che arriva da una citazione. */
  apri: (doc_id?: string, chunk_id?: string) => void;
  chiudi: () => void;
  scegliChunk: (chunk_id: string) => void;
}

const Contesto = createContext<Corpus | null>(null);

export function ProvvedeCorpus({ children }: { children: ReactNode }) {
  const { scelto: dataset } = usaDataset();
  const dataset_id = dataset?.dataset_id ?? null;

  const [aperto, setAperto] = useState(false);
  const [elenco, setElenco] = useState<StatoElenco>({ stato: "caricamento" });
  const [documento, setDocumento] = useState<StatoDocumento>({ stato: "nessuno" });
  const [scelto, setScelto] = useState<string | null>(null);
  /** Il chunk che si e' chiesto aprendo, finche' i suoi fratelli non arrivano. */
  const [chiesto, setChiesto] = useState<string | null>(null);

  // L'elenco si chiede **solo quando serve**: 21 KB e 0,35 s che chi non apre
  // mai l'esploratore non deve pagare all'avvio, dove c'e' gia' `/datasets`.
  useEffect(() => {
    if (!aperto || dataset_id === null) return;
    const ctrl = new AbortController();
    setElenco({ stato: "caricamento" });
    api
      .documents(dataset_id, undefined, { signal: ctrl.signal })
      .then((r) => setElenco({ stato: "pronto", documenti: r.documents }))
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return;
        setElenco({ stato: "guasto", errore: e instanceof Error ? e.message : String(e) });
      });
    return () => ctrl.abort();
  }, [aperto, dataset_id]);

  // Il documento aperto apparteneva al dataset di prima: si lascia, invece di
  // mostrarne i chunk sotto il nome di un altro corpus.
  useEffect(() => {
    setDocumento({ stato: "nessuno" });
    setScelto(null);
  }, [dataset_id]);

  const doc_id = documento.stato === "nessuno" ? null : documento.doc_id;

  useEffect(() => {
    if (doc_id === null || dataset_id === null || documento.stato !== "caricamento") return;
    const ctrl = new AbortController();
    api
      .documentChunks(doc_id, dataset_id, undefined, { signal: ctrl.signal })
      .then((r) => {
        setDocumento({ stato: "pronto", doc_id, chunks: r.chunks });
        setScelto(chunkIniziale(r.chunks, chiesto));
      })
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return;
        setDocumento({
          stato: "guasto",
          doc_id,
          errore: e instanceof Error ? e.message : String(e),
        });
      });
    return () => ctrl.abort();
    // `chiesto` sta fuori dalle dipendenze di proposito: e' il chunk **di questa
    // apertura**, e va letto quando la risposta arriva, non inseguito. Elencarlo
    // qui rifarebbe la richiesta a ogni apertura che cambia solo la selezione.
    // In questo repo le liste di dipendenze sono scritte a mano (D-13), quindi
    // la deroga si dichiara qui invece che a un linter che non c'e'.
  }, [doc_id, dataset_id, documento.stato]);

  /**
   * Tre casi, e vanno distinti tutti e tre.
   *
   * Senza documento e' la corsia: si apre l'esploratore dov'era, perche' chi
   * torna a guardare la risposta e riapre sta continuando la stessa verifica.
   *
   * Con un documento **gia' caricato** si cambia la sola selezione: rifare la
   * richiesta per dei chunk che sono gia' in mano sarebbe mezzo secondo di
   * attesa per niente.
   *
   * Con un documento **diverso** la selezione si azzera invece di restare: il
   * chunk di prima appartiene a un altro documento, e tenerlo evidenziato sulla
   * mappa nuova indicherebbe una tessera che non e' quella.
   */
  const apri = useCallback(
    (doc?: string, chunk?: string) => {
      setAperto(true);
      if (doc === undefined) return;
      // Lo stato si legge qui e non dentro un aggiornatore: una `setX` chiamata
      // dentro l'aggiornatore di un'altra e' un effetto in un posto che React
      // puo' rieseguire, ed e' il modo in cui una selezione si perde una volta
      // su due senza che si capisca quale.
      const stesso = documento.stato === "pronto" && documento.doc_id === doc;
      setChiesto(chunk ?? null);
      if (chunk !== undefined) setScelto(chunk);
      else if (!stesso) setScelto(null);
      if (!stesso) setDocumento({ stato: "caricamento", doc_id: doc });
    },
    [documento],
  );

  const chiudi = useCallback(() => setAperto(false), []);
  const scegliChunk = useCallback((chunk_id: string) => setScelto(chunk_id), []);

  const valore = useMemo(
    () => ({ aperto, elenco, documento, scelto, apri, chiudi, scegliChunk }),
    [aperto, elenco, documento, scelto, apri, chiudi, scegliChunk],
  );
  return <Contesto.Provider value={valore}>{children}</Contesto.Provider>;
}

export function usaCorpus(): Corpus {
  const c = useContext(Contesto);
  if (!c) throw new Error("usaCorpus fuori da <ProvvedeCorpus>");
  return c;
}
