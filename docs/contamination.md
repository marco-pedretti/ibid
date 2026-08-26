# Verifica di contaminazione: T-03

**Data:** 2026-08-04  
**Modelli testati:** Gemma 4 E4B (`gemma4:latest`, 8.0B Q4_K_M), Gemma 4 12B (`gemma4:12b`, 11.9B Q4_K_M)  
**Parametri:** temperatura 0, think: false, num_ctx 4096  
**Dati grezzi:** `eval/contamination/contamination_open_ragbench_20260804_112523.json`

---

## Dataset principale: `vectara/open_ragbench`

### Struttura del dataset

- 3045 query da paper arXiv pubblicati tra gen-2024 e dic-2024
- Ogni query è legata a un documento specifico (`doc_id`) e a una sezione (`section_id`)
- Tipi: extractive e abstractive; sorgenti: text, text-image, text-table, text-table-image
- Include: `queries.json`, `answers.json`, `qrels.json`, `corpus/<arxiv_id>.json`
- **Cutoff Gemma 4:** gennaio 2025: tutti i paper del dataset sono nel finestra di addestramento

### Campione testato

16 query da 16 paper diversi + 2 controlli positivi = 18 domande totali.  
Distribuzione: 6 text, 5 text-image, 3 text-table, 2 text-table-image.

### Controlli positivi

| Domanda | E4B | 12B | Esito |
|---|---|---|---|
| Cosa significa RAG? | ✅ Retrieval-Augmented Generation | ✅ Retrieval-Augmented Generation | Modelli funzionanti |
| Capitale della Francia? | ✅ Paris | ✅ Paris | Modelli funzionanti |

### Analisi manuale dei casi (revisione del JSON completo)

| # | Query (sorgente) | Expected | E4B | 12B | Verdetto |
|---|---|---|---|---|---|
| 1 | Uniformly sharp → achievability? (text) | Yes | ❌ "non implica necessariamente" | ✅ "Yes" con spiegazione matematica | **Conoscenza generale**: Il 12B deriva la risposta da ragionamento matematico (proprietà uniforme → proprietà locale), non da training sul paper specifico |
| 2 | Imprecision noise ↓ con optical power↑? (text) | Yes | "I don't know" | ❌ "No" (sbaglia la fisica) | **Non contaminato**: 12B risponde dalla fisica generale ma sbaglia |
| 3 | CT vs CXR differenze per lesion type? (text) | Yes, p<0.001 | "I don't know" | ✅ "Yes" con spiegazione generica | **Conoscenza medica generale**: il 12B sa che CT supera CXR, ma non cita p<0.001 né il dataset specifico |
| 4 | Skills in VR projects? (text) | comunicazione, time mgt, creatività | Liste generiche | Liste generiche | **Non contaminato**: domanda troppo generica, entrambi rispondono da conoscenza generale |
| 5 | Manager threshold test ottimale se Pr[λ≥λ*]>0? (text) | Yes | "I don't know" | Risposta sfumata, non conclude "yes" | **Non contaminato** |
| 6 | Dual accuracy efficace per LMMs? (text) | "senza compromettere applicabilità reale" | Risposta generica su multi-dimensionalità | Risposta generica su allineamento visivo | **Non contaminato**: nessuno riproduce la motivazione specifica del paper |
| 7 | Price discrimination benefit sellers? (text-image) | cattura consumer surplus | ✅ risposta corretta | ✅ risposta corretta | **Conoscenza economica generale**: microeconomia standard, nessuna contaminazione specifica |
| 8 | Multi-domain model underperform? (text-image) | negative transfer | ✅ "negative transfer" tra le cause | ✅ "negative transfer" esplicito | **Conoscenza ML generale**: negative transfer è un concetto noto in letteratura, non specifico del paper |
| 9 | LLM loan approval frequencies? (text-image) | frequenze variano per modello | "I don't know" | "No benchmark standardizzato" | **Non contaminato** ✅ |
| 10 | Chialvo neuron model randomness? (text-image) | Gaussian noise, parametri corrente ionica | "I don't know" | "stochastic term, Gaussian distribution" | **Parzialmente ambiguo**: Il 12B conosce il Chialvo model come modello stochastico ma non menziona i parametri di corrente ionica specifici del paper |
| 11 | 2D scaling plot financial? (text-image) | clusters basati su differenze settoriali | Risposta generica DR | Risposta generica scatter plot | **Non contaminato**: nessuno cita "differenze settoriali", rispondono da data science generica |
| 12 | SD di RMSE per Ridge Regression? (text-table) | **0.0226** | "I don't know" | "Nessun valore standard" | **Non contaminato** ✅: valore numerico specifico sconosciuto a entrambi |
| 13 | One-inflation in hospital discharge? (text-table) | dimissioni al 1° giorno, bias ZTNB | Definizione errata | Confonde con zero-inflation | **Non contaminato** ✅: nessuno conosce la definizione specifica del paper |
| 14 | Costo 6000 GPT summaries? (text-table) | **$2.5** | "Non conosco il costo specifico" | "Impossibile determinare senza info" | **Non contaminato** ✅: valore numerico specifico sconosciuto |
| 15 | GCL gestisce queue gates? (text-table-image) | Yes | "I don't know" | ❌ "No" (confonde con security ACL) | **Non contaminato** ✅: 12B risponde dalla rete generica e sbaglia |
| 16 | Tecniche per parasitic capacitance? (text-table-image) | PCB layout optimization, 8 pF → 3 pF | Tecniche generali PCB | Tecniche generali PCB | **Conoscenza tecnica generale**: nessuno cita i valori specifici 8 pF → 3 pF |

### Verdetto su `vectara/open_ragbench`

**✅ DATASET APPROVATO: nessuna contaminazione significativa.**

Sintesi per modello:
- **E4B:** nessun caso di contaminazione. Risponde correttamente solo a domande di conoscenza generale (economia, ML). Per le domande specifiche del paper dice "I don't know" o sbaglia.
- **12B:** in 4 casi risponde correttamente (Q1, Q3, Q7, Q8) ma in tutti e 4 la risposta è derivabile da conoscenza disciplinare generale (matematica, medicina, economia, ML), non da training specifico sul paper. Nessun caso in cui riproduce dettagli numerici o claims specifici del documento.

**Dettaglio critico:** le tre domande con risposta numerica specifica (0.0226, $2.5, Pr[λ≥λ*]) e quella con valore tecnico specifico (8 pF → 3 pF) sono sconosciute a entrambi i modelli. Questo è il test più robusto: se il modello non conosce i numeri, non ha visto il documento.

---

## Secondo dataset (genere visuale/tabellare)

La selezione del secondo dataset è rinviata a **I-01** (profilatore documenti, Fase 1).  
Candidato preferenziale: ViDoRe v2 o equivalente (confrontare disponibilità e licenza in I-01).  
Il test di contaminazione per il secondo dataset verrà eseguito con lo stesso schema prima dell'ingestione.

---

## Gate T-03

- [x] Contaminazione verificata sul dataset principale con 16 domande + 2 controlli positivi
- [x] Risultati documentati (JSON grezzo + analisi manuale)
- [x] **Decisione presa:** `vectara/open_ragbench` è il dataset principale
- [ ] Verifica citazione risolvibile a chunk reale → completata in T-05 (richiede pipeline di retrieval)
