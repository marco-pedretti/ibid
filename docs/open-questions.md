# Domande aperte

Ipotesi emerse durante il lavoro, **non ancora verificate**, con il protocollo per verificarle.

Non è `progress.md` (che registra cosa è stato fatto) né `ROADMAP.md` (che definisce i task da fare): qui stanno le cose che abbiamo *notato* e che meritano una misura prima di essere chiamate cause. Una voce esce da qui quando diventa un task con un delta misurato, e il risultato — positivo o negativo — va in `progress.md`.

---

## OQ-01 — Perché il routing peggiora LEDGER di 17 punti

**RISOLTA A METÀ (2026-08-13, R-10).** Osservata il 2026-08-07 durante la riscrittura della dashboard. Riferimento: R-07.

> **Le tre ipotesi qui sotto sono cadute tutte. La causa principale non era in elenco.**
>
> **45,9% del regresso è richiamo perso da HNSW.** Con ricerca **esatta**, `ledger_routed` va da 0,7647 a 0,8471 (857 query recuperate contro 33 perse su 10.000) mentre `ledger` si muove di 0,37 punti. Il divario passa da −17,14 a **−9,27**. `ledger_routed` ha 228.331 punti contro 47.110, in una banda di similarità larga 0,0085: le condizioni peggiori per un grafo di prossimità. Costo del rimedio: **2,5 ms/query contro 1,4**, e nessuna re-ingestione — `exact` e `hnsw_ef` sono parametri di ricerca. Adozione proposta come **R-11**.
>
> **H1 (heading mancante) — falsificata.** La simulazione del passo 2 dà +17,33%, che letto da solo sarebbe positivo. Ma un `section_path` **sbagliato**, preso da un altro documento, guadagna **esattamente lo stesso** (+17,33%), e il confronto appaiato vero-contro-finto dà 12 discordanti contro 12, p=1,0000. Il guadagno era perturbazione di un quasi-pareggio, non contesto.
>
> **H2b e H3 — falsificate.** Le query fallite e quelle riuscite hanno chunk d'oro **strutturalmente identici**: 1034 contro 1022 caratteri, 0,75 contro 0,75 lettere/carattere, `section_path` nel testo nel 66,4% contro 65,3%. Se dimensione o isolamento fossero la causa, i due gruppi differirebbero. Non differiscono.
>
> **H2a — fattore parziale.** Passare da profondità 5 a 20 recupera 6 punti su 17.
>
> **Aggiornamento R-11 (stesso giorno).** Misurate tutte e quattro le collection: il guadagno della ricerca esatta segue il **richiamo dell'indice**, non la sua taglia. `open_ragbench` +0,0000 (l'ANN trova il 99,94% del vero top-5), `open_ragbench_routed` +0,0030, `ledger` +0,0046, `ledger_routed` **+0,0846** (84,84%). Su `doc_R@5` il divario fra le due pipeline LEDGER passa da **−21,71 a −13,72**: il **37%** del regresso attribuito al routing era l'indice. Il default resta spento — è una scelta, non una correzione — ma il §15 ora vieta di confrontare indici di densità diversa con la ricerca approssimata.
>
> **Cosa resta:** 9,27 punti dopo aver tolto HNSW. Il regime è quello del quasi-pareggio — il chunk d'oro perde per 0,0090 di coseno, l'intero top-5 sta dentro 0,0085, e il routing ha portato i concorrenti a pari merito da 7,1 a 9,0 di media. Descritto, non ancora azionabile. Numeri e ragionamento in [`progress.md`](progress.md) → *R-10*.
>
> **Sul protocollo qui sotto.** È stato eseguito com'era scritto, ed è giusto così. Ma il suo criterio binario non copriva il risultato reale né al passo 1 né al passo 2, e il passo 2 misurava senza saperlo l'instabilità dell'ordinamento invece del valore del contesto. **Pre-registrare un test protegge dallo scegliere il test dopo aver visto i dati; non protegge dall'aver scelto il test sbagliato prima.** Serve comunque un controllo che dica cosa il test sta misurando — ed è ciò che ha ribaltato la conclusione.

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

Il routing su LEDGER ha cambiato **tre cose insieme**, il che viola §15 se le si vuole attribuire:

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

**Il confronto è `ledger_routed_ctx` contro `ledger_routed`** — *non* contro `ledger` generic. Fra routed_ctx e routed cambia una cosa sola (§15). Fra routed_ctx e generic ne cambiano tre, e il delta non sarebbe attribuibile. Il comparator della dashboard lo dice da solo: selezionando i due run deve comparire *"Cambia un parametro solo"*.

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
| misure di questa nota | le originali con `client.scroll`, usa e getta; quelle di R-10 in `scripts/probe_routing_depth.py`, `probe_routing_failures.py`, `probe_section_context.py`, `probe_ann_recall.py` |
| ricerca esatta vs approssimata | `scripts/probe_ann_recall.py` — `SearchParams(exact=True)` e `hnsw_ef` |
| esplorazione interattiva | dashboard → Failure Explorer e Retrieval Playground (tab A/B) |

---

## OQ-02 — I prefissi `query:` / `passage:` di E5 non vengono mai aggiunti


> **Misurata il 2026-08-12 (I-08): non si vede.** Su indice ridotto, 1.903 query appaiate: doc@1 +0,0100 (p=0,0503), doc@3 **−0,0016**, doc@5 +0,0005. Sfiora la soglia solo dove c'è più margine, cambia segno più in profondità. La deviazione dalla model card resta reale; il suo costo su questo corpus non è dimostrato, e **I-09 non è giustificata da questi dati**. Dettagli in `progress.md`.
**DECISA, NON CHIUSA (2026-08-12).** Notata il 2026-08-11 durante l'audit delle librerie contro la loro documentazione ufficiale. Riferimento: I-07, E-03, e per estensione ogni numero dense del progetto.

> **Cosa significa «decisa, non chiusa».** La domanda *«quanto ci costa?»* ha una risposta misurata: su questo corpus, niente di dimostrabile. La deviazione dalla model card invece **resta**, ed è vera. Non c'è lavoro pendente, ma se un domani si cambiasse embedder o corpus la misura andrebbe rifatta — non ereditata.

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

**CHIUSA (2026-08-13).** Notata il 2026-08-11 nell'audit delle librerie. Riferimento: E-06 (baseline C), R-01 (hybrid RRF).

> **Fatto 1 — chiuso da R-08.** `modifier=IDF` è attivo su tutte e sette le collection, applicato in place. L'effetto è **opposto nei due dataset** e sta in [`progress.md`](progress.md) → *R-08*. La misura ha aperto **OQ-06**.
>
> **Fatto 2 — chiuso da R-09, con risultato nullo.** Le query passano da `query_embed()`. Effetto massimo: **4 query discordanti su 10.000**. Il motivo è aritmetico e non statistico — il punteggio sparso è un prodotto scalare, e nell'87–94% dei casi le due codifiche differiscono per un solo fattore di scala, che non cambia l'ordinamento. Dettagli in `progress.md` → *R-09*.
>
> **Quindi tutto il guadagno di OQ-03 è l'IDF, nella misura 100 a 0.** È l'informazione che si sarebbe persa correggendo le due metà insieme, ed è ciò che il §15 comprava.
>
> **La previsione scritta qui sotto il 2026-08-11 era metà giusta, ed è utile sapere quale metà.** Diceva: *«su LEDGER a discriminare sono token rari, cioè esattamente ciò che l'IDF pesa»*. A livello di **documento** ha colto in pieno — doc@5 da 0,6411 a 0,9196, +27,9 punti su 10.000 query. A livello di **chunk** ha sbagliato segno: −1,31 punti, p<0,0001. Trovare il documento giusto e trovare il passaggio giusto non sono la stessa cosa, e la previsione non distingueva fra i due.
>
> **E una previsione mancava del tutto:** che il fatto 2, pur essendo una deviazione reale dalla documentazione, non potesse quasi muovere niente. Bastava guardare l'aritmetica del prodotto scalare — nessuna misura era necessaria per sospettarlo. Non ci abbiamo pensato, e l'abbiamo scoperto misurando.

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

- ~~ricreare l'indice sparso con `modifier=models.Modifier.IDF`~~ — **fatto (R-08)**, e senza ricrearlo: `update_collection` lo aggiunge in place;
- ~~una riga in `encode_sparse()` per il percorso query~~ — **fatto (R-09)**: funzione separata `encode_sparse_query()`, e quattro percorsi query aggiornati.

Entrambe misurate appaiate con `scripts/probe_sparse_paired.py` (`--vary idf` e `--vary query_embed`) sulla golden intera. **Non su un campione**: a 200 query l'effetto dell'IDF su open_ragbench era `p=0,7266`, cioè invisibile, e a 3.045 è `p<0,0001`.

### Trappola

Non correggere i due difetti insieme e misurare una volta sola (§15: *mai due cambiamenti in una misura*). Sono due cause indipendenti: l'IDF vive nell'indice, la codifica della query nel client.

---

### Dove sono le cose (OQ-02, OQ-03)

| cosa | dove |
|---|---|
| prefissi mancanti | `src/index/embed.py` → `encode()`, e il percorso query in `src/eval/retrieval_backends.py` |
| creazione collection | `src/index/store.py` → `ensure_collection()`, `ensure_idf_modifier()` |
| codifica sparsa | `src/index/embed.py` → `encode_sparse()` (corpus) e `encode_sparse_query()` (query) |
| verifica dei fatti | model card E5; sorgente fastembed installato; `client.get_collection(name).config.params.sparse_vectors` |

---

## OQ-04 — Metà del testo di un chunk non entra nell'embedding


> **Misurata il 2026-08-12 (I-10): l'effetto c'è.** Su indice ridotto, 1.903 query appaiate: doc@1 +0,0126 (**p=0,0384**), doc@3 +0,0079 (p=0,0400), doc@5 +0,0074 (p=0,0336) — stessa direzione a tutte le profondità. Il prezzo è **4,05× i chunk**. Resta da decidere se valga una re-ingestione (I-11). Su LEDGER non misurabile: doc@5 è già a 0,9950. Dettagli in `progress.md`.

> **E non adottata (I-11, stesso giorno).** Il tetto non cambia la generazione — formato identico dopo il parser (p=1,0000), astensione non peggiorata — e gli +11 punti di `citation_precision` che sembravano sostenerlo erano **la lunghezza della premessa**: dentro un solo braccio l'accettazione cala da 79,2% a 57,8% al crescere del chunk. Nessun guadagno di qualità contro 618 minuti di re-ingestione e un indice ×4. Restano da riconsiderare alla prossima re-ingestione la latenza (−44%) e le premesse spezzate azzerate.
**DECISA, NON CHIUSA (2026-08-12).** Notata il 2026-08-11 controllando perché I-03 e I-04 non hanno un criterio di accettazione. Riferimento: I-03, I-04, I-07, e per estensione ogni misura di retrieval denso.

> **Cosa significa «decisa, non chiusa».** Qui l'effetto sul retrieval **c'è** ed è misurato; quello che non c'è è un guadagno sulla generazione che giustifichi il prezzo. Il troncamento continua quindi a esistere in ogni indice del progetto, per scelta consapevole. Le due voci da riconsiderare alla prossima re-ingestione — latenza −44% e premesse spezzate — sono lavoro reale, ma condizionato a un evento che non è ancora in programma.

### Il fatto

Il tokenizer di `multilingual-e5-large` tronca a **512 token**, direzione destra: tutto ciò che segue viene scartato prima dell'embedding. Le pipeline di chunking non conoscono quel limite. Misurato su 1.500 chunk per collection, con il tokenizer vero e la troncatura disattivata per contare i token reali:

| collection | mediana | p99 | max | oltre 512 token | testo embeddato (mediana) |
|---|---|---|---|---|---|
| open_ragbench | 1.009 tok | 16.373 | 39.348 | **67,6%** | **50,8%** |
| ledger | 881 tok | 2.117 | 3.385 | **82,1%** | **58,2%** |

Il chunk mediano è indicizzato per **circa metà del suo testo**. Il chunk al p99 di open_ragbench è indicizzato per il 3%.

Il testo completo arriva comunque all'LLM in generazione: **il sistema risponde su materiale che non ha potuto trovare.** Il difetto è nel retrieval, non nella risposta.

### Perché è più grande di OQ-02

OQ-02 è un prefisso mancante su un input per il resto integro. Qui l'input è mezzo. Le due cose vivono nella stessa funzione (`encode()`) e sono entrambe misurabili sullo stesso indice ridotto, ma **non vanno misurate insieme** (§15).

### Impatto sulle misure già fatte

Verificato sui contesti reali di C-01 (200 query, dump `20260810_102617`): 10 chunk su 920 recuperati superano i 32.000 caratteri, e **1 query su 200** produce un contesto che eccede la finestra da 32k token del modello. Sulle risposte già misurate il danno è quindi marginale. Sul **retrieval** no: lì il difetto agisce su due terzi del corpus.

### Il difetto morde? Sì su open_ragbench, non visibile su LEDGER

Misurato senza spendere GPU, su dati già su disco: i chunk recuperati stanno nei dump di C-01, i chunk giusti nei qrels, i testi in Qdrant. Riproducibile con `scripts/probe_truncation.py`.

Per ogni query si guarda la lunghezza del chunk **giusto** (quello dei qrels), separando le query in cui il retrieval l'ha trovato da quelle in cui l'ha mancato:

| | trovato | mancato | oltre 512 token | Fisher esatto |
|---|---|---|---|---|
| **open_ragbench** | mediana **564** tok (n=162) | mediana **1.525** tok (n=38) | 51,2% contro **81,6%** | **p = 0,00087** |
| ledger | mediana 1.356 tok (n=70) | mediana 1.061 tok (n=130) | 95,7% contro 90,8% | p = 0,267 |

Su open_ragbench **il chunk giusto mancato è quasi tre volte più lungo di quello trovato.** La direzione è ciò che rende la lettura non banale: a parità di tutto il resto un chunk più lungo contiene *più* testo, quindi dovrebbe essere più facile da trovare. Se viene mancato di più, la spiegazione più semplice è che quel testo in più nell'indice non c'è.

Su LEDGER non si vede niente, e non è la stessa cosa che non esserci: là **il 90-96% dei chunk giusti supera i 512 token in entrambi i gruppi**. Il confronto è fra troncato e troncato, quindi la variabile è quasi costante e il test non ha nulla da separare. Assenza di potenza, non evidenza di assenza.

**Resta descrittivo.** La lunghezza correla con altro — genere della sezione, posizione nel documento, quanto è specifica la domanda — e da qui non si separa. È il motivo per cui I-10 esiste comunque: questo dice che vale la pena di misurarlo, non lo sostituisce.

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

---

## OQ-05 — Cosa serve per verificare una citazione numerica contro una tabella

> **CHIUSA il 2026-08-12.** Decisa con l'opzione 2 e il vincolo del nome, implementata come **C-09**: `numeric_citation_precision` 0,7328 su LEDGER contro lo 0,2374 dell'NLI sulle stesse coppie, copertura 39,6%. Le due metriche restano separate, come il vincolo imponeva. Il resoconto è in [`progress.md`](progress.md), C-09; quel che segue è la nota che ha portato alla decisione e resta per come ci si è arrivati.

**Aperta.** Nata il 2026-08-12 da un risultato negativo: C-08 ha escluso la spiegazione più semplice, e ciò che resta richiede una decisione più grande.

### Il fatto

Su LEDGER `citation_precision` vale 0,3656 e non è interpretabile come proprietà del generatore. La diagnosi aveva due metà:

1. le premesse sono markup di tabelle OCR — mediana **26,5%** di token di markup, peggiore 77,2%;
2. il **96,7%** dei claim è numerico, cioè valori estratti da quelle tabelle.

**C-08 ha testato la prima ed è stata falsificata.** Rendendo le tabelle in righe `cella | cella` sulle stesse 331 coppie: 0,3656 → 0,3263, **35 citazioni perse contro 22 guadagnate, p = 0,1112**. La variazione di P(entailment) è simmetrica (mediana +0,0000, 132 giù e 125 su): il verificatore è **indifferente alla forma superficiale** della tabella.

### Cosa resta, e perché è una decisione più grande

Resta la seconda metà, che nessuna riformattazione tocca: un modello NLI addestrato su prosa deve giudicare se *«i ricavi 2017 sono 1.234»* è implicato da una tabella di bilancio. Non è un problema di come la tabella è scritta — è che l'operazione richiesta è **una ricerca in una griglia più un confronto numerico**, non un'inferenza linguistica.

Il ROADMAP §8 diceva: *«prendere ora quella decisione significherebbe costruire un secondo strumento per aggirare un difetto rimediabile nel primo»*. Ora sappiamo che il difetto **non è rimediabile nel primo**, quindi l'obiezione cade e la decisione è giustificata.

### Quanto sbaglia lo strumento attuale — misurato il 2026-08-12

Prima di scegliere serviva sapere **quanto sbaglia il verificatore sulle tabelle**, che era la cosa che la sezione qui sotto dichiarava non dimostrata. Ora è misurata, e senza spendere GPU: i punteggi sono nei verdetti salvati, i testi in Qdrant, e *«il numero asserito è nel chunk»* è una ricerca di stringa. Riproducibile con `scripts/probe_table_floor.py`.

Su claim i cui numeri distintivi stanno **tutti** nel chunk citato — cioè affermazioni che il chunk quantomeno contiene:

| | coppie | accettate a soglia 0,5 | P(entailment) mediana |
|---|---|---|---|
| **open_ragbench** (prosa) | 29 | **58,6%** | **0,580** — sopra soglia |
| **ledger** (tabelle) | 161 | **28,0%** | **0,276** — ben sotto |

Stesso tipo di affermazione, stesso verificatore, stessa soglia: **lo strumento è circa la metà sensibile sul genere tabellare.** Su LEDGER dà 0,276 di mediana a claim i cui numeri sono dimostrabilmente lì.

Quindi `citation_precision` 0,3656 è dominata dal **pavimento dello strumento**, non dal generatore. E la differenza fra i due dataset (0,657 contro 0,366) riflette in buona parte la differenza fra i due pavimenti (0,586 contro 0,280), non due modi diversi di citare.

**Il numero che questa misura NON dà.** La presenza del numero non prova che il claim sia corretto: `1.234` può stare nella riga sbagliata o nell'anno sbagliato. È un proxy direzionale. Ma per la decisione basta: qualunque sia la verità su quei 161 claim, **il verificatore attuale non la sta misurando** — dà 0,276 sia quando il numero c'è sia quando non c'è (mediana 0,283 sui 5 casi in cui manca, troppo pochi per un test ma non incoraggianti).

**Nota su cosa questo non autorizza:** abbassare la soglia. A 0,276 si accetterebbe metà del gruppo "presenti", ma sarebbe una soglia tarata sugli stessi dati su cui si riporta la metrica — la trappola che `config.py` documenta e che C-03 ha evitato di proposito. E cambierebbe anche open_ragbench, dove il problema non c'è.

### Le opzioni, e cosa costa sbagliarle

| opzione | cosa comporta | rischio |
|---|---|---|
| **Riga muta**: `citation_precision` riportata solo su open_ragbench | zero lavoro | metà della prima affermazione del §0 resta senza numero, e C-06 avrà una curva di scaling con una riga vuota |
| **Verificatore numerico per il genere tabellare**: il claim è supportato se i valori che asserisce compaiono nel chunk citato, con la loro etichetta di riga | scrivibile senza modelli nuovi | un numero che compare da qualche parte in una tabella non è il valore asserito: serve l'associazione riga/colonna, ed è lì che il lavoro vero sta |
| **Verificatore diverso per dataset** | massima fedeltà | due strumenti che producono la stessa metrica con definizioni diverse — **i due dataset smettono di essere confrontabili**, che è precisamente ciò che il §3.1 vieta |

La terza è la trappola: sembra la più rigorosa ed è quella che rompe il contratto. Se si va in quella direzione, la metrica va rinominata per dataset, non chiamata `citation_precision` in entrambi i casi.

### Da decidere prima di C-06

Vale ancora ciò che il §8 diceva: se C-06 gira senza aver risolto questo, la curva per taglia del modello ha una riga muta su un dataset su due, e la cosa emerge a run finite.

### Cosa NON è dimostrato

Che un verificatore numerico farebbe meglio. Il floor test di C-03 mostrava che il verificatore attuale, **su prosa**, mancava un terzo dei claim copiati alla lettera: la soglia 0,5 lo rende pessimista per scelta. Prima di costruire un secondo strumento va misurato quanto quello attuale sbaglia **su tabelle**, e il controllo dai qrels lì produce **3 sole coppie** — troppo poche. Serve prima un floor test costruito apposta per il genere tabellare.

---

## OQ-06 — L'IDF porta al documento giusto e allontana dal chunk giusto

**Aperta.** Emersa il 2026-08-13 dalla misura di R-08. Riferimento: R-08 in [`progress.md`](progress.md).

### Il fatto

Attivare `modifier=IDF` su LEDGER, misurato appaiato su 10.000 query:

| LEDGER, `sparse` | senza IDF | con IDF | Δ | p |
|---|---|---|---|---|
| doc@5 | 0,6411 | **0,9196** | **+27,85** | <0,0001 |
| chunk@5 | 0,0946 | **0,0815** | **−1,31** | <0,0001 |

Le due direzioni sono entrambe significative e vanno in senso opposto. Su open_ragbench il conflitto non esiste: l'IDF guadagna a tutti e due i livelli.

Dopo la fusione RRF il danno sul chunk **non si attenua, peggiora**: `hybrid` chunk@5 fa −2,32 (597 query perse contro 365 guadagnate). Ed è `hybrid` chunk@5 il numero che la generazione consuma davvero.

### L'ipotesi

Su LEDGER i token rari sono cifre e identificativi. Con l'IDF dominano il punteggio e tirano verso il documento che contiene quella cifra, ma verso il chunk che la *nomina* — un indice, un sommario, un rimando — invece che verso quello che risponde. Senza IDF domina la frequenza di termine, che premia i chunk che ripetono i termini della domanda.

**Non è misurata.** È coerente con i segni osservati e con quello che LEDGER è, ma "coerente con" non è "dimostrata da".

### Protocollo

1. Estrarre le query discordanti a `sparse` chunk@5 — sono **484 perse e 353 guadagnate**, numeri comodi da leggere a campione. `scripts/probe_idf_paired.py` le calcola già; serve solo farsele stampare.
2. Leggerne 30 per gruppo: il chunk recuperato con IDF è un indice/sommario/rimando, o è un chunk di contenuto sbagliato? Se prevale il primo caso l'ipotesi regge, e la correzione non è l'IDF ma il filtro sul `content_type`.
3. **Solo se i passi 1–2 sono positivi**, misurare l'IDF per genere: attivo su `continuous_text`, spento su `table_heavy`.

### Perché conta più di due punti di `hit@5`

Perché è materia dell'**affermazione 2 del §0** — *«il routing automatico per genere documentale batte una pipeline generica»* — e per una volta il candidato al routing non è la pipeline di chunking ma un parametro dell'indice. È la quarta volta che il genere emerge come variabile dominante in questo progetto.

### Trappola

Attivare l'IDF per genere **senza** i passi 1–2 sarebbe scegliere la configurazione che vince sui dati su cui la si misura: la stessa trappola della soglia tarata sui propri dati che C-03 ha evitato. E sarebbe un secondo cambiamento infilato nella misura di R-08 (§15).
