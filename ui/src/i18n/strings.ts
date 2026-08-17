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

  // Il numero in alto a destra di una scheda **non è una grandezza sola**: cambia
  // con la configurazione che ha girato, e un'unica etichetta «punteggio» sarebbe
  // vera e inutile — 0,875 in `dense` e 0,016 in `hybrid` sono due fonti ottime.
  "score.marker":
    "Il numero con cui la risposta cita questa fonte: cerca [{marker}] nel testo e trovi le frasi che vengono da qui.",
  "score.retrieval.dense":
    "Quanto questo pezzo di documento assomiglia alla domanda, da 0 a 1: più è alto, più parla della stessa cosa. Serve a mettere le fonti in ordine, non dice se la risposta è giusta. (Ricerca per significato.)",
  "score.retrieval.sparse":
    "Quanto le parole della domanda compaiono in questo pezzo, contando di più quelle rare. Cerca le parole e non il significato, quindi un sinonimo non lo trova. (BM25.)",
  "score.retrieval.hybrid":
    "Non è una somiglianza: dice quanto in alto questo pezzo è finito nelle due ricerche — quella per significato e quella per parole — messe insieme. Resta un numero piccolo per come è fatto: 0,03 qui può valere come uno 0,9 di somiglianza. (Fusione RRF.)",
  "score.retrieval.rerank":
    "Un secondo modello ha riletto domanda e pezzo insieme, uno alla volta, e li ha rimessi in ordine: questo è il suo giudizio, e prende il posto del punteggio della ricerca. Non va da 0 a 1, quindi si confronta solo con gli altri di questa stessa risposta. (Reranker.)",
  "score.retrieval.unknown":
    "Il punteggio con cui la ricerca ha messo in ordine questa fonte. Cosa misura esattamente dipende da come si è cercato, e quella informazione arriva quando la risposta è finita.",
  "sources.count": "Quante fonti la ricerca ha portato per questa domanda.",

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
  //
  // **I suggerimenti sono scritti per chi ne sa qualcosa ma non troppo**, e la
  // regola e' una: prima cosa vuol dire il numero per chi legge, poi come si
  // chiama. Il nome tecnico resta in coda, fra parentesi, per chi vuole cercarlo
  // altrove -- ma una frase che si apre con «somiglianza cosinusoidale» chiede di
  // sapere gia' la risposta, cioe' non spiega niente. Il modello che giudica le
  // citazioni si chiama qui **«il controllo»**, sempre, e quando ce ne sono due si
  // distinguono per cosa leggono: la prosa o i numeri.
  "verdict.supported": "sostiene",
  "verdict.unsupported": "non sostiene",
  "verdict.mixed": "{quante} su {su} non sostiene",
  "verdict.pending": "controllo…",
  "verdict.unverified": "non verificata",
  "verdict.notCited": "non citata",
  "verdict.inert": "marcatore non ancora attivo",
  // Cio' che si legge sul marcatore in mezzo alla prosa, e cio' che un lettore di
  // schermo sente al posto del glifo e del colore.
  "verdict.marker": "Questa frase cita la fonte {marker}. Il controllo dice: {verdetto}.",
  "verdict.marker.inert":
    "Il modello sta ancora scrivendo. Finché il testo non è definitivo questo non è un riferimento su cui contare: il controllo del formato può ancora correggerlo, o scartarlo se punta a una fonte che non c'è.",
  "verdict.marker.score":
    "Questa frase cita la fonte {marker}. Il controllo dice: {verdetto} — ne è convinto {punteggio} su 1.",
  // La soglia (0,50) non è scritta qui di proposito: è una costante del backend,
  // e U-00 vieta al frontend di portarsele dietro. Per mostrarla servirebbe un
  // campo nel contratto, come `GateView.threshold` ce l'ha per il gate.
  "verdict.score":
    "Quanto il controllo è convinto che questa fonte dica davvero ciò che la frase afferma: 0 per niente, 1 del tutto. Il verdetto accanto è il confronto con una soglia fissata nella configurazione.",
  "verdict.score.many":
    "Più frasi citano questa fonte, e questo è il numero della citazione più debole — quella più vicina a non passare. Mostrare la media di verdetti diversi non direbbe niente.",
  "verdict.count": "Quante frasi della risposta citano questa fonte.",

  // Il verificatore numerico di C-09, **accanto** a quello NLI e non al suo posto.
  // La parola dice cosa ha guardato e non il nome del verificatore: «numerico»
  // richiederebbe una legenda, «la tabella» no.
  "verdict.numeric.supported": "la tabella lo conferma",
  "verdict.numeric.unsupported": "la tabella non lo conferma",
  "verdict.numeric.mixed": "la tabella non conferma {quante} su {su}",
  "verdict.numeric.what":
    "Un secondo controllo, solo per le cifre: cerca i numeri della frase dentro la tabella citata, riga per riga. Non usa un modello di linguaggio, quindi sulle tabelle sbaglia meno di quello che legge la prosa.",

  // Perché quel verdetto è quello. È la spiegazione più utile del pannello, e
  // prima stava soltanto nel `title` del numero accanto -- cioè non c'era.
  "verdict.why.supported":
    "Il controllo ha riletto la frase e questa fonte, e ha giudicato che la fonte la sostenga.",
  "verdict.why.unsupported":
    "Il controllo non trova in questa fonte ciò che la frase afferma. Non è un guasto: è il dato che questo progetto esiste per misurare, e resta in vista invece di essere tolto.",
  "verdict.why.mixed":
    "Più frasi citano questa fonte, e il controllo non dà lo stesso esito su tutte: alcune le sostiene, altre no.",
  "verdict.why.pending":
    "Il controllo delle citazioni parte quando la risposta ha finito di scrivere: in mezzo ai due momenti il verdetto non esiste ancora.",
  "verdict.why.unverified":
    "Nessun verdetto per questa citazione: o il controllo era spento in questa run, o la frase era troppo corta perché «la fonte lo sostiene?» avesse una risposta.",
  "verdict.why.notCited":
    "La ricerca ha portato questa fonte, ma la risposta non l'ha citata. Resta qui perché nascondere le fonti non usate farebbe sembrare la ricerca più precisa di com'è.",

  // Il riepilogo sotto la risposta: e' qui che il verdetto diventa una **frase**,
  // e non un ornamento -- il §12 chiede glifo, colore e parola insieme, e sul
  // marcatore in mezzo alla prosa ci stanno solo i primi due.
  "report.title.unsupported": "Non tutte le citazioni reggono.",
  "report.title.uncited": "Qualche frase non cita nessuna fonte.",
  "report.title.unverified": "Non tutti i marcatori hanno un verdetto.",
  "report.title.disagreement": "I due verificatori non concordano.",
  "report.marks": "Non sostenute: {marcatori}.",
  "report.numeric":
    "Di queste, {quante} sono invece confermate dal controllo dei numeri: la cifra sta davvero nella tabella citata, ma il controllo che legge la prosa non la vede. Su una tabella vale il primo: in questo corpus il 96,7% delle frasi afferma un numero, ed è la ragione per cui il controllo dei numeri esiste.",
  "report.uncited": "Frasi senza citazione: {quante}, sottolineate nel testo.",
  "report.unverified":
    "Citazioni senza verdetto: {quante}. Il controllo non ha girato, oppure la frase era troppo corta perché «la fonte lo sostiene?» avesse una risposta.",
  "report.why":
    "Niente di tutto questo è nascosto: una citazione che non regge è il dato, non un errore. E dato che citare di meno fa salire la precisione, le frasi senza citazione si contano insieme alle altre.",

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

  "score.marker":
    "The number the answer uses to cite this source: look for [{marker}] in the text to find the sentences that come from here.",
  "score.retrieval.dense":
    "How much this piece of the document resembles the question, from 0 to 1: the higher it is, the more it talks about the same thing. It puts the sources in order; it does not say the answer is right. (Search by meaning.)",
  "score.retrieval.sparse":
    "How much the question’s words appear in this piece, counting rare ones for more. It looks for words, not meaning, so it will not find a synonym. (BM25.)",
  "score.retrieval.hybrid":
    "Not a similarity: it says how high this piece landed in the two searches — one by meaning, one by words — put together. It stays a small number by design: 0.03 here can be worth a 0.9 similarity. (RRF fusion.)",
  "score.retrieval.rerank":
    "A second model reread the question and the piece together, one at a time, and put them back in order: this is its judgement, and it takes the place of the search score. It does not run 0 to 1, so it only compares with the others in this same answer. (Reranker.)",
  "score.retrieval.unknown":
    "The score the search used to put this source in order. What exactly it measures depends on how the search ran, and that information arrives once the answer is done.",
  "sources.count": "How many sources the search brought back for this question.",

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
  "verdict.marker": "This sentence cites source {marker}. The checker says: {verdetto}.",
  "verdict.marker.inert":
    "The model is still writing. Until the text is final this is not a reference to rely on: the format check can still fix it, or drop it if it points at a source that is not there.",
  "verdict.marker.score":
    "This sentence cites source {marker}. The checker says: {verdetto} — it is {punteggio} out of 1 convinced.",
  "verdict.score":
    "How convinced the checker is that this source really says what the sentence claims: 0 not at all, 1 entirely. The verdict next to it is that number against a threshold set in the configuration.",
  "verdict.score.many":
    "Several sentences cite this source, and this is the weakest citation’s number — the one closest to not passing. Averaging different verdicts would say nothing.",
  "verdict.count": "How many sentences of the answer cite this source.",

  "verdict.numeric.supported": "the table confirms it",
  "verdict.numeric.unsupported": "the table does not confirm it",
  "verdict.numeric.mixed": "the table does not confirm {quante} of {su}",
  "verdict.numeric.what":
    "A second check, for figures only: it looks for the sentence’s numbers inside the cited table, row by row. No language model involved, so on tables it gets it wrong less often than the one reading prose.",

  "verdict.why.supported":
    "The checker reread the sentence and this source, and judged that the source supports it.",
  "verdict.why.unsupported":
    "The checker cannot find in this source what the sentence claims. This is not a failure: it is the very thing this project exists to measure, and it stays in view instead of being removed.",
  "verdict.why.mixed":
    "Several sentences cite this source, and the checker does not reach the same verdict on all of them.",
  "verdict.why.pending":
    "Citation checking starts once the answer has finished writing: between those two moments the verdict does not exist yet.",
  "verdict.why.unverified":
    "No verdict for this citation: either checking was off in this run, or the sentence was too short for “does the source support this?” to have an answer.",
  "verdict.why.notCited":
    "Retrieval brought this source back, but the answer did not cite it. It stays here because hiding the unused sources would make retrieval look more precise than it is.",

  "report.title.unsupported": "Not every citation holds up.",
  "report.title.uncited": "Some sentences cite no source.",
  "report.title.unverified": "Not every marker has a verdict.",
  "report.title.disagreement": "The two verifiers disagree.",
  "report.marks": "Not supported: {marcatori}.",
  "report.numeric":
    "Of those, {quante} are confirmed instead by the number check: the figure really is in the cited table, but the checker reading the prose does not see it. On a table the first one holds — in this corpus 96.7% of sentences assert a number, which is why the number check exists.",
  "report.uncited": "Sentences with no citation: {quante}, underlined in the text.",
  "report.unverified":
    "Citations with no verdict: {quante}. Checking did not run, or the sentence was too short for “does the source support this?” to have an answer.",
  "report.why":
    "None of this is hidden: a citation that does not hold up is the finding, not a bug. And since citing less makes precision go up, the sentences with no citation are counted alongside the rest.",

  "abstention.gate": "Abstained before generating",
  "abstention.model": "The model abstained",

  "history.local":
    "History stays in this browser: there is no account, and you will not find it on another machine.",
};

export const LINGUE = ["it", "en"] as const;
export type Lingua = (typeof LINGUE)[number];

export const DIZIONARI: Record<Lingua, Record<Chiave, string>> = { it, en };
