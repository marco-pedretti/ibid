# Hardware — risultati smoke test (T-02)

**Sistema:** AMD RX 6750 XT, 12 GB GDDR6 | Windows 11 Pro  
**Inferenza:** Ollama 0.32.5 (backend GPU: Vulkan/DirectML automatico)  
**Data:** 2026-08-04  
**Parametri fissi:** temperatura 0, contesto 32768 token, `think: false` (reasoning disabilitato)

---

## Risultati

| Modello (nome Google) | Tag Ollama | Parametri | Quant. | Gen. (tok/s) | Prefill (tok/s) | VRAM | Processor |
|---|---|---|---|---|---|---|---|
| Gemma 4 E2B | `gemma4:e2b` | 5.1B | Q4_K_M | **91.2** | 434.5 | 1.9 GB | 100% GPU |
| Gemma 4 E4B | `gemma4:latest` | 8.0B | Q4_K_M | **15.1** | 146.3 | 3.3 GB | 100% GPU |
| Gemma 4 12B | `gemma4:12b` | 11.9B | Q4_K_M | **2.4** | 33.8 | 8.1 GB | 100% GPU |
| Gemma 4 26B MoE | `gemma4:27b` | — | — | — | — | ~18 GB | — |

> **Nota sui nomi Google:** "E2B" e "E4B" non corrispondono al conteggio di parametri. I parametri reali (da `ollama show`) sono 5.1B e 8.0B rispettivamente. La nomenclatura Google usa probabilmente "E" per indicare una famiglia di architettura efficiente.

> **Nota su thinking:** Gemma 4 è un thinking model. Con `think: true` (default) i token vengono consumati dal ragionamento interno e la risposta visibile risulta vuota finché il budget non è esaurito. In produzione (`reasoning_enabled: true`, task C-07) le velocità saranno diverse: la generazione di thinking tokens è risultata più veloce (E4B ~78 tok/s nel primo test) ma produce output non visibili.

---

## Decisione sul 26B MoE

**Escluso.** Il file GGUF pesa ~18 GB, che supera i 12 GB di VRAM disponibili. Caricare il modello in RAM di sistema e usare la CPU produrrebbe velocità nell'ordine di 1-3 tok/s — inutilizzabili per la valutazione interattiva e per le run automatizzate di Fase 2-4.

La curva di scaling in **C-06** si ferma quindi a 12B. I tre punti della curva sono E2B (5.1B), E4B (8.0B), 12B (11.9B).

> Questo esito era previsto come rischio in `ROADMAP.md §17`: "26B inutilizzabile sulla GPU → si scala a 12B, la curva regge."

---

## Embedding — backend e modello (T-05)

### Perché non PyTorch + sentence-transformers

La scelta originale (STACK.md) era `BAAI/bge-m3` via `sentence-transformers`. Su questa macchina è inutilizzabile:

| Backend | Velocità (testi lunghi ~200 parole) | Note |
|---|---|---|
| PyTorch CPU (sentence-transformers) | **0.06 embed/s** | ~1675s per 100 chunk |
| fastembed ONNX CPU | **1.9 embed/s** | ONNX più efficiente, ma ancora lento |
| fastembed + onnxruntime-directml (AMD GPU) | **10.4 embed/s** | DirectX 12 → GPU senza ROCm |

PyTorch non vede la GPU AMD su Windows perché non esiste un backend nativo: ROCm è Linux-only e CUDA non è compatibile con AMD. `onnxruntime-directml` invece usa DirectX 12 Machine Learning, che funziona su qualsiasi GPU DirectX 12 — inclusa la RX 6750 XT.

### Soluzione adottata

`fastembed` + `onnxruntime-directml` con rilevamento automatico del provider in `src/index/embed.py`:

```python
_PROVIDERS = (
    ["DmlExecutionProvider", "CPUExecutionProvider"]
    if "DmlExecutionProvider" in onnxruntime.get_available_providers()
    else ["CPUExecutionProvider"]
)
```

### Modello attuale vs target

**Attuale (T-05):** `intfloat/multilingual-e5-large` — fastembed non ha ancora BGE-M3 nel catalogo.  
**Target:** `BAAI/bge-m3` — quando fastembed lo supporta, cambiare una riga in `src/config.py` e re-ingest.

La differenza qualitativa sul retrieval denso puro è piccola (~2-5 punti nDCG su benchmark BEIR). La differenza che conta è che **BGE-M3 produce anche vettori sparsi** nello stesso passaggio — necessari per il retrieval ibrido di R-01 senza aggiungere un secondo modello. Con e5-large R-01 richiederebbe un modello separato per la parte sparsa.

Il re-ingest è necessario al cambio modello perché le collection Qdrant contengono vettori nello spazio del modello corrente, incompatibili con quelli del nuovo.

---

## Note operative

- La colonna **VRAM** viene da `ollama ps` subito dopo la generazione con 32k context e prompt breve (~40 token); il KV cache occupa quota minima in questo caso.
- Il 12B a 2.4 tok/s è lento per uso interattivo (~50s per 120 token) ma accettabile per run di valutazione automatizzata notturna.
- Per verificare il backend GPU effettivo usato da Ollama: `%LOCALAPPDATA%\Ollama\logs\server.log`.
- I dati grezzi JSON sono in `eval/contamination/smoke_20260804_103814.json`.

---

## Cosa gira senza GPU (misurato 2026-08-07)

Domanda pratica: un secondo sviluppatore **senza GPU** cosa può fare del progetto?
Misure su `intfloat/multilingual-e5-large` via fastembed, forzando
`CPUExecutionProvider`.

| operazione | CPU | verdetto |
|---|---|---|
| embedding **query** (testi corti) | **35.9 embed/s** | ✅ nessun problema |
| embedding **chunk** (mediana 3182 char, chunk reali dall'indice) | **2.38 embed/s** | ❌ vedi sotto |
| sparse BM25 | statistico | ✅ già su CPU anche con GPU presente |

**Conseguenze concrete:**

- **Gli eval completi si eseguono su CPU.** Le query sono corte: open_ragbench
  (3045 query) ≈ 85 s, LEDGER (10000) ≈ 4.6 min. Non è un ripiego, è la stessa
  misura.
- **L'ingestion no.** Le due collection generic (65.950 chunk) sono **7.7 ore**
  di CPU contro ~1.8 ore su DirectML. Il rapporto GPU/CPU è ~4×.
- **Il 167× di T-05 non vale più**: quel numero confrontava PyTorch CPU con
  fastembed/DirectML, cioè due stack diversi. A parità di stack (ONNX) il
  divario è 4×.
- **La generazione richiede comunque una GPU.** Gemma 12B su CPU è
  inutilizzabile; `LLM_BASE_URL` esiste apposta — si punta a un endpoint
  remoto. **C-06** (curva di scaling con latenza e VRAM) è irriducibilmente
  legata alla macchina con GPU.

### Dimensioni dell'indice

| collection | punti | quota del volume |
|---|---|---|
| `open_ragbench` | 18.840 | 5% |
| `ledger` | 47.110 | 12% |
| `open_ragbench_routed` | 98.312 | 25% |
| `ledger_routed` | 228.331 | 58% |

Volume Docker totale: **4.97 GB**. Uno snapshot Qdrant di `open_ragbench` pesa
**222 MB** e si crea in ~1 s: circa **11.8 KB per punto**.

Nota: le due collection `*_routed` sono l'83% del volume ed esistono solo per
l'ablation R-07, **chiusa**. Chi non lavora su OQ-01 non ne ha bisogno: servono
le due generic, ~780 MB di snapshot.

### Da fare, quando serve (non ancora fatto)

1. **`scripts/snapshot.py`** (`--export` / `--restore`). Senza GPU l'indice non
   è ricostruibile in tempi ragionevoli, quindi lo snapshot non è una comodità
   ma l'unico canale di distribuzione. Oggi si farebbe a mano via API Qdrant.
2. **`data/README.md`** con licenza e attribuzione per dataset — già richiesto
   da STACK.md e oggi mancante. È il **prerequisito legale** per distribuire
   qualunque indice. Entrambi i dataset lo permettono: `vectara/open_ragbench`
   Apache 2.0, `artefactory/ledger-long-context-KPI-QA` CC-BY-4.0. Il divieto di
   ROADMAP §14 (*"niente snapshot Qdrant con il testo nel payload"*) riguarda i
   **corpus con licenza restrittiva**, non questi.
3. **U-08**, profilo `demo` con indice committato. A 11.8 KB/punto, un indice
   sotto i 20 MB significa ~1.700 chunk, cioè 40-60 documenti open_ragbench —
   committabile senza problemi. Oggi `data/demo/` contiene solo `.gitkeep`.

---

## Prefill e decode, e le due manopole di Ollama (2026-08-22)

**Perché è stato misurato.** Prima di valutare uno spostamento su Linux/ROCm per
far correre le run che restano (D-3, il punto 12B dell'affermazione 3) serviva
sapere *dove* va il tempo di una risposta. Se va nel decode, è banda di memoria e
non la sposta nessun backend; se va nel prefill, è calcolo e un backend migliore
si vede. La sonda è `scripts/probe_prefill.py`.

**Condizioni:** `gemma4:latest` Q4_K_M, `num_ctx` 32768, `think: false`,
temperatura 0. Cinque domande vere di `ledger`, ricostruite dai dump di
generazione con lo stesso `build_user_message` della pipeline — prompt mediano
**8.208 token**, cioè un contesto da cinque chunk come in valutazione. La prima
chiamata è di riscaldamento e non si conta. Mediane.

| condizione | prefill | decode | totale | quota prefill |
|---|---|---|---|---|
| flash attention **off**, `num_parallel` default | 835 tok/s | 72,3 tok/s | 12,73 s | 77% |
| flash attention **off**, `num_parallel` 1 | **916 tok/s** | **77,8 tok/s** | 13,24 s | 67% |
| flash attention **on**, `num_parallel` 1 | **34–48 tok/s** | — | ~293 s | — |

### Il prefill è tre quarti del costo

È la premessa che serviva, ed è più netta di quanto la nota di portabilità
stimasse: il decode sta a **72–78 tok/s** con varianza quasi nulla su tutte e
cinque le domande — è il tetto di banda della 6750 XT, e nessun backend lo
regala. Il prefill invece scala col prompt (da 5.015 token: 6,4 s; da 10.052:
10,5 s) ed è la voce su cui un backend diverso può fare la differenza.

Restano **~2 s non contabilizzati** per risposta (13,24 totali contro 9,7 di
prefill+decode): tokenizzazione, HTTP, scheduling. Non li sposta nessun backend,
e vanno tolti da qualunque stima di guadagno — sono il pavimento.

### `OLLAMA_FLASH_ATTENTION` su Vulkan: **da tenere spenta**

Era indicata come «leva gratuita da provare». Non lo è: accesa, il prompt
processing va **da 916 a 34–48 tok/s**, e una domanda da 10k token passa da
10,5 s a **293,5 s**. Ventitré volte più lenta.

E non è un fattore costante, è una curva che peggiora: 240 tok/s a 1.536 token,
121 a 2.560, 62 a 5.120, 34 a 10.048. Il costo per token cresce con la
posizione, che è il profilo di un'attenzione quadratica senza kernel dedicato —
cioè il percorso flash del backend Vulkan che ripiega su qualcosa di ingenuo.
Su un prompt corto non si nota; su uno da cinque chunk è tutto il tempo speso.

**Questo rende il confronto con ROCm più interessante, non meno**: la stessa
manopola su un percorso HIP è la strada battuta, mentre qui è la strada rotta.
Ma resta da misurare, non da dedurre.

### `OLLAMA_NUM_PARALLEL=1`: piccolo guadagno, nessun costo qui

+10% di prefill e +8% di decode, perché il contesto allocato è
`num_ctx × num_parallel` e con una sola sessione il KV cache smette di
riservare spazio per sessioni che non esistono. **Non costa niente a questo
progetto**: la valutazione è sequenziale per costruzione, e la schermata di
confronto genera **una** risposta sola — l'altra è quella già data, riletta
(`chat.tsx`, `confronta`). Non c'è nessun punto in cui il repo chieda due
generazioni insieme.

### `num_batch`: il default di Ollama vince già

Il log del prefill avanza a blocchi da 512 token, e alzare la dimensione del
blocco è la leva classica per saturare una GPU. Qui non paga: **non c'è niente
da saturare che non sia già saturo.**

| `num_batch` | prefill | decode |
|---|---|---|
| default (512) | **916 tok/s** | **77,8 tok/s** |
| 1024 | 871 tok/s | 73,6 tok/s |
| 2048 | 877 tok/s | 70,6 tok/s |

1024 e 2048 sono indistinguibili fra loro e tutti e due **peggiori** del
predefinito di circa il 5%. La lettura è che il collo di bottiglia non è il
numero di token per blocco, e che blocchi più grandi si pagano solo in memoria
di lavoro. Si lascia stare: `probe_prefill.py` passa `num_batch` **solo** se lo
si chiede sulla riga di comando, così il default resta quello che Ollama decide
e non un valore nostro che invecchia.

> **Il 5% è vicino al rumore di questa sonda**, che è cinque domande e una
> mediana. Basta a dire «non guadagna», non basterebbe a dire «peggiora»: per
> quello servirebbero più ripetizioni, e non ne vale la pena per una manopola
> che si sta per lasciare al suo posto. Il 23× della flash attention, invece, non
> ha questo problema.

**Con questo le leve gratuite su Windows sono finite.** Flash attention spenta,
`num_parallel` a 1, `num_batch` al default: una risposta su cinque chunk costa
~13 s, di cui ~9 di prefill. Quel che resta da provare non è una manopola, è un
backend — ed è lavoro di U-12/D-10, non di oggi.

### Due avvertenze per chi legge questi numeri

**La configurazione del motore cambia il testo generato, a temperatura 0.** Fra
le due righe con flash attention spenta la stessa domanda (`SHW_dividends_paid_2017`)
ha prodotto 22 token in un caso e 29 nell'altro: batching e layout del KV cache
spostano l'aritmetica quel tanto che basta. Ne segue che **cambiare backend non
è gratis per le misure**: i numeri di citazione dell'affermazione 1 sono stati
presi su Vulkan, e rifarne una parte altrove sarebbe misurare due cose insieme
(§15). `EvalRun` per giunta non ha un campo per il motore — registra `model`,
`quantization`, `context_window`, `temperature` — quindi due run fatte su
backend diversi sono oggi **indistinguibili nell'artefatto**.

**Una misura del genere si lascia confondere in silenzio.** Il primo tentativo
di questa tabella ha prodotto 365 tok/s di prefill e 10,5 di decode, che
sembravano un numero e invece erano un guasto: tre runner `llama-server` orfani,
rimasti da altrettanti riavvii di Ollama, tenevano ~6 GB di VRAM, e il modello
era entrato per **31 strati su 43** — il resto sulla CPU. La risposta arriva lo
stesso, solo lenta. Per questo `probe_prefill.py` ora confronta `size` e
`size_vram` di `/api/ps` dopo il riscaldamento e **si ferma** se il modello non è
tutto in VRAM.

> **I numeri di T-02 in cima a questa pagina non sono confrontabili con questi**,
> e la differenza non va letta come un miglioramento: là il prompt era corto e il
> *thinking* acceso, qui il prompt è quello vero della pipeline e `think` è
> spento, con una versione di Ollama più recente. Quale dei tre pesi di più non è
> stato misurato, e finché non lo è non si dice.
