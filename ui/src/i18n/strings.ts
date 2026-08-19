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
 *
 * ## Come si scrive una di queste frasi
 *
 * **Sintetica, chiara a un non esperto, e comunque apprezzabile da uno esperto.**
 * Tutte e tre insieme: la sintesi non e' l'extra da sacrificare quando si guadagna
 * chiarezza. Una spiegazione che non si legge non spiega, esattamente come una che
 * non si capisce — e si e' sbagliato in entrambi i versi prima di arrivare qui.
 *
 * - **una frase, due al massimo**;
 * - si apre con **cosa vuol dire per chi legge**, non con come si chiama;
 * - il nome tecnico resta, **in coda e fra parentesi**: e' cio' che rende la frase
 *   utile anche a chi ne sa — cercabile altrove, senza essere un prerequisito.
 *   «Somiglianza cosinusoidale fra la domanda e il chunk» chiede di sapere gia' la
 *   risposta; «quanto questo pezzo assomiglia alla domanda, da 0 a 1 (ricerca per
 *   significato)» la da' a tutti e due;
 * - si tiene **il dettaglio che un esperto cerca** — un intervallo, un limite
 *   noto, un caveat di confrontabilita' — e si taglia il resto. E' quello, non la
 *   lunghezza, a rendere una frase non banale;
 * - **niente sigle interne**: `C-03`, `C-09`, `NLI`, `parser`, `endpoint` restano
 *   nel codice, dove servono. Al loro posto un nome piano usato **sempre uguale**:
 *   il modello che giudica le citazioni e' «il controllo», e quando ce ne sono due
 *   si distinguono per cosa leggono, la prosa o i numeri.
 */

export const it = {
  "theme.label": "Tema",
  "theme.light": "Chiaro",
  "theme.dark": "Scuro",
  "theme.system": "Sistema",

  "lang.label": "Lingua dell'interfaccia",
  // Sul selettore, dove «questo» ha un referente che si vede.
  "lang.hint": "Cambia solo la lingua dell'interfaccia: la risposta segue quella della domanda.",

  "backend.loading": "Contatto il server…",
  "backend.down": "Server non raggiungibile",
  "backend.hint": "Avvialo con «make dev», poi ricarica.",
  "backend.retry": "Riprova",

  "datasets.title": "Dataset",
  "datasets.empty": "indice vuoto",
  "datasets.chunks": "chunk",
  "datasets.change": "Cambia dataset",
  "datasets.notQueryable": "indice vuoto: non interrogabile",
  "datasets.none": "Nessun indice pronto",
  "datasets.none.hint": "Costruisci un indice con «make ingest», poi ricarica.",

  // Il criterio di U-13 chiede che la cronologia **dichiari** di essere locale, e
  // la parola sta nel nome della sezione. Prima la frase intera stava sotto
  // l'elenco: vera, e scollegata da ciò di cui parlava. Qui «locale» ha un
  // referente, e la spiegazione è a un passaggio invece di prendere cinque righe
  // di una corsia larga 200 px.
  "history.title": "Cronologia locale",
  "history.hint":
    "Le conversazioni restano in questo browser: nessun account e nessun server, quindi su un'altra macchina non le ritrovi.",
  "history.new": "Nuova conversazione",
  // Sulle voci mentre una risposta sta arrivando: dice **cosa fare**, non solo
  // che non si può. Lo stream scrive in una conversazione sola.
  "history.busy": "Aspetta che la risposta finisca, o premi «Ferma».",
  // Il nome del cestino per chi ascolta: nella riga è solo un'icona.
  "history.clear": "Cancella la cronologia",
  // Armato, questa domanda **prende il posto** del nome della sezione: accanto
  // non ci starebbe, e sotto il puntatore c'è già il cestino a cui rispondere.
  "history.clear.confirm": "Cancellare tutto?",
  "history.clear.hint":
    "Toglie tutte le conversazioni da questo browser: chiede un secondo clic, e non si torna indietro.",
  "history.clear.again": "Ancora un clic e sono via.",

  "chat.empty.title": "Chiedi qualcosa al corpus.",
  "chat.empty.hint":
    "Ogni frase della risposta porta la fonte da cui viene, e le fonti compaiono prima del testo.",
  "chat.placeholder": "Scrivi una domanda…",
  "chat.send": "Invia",
  "chat.stop": "Ferma",
  "chat.noDataset": "Scegli un dataset per poter chiedere.",
  // Il modello configurato non è stato scaricato. Si segnala e non si scarica:
  // il download è gigabyte, l’API per farlo è quella nativa di un motore solo, e
  // U-08 chiede che la demo si apra in due minuti senza scaricare niente.
  "chat.noModel": "Il modello configurato non è installato: scegline uno dalla barra qui sotto.",
  "chat.hint.invio": "Invio per mandare, Maiusc+Invio per andare a capo.",

  // La nota a margine di U-15: si legge a malapena, come quella sopra il campo.
  // Non e' un messaggio della conversazione -- non l'ha detto nessuno.
  "params.start": "partita con",
  "params.default": "coi parametri predefiniti del servizio",
  "params.none": "nessuno",
  "params.all": "La configurazione che ha girato:",

  "bar.rag": "RAG",
  "bar.rag.hint":
    "Acceso, la risposta viene dal corpus e porta le fonti. Spento, il modello risponde da solo: è l'altra metà del confronto, non un guasto.",
  "bar.reasoning": "Ragionamento",
  // L'unico comando dell'interfaccia che dichiara il proprio costo, e con i
  // numeri veri di C-07: senza, un interruttore invita ad accendere ciò che
  // abbiamo misurato non convenire. Niente sigle di task nella UI.
  "bar.reasoning.hint":
    "Fa ragionare il modello prima che risponda. L'abbiamo misurato: +0,6 punti di citazioni ben formate, 9,5× i token, e sui bilanci le domande a cui rifiuta di rispondere passano da 56 a 90 su 200.",
  "bar.model": "Modello",
  "bar.default": "predefinito",
  "bar.model.hint":
    "Chi risponde. Con un buon recupero la taglia del modello conta meno del previsto: è una delle cose che questo progetto misura.",
  // `/config` dice come il servizio è configurato, non cosa è stato scaricato:
  // il predefinito compare in elenco lo stesso, disabilitato, perché una voce
  // assente non spiegherebbe perché non è selezionato niente.
  "bar.model.notInstalled": "non installato",
  "bar.model.missing":
    "Il modello configurato non è fra quelli installati sul servizio di inferenza: scegline uno dall’elenco, oppure installalo lì.",
  // Il nome si sa comunque, lo dice `/config`: ciò che manca non è sapere chi
  // risponde, è poterlo cambiare — e la frase dice quello.
  "bar.model.none":
    "L'elenco dei modelli non è arrivato dal servizio di inferenza: risponde quello configurato, e per ora non si può cambiare.",
  // Il secondo selettore di U-16. «Contesto» e non «finestra di contesto»: la
  // pastiglia sta accanto ad altre quattro, e la parola lunga la fa a capo.
  "bar.context": "Contesto",
  "bar.context.hint":
    "Quanto testo entra nel modello prima che risponda: più contesto vuol dire più fonti insieme, e più memoria occupata. Ci sono solo le misure che questo modello regge.",
  "bar.context.default": "predefinito",
  "bar.advanced": "Avanzate",
  "bar.advanced.hint":
    "Come si cerca nel corpus, prima che il modello scriva. Stanno chiuse di proposito: confrontare configurazioni è il lavoro del cruscotto, non di qui.",
  "bar.advanced.mode": "Ricerca",
  "bar.advanced.rerank": "Riordino",
  "bar.advanced.on": "acceso",
  "bar.advanced.off": "spento",
  "bar.advanced.auto": "auto",
  "bar.advanced.less": "Un passo in giù",
  "bar.advanced.more": "Un passo in su",
  "bar.advanced.reset": "Torna al predefinito",

  // Il confronto. È un'azione su una risposta già data, non un secondo
  // messaggio: le parole dicono «la stessa domanda», mai «chiedi di nuovo».
  "compare.action.bare": "Confronta senza le fonti",
  "compare.action.sourced": "Confronta con le fonti",
  "compare.action.hint":
    "Rifà la stessa domanda cambiando solo questo. Tutto il resto — modello, ricerca, temperatura — resta identico, altrimenti le due risposte differirebbero per più di una cosa.",
  "compare.title": "Stessa domanda",
  "compare.withSources": "Con le fonti",
  "compare.withoutSources": "Senza fonti",
  "compare.back": "Torna alla conversazione",
  "compare.busy": "Aspetta che la risposta finisca, oppure fermala.",
  "compare.verdicts": "{sostenute} su {citazioni} sostenute",
  // Non «sbagliato»: senza fonti non si può sapere se è giusta, ed è il punto.
  "compare.bare.title": "Niente di questo è verificabile.",
  "compare.bare.body":
    "Non c'è una fonte da aprire: nessuna frase di questa risposta si può controllare. È esattamente ciò che il progetto misura.",

  "example.note.numbers": "Un numero preciso: la citazione deve reggerlo.",
  "example.note.paper": "Sta dentro un paper: guarda da quale sezione arriva.",
  "example.note.table": "La risposta sta in una tabella.",
  "example.note.absent": "Non c'è nel corpus. Guarda cosa succede.",
  // Sotto gli esempi: spiega le **due righe**, che è la cosa che si vede lì.
  "example.lang":
    "Gli esempi sono tradotti, ma partono come li vedi nella seconda riga: la risposta segue la lingua della domanda.",

  "stato.attesa": "cerco nel corpus…",
  // Col RAG spento non c'è nessun retrieval: annunciarlo racconterebbe un passo
  // che non sta avvenendo, e nella colonna nuda far credere che si sia cercato
  // qualcosa è proprio l'equivoco da non creare.
  "stato.attesa.modello": "chiedo al modello…",
  "stato.fonti": "il modello sta scrivendo…",
  "stato.scrittura": "scrivo… · marcatori non ancora attivi",
  "stato.risposta": "testo definitivo · controllo le citazioni…",
  "stato.citazioni": "verdetti arrivati",
  "stato.interrotta": "fermata · resta la risposta parziale",
  "stato.errore": "interrotto",
  "stato.troncato": "risposta troncata: il limite di token è stato raggiunto",
  "stato.riparato": "marcatori rimessi nella forma richiesta",

  "sources.title": "Fonti",
  "sources.waiting":
    "Le fonti compaiono qui appena la ricerca risponde, prima che il modello scriva.",
  "sources.none": "Nessuna fonte trovata per questa domanda.",

  // Il numero in alto a destra di una scheda **non è una grandezza sola**: cambia
  // con la configurazione che ha girato, e un'unica etichetta «punteggio» sarebbe
  // vera e inutile — 0,875 in `dense` e 0,016 in `hybrid` sono due fonti ottime.
  "score.marker": "Il numero con cui la risposta cita questa fonte: cerca [{marker}] nel testo.",
  "score.retrieval.dense":
    "Quanto questo pezzo assomiglia alla domanda, da 0 a 1: ordina le fonti, non dice se la risposta è giusta. (Ricerca per significato.)",
  "score.retrieval.sparse":
    "Quanto le parole della domanda compaiono in questo pezzo, contando di più quelle rare: cerca le parole, non il significato. (BM25.)",
  "score.retrieval.hybrid":
    "Quanto in alto questo pezzo è finito nelle due ricerche, per significato e per parole, messe insieme. Non è una somiglianza: resta piccolo per costruzione. (Fusione RRF.)",
  "score.retrieval.rerank":
    "Un secondo modello ha riletto domanda e pezzo insieme e li ha rimessi in ordine. Non va da 0 a 1: si confronta solo dentro questa risposta. (Reranker.)",
  "score.retrieval.unknown":
    "Il punteggio con cui la ricerca ha ordinato questa fonte. Cosa misura dipende da come si è cercato, e si sa a risposta finita.",
  "sources.count": "Quante fonti la ricerca ha portato.",

  // I verdetti (U-07). Minuscoli perche' sono targhette di dato, non frasi: il
  // §12 mette il mono nel ruolo dei dati, e una maiuscola in mezzo alla prosa di
  // una scheda alta due righe si legge come un titolo che non c'e'.
  //
  // «non sostiene» **non e' un errore**: U-07 dice che e' il dato, e la palette
  // lo rispetta usando `warn` (ocra) e non un rosso. La parola non esagera: dice
  // cosa il chunk non fa, non che qualcuno ha sbagliato.
  "verdict.supported": "sostiene",
  "verdict.unsupported": "non sostiene",
  "verdict.mixed": "non sostiene {quante} su {su}",
  "verdict.pending": "controllo…",
  "verdict.unverified": "non verificata",
  "verdict.notCited": "non citata",
  "verdict.inert": "marcatore non ancora attivo",
  // Cio' che si legge sul marcatore in mezzo alla prosa, e cio' che un lettore di
  // schermo sente al posto del glifo e del colore.
  "verdict.marker": "Cita la fonte {marker}. Il controllo dice: {verdetto}.",
  "verdict.marker.inert":
    "Il testo non è ancora definitivo: questo marcatore può essere corretto, o scartato se punta a una fonte che non c'è.",
  "verdict.marker.score":
    "Cita la fonte {marker}. Il controllo dice: {verdetto}, {punteggio} su 1.",
  // La soglia (0,50) non è scritta qui di proposito: è una costante del backend,
  // e U-00 vieta al frontend di portarsele dietro. Per mostrarla servirebbe un
  // campo nel contratto, come `GateView.threshold` ce l'ha per il gate.
  "verdict.score":
    "Quanto il controllo è convinto che questa fonte dica ciò che la frase afferma, da 0 a 1. Il verdetto è quel numero contro una soglia.",
  "verdict.score.many":
    "Più frasi citano questa fonte: questo è il numero della più debole, non una media.",
  "verdict.count": "Quante frasi della risposta citano questa fonte.",

  // Il verificatore numerico di C-09, **accanto** a quello NLI e non al suo posto.
  // La parola dice cosa ha guardato e non il nome del verificatore: «numerico»
  // richiederebbe una legenda, «la tabella» no.
  "verdict.numeric.supported": "la tabella lo conferma",
  "verdict.numeric.unsupported": "la tabella non lo conferma",
  "verdict.numeric.mixed": "la tabella non conferma {quante} su {su}",
  "verdict.numeric.what":
    "Un secondo controllo, solo per le cifre: cerca i numeri della frase dentro la tabella citata. Nessun modello di linguaggio, quindi sulle tabelle sbaglia meno.",

  // Perché quel verdetto è quello. È la spiegazione più utile del pannello, e
  // prima stava soltanto nel `title` del numero accanto -- cioè non c'era.
  "verdict.why.supported":
    "Il controllo ha riletto frase e fonte, e ha giudicato che la fonte la sostenga.",
  "verdict.why.unsupported":
    "Il controllo non trova in questa fonte ciò che la frase afferma. Non è un guasto: è il dato, e resta in vista.",
  "verdict.why.mixed":
    "Più frasi citano questa fonte, e il controllo non le giudica tutte allo stesso modo.",
  "verdict.why.pending": "Il controllo parte a risposta finita: fino a lì il verdetto non esiste.",
  "verdict.why.unverified":
    "Nessun verdetto: il controllo era spento in questa run, o la frase era troppo corta per giudicarla.",
  "verdict.why.notCited":
    "La ricerca l'ha portata, la risposta non l'ha citata. Resta qui: nascondere le fonti non usate farebbe sembrare la ricerca più precisa.",

  // Il riepilogo sotto la risposta: e' qui che il verdetto diventa una **frase**,
  // e non un ornamento -- il §12 chiede glifo, colore e parola insieme, e sul
  // marcatore in mezzo alla prosa ci stanno solo i primi due.
  "report.title.unsupported": "Non tutte le citazioni reggono.",
  "report.title.uncited": "Qualche frase non cita nessuna fonte.",
  "report.title.unverified": "Non tutti i marcatori hanno un verdetto.",
  "report.title.disagreement": "I due verificatori non concordano.",
  "report.marks": "Non sostenute: {marcatori}.",
  "report.numeric":
    "Di queste, {quante} le conferma il controllo dei numeri: la cifra c'è nella tabella, ma chi legge la prosa non la vede. Su una tabella vale lui — qui il 96,7% delle frasi afferma un numero.",
  "report.uncited": "Frasi senza citazione: {quante}, sottolineate nel testo.",
  "report.unverified":
    "Citazioni senza verdetto: {quante}. Il controllo era spento, o la frase era troppo corta per giudicarla.",
  "report.why":
    "Niente di questo è nascosto: una citazione che non regge è il dato, non un errore. E citare di meno alza la precisione, quindi le frasi scoperte contano.",

  "abstention.gate":
    "Non ha risposto: le fonti trovate erano troppo deboli, e il modello non è stato interrogato.",
  "abstention.model": "Il modello ha dichiarato di non trovare la risposta nelle fonti.",

  // --- non ancora in uso ---------------------------------------------------
  // Nessuno legge queste, e ognuna appartiene a un task che ha un nome. Stanno
  // qui e non fra le altre perche' altrimenti un ripasso le rivede come se
  // fossero sullo schermo: **vanno riscritte quando il task le accende**, con
  // davanti la cosa che devono spiegare. Una frase giudicata al buio non e' una
  // frase giudicata.
  // U-11 (il README) e la testata che non c'e' piu'
  "app.tagline": "RAG con citazioni verificate a livello di frase",

  // l'esploratore del corpus, §12
  "nav.chat": "Chat",
  "nav.explore": "Esplora il corpus",

  // il debito di U-02: i dati dell'indice sotto «Dettagli della run»
  "index.title": "Indice",
  "index.collection": "Collection",
  "index.points": "punti",
  "index.dense": "dimensione densa",
  "index.sparse": "vettori sparsi",
  "index.missing": "Il server non elenca nessuna collection con questo nome.",
} as const;

export type Chiave = keyof typeof it;

export const en: Record<Chiave, string> = {
  "theme.label": "Theme",
  "theme.light": "Light",
  "theme.dark": "Dark",
  "theme.system": "System",

  "lang.label": "Interface language",
  "lang.hint":
    "Changes the interface language only: the answer follows the language of your question.",

  "backend.loading": "Reaching the server…",
  "backend.down": "Server unreachable",
  "backend.hint": "Start it with “make dev”, then reload.",
  "backend.retry": "Retry",

  "datasets.title": "Datasets",
  "datasets.empty": "empty index",
  "datasets.chunks": "chunks",
  "datasets.change": "Change dataset",
  "datasets.notQueryable": "empty index: not queryable",
  "datasets.none": "No index ready",
  "datasets.none.hint": "Build one with “make ingest”, then reload.",

  "history.title": "Local history",
  "history.hint":
    "Conversations stay in this browser: no account and no server, so you will not find them on another machine.",
  "history.new": "New conversation",
  "history.busy": "Wait for the answer to finish, or press “Stop”.",
  "history.clear": "Clear the history",
  "history.clear.confirm": "Clear everything?",
  "history.clear.hint":
    "Removes every conversation from this browser: it asks for a second click, and there is no undo.",
  "history.clear.again": "One more click and they are gone.",

  "chat.empty.title": "Ask the corpus something.",
  "chat.empty.hint":
    "Every sentence carries the source it came from, and the sources appear before the text does.",
  "chat.placeholder": "Type a question…",
  "chat.send": "Send",
  "chat.stop": "Stop",
  "chat.noDataset": "Pick a dataset before asking.",
  "chat.noModel": "The configured model is not installed: pick one from the bar below.",
  "chat.hint.invio": "Enter to send, Shift+Enter for a new line.",

  "params.start": "started with",
  "params.default": "with the service defaults",
  "params.none": "none",
  "params.all": "The configuration that ran:",

  "bar.rag": "RAG",
  "bar.rag.hint":
    "On, the answer comes from the corpus and carries its sources. Off, the model answers on its own: that is the other half of the comparison, not a failure.",
  "bar.reasoning": "Reasoning",
  "bar.reasoning.hint":
    "Lets the model reason before it answers. We measured it: +0.6 points of well-formed citations, 9.5× the tokens, and on the ledgers the questions it refuses to answer go from 56 to 90 out of 200.",
  "bar.model": "Model",
  "bar.default": "default",
  "bar.model.hint":
    "Who answers. With good retrieval, model size matters less than expected: it is one of the things this project measures.",
  "bar.model.notInstalled": "not installed",
  "bar.model.missing":
    "The configured model is not among those installed on the inference service: pick one from the list, or install it there.",
  "bar.model.none":
    "The model list did not arrive from the inference service: the configured one answers, and for now it cannot be changed.",
  "bar.context": "Context",
  "bar.context.hint":
    "How much text fits into the model before it answers: more context means more sources at once, and more memory used. Only the sizes this model can take are listed.",
  "bar.context.default": "default",
  "bar.advanced": "Advanced",
  "bar.advanced.hint":
    "How the corpus is searched, before the model writes. Closed on purpose: comparing configurations is the dashboard's job, not this one's.",
  "bar.advanced.mode": "Search",
  "bar.advanced.rerank": "Reranking",
  "bar.advanced.on": "on",
  "bar.advanced.off": "off",
  "bar.advanced.auto": "auto",
  "bar.advanced.less": "One step down",
  "bar.advanced.more": "One step up",
  "bar.advanced.reset": "Back to the default",

  "compare.action.bare": "Compare without the sources",
  "compare.action.sourced": "Compare with the sources",
  "compare.action.hint":
    "Asks the same question again, changing only this. Everything else — model, search, temperature — stays identical, otherwise the two answers would differ in more than one thing.",
  "compare.title": "Same question",
  "compare.withSources": "With the sources",
  "compare.withoutSources": "Without sources",
  "compare.back": "Back to the conversation",
  "compare.busy": "Wait for the answer to finish, or stop it.",
  "compare.verdicts": "{sostenute} of {citazioni} supported",
  "compare.bare.title": "None of this can be checked.",
  "compare.bare.body":
    "There is no source to open: not one sentence of this answer can be verified. That is exactly what this project measures.",

  "example.note.numbers": "A precise number: the citation has to hold it up.",
  "example.note.paper": "It sits inside a paper: look at which section it comes from.",
  "example.note.table": "The answer is in a table.",
  "example.note.absent": "It is not in the corpus. Watch what happens.",
  "example.lang":
    "The examples are translated, but they are sent as the second line reads: the answer follows the language of the question.",

  "stato.attesa": "searching the corpus…",
  "stato.attesa.modello": "asking the model…",
  "stato.fonti": "the model is writing…",
  "stato.scrittura": "writing… · markers not reliable yet",
  "stato.risposta": "final text · checking the citations…",
  "stato.citazioni": "verdicts in",
  "stato.interrotta": "stopped · the partial answer stays",
  "stato.errore": "interrupted",
  "stato.troncato": "answer truncated: the token limit was reached",
  "stato.riparato": "markers put back into the required form",

  "sources.title": "Sources",
  "sources.waiting": "Sources show up here as soon as the search answers, before the model writes.",
  "sources.none": "No sources found for this question.",

  "score.marker":
    "The number the answer uses to cite this source: look for [{marker}] in the text.",
  "score.retrieval.dense":
    "How much this piece resembles the question, from 0 to 1: it ranks the sources, it does not say the answer is right. (Search by meaning.)",
  "score.retrieval.sparse":
    "How much the question’s words appear in this piece, counting rare ones for more: it looks for words, not meaning. (BM25.)",
  "score.retrieval.hybrid":
    "How high this piece landed in the two searches, by meaning and by words, put together. Not a similarity: small by design. (RRF fusion.)",
  "score.retrieval.rerank":
    "A second model reread the question and the piece together and put them back in order. It does not run 0 to 1: it only compares within this answer. (Reranker.)",
  "score.retrieval.unknown":
    "The score the search used to rank this source. What it measures depends on how the search ran, and that is known once the answer is done.",
  "sources.count": "How many sources the search brought back.",

  "verdict.supported": "supports",
  "verdict.unsupported": "does not support",
  "verdict.mixed": "does not support {quante} of {su}",
  "verdict.pending": "checking…",
  "verdict.unverified": "unverified",
  "verdict.notCited": "not cited",
  "verdict.inert": "marker not active yet",
  "verdict.marker": "Cites source {marker}. The checker says: {verdetto}.",
  "verdict.marker.inert":
    "The text is not final yet: this marker can still be fixed, or dropped if it points at a source that is not there.",
  "verdict.marker.score":
    "Cites source {marker}. The checker says: {verdetto}, {punteggio} out of 1.",
  "verdict.score":
    "How convinced the checker is that this source says what the sentence claims, from 0 to 1. The verdict is that number against a threshold.",
  "verdict.score.many":
    "Several sentences cite this source: this is the weakest one’s number, not an average.",
  "verdict.count": "How many sentences of the answer cite this source.",

  "verdict.numeric.supported": "the table confirms it",
  "verdict.numeric.unsupported": "the table does not confirm it",
  "verdict.numeric.mixed": "the table does not confirm {quante} of {su}",
  "verdict.numeric.what":
    "A second check, for figures only: it looks for the sentence’s numbers inside the cited table. No language model, so on tables it is wrong less often.",

  "verdict.why.supported":
    "The checker reread sentence and source, and judged that the source supports it.",
  "verdict.why.unsupported":
    "The checker cannot find in this source what the sentence claims. Not a failure: it is the finding, and it stays in view.",
  "verdict.why.mixed":
    "Several sentences cite this source, and the checker does not judge them all the same way.",
  "verdict.why.pending": "Checking starts once the answer is done: until then there is no verdict.",
  "verdict.why.unverified":
    "No verdict: checking was off in this run, or the sentence was too short to judge.",
  "verdict.why.notCited":
    "The search brought it back, the answer did not cite it. It stays here: hiding unused sources would make the search look more precise.",

  "report.title.unsupported": "Not every citation holds up.",
  "report.title.uncited": "Some sentences cite no source.",
  "report.title.unverified": "Not every marker has a verdict.",
  "report.title.disagreement": "The two verifiers disagree.",
  "report.marks": "Not supported: {marcatori}.",
  "report.numeric":
    "Of those, {quante} are confirmed by the number check: the figure is in the table, but the one reading prose does not see it. On a table that one holds — here 96.7% of sentences assert a number.",
  "report.uncited": "Sentences with no citation: {quante}, underlined in the text.",
  "report.unverified":
    "Citations with no verdict: {quante}. Checking was off, or the sentence was too short to judge.",
  "report.why":
    "None of this is hidden: a citation that does not hold up is the finding, not a bug. And citing less raises precision, so the uncovered sentences count too.",

  "abstention.gate": "No answer: the sources found were too weak, and the model was never asked.",
  "abstention.model": "The model stated it could not find the answer in the sources.",

  // --- non ancora in uso ---------------------------------------------------
  // Nessuno legge queste, e ognuna appartiene a un task che ha un nome. Stanno
  // qui e non fra le altre perche' altrimenti un ripasso le rivede come se
  // fossero sullo schermo: **vanno riscritte quando il task le accende**, con
  // davanti la cosa che devono spiegare. Una frase giudicata al buio non e' una
  // frase giudicata.
  // U-11 (il README) e la testata che non c'e' piu'
  "app.tagline": "RAG with sentence-level verified citations",

  // l'esploratore del corpus, §12
  "nav.chat": "Chat",
  "nav.explore": "Explore the corpus",

  // il debito di U-02: i dati dell'indice sotto «Dettagli della run»
  "index.title": "Index",
  "index.collection": "Collection",
  "index.points": "points",
  "index.dense": "dense size",
  "index.sparse": "sparse vectors",
  "index.missing": "The server lists no collection with this name.",
};

export const LINGUE = ["it", "en"] as const;
export type Lingua = (typeof LINGUE)[number];

export const DIZIONARI: Record<Lingua, Record<Chiave, string>> = { it, en };
