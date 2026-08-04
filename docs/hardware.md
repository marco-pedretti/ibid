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
