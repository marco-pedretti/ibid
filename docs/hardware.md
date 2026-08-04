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

## Note operative

- La colonna **VRAM** viene da `ollama ps` subito dopo la generazione con 32k context e prompt breve (~40 token); il KV cache occupa quota minima in questo caso.
- Il 12B a 2.4 tok/s è lento per uso interattivo (~50s per 120 token) ma accettabile per run di valutazione automatizzata notturna.
- Per verificare il backend GPU effettivo usato da Ollama: `%LOCALAPPDATA%\Ollama\logs\server.log`.
- I dati grezzi JSON sono in `eval/contamination/smoke_20260804_103814.json`.
