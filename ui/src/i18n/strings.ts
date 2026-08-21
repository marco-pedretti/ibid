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

  // U-18: la corsia si comprime. Il nome del comando dice **il verso**, perché
  // l'icona è la stessa nei due stati — un pannello con la sua striscia — e una
  // freccia che si specchia costringerebbe a ricordare quale significa cosa.
  "rail.collapse": "Comprimi la corsia",
  "rail.collapse.hint": "Resta una striscia di comandi, e la scelta vale anche al prossimo avvio.",
  "rail.expand": "Apri la corsia",
  "rail.expand.hint": "Torna larga, con i titoli delle conversazioni e il nome del dataset.",
  // Sul bottone della cronologia nella striscia: dice **perché** questo comando
  // riapre invece di aprire un elenco, che è l'unica cosa che chi clicca non si
  // aspetta.
  "rail.history.hint":
    "Un titolo troncato a una striscia non è un titolo: il clic riapre la corsia.",

  // U-21: a colonna sola la corsia e le fonti diventano due strati che si aprono
  // sopra il lavoro. Il nome dice **cosa si chiude** e non «chiudi»: il velo è un
  // bersaglio grande e senza forma, e chi ci arriva da tastiera lo sente
  // annunciare prima di premerlo.
  "rail.close": "Chiudi la corsia",
  "sources.close": "Chiudi le fonti",
  "sources.open.hint":
    "Le fonti di questa risposta, coi verdetti. Si apre di lato, e si chiude toccando fuori.",

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

  // U-20: l'avvio guidato. Quattro passi, nell'ordine in cui le cose compaiono
  // guardando una risposta nascere — non un elenco di funzionalità. La riga
  // sotto dichiara le due cose che il criterio chiede di dichiarare: che si può
  // chiedere mentre è aperta, e che la scelta di saltarla è locale a questo
  // browser, come la cronologia.
  "start.title": "Avvio guidato",
  "start.step": "{n} di {tot}",
  "start.next": "Avanti",
  "start.done": "Ho capito",
  "start.skip": "Salta",
  "start.local":
    "Puoi chiedere mentre è aperta. Saltata una volta non torna, e la scelta resta in questo browser come la cronologia.",

  "start.sources.title": "Le fonti arrivano prima della risposta",
  "start.sources":
    "Il pannello a destra si riempie in un attimo, il testo comincia qualche secondo dopo: si vede da dove nasce la risposta mentre nasce.",
  "start.verdicts.title": "Ogni frase porta un verdetto",
  "start.verdicts":
    "Un controllo rilegge ogni frase contro il pezzo che cita e dice se lo sostiene davvero: senza, una citazione ben scritta e una corretta si somigliano troppo.",
  "start.bar.title": "Qui sotto si decide come nasce la risposta",
  "start.bar":
    "Fonti sì o no, ragionamento, modello e finestra di contesto: ogni pastiglia cambia la prossima domanda. Quella che ha girato resta scritta sopra ogni risposta, quindi si sa sempre con cosa è stata fatta.",
  "start.corpus.title": "Sa solo quello che c'è nel corpus",
  "start.corpus":
    "Fuori dai documenti del dataset scelto si astiene invece di inventare, e la terza domanda d'esempio serve a vederlo. Da qui si cambia corpus, e «Esplora» mostra come è stato spezzato.",
  "start.rest.title": "Il resto sta in «Che cos'è»",
  "start.rest":
    "Cosa dimostra il progetto, cosa regge e cosa no: in fondo alla corsia, e resta lì. Questa guida invece non torna.",

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
  // Il costo di una finestra grande è un **rallentamento**, non un guasto: se la
  // memoria della scheda non basta il servizio continua sulla CPU. Dirlo qui è
  // meglio che nascondere le taglie grandi, perché il rallentamento si vede da
  // sé nella riga dei tempi.
  "bar.context.hint":
    "Quanto testo entra nel modello prima che risponda. Le finestre grandi tengono più fonti insieme ma occupano più memoria: oltre quella della scheda il servizio continua sulla CPU e diventa molto più lento.",
  // Attenuata: la finestra e' una sola, e la pastiglia dice perche' invece di
  // sparire -- sparendo, la funzione non esisterebbe per chi non sa dello script.
  "bar.context.only":
    "Questo modello ha una finestra sola. Per poter scegliere, creane altre con «scripts/model_sizes.py».",
  "bar.advanced": "Avanzate",
  "bar.advanced.hint":
    "Come si cerca nel corpus, prima che il modello scriva. Stanno chiuse di proposito: confrontare configurazioni è il lavoro del cruscotto, non di qui.",
  // Le quattro manopole del pannello. Il nome sul campo resta quello del campo
  // dell'API — `top_k`, `hnsw_ef` — perché è ciò che parte sul filo e ciò che si
  // rilegge in «Dettagli della run»; la frase è il posto dove diventano
  // leggibili anche a chi quel campo non lo conosce.
  "bar.advanced.mode": "Ricerca",
  "bar.advanced.mode.hint":
    "Come si trova un pezzo del corpus: per significato, per parole esatte, o le due cose fuse insieme (dense, sparse, hybrid). Nessuna delle tre vince sempre — su articoli e su bilanci si comportano in modo diverso, ed è il motivo per cui qui le misure non si mediano mai fra dataset.",
  "bar.advanced.rerank": "Riordino",
  "bar.advanced.rerank.hint":
    "Un secondo modello rilegge i pezzi trovati e li rimette in ordine, stavolta guardando domanda e pezzo insieme invece che separatamente. Costa tempo a ogni domanda, e quanto si legge nella riga dei tempi.",
  // Quanti pezzi vanno nel prompt. Il rischio dei due estremi è diverso, e la
  // frase li nomina tutti e due: senza, «alza top_k» sembra sempre migliorativo.
  "bar.advanced.topk.hint":
    "Quanti pezzi del corpus finiscono davanti al modello. Pochi rischiano di lasciar fuori la risposta; tanti la annacquano fra i vicini e riempiono la finestra di contesto.",
  // Il dettaglio che un esperto cerca è il richiamo misurato in R-11 — 0,9994 su
  // open_ragbench e 0,9892 su ledger — arrotondato onestamente a «il 99%», con
  // la condizione in cui smetterebbe di valere.
  "bar.advanced.ef.hint":
    "Quanti candidati l'indice visita prima di rispondere: più ne visita, più i primi cinque sono davvero i primi cinque, e più lentamente risponde. Sui due indici di questa demo l'approssimazione ne prende già il 99%, quindi alzarlo cambia poco — su un indice più denso cambierebbe molto.",
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
  // La seconda frase è una correzione della revisione di U-04: la colonna nuda
  // viene **più bella** delle due, e un avviso che dice solo «non si può
  // controllare» lascia quell'impressione a lavorare indisturbata. Dice il
  // meccanismo, non un giudizio: niente la obbliga a fermarsi dove finiscono i
  // documenti — né in lunghezza né in impaginazione.
  "compare.bare.body":
    "Non c'è una fonte da aprire: nessuna frase di questa risposta si può controllare. Spesso è anche la più lunga e la meglio scritta delle due, perché niente la obbliga a fermarsi dove finiscono i documenti.",
  // U-04: le due pastiglie nella colonna nuda. Si leggono per **cosa fanno** —
  // «permissivo» e «severo» sono i nomi delle due run, e stanno nel
  // suggerimento insieme ai numeri che le hanno misurate.
  "compare.prompt": "Come è stata posta la domanda",
  "compare.prompt.permissive": "Risponde comunque",
  "compare.prompt.strict": "Si astiene",
  "compare.prompt.hint":
    "Cambia come è stata posta la domanda al modello senza fonti, e rifà questa colonna sola: l'altra resta ferma a fare da paragone. Chiedendogli di astenersi quando non sa, le risposte inventate scendono dal 45% al 17% e quelle corrette non calano (prompt severo, misurato su 100 domande sui paper).",

  // U-05: come il documento e' stato riconosciuto e come e' stato spezzato. Due
  // vocabolari separati anche dove una parola coincide: «tabelle» come genere
  // dice com'e' fatto il documento, «per tabelle» come taglio dice come e' stato
  // spezzato — e che il primo scelga il secondo e' la decisione da mostrare.
  "source.genre.paper": "paper",
  "source.genre.tables": "tabelle",
  "source.genre.prose": "testo continuo",
  // «generico» non e' un dato mancante: e' il termine di paragone, cioe' l'unita'
  // che il documento offriva gia' — una pagina, una sezione — senza pipeline.
  "source.cut.generic": "taglio generico",
  "source.cut.sections": "per sezioni",
  "source.cut.tables": "per tabelle",
  "source.cut.paragraphs": "per paragrafi",
  "source.pipeline.hint":
    "Come questo documento è stato spezzato prima di entrare nell'indice: riconosciuto come {genere}, tagliato {taglio}. Se scegliere il taglio in base al genere migliori il recupero è una delle cose che questo progetto misura.",
  // Quando una pipeline e' stata scelta per il genere, e quando invece no. Due
  // frasi e non una con un «non»: la seconda deve dire cosa **e'** successo.
  "source.pipeline.routed": "Il taglio è stato scelto in base al genere.",
  "source.pipeline.generic":
    "Tutti i documenti di questo indice sono stati tagliati allo stesso modo, qualunque fosse il genere.",

  // U-06, l'esploratore. La didascalia del mockup: qui non si confrontano
  // configurazioni, si guarda il corpus e come e' stato spezzato.
  "corpus.title": "Il corpus",
  "corpus.subtitle":
    "Come i documenti di {dataset} sono stati spezzati prima di finire nell'indice.",
  "corpus.open.action": "Esplora il corpus",
  "corpus.back": "Torna alla conversazione",
  "corpus.documents": "Documenti",
  // Sui due manici: e' l'`aria-label` di un `separator`, quindi dice **cosa si
  // sta ridimensionando**, non «trascina qui».
  "corpus.resize.documents": "Larghezza dell'elenco dei documenti",
  "corpus.resize.detail": "Larghezza del chunk selezionato",
  "corpus.search": "Cerca un documento…",
  "corpus.loading": "carico…",
  "corpus.count": "{visti} su {tutti}",
  "corpus.chunks": "{n} chunk",
  "corpus.pickDocument": "Scegli un documento per vedere com'è stato spezzato.",
  "corpus.howSplit": "Com'è stato spezzato",
  // U-17. **Non «il documento»**: il PDF non ce l'abbiamo, e ciò che si mette in
  // fila sono i chunk. Oggi coincidono — nell'indice generico non c'è nessuna
  // sovrapposizione, misurata — ma il nome deve reggere anche quando non sarà
  // più vero (D-18).
  "corpus.indexedText": "Il testo indicizzato",
  // Sulla cucitura: il numero del pezzo e quanto è lungo. In mono perché è un
  // dato, e attenuato perché non è il testo — è dove il testo è stato staccato.
  "corpus.seam": "{n} · {caratteri} car.",
  "corpus.legend.text": "testo",
  // Due etichette per la stessa tessera, e non e' un vezzo: «mai spezzata» e' una
  // proprieta' della pipeline `table_heavy`, che nell'indice generico **non ha
  // girato**. Scriverlo comunque sarebbe la stessa dichiarazione non verificata
  // che U-05 ha appena tolto dal campo `pipeline`.
  "corpus.legend.table": "contiene una tabella",
  "corpus.legend.table.routed": "tabella · mai spezzata",
  // Terza voce, ed e' quella che mancava: l'accento vuol dire «scelto» in tutta
  // l'interfaccia, e la legenda deve dirlo invece di lasciarlo indovinare.
  "corpus.legend.selected": "il chunk scelto",
  "corpus.chunkHint": "{id} · {tipo} · {caratteri} caratteri",
  "corpus.selected": "Chunk selezionato",
  // Due modi, e il secondo non e' un ripiego: «grezzo» e' la stringa che sta
  // nell'indice, cioe' quella che il modello ha ricevuto e che il controllo ha
  // giudicato. In un progetto che verifica, il dato e' quello.
  "corpus.readable": "leggibile",
  "corpus.raw": "grezzo",
  "corpus.page": "p. {n}",
  "corpus.open": "Apri la fonte",
  "corpus.split.title": "Riconosciuto come {genere}, tagliato {taglio}.",
  "corpus.split.routed":
    "Il taglio è stato scelto guardando il documento: generi diversi vengono spezzati in modo diverso, e le tabelle restano intere perché una riga senza intestazione è illeggibile.",
  "corpus.split.generic":
    "Ogni documento di questo indice è stato spezzato allo stesso modo, prendendo l'unità che il documento offriva già.",
  // Il criterio di U-06 chiede di dichiararla, non di simularla. E il motivo è
  // più largo del solo `bbox`: un PDF non c'è proprio, su nessuno dei due corpus.
  "corpus.noPdf":
    "Nessuna pagina da mostrare: di questo corpus non abbiamo i PDF, solo il testo estratto. L'evidenziazione sulla pagina non è disponibile — dichiarata, non simulata.",
  "corpus.fromCitation": "Apri questa fonte nel corpus",

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

  // U-19 — la pagina «Che cos'è».
  //
  // **I numeri non ci sono, ed è una scelta scritta.** Il criterio del task ne
  // ammette due: quelli del README, da una fonte sola, oppure nessuno. Vale la
  // seconda, e non per pigrizia — le misure delle tre affermazioni vanno rifatte
  // col prompt cambiato da U-14, e una copia scritta a mano qui invecchierebbe
  // senza dirlo, che è il difetto peggiore per una pagina che spiega. Ciò che la
  // pagina mostra invece è la **configurazione in vigore**: non è una misura, e
  // arriva viva dal server come tutto il resto dell'interfaccia.
  "about.title": "Che cos'è",
  "about.subtitle": "Cosa fa ibid, cosa vuole dimostrare, e dove non arriva.",
  "about.action": "Che cos'è ibid",
  "about.hint": "Cosa fa il progetto, cosa ha misurato finora, e cosa questa demo non è.",
  "about.back": "Chiudi",

  "about.what.title": "Cosa fa",
  "about.what":
    "Risponde con i documenti di un corpus davanti, e di ogni frase che scrive dice da quale pezzo viene. Poi rilegge: un secondo modello controlla se quel pezzo sostiene davvero la frase, e il verdetto resta visibile anche quando è negativo.",
  "about.name":
    "«ibid» è l'abbreviazione con cui una nota bibliografica rimanda alla fonte appena citata, senza ripeterla. È il nome del progetto perché è ciò che il sistema fa per ogni singola frase.",

  "about.claims.title": "Le tre cose che vuole dimostrare",
  "about.claims.note":
    "I numeri non stanno qui: stanno nelle tabelle del repository, l'unico posto in cui vengono rifatti quando cambia qualcosa. Una copia in questa pagina invecchierebbe senza dirlo.",
  "about.claim1":
    "Che l'attribuzione verificata frase per frase si può misurare, e che i modelli piccoli, senza quel controllo, sbagliano in modo sistematico.",
  "about.claim1.state": "Regge",
  "about.claim1.detail":
    "È la ragione per cui qui ogni frase porta un verdetto invece di un elenco di link in fondo: senza il controllo, un rimando ben scritto e un rimando giusto sono indistinguibili.",
  "about.claim2":
    "Che scegliere come spezzare i documenti in base al loro genere batta una pipeline unica per tutti.",
  "about.claim2.state": "Non regge",
  "about.claim2.detail":
    "Dipende dal genere: sugli articoli guadagna poco, e sui bilanci la pipeline scritta apposta per le tabelle peggiora il recupero. È un risultato negativo, ed è il reperto più interessante del progetto: resta in tabella invece di sparire.",
  "about.claim3":
    "Che con un recupero buono la taglia del modello conti molto meno di quanto si crede.",
  "about.claim3.state": "Non decisa",
  "about.claim3.detail":
    "Manca il confronto col modello grande, che costa ore di scheda video. Finché non c'è resta un'ipotesi, e viene scritta come tale.",

  "about.not.title": "Cosa questa demo non è",
  "about.not.product":
    "Non è un prodotto, è un banco di prova. Serve a misurare, e mostra anche ciò che misura male.",
  // Le due cose che il criterio chiede per nome — quale modello ha risposto e su
  // quale corpus — stanno qui come **limite** e non come scheda tecnica: la
  // pagina dice cosa la demo non è, e «non è un panorama» è esattamente questo.
  // I due nomi arrivano dal servizio, mai scritti a mano: vedi `app/scheda.ts`.
  "about.not.only":
    "Non è un panorama: a ogni domanda risponde un modello solo, su un corpus solo. Adesso sono {modello} e {corpus}, e si cambiano dalla barra sotto il campo e dalla corsia.",
  "about.not.only.unknown":
    "Non è un panorama: a ogni domanda risponde un modello solo, su un corpus solo. Quali, in questo momento il server non lo dice.",
  "about.not.world":
    "Non sa niente oltre il corpus qui sopra. Fuori da lì si astiene invece di inventare, ed è metà della dimostrazione: una delle domande d'esempio sta fuori dal corpus apposta.",
  "about.not.truth":
    "Una citazione verificata dice che il pezzo citato sostiene la frase, non che la frase sia vera. Se il documento sbaglia, la risposta sbaglia con lui.",
  "about.not.measure":
    "Una risposta sola non è una misura. Lo stesso modello, con tutto il resto uguale, risponde in modo diverso da un'esecuzione all'altra: le tabelle nascono da migliaia di domande, non da quella che hai appena fatto.",
  // Il punto che il piano chiede di dire qui, per nome: è l'unica differenza fra
  // com'è configurata la demo e com'è configurata la valutazione.
  "about.not.exact":
    "Non è configurata esattamente come la valutazione, e la differenza è una: qui la ricerca nell'indice è esatta invece che approssimata. Su un indice fitto quella approssimata salta qualcosa, e una dimostrazione finirebbe per mostrare quel difetto credendo di mostrare il recupero.",

  "about.who.title": "Chi l'ha fatto",
  "about.who":
    "Marco Pedretti ed Elia Dallanoce, in due sulla stessa parte. È il motivo per cui qui quasi ogni scelta ha accanto la ragione per cui è stata presa: erano in due a doverla accettare.",
  "about.who.license":
    "Il codice è aperto, licenza MIT. Insieme al codice ci sono il piano, le tabelle delle misure e le domande ancora senza risposta — comprese le misure andate male, che restano in tabella.",
  "about.who.repo": "Il progetto su GitHub",
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

  "rail.collapse": "Collapse the sidebar",
  "rail.collapse.hint": "A strip of commands stays, and the choice holds next time too.",
  "rail.expand": "Open the sidebar",
  "rail.expand.hint": "It comes back wide, with conversation titles and the dataset name.",
  "rail.history.hint": "A title cut down to a strip is not a title: the click reopens the sidebar.",

  "rail.close": "Close the sidebar",
  "sources.close": "Close sources",
  "sources.open.hint":
    "The sources behind this answer, with their verdicts. It opens at the side; tap outside to close.",

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

  "start.title": "Guided start",
  "start.step": "{n} of {tot}",
  "start.next": "Next",
  "start.done": "Got it",
  "start.skip": "Skip",
  "start.local":
    "You can ask a question while this is open. Skipped once it does not come back, and that choice stays in this browser, like the history.",

  "start.sources.title": "Sources arrive before the answer",
  "start.sources":
    "The panel on the right fills in an instant, the text starts a few seconds later: you watch where the answer comes from while it is being written.",
  "start.verdicts.title": "Every sentence carries a verdict",
  "start.verdicts":
    "A check reads each sentence against the passage it cites and says whether it really supports it: without that, a well-formed citation and a correct one look too much alike.",
  "start.bar.title": "Down here is how the answer gets made",
  "start.bar":
    "Sources on or off, reasoning, model and context window: each pill changes the next question. Whichever ones ran stay written above every answer, so you always know what made it.",
  "start.corpus.title": "It only knows what is in the corpus",
  "start.corpus":
    "Outside the documents of the chosen dataset it abstains instead of inventing, and the third example question is there to show that. The corpus is changed from here, and «Explore» shows how it was split.",
  "start.rest.title": "The rest is in «What this is»",
  "start.rest":
    "What the project sets out to prove, what holds and what does not: at the bottom of the sidebar, and it stays there. This guide does not come back.",

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
    "How much text fits into the model before it answers. Larger windows hold more sources at once but take more memory: past what the card has, the service keeps going on the CPU and gets much slower.",
  "bar.context.only":
    "This model has a single context size. To get a choice, create more with «scripts/model_sizes.py».",
  "bar.advanced": "Advanced",
  "bar.advanced.hint":
    "How the corpus is searched, before the model writes. Closed on purpose: comparing configurations is the dashboard's job, not this one's.",
  "bar.advanced.mode": "Search",
  "bar.advanced.mode.hint":
    "How a piece of the corpus is found: by meaning, by exact words, or the two fused together (dense, sparse, hybrid). None of the three always wins — they behave differently on articles and on ledgers, which is why measurements here are never averaged across datasets.",
  "bar.advanced.rerank": "Reranking",
  "bar.advanced.rerank.hint":
    "A second model reads the retrieved pieces again and reorders them, this time looking at question and piece together instead of separately. It costs time on every question, and the timing line says how much.",
  "bar.advanced.topk.hint":
    "How many pieces of the corpus end up in front of the model. Too few risk leaving the answer out; too many dilute it among its neighbours and fill the context window.",
  "bar.advanced.ef.hint":
    "How many candidates the index visits before answering: the more it visits, the more the top five really are the top five, and the slower it answers. On this demo's two indexes the approximation already gets 99% of them, so raising it changes little — on a denser index it would change a lot.",
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
    "There is no source to open: not one sentence of this answer can be verified. It is often the longer and better-written of the two, because nothing makes it stop where the documents stop.",
  "compare.prompt": "How the question was put",
  "compare.prompt.permissive": "Answers anyway",
  "compare.prompt.strict": "Abstains",
  "compare.prompt.hint":
    "Changes how the question was put to the model without sources, and re-runs this column only: the other one stays put as the comparison. Asking it to abstain when it does not know takes invented answers from 45% down to 17%, and correct ones do not drop (strict prompt, measured on 100 paper questions).",

  "source.genre.paper": "paper",
  "source.genre.tables": "tables",
  "source.genre.prose": "continuous text",
  "source.cut.generic": "generic split",
  "source.cut.sections": "by section",
  "source.cut.tables": "by table",
  "source.cut.paragraphs": "by paragraph",
  "source.pipeline.hint":
    "How this document was split before it entered the index: recognised as {genere}, cut {taglio}. Whether choosing the split by document kind improves retrieval is one of the things this project measures.",
  "source.pipeline.routed": "The split was chosen from the document kind.",
  "source.pipeline.generic":
    "Every document in this index was split the same way, whatever its kind.",

  "corpus.title": "The corpus",
  "corpus.subtitle": "How the documents in {dataset} were split before they entered the index.",
  "corpus.open.action": "Explore the corpus",
  "corpus.back": "Back to the conversation",
  "corpus.documents": "Documents",
  "corpus.resize.documents": "Width of the document list",
  "corpus.resize.detail": "Width of the selected chunk",
  "corpus.search": "Find a document…",
  "corpus.loading": "loading…",
  "corpus.count": "{visti} of {tutti}",
  "corpus.chunks": "{n} chunks",
  "corpus.pickDocument": "Pick a document to see how it was split.",
  "corpus.howSplit": "How it was split",
  "corpus.indexedText": "The indexed text",
  "corpus.seam": "{n} · {caratteri} char.",
  "corpus.legend.text": "text",
  "corpus.legend.table": "contains a table",
  "corpus.legend.table.routed": "table · never split",
  "corpus.legend.selected": "the selected chunk",
  "corpus.chunkHint": "{id} · {tipo} · {caratteri} characters",
  "corpus.selected": "Selected chunk",
  "corpus.readable": "readable",
  "corpus.raw": "raw",
  "corpus.page": "p. {n}",
  "corpus.open": "Open the source",
  "corpus.split.title": "Recognised as {genere}, cut {taglio}.",
  "corpus.split.routed":
    "The split was chosen by looking at the document: different kinds are split differently, and tables stay whole because a row without its header is unreadable.",
  "corpus.split.generic":
    "Every document in this index was split the same way, taking the unit the document already offered.",
  "corpus.noPdf":
    "No page to show: we do not have the PDFs for this corpus, only the extracted text. Highlighting on the page is unavailable — declared, not simulated.",
  "corpus.fromCitation": "Open this source in the corpus",

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

  "about.title": "What this is",
  "about.subtitle": "What ibid does, what it sets out to show, and where it stops.",
  "about.action": "What ibid is",
  "about.hint": "What the project does, what it has measured so far, and what this demo is not.",
  "about.back": "Close",

  "about.what.title": "What it does",
  "about.what":
    "It answers with the documents of a corpus in front of it, and for every sentence it writes it says which passage that sentence came from. Then it reads back: a second model checks whether the passage really supports the sentence, and the verdict stays visible even when it is negative.",
  "about.name":
    "“ibid” is the abbreviation a footnote uses to point at the source it has just cited, without repeating it. It is the name of the project because that is what the system does for every single sentence.",

  "about.claims.title": "The three things it sets out to show",
  "about.claims.note":
    "The numbers are not here: they are in the tables in the repository, the only place where they are redone when something changes. A copy on this page would go stale without saying so.",
  "about.claim1":
    "That sentence-level verified attribution can be measured, and that small models, without that check, get it wrong systematically.",
  "about.claim1.state": "Holds",
  "about.claim1.detail":
    "It is why every sentence here carries a verdict instead of a list of links at the bottom: without the check, a well-formed reference and a correct one look exactly alike.",
  "about.claim2":
    "That picking how to split documents by their genre beats a single pipeline for everything.",
  "about.claim2.state": "Does not hold",
  "about.claim2.detail":
    "It depends on the genre: on articles it gains little, and on ledgers the pipeline written specifically for tables makes retrieval worse. It is a negative result, and it is the most interesting find in the project: it stays in the table instead of disappearing.",
  "about.claim3": "That with good retrieval, model size matters far less than people assume.",
  "about.claim3.state": "Undecided",
  "about.claim3.detail":
    "The comparison against the large model is missing, and it costs hours of GPU time. Until it exists this stays a hypothesis, and it is written as one.",

  "about.not.title": "What this demo is not",
  "about.not.product":
    "It is not a product, it is a testbed. It exists to measure, and it shows what it measures badly too.",
  "about.not.only":
    "It is not a panorama: every question is answered by one model, on one corpus. Right now those are {modello} and {corpus}, and both are changed from the bar under the field and from the sidebar.",
  "about.not.only.unknown":
    "It is not a panorama: every question is answered by one model, on one corpus. Which ones, the server is not saying right now.",
  "about.not.world":
    "It knows nothing beyond the corpus named above. Outside it the system abstains instead of inventing, and that is half the demonstration: one of the example questions sits outside the corpus on purpose.",
  "about.not.truth":
    "A verified citation says the cited passage supports the sentence, not that the sentence is true. If the document is wrong, the answer is wrong with it.",
  "about.not.measure":
    "A single answer is not a measurement. The same model, with everything else identical, answers differently from one run to the next: the tables come from thousands of questions, not from the one you just asked.",
  "about.not.exact":
    "It is not configured exactly the way the evaluation is, and there is one difference: here the index is searched exactly rather than approximately. On a dense index the approximate search misses things, and a demonstration would end up showing that flaw while believing it was showing retrieval.",

  "about.who.title": "Who made it",
  "about.who":
    "Marco Pedretti and Elia Dallanoce, two people on the same part. It is why almost every choice here has the reason for it written next to it: two people had to agree on it.",
  "about.who.license":
    "The code is open, MIT licensed. Alongside it are the plan, the measurement tables and the questions still without an answer — including the measurements that went badly, which stay in the table.",
  "about.who.repo": "The project on GitHub",
};

export const LINGUE = ["it", "en"] as const;
export type Lingua = (typeof LINGUE)[number];

export const DIZIONARI: Record<Lingua, Record<Chiave, string>> = { it, en };
