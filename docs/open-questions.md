# Domande aperte

Ipotesi emerse durante il lavoro, **non ancora verificate**, con il protocollo per verificarle.

Non è `progress.md` (che registra cosa è stato fatto) né `ROADMAP.md` (che definisce i task da fare): qui stanno le cose che abbiamo *notato* e che meritano una misura prima di essere chiamate cause. Una voce esce da qui quando diventa un task con un delta misurato, e il risultato — positivo o negativo — va in `progress.md`.

---

## OQ-01 — Perché il routing peggiora LEDGER di 17 punti

**Aperta.** Osservata il 2026-08-07 durante la riscrittura della dashboard. Riferimento: R-07.

### Il fatto da spiegare

Misura definitiva (2026-08-07, golden set **completi**, profondità 10 — i numeri originali di R-07 erano affetti dai difetti descritti in `eval/results/archive/README.md`):

| dataset | n query | generic | routed | delta | McNemar appaiato |
|---|---|---|---|---|---|
| open_ragbench | 3045 | 0.9681 | 0.9757 | +0.76 pt | 71 contro 48, p=0.043 — reale ma marginale |
| ledger | 10000 | 0.9433 | 0.7730 | **−17.03 pt** | **1797 contro 94**, p<0.0001 |

(Tassi sul criterio binario *"almeno un documento rilevante nei primi 5"*, non `doc_R@5`, che è una frazione quando una query ha più documenti rilevanti. Riproducibile con `scripts/compare_runs.py`.)

La domanda è solo la seconda riga. Su LEDGER il routing sbaglia **1797 query su 10000** che la pipeline generica azzeccava, e ne recupera 94: non è rumore né un effetto di soglia, è un regresso sistematico. In `progress.md` la causa era annotata come *"sub-chunking aggressivo → chunk troppo piccoli, IDF diluito"*. È una congettura scritta senza misura: va verificata o sostituita.

### Cosa è stato misurato finora

Tutto quanto segue viene da campioni di 3000 punti per collection (`client.scroll`, nessun filtro se non dove indicato). Sono **osservazioni sul corpus indicizzato**, non ancora esperimenti.

**1. I chunk tabella di `ledger_routed` non embeddano il proprio titolo di sezione.**

Stesso contenuto, due collection:

| | `ledger` | `ledger_routed` |
|---|---|---|
| chunk | `ledger:AMEX_BRN_2017:0001` | `ledger:AMEX_BRN_2017:0002` |
| `content_type` | `mixed` | `table` |
| `pipeline` | `table_heavy` | `table_heavy` |
| `section_path` | `''` | `'FINANCIAL AND OPERATING HIGHLIGHTS'` |
| `text` inizia con | `## FINANCIAL AND OPERATING HIGHLIGHTS` | `<table><tr><td rowspan=…` |

Il routing **estrae correttamente** l'heading in `section_path` — la pipeline fa il suo lavoro. Ma `src/index/embed.py` embedda `Chunk.text`, e lì l'heading non c'è più.

Su 3000 chunk con `content_type="table"` di `ledger_routed`: 1960 hanno `section_path` valorizzato, di cui **solo 96 (5%) hanno l'heading anche nel testo**. 1864 chunk conoscono il proprio titolo e non lo usano.

**2. I chunk tabella sono corti e poco alfabetici.** Mediane sul campione:

| collection | content_type | n | testo utile (dopo strip del markup) | lettere / carattere |
|---|---|---|---|---|
| `open_ragbench_routed` | text | 2774 | 1189 char | 0.67 |
| `open_ragbench_routed` | mixed | 226 | 1190 char | 0.75 |
| `ledger_routed` | **table** | 408 | **310 char** | **0.52** |
| `ledger_routed` | text | 2592 | 1111 char | 0.81 |
| `ledger` | mixed | 1229 | 2813 char | 0.72 |
| `ledger` | text | 1771 | 3687 char | 0.81 |

Il routing su LEDGER ha ridotto la mediana del testo utile di **~3.3×** sui chunk di prosa (3687 → 1111) e di **~12×** sui chunk tabella (3687 → 310). Metà dei caratteri di un chunk tabella non sono lettere: sono cifre, `$`, punteggiatura.

**3. I fallimenti hanno score alto.** Su 30 query LEDGER (dense, top_k=5, via Failure Explorer): `ledger` doc-recall 0.756 con 1/30 fallimenti; `ledger_routed` 0.594 con 5/30. I fallimenti di `ledger_routed` hanno `top_score` **0.855–0.873** — il retrieval non ignora i chunk piccoli, li recupera **con confidenza sbagliata**. Un chunk di soli numeri assomiglia a qualunque tabella finanziaria.

### La controprova che complica tutto (leggere prima di partire)

**`open_ragbench_routed` perde l'heading ancora più severamente — e migliora.**

| collection | con `section_path` | heading anche nel `text` |
|---|---|---|
| `open_ragbench_routed` | 2588 / 3000 (86%) | **17 (1%)** |
| `ledger_routed` | 2262 / 3000 (75%) | 768 (34%) |

Se la perdita dell'heading fosse sufficiente a causare un crollo, ORB dovrebbe crollare più di LEDGER. Invece ORB guadagna +4%.

**Quindi l'ipotesi "manca l'heading" da sola è già falsificata.** Quello che resta in piedi è una versione condizionata:

> La perdita dell'heading fa danno **solo quando il corpo del chunk non porta abbastanza semantica per conto proprio**. I chunk ORB sono prosa da ~1190 caratteri: reggono senza titolo. I chunk tabella LEDGER sono 310 caratteri per metà non alfabetici: senza titolo non resta quasi nulla su cui costruire un embedding.

### Le tre ipotesi, e perché non sono separabili così come stanno

Il routing su LEDGER ha cambiato **tre cose insieme**, il che viola §14 se le si vuole attribuire:

- **H1 — perdita del contesto di sezione.** Il chunk tabella non embedda il proprio heading (misura 1).
- **H2 — dimensione.** I chunk sono 3–12× più piccoli (misura 2). Due sotto-varianti, che vanno distinte:
  - **H2a — profondità di ranking**: i chunk giusti ci sono ma vengono spinti fuori dal top-5 dai concorrenti.
  - **H2b — qualità dell'embedding**: un chunk corto produce un vettore poco discriminante, indipendentemente da quanto in profondità si guardi.
- **H3 — isolamento del contenuto.** La tabella è diventata un chunk atomico senza la prosa che la circondava (misura 2, colonna lettere/carattere).

H1 e H3 sono quasi la stessa cosa vista da due lati; H2 è indipendente. Un singolo esperimento che le muove tutte insieme non dirà quale conta.

### ⚠️ Due trappole nei dati esistenti

**1. `doc_R@10` nei run di `eval/results/archive/` non significa niente.** Tutti riportano `doc_R@10 == doc_R@5`. Non è un risultato: il retrieval girava con `top_k=5`, quindi c'erano solo 5 chunk per query e `@10` non poteva eccedere `@5`. **Non leggere quei numeri come "andare più in profondità non aiuta"** — dice il contrario, vedi il passo 1 qui sotto. Corretto il 2026-08-07: la profondità di valutazione è ora separata da quella di servizio (`harness.py`, `eval_depth = max(top_k, METRIC_DEPTH)`), e i run in `eval/results/` non hanno più il problema.

**2. Il rumore di fondo per il retrieval è esattamente zero, e questo NON significa che ogni delta conti.** Misurato il 2026-08-07 (E-07, 5 esecuzioni, 200 query, entrambi i dataset): σ = 0.000000 su ogni metrica. La pipeline di retrieval è deterministica — embedding ONNX senza campionamento, indice Qdrant fisso — quindi due esecuzioni identiche danno risultati identici bit per bit. La premessa di E-07 (*"lo stesso modello sulla stessa domanda cambia risposta tra esecuzioni"*) vale per la **generazione**, non per il retrieval.

Conseguenza pratica: per gli eval di retrieval il rumore di fondo E-07 non cattura l'incertezza rilevante, e un σ=0 letto distrattamente fa sembrare significativo qualunque delta. L'incertezza che conta è quella di **campionamento sul set di query**, e va stimata con un test appaiato sulle stesse query — McNemar sulle discordanti, non un confronto fra due medie. È così che si è scoperto che il +2.5% su open_ragbench non è distinguibile dal caso (7 query discordanti su 200).

---

## Protocollo

A stadi, dal più economico. Ogni stadio può chiudere la questione senza pagare quello dopo.

### Passo 0 — Rumore di fondo *(fatto, non ripetere)*

**Già fatto il 2026-08-07**: `eval/results/` contiene i `NoiseFloorResult` per entrambi i dataset. Risultato: **σ = 0.000000 ovunque** — il retrieval è deterministico.

Non rifarlo, e soprattutto **non leggerlo come "ogni delta è significativo"**. Per giudicare i delta degli stadi seguenti usa il test appaiato di McNemar sulle stesse query (vedi trappola 2 sopra), non la σ di E-07.

### Passo 1 — H2a, profondità di ranking *(~10 min, nessuna re-ingestione)*

I chunk giusti sono nell'indice ma fuori dal top-5, o proprio non emergono?

```bash
python scripts/eval.py --dataset ledger --collection ledger_routed \
  --pipeline-mode routed --doc-aggregate --top-k 20 --limit 200
python scripts/eval.py --dataset ledger \
  --pipeline-mode generic --doc-aggregate --top-k 20 --limit 200
```

**Cosa guardare:** `doc_R@10` (ora significativo, perché `top_k=20 > 10`) e `doc_R@5` su entrambi.

| esito | lettura |
|---|---|
| `doc_R@10` di routed risale vicino a `ledger` generic | **H2a confermata**: il problema è di *ranking*, non di rappresentazione. Il chunk giusto c'è, è il vicinato che lo supera. Direzione: reranker (R-02 già implementato) o `top_k` più alto in produzione — non serve re-ingestare niente. **La questione si chiude qui.** |
| `doc_R@10` resta piatto vicino a 0.60 | **H2a esclusa.** Il chunk giusto non emerge nemmeno guardando il doppio in profondità: è un problema di rappresentazione. Procedere al passo 2. |

Nota: usare `--limit 200` su entrambi, non l'intero golden set, e **lo stesso limite** su entrambi — altrimenti si confrontano popolazioni diverse.

### Passo 2 — H1, simulazione offline del contesto *(~10 min, nessuna re-ingestione)*

Verifica se prependere `section_path` al testo aiuta, **senza** re-ingestare 228k chunk. Idea: ricalcolare il ranking dentro un pool ristretto per le sole query che falliscono.

Per ogni query fallita su `ledger_routed` (`doc_recall == 0`):

1. recuperare il top-20 attuale da `ledger_routed` → il *pool sbagliato*;
2. risalire al `doc_id` corretto dai qrels golden (`doc_id_from_chunk_id`), e recuperare da `ledger_routed` **tutti** i chunk di quel documento (filtro Qdrant su `doc_id`) → il *pool giusto*;
3. per ogni chunk dei due pool, calcolare due embedding: `text` e `f"{section_path}\n\n{text}"` (saltare i chunk con `section_path` vuoto — restano invariati);
4. ricalcolare la similarità con la query e riordinare il pool unito, in entrambe le varianti;
5. contare in quante query un chunk del documento corretto entra nei primi 5 **solo** nella variante con contesto.

Costo: ~50 query × ~50 chunk × 2 varianti ≈ 5000 embedding ≈ 8 min a ~10/s.

**Cosa guardare:**

| esito | lettura |
|---|---|
| nessun miglioramento, o < 10% delle query | **H1 falsificata.** Non spendere le ore GPU del passo 3. Restano H2b e H3: il problema è la dimensione/natura del chunk, non il titolo mancante. Direzione alternativa: alzare la soglia minima di chunk nella pipeline `table_heavy`, o non isolare le tabelle da un minimo di prosa circostante. |
| miglioramento su ≥ 25% delle query fallite | **H1 sopravvive.** Vale il passo 3. |

**Attenzione al bias:** questa simulazione ri-embedda solo il pool, mentre una re-ingestione vera cambierebbe *tutti* i chunk dell'indice, inclusi i concorrenti che oggi non vediamo. È quindi **ottimistica per costruzione**: va usata per *falsificare* H1 (se non migliora nemmeno qui, è morta), non per confermarla. Un risultato positivo qui non è il risultato — è il permesso di pagare il passo 3.

### Passo 3 — Ablation vera *(~6–7 h GPU, solo se il passo 2 è positivo)*

**La modifica.** In `src/ingestion/pipeline_table_heavy.py`, `chunk_document()`: anteporre il `section_path` corrente al testo del chunk quando è non vuoto. Dietro un flag, mai come default — il default resta ciò che è già stato misurato in R-07.

**Perché lì e non altrove:** `section_path` è già calcolato da `_first_heading()` (I-05) ed ereditato dai chunk tabella; è già nel payload. Serve solo farlo entrare in `Chunk.text`, che è ciò che `embed.py` vede.

**Nota sui `chunk_id`:** non cambiano — sono sequenziali e non dipendono dal testo. Quindi il confronto è pulitissimo: stessi id, stessa segmentazione, **una sola differenza**.

```bash
# costruisce una terza collection, non tocca le esistenti
python scripts/ingest.py --dataset ledger --pipeline-mode routed \
  --collection-suffix routed_ctx --skip-download --drop

python scripts/eval.py --dataset ledger --collection ledger_routed_ctx \
  --pipeline-mode routed --doc-aggregate --limit 200
```

**Il confronto è `ledger_routed_ctx` contro `ledger_routed`** — *non* contro `ledger` generic. Fra routed_ctx e routed cambia una cosa sola (§14). Fra routed_ctx e generic ne cambiano tre, e il delta non sarebbe attribuibile. Il comparator della dashboard lo dice da solo: selezionando i due run deve comparire *"Cambia un parametro solo"*.

**Cosa guardare, in ordine:**

1. **`doc_R@5`, contro la σ del passo 0.** Punti di riferimento: `ledger_routed` = 0.6033, `ledger` generic = 0.8033.
   - delta ≤ σ → **nessun effetto**, H1 chiusa negativamente;
   - 0.60 → ~0.65-0.70 → H1 è **un fattore, non la causa**: resta un buco verso 0.80 da spiegare con H2b/H3;
   - 0.60 → ≥ 0.78 → H1 è **la** causa; a quel punto la modifica va valutata come default, e va rifatta anche per ORB.
2. **Le metriche chunk-level restano 0** su entrambi. È atteso e corretto: i `chunk_id` di routed non coincidono con i qrels. Se *non* fossero 0, qualcosa è andato storto nell'ingestione.
3. **Il set dei fallimenti, non solo la media.** Failure Explorer su entrambe le collection, 200 query: le query risolte sono *quelle* con chunk tabella? Se il guadagno arrivasse tutto da chunk di prosa, l'effetto misurato non sarebbe quello ipotizzato.
4. **Se il risultato è negativo, va in `progress.md` comunque.** ROADMAP §7: *"I risultati negativi restano in tabella"*.

---

### Dove sono le cose

| cosa | dove |
|---|---|
| pipeline da modificare | `src/ingestion/pipeline_table_heavy.py` → `chunk_document()` |
| heading già estratto | `_first_heading()`, stesso file (I-05) |
| cosa viene embeddato | `src/index/embed.py` → riceve `Chunk.text` |
| routing per genere | `src/ingestion/router.py` → `route_text()` |
| profondità di valutazione | `src/eval/harness.py`, `eval_depth` |
| test appaiato | `src/eval/paired.py`, `scripts/compare_runs.py` |
| misure di questa nota | riprodotte con `client.scroll` su Qdrant; nessuno script committato — sono usa e getta |
| esplorazione interattiva | dashboard → Failure Explorer e Retrieval Playground (tab A/B) |

---

## OQ-02 — I prefissi `query:` / `passage:` di E5 non vengono mai aggiunti

**Aperta.** Notata il 2026-08-11 durante l'audit delle librerie contro la loro documentazione ufficiale. Riferimento: I-07, E-03, e per estensione ogni numero dense del progetto.

### Il fatto

La model card ufficiale di `intfloat/multilingual-e5-large` è esplicita:

> *"Each input text should start with `query: ` or `passage: `, even for non-English texts. [...] This is how the model is trained, otherwise you will see a performance degradation."*

`src/index/embed.py` non li aggiunge mai — né sui chunk, né sulle query — e non è un'omissione compensata dalla libreria. Verificato sul sorgente della versione installata (fastembed 0.8.0):

- il modello è servito dalla classe `PooledEmbedding` (`fastembed/text/pooled_embedding.py`);
- quella classe sovrascrive solo `_get_worker_class`, `mean_pooling`, `_list_supported_models`, `_post_process_onnx_output`;
- **non** sovrascrive `query_embed` né `passage_embed`, che quindi cadono sulla base in `text_embedding_base.py`, dove entrambi si limitano a chiamare `embed()`.

fastembed sa che il problema esiste: la descrizione dei modelli nomic nel suo stesso registro dice *"Prefixes for queries/documents: necessary"*. Documenta la necessità e lascia il compito al chiamante.

### Cosa NON è dimostrato

Che aggiungerli migliori i nostri numeri. La model card afferma un degrado in generale; su questo corpus non è misurato. È una discrepanza fra uso e documentazione, non ancora un difetto quantificato.

### Perché è grave se lo è

Tocca il percorso dense, cioè **tutto**: R-07 e la conclusione sull'affermazione 2 del §0, le soglie di astensione di C-04 (calibrate su punteggi coseno dense), il contesto su cui poggiano C-01 e C-03. Non invalida i confronti *interni* — ogni ablation ha confrontato configurazioni che condividevano lo stesso difetto — ma sposterebbe il livello assoluto di ogni misura.

Nota anche che i prefissi sono **asimmetrici**: query e passaggi ricevono stringhe diverse. Un difetto simmetrico si semplifica in un confronto, uno asimmetrico no.

### Protocollo per misurarlo — *senza* re-ingestione completa

Una re-ingestione costa 618 minuti di GPU (misurati in R-07) e non serve per rispondere alla domanda.

1. **Indice ridotto, due varianti.** Campionare ~5.000 chunk da un dataset e indicizzarli due volte: `probe_plain` (come oggi) e `probe_prefixed` (`passage: ` su ogni chunk). ~15 min di GPU ciascuno.
2. **Le query nella forma corrispondente**: nude contro `probe_plain`, con `query: ` contro `probe_prefixed`. Le query golden i cui chunk rilevanti sono nel campione.
3. **Confronto appaiato** con `scripts/compare_runs.py`, criterio binario "almeno un documento rilevante nei primi 5".
4. **Non fare la variante mista** (query con prefisso contro indice senza) se non come curiosità: è una terza configurazione, non la correzione.

Se il delta è reale e positivo, la correzione è una re-ingestione completa e una ri-misura di tutta la Fase 3 — cioè un task del ROADMAP, non una patch.

---

## OQ-03 — Il retrieval "BM25" non è BM25

**Aperta.** Notata il 2026-08-11 nello stesso audit. Riferimento: E-06 (baseline C), R-01 (hybrid RRF).

### I due fatti

**1. Il modificatore IDF non è attivo.** La documentazione di Qdrant dice che i modelli BM25 *vanno* usati con `modifier="idf"` sull'indice sparso, perché fastembed **esclude di proposito** la componente IDF dai suoi vettori: la calcola Qdrant, a query time, dalle statistiche dell'indice. `ensure_collection()` crea `SparseVectorParams()` senza argomenti, e le collection in esecuzione lo confermano:

```
open_ragbench -> SparseVectorParams(index=None, modifier=None)
ledger        -> SparseVectorParams(index=None, modifier=None)
```

Senza IDF il punteggio è la sola frequenza di termine: una parola comune pesa quanto una rara. È BM25 privato della metà che discrimina.

**2. Le query vengono codificate come documenti.** `encode_sparse()` chiama `.embed()` anche sulle query. Il docstring di `Bm25.query_embed` in fastembed dice cosa andrebbe fatto invece:

> *"To emulate BM25 behaviour, we don't need to use weights in the query, and it's enough to just hash the tokens and assign a weight of 1.0 to them."*

Passando dalla via `embed()`, alla query viene applicata la normalizzazione per lunghezza del documento (il termine `b · doc_len / avg_len`): la domanda viene trattata come se fosse un documento del corpus.

### Il sospetto, e perché è più di un sospetto

Su LEDGER lo sparse crolla, e trascina l'hybrid **sotto** il dense:

| ledger | doc_R@5 | nDCG@10 |
|---|---|---|
| dense | 0.9367 | 0.0937 |
| sparse | **0.4758** | 0.0174 |
| hybrid (RRF) | 0.8408 | 0.0754 |
| dense + rerank | 0.9483 | 0.1276 |
| hybrid + rerank | 0.8858 | 0.1108 |

Su open_ragbench invece lo sparse regge (0.9700) e l'hybrid aiuta.

La direzione combacia con il difetto: LEDGER è fatto di bilanci, dove a discriminare sono token rari — nomi di voci, sigle, cifre — cioè esattamente ciò che l'IDF pesa e la sola frequenza di termine no. Su paper accademici il vocabolario è più uniforme e l'assenza di IDF costa meno.

**Non è dimostrato** che correggere i due difetti ribalti il risultato. È dimostrato che l'esperimento non ha misurato ciò che dichiarava: E-06 si chiama *"baseline C: retrieval lessicale BM25"* e non era BM25, e R-01 ha fuso quel braccio.

### Perché è molto più economico di OQ-02

Nessuna re-embeddatura dei chunk: i vettori sparsi sono già su disco e sono corretti così com'è (la componente TF è quella giusta). Serve

- ricreare l'indice sparso con `modifier=models.Modifier.IDF` — l'IDF viene dalle statistiche dell'indice, non dai vettori;
- una riga in `encode_sparse()` per il percorso query.

Poi si rilanciano `--retrieval-mode sparse` e `--retrieval-mode hybrid` sui due dataset.

### Trappola

Non correggere i due difetti insieme e misurare una volta sola (§14: *mai due cambiamenti in una misura*). Sono due cause indipendenti: l'IDF vive nell'indice, la codifica della query nel client.

---

### Dove sono le cose (OQ-02, OQ-03)

| cosa | dove |
|---|---|
| prefissi mancanti | `src/index/embed.py` → `encode()`, e il percorso query in `src/eval/retrieval_backends.py` |
| creazione collection | `src/index/store.py` → `ensure_collection()` |
| codifica sparsa | `src/index/embed.py` → `encode_sparse()` |
| verifica dei fatti | model card E5; sorgente fastembed installato; `client.get_collection(name).config.params.sparse_vectors` |

---

## OQ-04 — Metà del testo di un chunk non entra nell'embedding

**Aperta.** Notata il 2026-08-11 controllando perché I-03 e I-04 non hanno un criterio di accettazione. Riferimento: I-03, I-04, I-07, e per estensione ogni misura di retrieval denso.

### Il fatto

Il tokenizer di `multilingual-e5-large` tronca a **512 token**, direzione destra: tutto ciò che segue viene scartato prima dell'embedding. Le pipeline di chunking non conoscono quel limite. Misurato su 1.500 chunk per collection, con il tokenizer vero e la troncatura disattivata per contare i token reali:

| collection | mediana | p99 | max | oltre 512 token | testo embeddato (mediana) |
|---|---|---|---|---|---|
| open_ragbench | 1.009 tok | 16.373 | 39.348 | **67,6%** | **50,8%** |
| ledger | 881 tok | 2.117 | 3.385 | **82,1%** | **58,2%** |

Il chunk mediano è indicizzato per **circa metà del suo testo**. Il chunk al p99 di open_ragbench è indicizzato per il 3%.

Il testo completo arriva comunque all'LLM in generazione: **il sistema risponde su materiale che non ha potuto trovare.** Il difetto è nel retrieval, non nella risposta.

### Perché è più grande di OQ-02

OQ-02 è un prefisso mancante su un input per il resto integro. Qui l'input è mezzo. Le due cose vivono nella stessa funzione (`encode()`) e sono entrambe misurabili sullo stesso indice ridotto, ma **non vanno misurate insieme** (§14).

### Impatto sulle misure già fatte

Verificato sui contesti reali di C-01 (200 query, dump `20260810_102617`): 10 chunk su 920 recuperati superano i 32.000 caratteri, e **1 query su 200** produce un contesto che eccede la finestra da 32k token del modello. Sulle risposte già misurate il danno è quindi marginale. Sul **retrieval** no: lì il difetto agisce su due terzi del corpus.

### Il dato che tocca OQ-01

| collection | mediana | oltre 512 token |
|---|---|---|
| ledger | 881 tok | 82,1% |
| **ledger_routed** | **243 tok** | **5,8%** |

`ledger_routed` entra quasi interamente nella finestra dell'embedder — **e perde di 17 punti**. La congettura registrata in `progress.md` (*«sub-chunking aggressivo → chunk troppo piccoli, IDF diluito»*) punta nella direzione opposta a questo dato: la pipeline generica vince **nonostante** sia troncata all'82%.

Non risolve OQ-01. Elimina però l'ipotesi più intuitiva — che generic vinca perché porta più testo nell'indice — perché in proporzione ne porta **meno**. La domanda si stringe: da dove viene il vantaggio di generic, se non dalla quantità di testo indicizzato?

### Protocollo

Stesso impianto di OQ-02, e per la stessa ragione: indice ridotto, niente re-ingestione.

1. **Campionare** ~5.000 chunk di un dataset dai documenti coperti dai golden.
2. **Ri-chunkare** quel campione con un tetto a 512 token (le pipeline sono già parametriche: il tetto è un parametro, non una riscrittura).
3. **Indicizzare le due varianti** e confrontare in appaiato con `scripts/compare_runs.py`, criterio binario "almeno un documento rilevante nei primi 5".
4. **Non cambiare anche i prefissi** nella stessa misura.

Attenzione a un confondente: a parità di corpus, chunk più piccoli significano **più chunk**, quindi più concorrenti nel ranking e più chunk dello stesso documento fra i primi k. È esattamente la variabile che rende OQ-01 difficile, e va letta a livello di documento per la stessa ragione per cui R-07 si legge su `doc_R@5`.

### Cosa NON è dimostrato

Che rispettare la finestra migliori il retrieval. `ledger_routed` è la prova che non è automatico: sta nella finestra e va peggio. La misura serve proprio perché il ragionamento a tavolino qui ha già sbagliato una volta.
