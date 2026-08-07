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

> Questo esito era previsto come rischio in `ROADMAP.md §14`: "26B inutilizzabile sulla GPU → si scala a 12B, la curva regge."

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
   ROADMAP §11 (*"niente snapshot Qdrant con il testo nel payload"*) riguarda i
   **corpus con licenza restrittiva**, non questi.
3. **U-08**, profilo `demo` con indice committato. A 11.8 KB/punto, un indice
   sotto i 20 MB significa ~1.700 chunk, cioè 40-60 documenti open_ragbench —
   committabile senza problemi. Oggi `data/demo/` contiene solo `.gitkeep`.
