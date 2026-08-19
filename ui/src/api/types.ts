// Generato da `python scripts/gen_api_types.py` -- non modificare a mano.
//
// Il contratto del §3.5 in TypeScript. La Fase 8 vieta al frontend di importare
// `src/`, quindi il contratto esiste due volte; questo file e' la copia che non
// si scrive. `tests/test_ui_types.py` fallisce se non e' aggiornato.
//
// `GET /health` non e' qui: risponde `{"status": "ok"}`, che e' una sonda di
// vitalita' e non un contratto dati.

// --- Cosa si puo' chiedere ---------------------------------------------
// Solo `query` (e `queries`) e' obbligatorio: tutto il resto ha un default
// lato server, ed e' il motivo per cui un client minimo continua a valere.

/** Una domanda, e come rispondervi. */
export interface QueryRequest {
  query: string;
  dataset_id?: string;
  collection?: string | null;
  top_k?: number | null;
  retrieval_mode?: string | null;
  rerank?: boolean | null;
  query_rewrite?: boolean | null;
  filter_content_type?: string | null;
  search_exact?: boolean | null;
  hnsw_ef?: number | null;
  model?: string | null;
  temperature?: number | null;
  max_new_tokens?: number | null;
  reasoning_effort?: string | null;
  rag?: boolean | null;
  baseline_prompt?: string | null;
  verify?: boolean | null;
}

/** Cercare senza rispondere, per una o molte query. */
export interface RetrieveRequestBody {
  queries: string[];
  dataset_id?: string;
  collection?: string | null;
  top_k?: number | null;
  retrieval_mode?: string | null;
  rerank?: boolean | null;
  query_rewrite?: boolean | null;
  filter_content_type?: string | null;
  search_exact?: boolean | null;
  hnsw_ef?: number | null;
}

// --- Cosa si riceve ----------------------------------------------------

/** La configurazione che ha davvero girato, rimandata indietro. */
export interface ConfigView {
  top_k: number;
  retrieval_mode: string;
  rerank: boolean;
  query_rewrite: boolean;
  filter_content_type: string;
  search_exact: boolean;
  hnsw_ef: number | null;
  model: string;
  temperature: number;
  max_new_tokens: number;
  reasoning_effort: string;
  rag: boolean;
  baseline_prompt: string;
  verify: boolean;
}

/** Un chunk recuperato, con tutto cio' che serve per mostrarlo e aprirlo. */
export interface ChunkView {
  marker: number;
  score: number;
  chunk_id: string;
  dataset_id: string;
  doc_id: string;
  doc_genre: string;
  pipeline: string;
  section_path: string;
  page: number;
  bbox: [number, number, number, number] | null;
  content_type: string;
  text: string;
  source_uri: string;
}

/** Una citazione col suo verdetto. **Nessuna viene filtrata** (U-07). */
export interface CitationView {
  marker: number;
  chunk_id: string;
  claim: string;
  supported: boolean;
  score: number;
  numeric: string;
}

/** Il gate di astensione (C-04), e se ha girato. */
export interface GateView {
  active: boolean;
  abstain: boolean;
  score: number;
  threshold: number | null;
}

/** La risposta intera, per chi non streamma. */
export interface AnswerResponse {
  query: string;
  dataset_id: string;
  collection: string;
  config: ConfigView;
  text: string;
  raw_text: string;
  repaired: boolean;
  abstained: boolean;
  abstention: string;
  truncated: boolean;
  chunks: ChunkView[];
  cited: number[];
  citations: CitationView[];
  uncited_claims: string[];
  verified: boolean;
  gate: GateView;
  timings: Record<string, number>;
}

/** I risultati, **nell'ordine delle query**. */
export interface RetrieveResponse {
  results: ChunkView[][];
  config: ConfigView;
}

/** Un documento della collection, e quanti chunk ne sono usciti (A-07). */
export interface DocumentView {
  doc_id: string;
  n_chunks: number;
}

/** I documenti di una collection, e da quale collection vengono. */
export interface DocumentsResponse {
  collection: string;
  documents: DocumentView[];
}

/** I chunk di un documento, **nell'ordine in cui sono stati prodotti**. */
export interface DocumentChunksResponse {
  collection: string;
  doc_id: string;
  chunks: ChunkView[];
}

/** Un modello del catalogo, con cio' che il motore sa dirne (A-08). */
export interface ModelView {
  name: string;
  family: string;
  context_max: number | null;
  context: number | null;
  parent: string;
  quantization: string;
  parameter_size: string;
}

/** Un dataset interrogabile, e lo stato del suo indice (U-01). */
export interface DatasetView {
  dataset_id: string;
  collection: string;
  ready: boolean;
  n_chunks: number;
}

/** Una collection e la forma del suo indice. */
export interface CollectionView {
  name: string;
  points: number;
  dense_size: number;
  has_sparse: boolean;
}

/** Cosa questo backend accetta. Letto, non indovinato. */
export interface Capabilities {
  retrieval_modes: string[];
  baseline_prompts: string[];
  reasoning_efforts: string[];
  models: string[];
  model_catalog: ModelView[];
  datasets: DatasetView[];
  collections: CollectionView[];
}

// --- Lo stream ---------------------------------------------------------
// I payload sono presi eseguendo `to_wire()`, non leggendolo: e' l'unico
// punto del contratto costruito a mano, cioe' l'unico che potrebbe
// divergere in silenzio.

export interface ChunksPayload {
  chunks: ChunkView[];
}

export interface TokenPayload {
  text: string;
}

export interface AnswerPayload {
  text: string;
  raw_text: string;
  repaired: boolean;
  abstained: boolean;
  abstention: string;
  truncated: boolean;
  verification_pending: boolean;
}

export interface CitationsPayload {
  citations: CitationView[];
  uncited_claims: string[];
}

export interface DonePayload {
  abstained: boolean;
  abstention: string;
  verified: boolean;
  timings: Record<string, number>;
  config: ConfigView;
}

export interface ErrorPayload {
  message: string;
  stage: string;
}

export type SseEvent =
  | { event: "chunks"; data: ChunksPayload }
  | { event: "token"; data: TokenPayload }
  | { event: "answer"; data: AnswerPayload }
  | { event: "citations"; data: CitationsPayload }
  | { event: "done"; data: DonePayload }
  | { event: "error"; data: ErrorPayload };

/** I nomi degli eventi del §3.5, nell'ordine in cui uno stream li emette. */
export const SSE_EVENTS = ["chunks", "token", "answer", "citations", "done", "error"] as const;

/** I valori di `abstention`, da `src/service/answer.py`. */
export const ABSTENTION = {
  nessuna: "",
  gate: "retrieval",
  modello: "model",
} as const;
