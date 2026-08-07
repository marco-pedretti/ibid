# Run archiviati (2026-08-07)

Questi 16 `EvalRun` sono stati prodotti prima della correzione della profondità di
retrieval. Sono archiviati, non cancellati: le conclusioni in `docs/progress.md`
li citano, e una parte delle loro metriche è tuttora corretta.

Il caricatore della dashboard legge solo `eval/results/*.json`, non questa
sottocartella — quindi il comparator non mescola più numeri validi e invalidi.

## Il difetto

Il retrieval recuperava `top_k` chunk (5 in tutti questi run), ma
`DEFAULT_MEASURES` chiede metriche `@10`. Le metriche `@10` sono quindi state
calcolate su una lista di 5 documenti: non possono vedere le posizioni 6–10.

Misurato su open_ragbench, 100 query, dense:

| `top_k` | R@5 | R@10 | nDCG@10 | RR@10 | Success@1 |
|---|---|---|---|---|---|
| 5 (come questi run) | 0.7800 | 0.7800 | 0.6744 | 0.6390 | 0.5500 |
| 10 | 0.7800 | **0.8600** | **0.7004** | **0.6499** | 0.5500 |
| 20 | 0.7800 | 0.8600 | 0.7004 | 0.6499 | 0.5500 |

In tutti e 16 i file `R@10 == R@5` esattamente — non è una proprietà dei dati.

## Cosa resta valido qui dentro

| metrica | stato | perché |
|---|---|---|
| `R@5` | ✅ valida | bastano 5 risultati, identica a ogni profondità |
| `Success@1` | ✅ valida | idem |
| `R@10` | ❌ sottostimata | non può vedere oltre la 5ª posizione |
| `nDCG@10` | ❌ sottostimata | idem |
| `RR@10` | ❌ sottostimata | idem |
| `doc_R@5` | ❌ **sottostimata** | vedi sotto |
| `doc_R@10` | ❌ priva di significato | identica per costruzione a `doc_R@5` |

### Perché anche `doc_R@5` è sottostimata

Questa era stata inizialmente classificata come valida, per errore. `doc_R@5` è
Recall@5 sui **documenti**, ma i documenti si ottengono aggregando i chunk
recuperati: se i 5 chunk provengono da 3 documenti soli, la lista di documenti
candidati ne contiene 3, non 5. Recuperare più in profondità produce più
documenti distinti e quindi una lista top-5 più piena.

Misurato sulle stesse 200 query, `doc_R@5` a profondità 5 contro 10:

| collection | profondità 5 | profondità 10 | delta |
|---|---|---|---|
| `ledger` | 0.8383 | 0.9367 | **+0.098** |
| `ledger_routed` | 0.7517 | 0.8225 | **+0.071** |
| `open_ragbench` | 0.9600 | 0.9650 | +0.005 |
| `open_ragbench_routed` | 0.9900 | 0.9900 | 0.000 |

L'effetto è grande su LEDGER e trascurabile su open_ragbench, come atteso: i
chunk LEDGER sono pagine intere, quindi più chunk recuperati cadono nello stesso
documento; quelli ORB sono sezioni sparse su documenti diversi.

### Conseguenze sulle conclusioni già scritte in `progress.md`

- **R-07** (+4% ORB / −20% LEDGER) — **numeri da sostituire**. La direzione
  regge (ORB su, LEDGER giù) ed è stabile su tutte le varianti provate, ma
  entrambe le magnitudini erano gonfiate. Valori corretti in `progress.md`.
- **R-05** (chunk R@5 0.80 vs doc R@5 0.96) — il confronto **regge come
  direzione** (doc-recall ≫ chunk-recall), la magnitudine no: `doc_R@5` era
  sottostimata, quindi il divario reale è più ampio, non più stretto.
- **R-03** (query rewrite, −10.4% su nDCG@10) — direzione plausibile,
  **magnitudine inaffidabile**
- **R-04** (filtri metadata) — la parte `R@5 −5.0%` regge, la parte
  `nDCG@10 −4.1%` no

## Secondo limite: non si sa su quante query girarono

Nessuno di questi file registra `limit`. Diversi provengono da smoke test
(`--limit 50`), inclusi i quattro di R-07, ma il file non lo dice e il
`config_hash` non lo distingue. I run successivi alla correzione registrano
`n_queries`.

## Non rieseguire da qui

I run corretti vanno in `eval/results/`. Questa cartella è sola lettura, per
riferimento storico.
