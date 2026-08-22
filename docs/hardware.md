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

## Dove va il tempo di una risposta (2026-08-22)

**Perché è stato misurato.** Prima di valutare uno spostamento su Linux/ROCm per
far correre le run che restano serviva sapere *dove* va il tempo. Se va nel
decode è banda di memoria e non la sposta nessun backend; se va nel prefill è
calcolo, e un backend migliore si vede. La sonda è `scripts/probe_prefill.py`.

**Condizioni:** `gemma4:latest` Q4_K_M, `num_ctx` 32768, `think: false`,
temperatura 0, `OLLAMA_NUM_PARALLEL=1`. Cinque domande vere di `ledger`
ricostruite dai dump con lo stesso `build_user_message` della pipeline — prompt
mediano **8.208 token**, cioè cinque chunk come in valutazione. Prima chiamata di
riscaldamento, scartata. Mediane. Ogni condizione parte da un Ollama riavviato
con **zero runner orfani** e il modello a 43/43 strati: sotto si spiega perché
quella riga del protocollo vale quanto la misura.

### La risposta è per due terzi prefill, e per un terzo nemmeno GPU

| voce | tempo | quota |
|---|---|---|
| prefill (8.208 token) | **8,2 s** | ~63% |
| decode (~40 token) | **0,7 s** | ~5% |
| resto del motore | ~2,1 s | ~16% |
| fuori dal motore (HTTP, JSON, coda) | ~2,1 s | ~16% |
| **totale a orologio** | **~13,0 s** | |

Il decode è inchiodato a **72–78 tok/s** in ogni condizione provata, con varianza
quasi nulla fra le domande: è il tetto di banda della 6750 XT, e non lo regala
nessun backend. Il prefill scala col prompt (5.015 token: 6,3 s; 10.052: 9,2 s)
ed è l'unica voce su cui un backend diverso possa fare qualcosa.

**Un terzo del tempo non è calcolo GPU.** `total_duration` di Ollama non copre
tutto, e quel che resta fuori — più i ~2 s che il motore spende in tokenizzazione
e contabilità — fa ~4 s su 13. Nessun backend li tocca. È il pavimento di
qualunque stima di guadagno, e va sottratto prima di moltiplicare.

### Le manopole: muovono il motore, non l'orologio

| condizione | prefill | decode | totale a orologio |
|---|---|---|---|
| flash attention **on**, `num_batch` default | 835 / 836 tok/s | 72,3 / 72,7 | 12,73 / 12,72 s |
| flash attention **off**, `num_batch` default | 916 / 920 tok/s | 77,8 / 77,9 | 13,24 / 13,18 s |
| flash attention off, `num_batch` **1024** | **1064 / 1050 tok/s** | 77,3 | 13,01 / 13,02 s |
| flash attention off, `num_batch` 2048 | 937 tok/s | 74,7 | 13,13 s |

Due colonne per condizione dove ci sono due ripetizioni: servono a dire che il
ritmo del motore è **riproducibile a tre cifre** (835,0 e 835,9; 916,3 e 920,1),
quindi le differenze fra le righe sono reali e non rumore.

**E nonostante questo il totale a orologio non si muove**: 12,7–13,2 s in tutte e
quattro le condizioni, mentre il ritmo di prefill fra la peggiore e la migliore
cambia del **27%**. I ~4 s di fuori-motore assorbono il guadagno.

Ne segue la sola raccomandazione che questi numeri sostengono: **nessuna di
queste manopole vale un cambio di configurazione.** `num_batch` a 1024 è la
migliore per ritmo di prefill ed è quella da provare per prima se un giorno il
fuori-motore verrà ridotto; oggi non cambia la durata di una run.

### Cosa è stato misurato e cosa no

`OLLAMA_NUM_PARALLEL` **non è stato misurato.** Era già a 1 prima della prima
misura della giornata, quindi tutte le righe qui sopra la condividono e nessuna
la isola. Resta plausibile che conti — il contesto allocato è
`num_ctx × num_parallel`, e con quattro sessioni il KV cache quadruplica su una
scheda da 12 GB — ma plausibile non è misurato, e in questa pagina la differenza
è tutta.

Non costa comunque niente tenerla a 1: la valutazione è sequenziale per
costruzione, e la schermata di confronto genera **una** risposta sola — l'altra è
quella già data, riletta (`chat.tsx`, `confronta`). Nessun punto del repo chiede
due generazioni insieme.

### Il confonditore, che ha falsificato due letture su quattro

Le prime versioni di questa pagina davano la flash attention accesa a **34–48
tok/s** contro 916 spenta, cioè un fattore 23, e la conclusione era «tenerla
spenta». **Era falso.** Accesa fa 835 tok/s, il 10% meno che spenta, e la misura
si riproduce a tre cifre.

La causa dei 34–48 erano **runner `llama-server` orfani**: fermando `ollama.exe`
per riavviarlo col nuovo ambiente, il processo figlio sopravvive e continua a
tenere la sua VRAM. Con tre riavvii c'erano tre orfani e ~6 GB occupati. Il
sintomo non è un errore: la risposta arriva lo stesso, solo lenta.

**Ed è un confonditore che si presenta in due forme diverse**, il che è la
ragione per cui è riuscito a passare due volte:

1. **Il modello entra a metà.** 31 strati su 43, il resto sulla CPU: 365 tok/s di
   prefill e 10,5 di decode. Questa la sonda ora la **ferma**, confrontando
   `size` e `size_vram` di `/api/ps` dopo il riscaldamento.
2. **Il modello entra tutto e va lo stesso piano.** 43 strati su 43, e 34–48
   tok/s con un ritmo che **peggiora col crescere del contesto** — 240 tok/s a
   1.536 token, 121 a 2.560, 62 a 5.120, 34 a 10.048. È il profilo di un KV cache
   che non sta dove dovrebbe. **Questa la sonda non la rileva**: dal suo punto di
   vista il modello è interamente in VRAM, ed è vero.

Contro la seconda non c'è un campo dell'API da leggere, quindi vale una riga di
protocollo invece di un controllo: **prima di ogni condizione, riavviare Ollama e
verificare che i runner siano zero.**

```powershell
Get-Process llama-server,ollama,"ollama app" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3
Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe"
Start-Sleep -Seconds 7
"orfani: $((Get-Process llama-server -ErrorAction SilentlyContinue | Measure-Object).Count)"
```

> **La lezione generale, che vale oltre questa pagina.** Le due letture false
> erano *plausibili*: un fattore 23 sulla flash attention ha una spiegazione
> pronta («il percorso Vulkan ripiega su un'attenzione ingenua»), e quella
> spiegazione è stata scritta prima di verificare che le due condizioni
> differissero solo per la manopola. La verifica che le ha smontate non è stata
> una misura in più ma la **rilettura dei log del motore**, che dicevano
> `flash_attn = enabled` anche nella riga chiamata «off». Quando una manopola dà
> un fattore 20, la prima ipotesi da scartare è che si stia misurando altro.

### Cosa questo dice su ROCm

Rafforza poco e indebolisce parecchio. Il prefill resta la voce grossa — ~63% —
e quella un backend la tocca. Ma il decode è al muro di banda, e i **~4 s di
fuori-motore su 13 non li tocca nessuno**: anche raddoppiando il ritmo di
prefill, una risposta passerebbe da 13,0 a ~8,9 s, cioè un guadagno del 32% e non
un dimezzamento. Sulle ~6 ore che restano fra D-3, D-4 e l'affermazione 3 fanno
meno di due ore, contro una giornata di sistema da mettere in piedi.

La misura vera ROCm-contro-Vulkan si fa in **U-12/D-10**, dove Linux va
affrontato comunque e nessuna misura è in ballo. La sonda ci gira sopra tale e
quale: `/api/ps` e `/api/chat` sono gli stessi su ogni sistema.

> **I numeri di T-02 in cima a questa pagina non sono confrontabili con questi**,
> e la differenza non va letta come un miglioramento: là il prompt era corto e il
> *thinking* acceso, qui il prompt è quello vero della pipeline e `think` è
> spento, con una versione di Ollama più recente. Quale dei tre pesi di più non è
> stato misurato, e finché non lo è non si dice.
