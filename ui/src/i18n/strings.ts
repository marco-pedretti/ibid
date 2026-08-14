/**
 * La cornice in due lingue. **Non il contenuto.**
 *
 * Il selettore IT/EN traduce etichette, avvisi e nomi degli stati. Non tocca il
 * testo del modello, gli estratti dei chunk ne' i messaggi del backend: quelli
 * seguono la lingua della domanda e del corpus.
 *
 * Non e' comodita'. Far rispondere in italiano su un corpus inglese
 * significherebbe che le citazioni sostengono un testo **tradotto**, e il
 * verificatore NLI di C-03 dovrebbe giudicare cross-lingua un'implicazione che
 * non ha mai misurato in quella condizione. La precisione di citazione e' la
 * prima affermazione del §0: non si baratta con una comodita' di presentazione.
 *
 * Che la lingua non arrivi mai all'API non e' una regola da ricordare, e' una
 * proprieta' del contratto: `QueryRequest` non ha un campo lingua, quindi non
 * c'e' modo di mandarla.
 *
 * Nessuna libreria i18n: due lingue e un dizionario piatto sono trenta righe, e
 * `Record<Chiave, string>` fa fallire **la compilazione** su una chiave mancante
 * — prima e meglio di qualsiasi test.
 */

export const it = {
  "app.tagline": "RAG con citazioni verificate a livello di frase",

  "nav.chat": "Chat",
  "nav.explore": "Esplora il corpus",

  "theme.label": "Tema",
  "theme.light": "Chiaro",
  "theme.dark": "Scuro",
  "theme.system": "Sistema",

  "lang.label": "Lingua dell'interfaccia",
  "lang.note":
    "La risposta segue la lingua della domanda, non questo selettore.",

  "backend.loading": "Contatto il backend…",
  "backend.down": "Backend non raggiungibile",
  "backend.hint": "Avvia l'API e riprova.",
  "backend.retry": "Riprova",

  "datasets.title": "Dataset",
  "datasets.ready": "pronto",
  "datasets.empty": "indice vuoto",
  "datasets.chunks": "chunk",
  "datasets.change": "Cambia dataset",
  "datasets.notQueryable": "indice vuoto: non interrogabile",
  "datasets.none": "Nessun indice pronto",
  "datasets.none.hint": "Costruisci un indice con «make ingest», poi ricarica.",

  "index.title": "Indice",
  "index.collection": "Collection",
  "index.points": "punti",
  "index.dense": "dimensione densa",
  "index.sparse": "vettori sparsi",
  "index.missing": "Il server non elenca nessuna collection con questo nome.",

  "chat.empty.title": "Chiedi qualcosa al corpus.",
  "chat.empty.hint":
    "Ogni frase della risposta porta la fonte da cui viene, e le fonti compaiono prima del testo.",
  "chat.placeholder": "Scrivi una domanda…",
  "chat.send": "Invia",
  "chat.stop": "Ferma",
  "chat.noDataset": "Scegli un dataset per poter chiedere.",
  "chat.hint.invio": "Invio per mandare, Maiusc+Invio per andare a capo.",

  "example.note.numbers": "Un numero preciso: la citazione deve reggerlo.",
  "example.note.paper": "Sta dentro un paper: guarda da quale sezione arriva.",
  "example.note.table": "La risposta sta in una tabella.",
  "example.note.absent": "Non c'è nel corpus. Guarda cosa succede.",

  "stato.attesa": "cerco nel corpus…",
  "stato.fonti": "il modello sta scrivendo…",
  "stato.scrittura": "scrivo… · marcatori non ancora attivi",
  "stato.risposta": "testo definitivo · controllo le citazioni…",
  "stato.citazioni": "verdetti arrivati",
  "stato.interrotta": "fermata · resta la risposta parziale",
  "stato.errore": "interrotto",
  "stato.troncato": "risposta troncata: il limite di token è stato raggiunto",
  "stato.riparato": "marcatori normalizzati dal parser",

  "sources.title": "Fonti",
  "sources.waiting":
    "Le fonti compaiono qui appena il retrieval risponde, prima che il modello cominci a scrivere.",
  "sources.none": "Nessuna fonte recuperata per questa domanda.",
  "sources.uncited": "Frasi senza citazione",

  "yes": "sì",
  "no": "no",

  "models.title": "Modelli",
  "models.none":
    "Nessun modello: l'endpoint di inferenza non risponde. I dataset restano interrogabili.",

  "verdict.supported": "Sostenuta",
  "verdict.unsupported": "Non sostiene",
  "verdict.pending": "Verifica in corso",
  "verdict.unverified": "Non verificata",

  "abstention.gate": "Astenuto prima di generare",
  "abstention.model": "Il modello si è astenuto",

  "history.local":
    "La cronologia resta in questo browser: non c'è nessun account, e cambiando macchina non la ritrovi.",
} as const;

export type Chiave = keyof typeof it;

export const en: Record<Chiave, string> = {
  "app.tagline": "RAG with sentence-level verified citations",

  "nav.chat": "Chat",
  "nav.explore": "Explore the corpus",

  "theme.label": "Theme",
  "theme.light": "Light",
  "theme.dark": "Dark",
  "theme.system": "System",

  "lang.label": "Interface language",
  "lang.note": "The answer follows the language of your question, not this setting.",

  "backend.loading": "Reaching the backend…",
  "backend.down": "Backend unreachable",
  "backend.hint": "Start the API and try again.",
  "backend.retry": "Retry",

  "datasets.title": "Datasets",
  "datasets.ready": "ready",
  "datasets.empty": "empty index",
  "datasets.chunks": "chunks",
  "datasets.change": "Change dataset",
  "datasets.notQueryable": "empty index: not queryable",
  "datasets.none": "No index ready",
  "datasets.none.hint": "Build one with “make ingest”, then reload.",

  "index.title": "Index",
  "index.collection": "Collection",
  "index.points": "points",
  "index.dense": "dense size",
  "index.sparse": "sparse vectors",
  "index.missing": "The server lists no collection with this name.",

  "chat.empty.title": "Ask the corpus something.",
  "chat.empty.hint":
    "Every sentence carries the source it came from, and the sources appear before the text does.",
  "chat.placeholder": "Type a question…",
  "chat.send": "Send",
  "chat.stop": "Stop",
  "chat.noDataset": "Pick a dataset before asking.",
  "chat.hint.invio": "Enter to send, Shift+Enter for a new line.",

  "example.note.numbers": "A precise number: the citation has to hold it up.",
  "example.note.paper": "It sits inside a paper: look at which section it comes from.",
  "example.note.table": "The answer is in a table.",
  "example.note.absent": "It is not in the corpus. Watch what happens.",

  "stato.attesa": "searching the corpus…",
  "stato.fonti": "the model is writing…",
  "stato.scrittura": "writing… · markers not reliable yet",
  "stato.risposta": "final text · checking the citations…",
  "stato.citazioni": "verdicts in",
  "stato.interrotta": "stopped · the partial answer stays",
  "stato.errore": "interrupted",
  "stato.troncato": "answer truncated: the token limit was reached",
  "stato.riparato": "markers normalised by the parser",

  "sources.title": "Sources",
  "sources.waiting":
    "Sources show up here as soon as retrieval answers, before the model starts writing.",
  "sources.none": "No sources retrieved for this question.",
  "sources.uncited": "Sentences with no citation",

  "yes": "yes",
  "no": "no",

  "models.title": "Models",
  "models.none":
    "No models: the inference endpoint is not answering. Datasets remain queryable.",

  "verdict.supported": "Supported",
  "verdict.unsupported": "Not supported",
  "verdict.pending": "Verifying",
  "verdict.unverified": "Unverified",

  "abstention.gate": "Abstained before generating",
  "abstention.model": "The model abstained",

  "history.local":
    "History stays in this browser: there is no account, and you will not find it on another machine.",
};

export const LINGUE = ["it", "en"] as const;
export type Lingua = (typeof LINGUE)[number];

export const DIZIONARI: Record<Lingua, Record<Chiave, string>> = { it, en };
