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

  "yes": "sì",
  "no": "no",

  "models.title": "Modelli",
  "models.none":
    "Nessun modello: l'endpoint di inferenza non risponde. I dataset restano interrogabili.",

  // I verdetti (U-07). Minuscoli perche' sono targhette di dato, non frasi: il
  // §12 mette il mono nel ruolo dei dati, e una maiuscola in mezzo alla prosa di
  // una scheda alta due righe si legge come un titolo che non c'e'.
  //
  // «non sostiene» **non e' un errore**: U-07 dice che e' il dato, e la palette
  // lo rispetta usando `warn` (ocra) e non un rosso. La parola non esagera: dice
  // cosa il chunk non fa, non che qualcuno ha sbagliato.
  "verdict.supported": "sostiene",
  "verdict.unsupported": "non sostiene",
  "verdict.mixed": "{quante} su {su} non sostiene",
  "verdict.pending": "controllo…",
  "verdict.unverified": "non verificata",
  "verdict.notCited": "non citata",
  "verdict.inert": "marcatore non ancora attivo",
  // Cio' che un lettore di schermo sente al posto del glifo e del colore.
  "verdict.aria": "citazione {marker}: {verdetto}",
  "verdict.score": "punteggio di implicazione",
  "verdict.count": "frasi sostenute su frasi che citano questa fonte",

  // Il verificatore numerico di C-09, **accanto** a quello NLI e non al suo posto.
  // La parola dice cosa ha guardato e non il nome del verificatore: «numerico»
  // richiederebbe una legenda, «la tabella» no.
  "verdict.numeric.supported": "la tabella lo conferma",
  "verdict.numeric.unsupported": "la tabella non lo conferma",
  "verdict.numeric.mixed": "la tabella non conferma {quante} su {su}",
  "verdict.numeric.what":
    "verifica numerica sulle tabelle (C-09): confronta le cifre della frase con quelle della tabella citata",

  // Il riepilogo sotto la risposta: e' qui che il verdetto diventa una **frase**,
  // e non un ornamento -- il §12 chiede glifo, colore e parola insieme, e sul
  // marcatore in mezzo alla prosa ci stanno solo i primi due.
  "report.title.unsupported": "Non tutte le citazioni reggono.",
  "report.title.uncited": "Qualche frase non cita nessuna fonte.",
  "report.title.unverified": "Non tutti i marcatori hanno un verdetto.",
  "report.title.disagreement": "I due verificatori non concordano.",
  "report.marks": "Non sostenute: {marcatori}.",
  "report.numeric":
    "Di queste, {quante} sono confermate dalla verifica numerica: la cifra sta nella tabella citata, ma il modello NLI non la vede. Su tabelle vale il secondo verificatore — il 96,7% dei claim di questo corpus è numerico, ed è la ragione per cui C-09 esiste.",
  "report.uncited": "Frasi senza citazione: {quante}, sottolineate nel testo.",
  "report.unverified":
    "Citazioni senza verdetto: {quante}. La verifica non ha girato, o la frase era troppo corta perché «il chunk la sostiene?» avesse una risposta.",
  "report.why":
    "Nessuna è nascosta: una citazione che non regge è il dato, non un errore. E la precisione si alza citando di meno, quindi le frasi scoperte si contano insieme alle altre.",

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

  "yes": "yes",
  "no": "no",

  "models.title": "Models",
  "models.none":
    "No models: the inference endpoint is not answering. Datasets remain queryable.",

  "verdict.supported": "supports",
  "verdict.unsupported": "does not support",
  "verdict.mixed": "{quante} of {su} do not hold",
  "verdict.pending": "checking…",
  "verdict.unverified": "unverified",
  "verdict.notCited": "not cited",
  "verdict.inert": "marker not active yet",
  "verdict.aria": "citation {marker}: {verdetto}",
  "verdict.score": "entailment score",
  "verdict.count": "supported sentences out of sentences citing this source",

  "verdict.numeric.supported": "the table confirms it",
  "verdict.numeric.unsupported": "the table does not confirm it",
  "verdict.numeric.mixed": "the table does not confirm {quante} of {su}",
  "verdict.numeric.what":
    "numeric verification over tables (C-09): matches the figures in the sentence against the cited table",

  "report.title.unsupported": "Not every citation holds up.",
  "report.title.uncited": "Some sentences cite no source.",
  "report.title.unverified": "Not every marker has a verdict.",
  "report.title.disagreement": "The two verifiers disagree.",
  "report.marks": "Not supported: {marcatori}.",
  "report.numeric":
    "Of those, {quante} are confirmed by numeric verification: the figure is in the cited table, but the NLI model does not see it. On tables the second verifier is the one that holds — 96.7% of this corpus’s claims are numeric, which is why C-09 exists.",
  "report.uncited": "Sentences with no citation: {quante}, underlined in the text.",
  "report.unverified":
    "Citations with no verdict: {quante}. Verification did not run, or the sentence was too short for “does the chunk support this?” to have an answer.",
  "report.why":
    "None of this is hidden: a citation that does not hold up is the finding, not a bug. And precision goes up by citing less, so the uncovered sentences are counted alongside the rest.",

  "abstention.gate": "Abstained before generating",
  "abstention.model": "The model abstained",

  "history.local":
    "History stays in this browser: there is no account, and you will not find it on another machine.",
};

export const LINGUE = ["it", "en"] as const;
export type Lingua = (typeof LINGUE)[number];

export const DIZIONARI: Record<Lingua, Record<Chiave, string>> = { it, en };
