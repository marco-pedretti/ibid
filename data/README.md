# data/

Gitignored tranne il mini-dataset demo in `data/demo/`.

**La licenza MIT del progetto non copre i dati** (STACK.md §Licenze). Il codice si ridistribuisce sotto MIT; i corpus no, e ognuno porta i suoi obblighi. Questo file è dove vivono, ed è il posto da aggiornare quando si aggiunge un dataset.

## I dataset usati

| dataset | repo HuggingFace | licenza | obbligo nel ridistribuire |
|---|---|---|---|
| `open_ragbench` | [`vectara/open_ragbench`](https://huggingface.co/datasets/vectara/open_ragbench) | Apache 2.0 | copia della licenza + NOTICE |
| `ledger` | [`artefactory/ledger-long-context-KPI-QA`](https://huggingface.co/datasets/artefactory/ledger-long-context-KPI-QA) | CC-BY-4.0 | attribuzione all'autore, indicazione della licenza, nota delle modifiche |

**Entrambi permettono la ridistribuzione.** È la ragione per cui `data/demo/` può esistere: senza quel via libera, l'unica strada per chi arriva da GitHub sarebbe rigenerare i vettori a proprie spese, cioè due ore di GPU prima di vedere qualcosa.

## Ridistribuire un indice non è ridistribuire dei vettori

Un indice contiene **il testo dei chunk** nel payload, non solo gli embedding. Non è un artefatto derivato opaco: è il corpus, riorganizzato e ricercabile. Va quindi trattato come i dati che è, e `data/demo/` (1.758 chunk dei due corpus) è esattamente questo caso.

Da qui due regole operative:

1. **L'attribuzione viaggia con l'artefatto, non solo col repository.** Finché l'artefatto è il repository, questo file la porta. Se un giorno un indice uscisse di qui dentro un archivio, l'attribuzione dovrebbe entrarci dentro: chi scarica un file può non aver mai aperto questa pagina. **Oggi non succede**: la via dello snapshot pubblicato su Release è stata tolta il 2026-08-27, rivedendo U-08.

2. **CC-BY-4.0 chiede di segnalare le modifiche**, e noi ne facciamo: il corpus viene spezzato in chunk, arricchito con `doc_genre` e `pipeline`, e in una variante re-indicizzato con una segmentazione diversa (`_routed`). Va detto («derivato da …, suddiviso in chunk e indicizzato»), non lasciato dedurre.

## Cosa è ridistribuibile, e cosa conviene

- **`open_ragbench` e `ledger`**: sì, e in `data/demo/` ne sta un ritaglio di 1.758 chunk, che è ciò che U-08 consegna. Gli indici interi restano fuori: chi li vuole ingerisce.
- **Le varianti `_routed`**: tecnicamente sì, ma sono 2,1 GB e servono all'ablation R-07, cioè a chi riproduce le misure, e chi riproduce ingerisce da sé.
- **Il golden set** (`eval/golden/`): sono query e qrels derivati dagli stessi corpus, quindi seguono le stesse licenze.
- **I risultati** (`eval/results/`): sono nostre misure, non dati altrui. Vanno con il codice.

## Il legame che un indice non può perdere

Un indice è legato al **modello di embedding** che lo ha prodotto: interrogarlo con un altro restituisce risultati plausibili e privi di senso, senza nessun errore (è la stessa ragione per cui `RequestConfig` non contiene `embedding_model`: vedi `src/config.py`). Quindi ogni indice che esce da qui porta con sé, scritto:

- il **commit** da cui è stato generato;
- il **modello di embedding** e la sua dimensione (oggi `intfloat/multilingual-e5-large`, 1024);
- il **numero di punti** atteso per collection, così che un caricamento incompleto si veda subito.

Per `data/demo/` è il file `manifest.json`, scritto da `scripts/build_demo_index.py` e ricaricato su Qdrant come cartellino: da lì `/datasets` sa dire che quell'indice è ridotto, e l'interfaccia lo scrive.
