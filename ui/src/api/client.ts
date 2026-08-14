/**
 * Le chiamate che non streammano. Tipizzate dal contratto generato, non a mano.
 *
 * Un modulo sottile di proposito: aggiunge l'URL di base, il JSON e la
 * traduzione degli errori, e nient'altro. Se qui cominciasse a comparire logica
 * — un default, una soglia, un elenco di modalita' valide — sarebbe la stessa
 * copia scritta a mano che `types.ts` esiste per non avere: quelle cose
 * arrivano da `/datasets` e `/config`, che le sanno.
 */
import type {
  AnswerResponse,
  Capabilities,
  ChunkView,
  ConfigView,
  DocumentChunksResponse,
  DocumentsResponse,
  QueryRequest,
  RetrieveRequestBody,
  RetrieveResponse,
} from "./types";
import { BASE } from "./sse";

/**
 * Un guasto con lo stato accanto, perche' 404 e 500 non si mostrano uguali.
 *
 * Un 404 su `/document/{id}/chunks` e' un documento che non c'e' — un messaggio
 * nella pagina. Un 500 e' un guasto del backend — un altro messaggio, e nessuna
 * ragione di riprovare da soli.
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(`HTTP ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

/**
 * Il `detail` di FastAPI, leggibile.
 *
 * Su 422 e' una lista di errori con il **nome del campo** rifiutato, ed e'
 * l'informazione che rende utile la validazione all'orlo di A-07: appiattirla in
 * «422 Unprocessable Entity» butterebbe via proprio il pezzo per cui esiste.
 */
function leggiDetail(corpo: unknown): string {
  if (typeof corpo === "string") return corpo;
  if (corpo && typeof corpo === "object" && "detail" in corpo) {
    const d = (corpo as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return d
        .map((e) => {
          const campo = Array.isArray(e?.loc) ? e.loc.slice(1).join(".") : "?";
          return `${campo}: ${e?.msg ?? "non valido"}`;
        })
        .join("; ");
    }
  }
  return JSON.stringify(corpo).slice(0, 300);
}

async function chiedi<T>(percorso: string, init: RequestInit, base: string): Promise<T> {
  const risposta = await fetch(`${base}${percorso}`, {
    ...init,
    headers: { Accept: "application/json", ...init.headers },
  });
  const corpo = await risposta.json().catch(() => null);
  if (!risposta.ok) throw new ApiError(risposta.status, leggiDetail(corpo));
  return corpo as T;
}

export interface Opzioni {
  signal?: AbortSignal;
  base?: string;
}

function get<T>(percorso: string, o: Opzioni = {}): Promise<T> {
  return chiedi<T>(percorso, { method: "GET", signal: o.signal }, o.base ?? BASE);
}

function post<T>(percorso: string, corpo: unknown, o: Opzioni = {}): Promise<T> {
  return chiedi<T>(
    percorso,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo),
      signal: o.signal,
    },
    o.base ?? BASE,
  );
}

/** `?a=1&b=2`, saltando cio' che non e' stato deciso. */
function query(parametri: Record<string, string | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(parametri)) if (v !== undefined) q.set(k, v);
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const api = {
  /** Vivo, e nient'altro: non dice se l'indice c'e' (quello lo dice `ready`). */
  health: (o?: Opzioni) => get<{ status: string }>("/health", o),

  /** Cosa questo backend accetta. Letto all'avvio, mai indovinato (U-01). */
  capabilities: (o?: Opzioni) => get<Capabilities>("/datasets", o),

  /** I default di **questo** deployment, per mostrarli prima di chiedere. */
  config: (o?: Opzioni) => get<ConfigView>("/config", o),

  /** La fonte dietro una citazione (U-06). */
  chunk: (chunkId: string, collection?: string, o?: Opzioni) =>
    get<ChunkView>(`/chunk/${encodeURI(chunkId)}${query({ collection })}`, o),

  /** I documenti della collection, per sfogliarla (A-07). */
  documents: (datasetId: string, collection?: string, o?: Opzioni) =>
    get<DocumentsResponse>(`/documents${query({ dataset_id: datasetId, collection })}`, o),

  /** I chunk di un documento, nell'ordine in cui sono stati prodotti (U-05). */
  documentChunks: (docId: string, datasetId: string, collection?: string, o?: Opzioni) =>
    get<DocumentChunksResponse>(
      `/document/${encodeURIComponent(docId)}/chunks${query({
        dataset_id: datasetId,
        collection,
      })}`,
      o,
    ),

  /** Cercare senza generare: nessuna GPU spesa per vedere delle fonti. */
  retrieve: (corpo: RetrieveRequestBody, o?: Opzioni) =>
    post<RetrieveResponse>("/retrieve", corpo, o),

  /** La risposta intera, per chi non streamma. Lo stream sta in `sse.ts`. */
  query: (corpo: QueryRequest, o?: Opzioni) => post<AnswerResponse>("/query", corpo, o),
};
