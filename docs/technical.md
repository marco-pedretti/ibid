# Documentazione tecnica

Questa pagina è per chi ha già deciso di provare il progetto. Il [README](../README.md)
serve a un lettore che ha tre minuti e vuole sapere se la cosa è seria; qui si dà
per scontato che quella domanda abbia avuto risposta, e si risponde all'altra:
**come si rifà una di quelle misure, e come si capisce se il numero ottenuto vuol
dire la stessa cosa del nostro.**

L'ordine è quello del lavoro reale: prima cosa serve, poi come si installa, poi
come si costruisce l'indice, poi la misura. Le sezioni di riferimento
(metriche, contratti, architettura) vengono dopo, perché si consultano invece di
leggersi.

**Nessun passo di questa pagina chiede di aprire il codice.** Dove un dettaglio
sta solo nel sorgente, il file è citato per farlo trovare, non perché sia
necessario leggerlo.

## Indice

1. [Cosa serve, e per fare cosa](#1-cosa-serve-e-per-fare-cosa)
2. [Installazione](#2-installazione)
3. [Le variabili d'ambiente](#3-le-variabili-dambiente)
4. [I corpus, l'indice e il golden set](#4-i-corpus-lindice-e-il-golden-set)
5. [Riprodurre una misura](#5-riprodurre-una-misura)
6. [Le metriche](#6-le-metriche)
7. [I contratti dati](#7-i-contratti-dati)
8. [L'architettura](#8-larchitettura)
9. [Estendere il progetto](#9-estendere-il-progetto)
10. [Guasti comuni](#10-guasti-comuni)
11. [Cosa non c'è in questa pagina](#11-cosa-non-cè-in-questa-pagina)

---

## 1. Cosa serve, e per fare cosa

Non tutto il progetto chiede la stessa macchina. La GPU serve a due cose sole
(costruire l'indice e generare risposte), e nessuna delle due è necessaria per
rifare una misura di recupero.

| voglio | mi serve | non mi serve |
|---|---|---|
| **vederlo funzionare** | Docker | Python, GPU, corpus: l'indice ridotto è nel repo (§2.0) |
| rileggere i risultati già misurati | Python e il repo | nient'altro: sono JSON in `eval/results/`, committati |
| **rifare un confronto appaiato fra due run** | Python e il repo | nient'altro: anche i risultati per query sono committati (§5.7) |
| **rifare una misura di recupero** | Qdrant con l'indice costruito | GPU, endpoint LLM |
| **rifare la precisione di citazione** | Qdrant, il verificatore NLI (~1 GB di pesi) | endpoint LLM: si rimisura sulle generazioni già salvate |
| generare risposte nuove (formato, astensione, curva delle taglie) | endpoint OpenAI-compatibile con GPU | n/d |
| costruire l'indice da zero | GPU consigliata: 2 ore contro 8 | n/d |
| l'interfaccia web | Node 20+ e il backend acceso | n/d |

### Il software

| | versione | nota |
|---|---|---|
| Python | ≥ 3.12 (sviluppato su 3.14) | dichiarato in `pyproject.toml` |
| Docker | qualunque recente | serve solo per Qdrant e, se lo si vuole, per il backend |
| Node | 20+ | solo per `ui/` |
| endpoint LLM | [Ollama](https://ollama.com) o `llama-server` di llama.cpp | qualunque cosa parli il protocollo OpenAI su `/v1` |

### Lo spazio su disco

| cosa | quanto |
|---|---|
| corpus scaricati in `data/` | 2,3 GB (714 MB `open_ragbench`, 1,6 GB `ledger`) |
| volume Qdrant con le quattro collection | 4,97 GB |
| ... con le sole due che servono a chi non riproduce l'ablation R-07 | ~780 MB |
| pesi dei modelli ONNX (embedder, reranker, verificatore) | ~2,5 GB |

### La GPU, e cosa cambia senza

Misurato il 2026-08-07 su `intfloat/multilingual-e5-large`, forzando
`CPUExecutionProvider` (dettaglio in [`hardware.md`](hardware.md)):

| operazione | con GPU (DirectML) | solo CPU |
|---|---|---|
| embedding delle **query** (testi corti) | veloce | **35,9 embed/s**: nessun problema |
| embedding dei **chunk** (mediana 3.182 caratteri) | ~10 embed/s | **2,38 embed/s** |
| ingestione dei due corpus (65.950 chunk) | **122 minuti** | ~7,7 ore |
| embedding delle query di una valutazione completa | vedi §5.2 | ~85 s per `open_ragbench`, ~4,6 min per `ledger` |

**Le valutazioni di recupero si eseguono su CPU senza compromessi**: le query
sono corte, e l'unica cosa che il denso deve calcolare è il loro vettore. La
generazione invece una GPU la vuole, ed è esattamente il motivo per cui esiste
`LLM_BASE_URL`: il modello può stare su un'altra macchina.

---

## 2. Installazione

Quattro passi con il loro controllo, più uno facoltativo. Se un controllo non dà
quello che c'è scritto, fermarsi lì: i passi dopo non lo aggiustano.

Prima però conviene sapere che **per guardare non serve installare niente**.

### 2.0 La via breve, se si vuole solo vedere

```bash
git clone <url> ibid && cd ibid
docker compose --profile demo up          # oppure: make demo
```

`http://localhost:8000`, e serve solo Docker. Misurato con l'immagine già
costruita e il volume azzerato: **17,9 secondi** dal comando alla pagina che
risponde, di cui 3,7 per caricare l'indice. La prima volta l'immagine si
costruisce (~45 s con la cache dei layer calda, qualche minuto senza).

Dentro c'è un **indice ridotto committato nel repository**, `data/demo/`: 1.758
chunk (658 di `open_ragbench`, 1.100 di `ledger`) ritagliati dai due corpus
veri. I vettori sono **quelli originali, letti dall'indice completo e non
ricalcolati**: un ritaglio riembeddato darebbe punteggi *simili*, e simile non
basta, perché il margine con cui il terzo esempio di `ledger` chiude il gate di
astensione è +0,0078, meno di quanto una versione diversa di `onnxruntime`
sposti uno score.

**Non riproduce nessuna misura, e lo dichiara mentre gira.** Con 658 punti
invece di 18.840 il recupero ha meno concorrenti, quindi trova più facilmente; e
il BM25 sparso cambia proprio i pesi, perché l'IDF lo calcola Qdrant sulle
statistiche della collection. Il caricamento lascia su Qdrant una collection
`ibid_demo` con dentro il manifesto (commit di provenienza, modello di
embedding, conteggi), `/datasets` la legge e riporta `ridotto: true`, e
l'interfaccia scrive *«Indice ridotto: questa demo cerca in 658 chunk, non nel
corpus intero»*.

Due cose che questo profilo **non** fa, e sono deliberate:

- **non tocca l'indice completo.** Ha un Qdrant suo con un volume suo
  (`qdrant_demo_data`), e il caricamento si rifiuta comunque di scrivere su una
  collection che non porta il cartellino `ibid_demo`. Per la stessa ragione usa
  `DEMO_QDRANT_URL` e non `QDRANT_URL`: chi sviluppa ha la seconda esportata
  verso il proprio indice.
- **non pubblica la porta del suo Qdrant.** Nessuno ci parla da fuori, e
  pubblicarla la farebbe scontrare con il Qdrant di sviluppo sulla 6333.

Per generare le risposte serve comunque un endpoint LLM (§2.3): senza, si
sfoglia il corpus e il recupero risponde, cade solo la generazione.

Il ritaglio si rifà con `make demo-index`, ma **solo da una macchina che ha
l'indice completo**: legge da Qdrant, riscrive `data/demo/` e rilancia
`verify_esempi.py`. Il risultato si committa.

### 2.1 Il codice e le dipendenze

```bash
git clone <url> ibid && cd ibid
python -m venv .venv
.venv\Scripts\activate           # Windows
source .venv/bin/activate        # Linux, macOS

pip install -e ".[gpu-directml]" # Windows con GPU DirectX 12
pip install -e .                 # CPU, ovunque
```

> **Su Debian e Ubuntu il primo comando non funziona**, e il messaggio d'errore
> non è quello che ci si aspetta. Provato su una Ubuntu 26.04 appena installata:
> `python3 -m venv` fallisce perché `ensurepip` non c'è, `python3 -m pip` non
> esiste affatto, e `/usr/lib/python3.14/EXTERNALLY-MANAGED` vieta comunque di
> installare nel Python di sistema (PEP 668). Serve una riga prima:
>
> ```bash
> sudo apt install python3-venv     # oppure python3.14-venv, per la versione esatta
> ```
>
> Su Arch, Fedora e macOS `venv` arriva con Python e questo passo non serve. È
> l'unico punto della procedura che dipende dalla distribuzione.

Gli acceleratori ONNX sono **extra che si escludono a vicenda**: forniscono
tutti il modulo `onnxruntime`, e con due installati vince chi ha scritto i file
per ultimo. Le tre varianti sono `gpu-directml` (Windows, qualunque GPU
DirectX 12), `gpu-rocm` (Linux e AMD) e `gpu-cuda` (NVIDIA). Senza nessun extra,
`fastembed` tira comunque `onnxruntime` per CPU e tutto funziona, più
lentamente.

> **E `pip` ci arriva da solo, a due distribuzioni.** `fastembed` richiede
> `onnxruntime` (quello CPU) per ogni versione di Python, quindi
> `pip install -e ".[gpu-rocm]"` installa **anche** quello: ne escono
> `onnxruntime-rocm` e `onnxruntime` insieme, e a quel punto **vince quella
> CPU**, cioè l'acceleratore c'è e non si usa.
>
> **Togliere quella di troppo non basta**, ed è la parte che non si indovina.
> Le due distribuzioni scrivono la *stessa* cartella `onnxruntime/`: la seconda
> arrivata sovrascrive i file e ne diventa la proprietaria, quindi
> `pip uninstall -y onnxruntime` **se li porta via tutti**. Resta una cartella
> vuota: `import onnxruntime` riesce, `__file__` è `None`, e la prima chiamata
> muore con `AttributeError: module 'onnxruntime' has no attribute
> 'get_available_providers'`. La distribuzione GPU, intanto, continua a
> risultare installata.
>
> Verificato riproducendo lo stato in un ambiente pulito. La sequenza che
> funziona è di tre passi, e l'ultimo è quello che manca a chi si ferma prima:
>
> ```bash
> pip install -e ".[gpu-rocm]"
> pip uninstall -y onnxruntime
> pip install --force-reinstall --no-deps onnxruntime-rocm   # riscrive i suoi file
> ```
>
> Lo stesso comando è anche la **riparazione** se ci si è già finiti dentro: non
> serve rifare l'ambiente. `scripts/verify_platform.py` riconosce quello stato e
> lo stampa invece di sollevare.

> **Su Arch conviene il pacchetto della distribuzione, non il wheel.** Il wheel
> di PyPI (`onnxruntime-rocm` 1.22.2) è compilato contro ROCm 6 e cerca
> `libamdhip64.so.6`, mentre Arch è a ROCm 7.2.4: `extra/python-onnxruntime-rocm`
> è alla **1.29.0**, costruito contro la ROCm del sistema, e dichiara di fornire
> `python-onnxruntime`. Il venv lo vede se lo si crea con
> `--system-site-packages`, e non serve nessun extra:
>
> ```bash
> sudo pacman -S python-onnxruntime-rocm
> python -m venv --system-site-packages .venv && source .venv/bin/activate
> pip install -e .                  # senza extra
> ```
>
> Il pacchetto registra `onnxruntime-1.29.0.dist-info`, quindi pip lo considera
> gia' soddisfatto e **non scarica quello di PyPI**: nessuna delle due
> distribuzioni di troppo, e niente da disinstallare.
>
> **Una cosa resta da verificare sulla macchina, non dalla documentazione**: la
> lista dei file di quel pacchetto contiene `libonnxruntime_providers_migraphx.so`
> e **non** `libonnxruntime_providers_rocm.so`. Puo' voler dire che il provider
> ROCm e' compilato dentro la libreria principale, oppure che quel build offre
> MIGraphX al suo posto. La risposta la da' `verify_platform.py --veloce` in due
> secondi, e nel secondo caso lo dice a chiare lettere: MIGraphX non e' in
> `PREFERRED_ACCELERATORS`, quindi verrebbe ignorato in silenzio.

Il controllo, che guarda **tre cose e non una**:

```bash
python scripts/verify_platform.py            # tutto
python scripts/verify_platform.py --veloce   # solo l'ambiente, nessun modello
```

Le tre cose sono diverse fra loro, ed è il motivo per cui il controllo esiste:
cosa la macchina **offre** (`onnxruntime.get_available_providers()`), cosa il
progetto **sceglie** (`src/providers.py`), e su cosa la sessione è **finita**
(`InferenceSession.get_providers()`). Solo la terza è una misura: onnxruntime
scarta in silenzio un provider che non riesce a inizializzare, quindi esiste uno
stato in cui le prime due dicono ROCm e la terza dice CPU. Lo script esce con 1
in quel caso, e anche quando trova due distribuzioni insieme.

Stampa anche il throughput sui chunk veri di `data/demo/`, confrontabile con i
due numeri noti: **10,0 embed/s** misurati su DirectML mentre questa pagina
veniva scritta, contro i ~10 di I-07 e i ~2,4 su CPU. Se dice CPU su una
macchina che ha una GPU, l'extra non è installato, il provider non è visibile a
`onnxruntime`, oppure le distribuzioni sono due: è un guasto silenzioso che
costa sei ore di ingestione, quindi vale la pena guardarlo adesso.

**`gpu-rocm` e `gpu-cuda` restano dichiarati e non verificati** finché U-12 non
li prova su una macchina che ha quell'hardware. Ciò che è verificato oggi è che
esistono, per quali Python e con quale glibc: `onnxruntime-gpu` 1.29.0
(manylinux_2_28), `onnxruntime-rocm` 1.22.2 (manylinux_2_34, cioè Ubuntu 22.04 o
più recente).

### 2.2 Qdrant

```bash
docker compose --profile eval up -d qdrant
curl http://localhost:6333/collections
```

Deve rispondere `{"result":{"collections":[...]},"status":"ok",...}`. Su un
Qdrant appena avviato la lista è vuota: la si riempie nel §4.

`make up` avvia anche il backend nel container, che a questo punto non serve.

> **I target `make` sono scorciatoie.** Su Windows `make` spesso non c'è: accanto
> a ognuno, qui, sta il comando che esegue, e quello funziona ovunque.

> **`docker compose` è un plugin, e su alcune distribuzioni si installa a parte.**
> Il sintomo è un `docker` che risponde ma non conosce il sottocomando. Su Arch
> servono tre cose e la terza chiede di rientrare nella sessione:
>
> ```bash
> sudo pacman -S docker docker-compose docker-buildx
> sudo systemctl enable --now docker
> sudo usermod -aG docker $USER      # poi logout/login, oppure `newgrp docker`
> ```

### 2.3 L'endpoint LLM (solo se si genera)

```bash
ollama pull gemma4:latest
OLLAMA_CONTEXT_LENGTH=32768 OLLAMA_FLASH_ATTENTION=1 ollama serve
curl http://localhost:11434/v1/models
```

**`OLLAMA_CONTEXT_LENGTH` non è cosmetico.** Senza, Ollama sceglie da sé la
finestra fra 4k, 32k e 256k guardando la memoria disponibile: su una scheda
piccola darebbe 4096, cinque chunk non entrerebbero in contesto, e il risultato
continuerebbe a dichiarare 32768. Da A-09 il valore registrato in `EvalRun` si
legge da `/api/ps` invece di essere copiato dalla costante, quindi un
disallineamento si vede nel JSON: ma è meglio non produrlo.

`OLLAMA_FLASH_ATTENTION` invece è una manopola di velocità, e quanto valga
dipende dalla taglia del modello: su E4B sposta il motore ma non l'orologio, sul
12B vale un fattore quattro sul prefill. I numeri sono in
[`hardware.md`](hardware.md).

### 2.4 La suite

```bash
pip install pytest ruff      # non arrivano con `pip install -e .`: vedi sotto
python -m pytest -q
```

**`pytest` e `ruff` stanno in `[tool.uv] dev-dependencies`**, che è una sezione
di `uv` e **pip non la legge**: con pip vanno chiesti a mano, e chi non lo fa
riceve `No module named pytest` dopo un'installazione andata a buon fine. Con
`uv sync` arrivano da soli.

**1808 test, ~31 secondi** (misurato il 2026-08-27 sul commit corrente; 1808
anche su Linux x86_64 con Python 3.12, dentro l'immagine). La suite
**non ha bisogno né di Qdrant né dell'LLM** e non carica nessun modello ONNX: se
passa, l'installazione Python è completa, e un fallimento qui è un problema di
dipendenze e non di configurazione.

Per il frontend, `cd ui && npm install && npm run test` (365 test) e
`npm run build`.

### 2.5 L'interfaccia, se si vuole guardarla

`make dev` (cioè `python scripts/dev.py`) avvia il backend, **aspetta** che
risponda, poi avvia Vite, su http://localhost:5173. L'attesa non è cortesia: senza, la prima chiamata parte
contro una porta chiusa e la pagina si apre già in stato di guasto, che chi
guarda legge come un difetto del frontend. Non è il modo in cui il progetto si
consegna (quello è `docker compose --profile demo up`, §2.0): serve a chi tocca
il codice. Nella consegna il proxy di Vite non esiste, perché l'API serve
`ui/dist` dalla stessa origine.

---

## 3. Le variabili d'ambiente

**Non tutti i parametri sono variabili d'ambiente, ed è una decisione.** I
parametri di recupero e generazione (profondità, modalità, reranker, modello,
temperatura) viaggiano nella **richiesta**, perché due richieste concorrenti
possono legittimamente volerli diversi: metterli nell'ambiente li renderebbe
globali e condivisi. Nell'ambiente sta solo la categoria «deployment»: dove
stanno i servizi e su che piattaforma si gira.

| variabile | default | cosa decide |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | dove sta il vector store |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | dove sta l'inferenza. **L'unico modo in cui il progetto la raggiunge** |
| `LLM_MODEL` | `gemma4:latest` | il modello chiesto all'endpoint |
| `LLM_QUANTIZATION` | `Q4_K_M` | annotazione registrata in `EvalRun`, non una richiesta al motore |
| `MAX_NEW_TOKENS` | `1024` | tetto dei token generati. Va alzato a 2048 col ragionamento acceso, o metà delle risposte torna troncata |
| `REASONING_EFFORT` | `none` | ragionamento del modello: `none`, `low`, `medium`, `high`, `max`. Da qui si deriva `EvalRun.reasoning_enabled` |
| `ONNX_PROVIDERS` | vuoto | impone l'acceleratore. Vuoto lascia decidere alla piattaforma. `CPUExecutionProvider` per confrontare i tempi senza GPU |
| `FASTEMBED_CACHE_PATH` | `~/.cache/fastembed` | dove stanno i pesi. Il default di fastembed è sotto `%TEMP%`, cioè una cartella che il sistema ha il diritto di svuotare, ed è successo a metà run |
| `SEARCH_EXACT` | spento | salta il grafo HNSW e confronta con tutti i punti. **Necessario per confrontare due indici di densità diversa**: vedi §5.9 |
| `HNSW_EF` | default di Qdrant | quanto a fondo la ricerca approssimata cammina nel grafo |
| `QUERY_REWRITE_MODEL` | vuoto | un modello dedicato alla riscrittura. Vuoto usa `LLM_MODEL` |
| `ENTAILMENT_RENDER_TABLES` | spento | rende leggibili le tabelle OCR prima della verifica (C-08). **Cambiarlo cambia `citation_precision` già riportata** |
| `WARMUP` | acceso | scalda embedder e verificatore all'avvio dell'API, in un thread di sottofondo. `WARMUP=0` per lavorare all'interfaccia mentre la GPU è occupata da una valutazione |
| `SERVE_UI` | spento | fa servire `ui/dist` dall'API sulla stessa origine. **Acceso solo dentro l'immagine**: una `ui/dist` in un clone è costruita per il proxy di Vite, e servirla darebbe una pagina che si carica e non parla col backend |
| `DEMO_QDRANT_URL` | `http://qdrant-demo:6333` | dove il profilo `demo` carica l'indice ridotto. Separata da `QDRANT_URL` apposta: chi sviluppa ha quella esportata verso il proprio indice |
| `IBID_API_URL` | `http://localhost:8000` | dove la dashboard cerca il backend |
| `API_PORT`, `QDRANT_PORT` | `8000`, `6333` | porte esposte sull'host |
| `VITE_API_TARGET` | `http://127.0.0.1:8000` | dove il frontend manda le chiamate in sviluppo |
| `PYTHONIOENCODING` | n/d | su Windows va messa a `utf-8`, vedi §10 |

`.env.example` è il file da copiare in `.env` e adattare: contiene le sole
variabili di deployment, con i default di compose e il commento che spiega
quando cambiarle.

> **La sintassi degli esempi.** Da qui in avanti i comandi sono scritti nella
> forma POSIX `VAR=valore comando`, che vale su Linux, macOS e Git Bash. In
> PowerShell la variabile si imposta prima e resta per la sessione:
> `$env:SEARCH_EXACT = "1"`.

---

## 4. I corpus, l'indice e il golden set

### 4.1 Scaricare

```bash
python scripts/fetch_dataset.py --dataset all
```

Scarica da HuggingFace in `data/` (2,3 GB). I due corpus hanno licenze diverse e
obblighi diversi in caso di ridistribuzione: la tabella sta in
[`data/README.md`](../data/README.md), ed è il file da aggiornare quando se ne
aggiunge uno.

### 4.2 Indicizzare

```bash
python scripts/ingest.py --dataset all --drop
```

**122 minuti** su una RX 6750 XT per 65.950 chunk (misurato in I-07), ~7,7 ore su
CPU. Il collo di bottiglia è l'embedding denso a ~10 chunk/s; la parte sparsa
(BM25, statistica, su CPU) costa 41 secondi in tutto e l'upsert altri 50.

`--drop` ricrea la collection da zero. Senza, i punti si sovrascrivono per id,
che è la cosa giusta quando si reindicizza lo stesso corpus e la cosa sbagliata
quando si è cambiata la segmentazione.

Le collection che ne escono:

| collection | punti | cos'è |
|---|---|---|
| `open_ragbench` | 18.840 | paper accademici, pipeline generica (una sezione per chunk) |
| `ledger` | 47.110 | bilanci OCR, pipeline generica (una pagina per chunk) |
| `open_ragbench_routed` | 98.312 | stesso corpus con la pipeline scelta dal profilatore |
| `ledger_routed` | 228.331 | idem |

Le due `_routed` servono solo all'ablation dell'affermazione 2 e costano 618
minuti di GPU:

```bash
python scripts/ingest.py --dataset all --pipeline-mode routed --collection-suffix routed
```

Il controllo, che è anche il primo sospetto quando un numero non torna:

```bash
curl -s http://localhost:6333/collections/open_ragbench | python -c "import sys,json; print(json.load(sys.stdin)['result']['points_count'])"
```

Deve stampare `18840`.

> **Un indice è legato al modello di embedding che lo ha prodotto.**
> Interrogarlo con un altro restituisce risultati plausibili e privi di senso,
> **senza nessun errore**. È la ragione per cui il modello di embedding non è un
> parametro della richiesta, ed è il motivo per cui `config_hash` lo contiene.

### 4.3 Il golden set

Sta in `eval/golden/`, un JSONL per dataset, ed è committato: non va rigenerato
per riprodurre una misura.

```json
{"query_id": "852703f0-...", "dataset_id": "open_ragbench",
 "query_text": "What are the challenges in estimating output impedance...?",
 "qrels": [{"chunk_id": "open_ragbench:2410.14077v2:1", "relevance": 2}],
 "reference_answer": "Estimating output impedance ... is challenging due to ...",
 "meta": {"type": "abstractive", "source": "text-image"}}
```

| campo | cosa contiene |
|---|---|
| `query_id` | identificatore stabile: è la chiave su cui si fanno i test appaiati |
| `qrels` | i chunk giudicati rilevanti, con grado. Solo `relevance > 0` entra nel calcolo |
| `reference_answer` | la risposta di riferimento del dataset originale, usata dai giudizi di generazione |
| `answerable` | assente significa vera. Le query **non rispondibili** (35 per corpus) sono marcate `false` e sono escluse da qrels e recall: servono a misurare l'astensione |

`--limit N` prende **le prime N query rispondibili nell'ordine del file**, che
non cambia: due smoke test con lo stesso limite girano sulle stesse domande.

---

## 5. Riprodurre una misura

### 5.1 Quattro secondi, per sapere se l'impianto regge

```bash
SEARCH_EXACT=1 python scripts/eval.py --dataset open_ragbench --retrieval-mode dense --limit 50 --no-write
```

Su una macchina con l'indice a posto finisce in **meno di quattro secondi** (di
cui tre sono il caricamento dell'embedder) e stampa:

| | `nDCG@10` | `Success@1` | `R@5` | `doc_R@5` |
|---|---|---|---|---|
| `open_ragbench`, dense, prime 50 | 0,7051 | 0,5400 | 0,8000 | 0,9600 |
| `open_ragbench`, hybrid, prime 50 | 0,7836 | 0,5600 | 0,8800 | 0,9800 |
| `ledger`, dense, prime 50 | 0,0736 | 0,1400 | 0,0610 | 0,9167 |

<sub>Rieseguiti il 2026-08-26 sul commit corrente. Il recupero è deterministico
(§5.6), quindi questi numeri sono attesi <b>identici</b>, non simili.</sub>

`--no-write` è quello che rende questo comando uno smoke test e non una misura:
non scrive nessun `EvalRun`, e un file in `eval/results/` è per definizione una
misura archiviata.

### 5.2 La misura vera

Togliere `--limit` e `--no-write`:

```bash
SEARCH_EXACT=1 python scripts/eval.py --dataset open_ragbench --retrieval-mode dense
```

**56 secondi** per le 3.045 query di `open_ragbench`, **2 minuti e 52 secondi** per le 10.000
di `ledger`. Le otto configurazioni della tabella del README sono otto comandi di
questa forma, con i flag `--retrieval-mode {dense,sparse,hybrid}` e `--rerank`.

Il comando scrive due file:

| file | cos'è |
|---|---|
| `eval/results/{ts}_{dataset}_{pipeline_mode}_{slug}.json` | l'`EvalRun`: la misura e le condizioni in cui è stata presa |
| `eval/results/retrieved/{stesso nome}.jsonl` | **un record per query**, scritto mentre la run gira |

Il secondo file è quello che permette il test appaiato del §5.7: senza risultati
per query si possono confrontare due medie e nient'altro. Si accumula sotto un
nome che finisce in `.partial` e viene rinominato solo dopo l'ultimo record,
quindi **l'esistenza del nome definitivo è la prova che la run è arrivata in
fondo**.

I valori attesi per le due configurazioni dense complete, rieseguiti il
2026-08-26:

| | `nDCG@10` | `Success@1` | `R@5` | `doc_R@5` |
|---|---|---|---|---|
| `open_ragbench` (3.045 query) | 0,7184 | 0,5448 | 0,8279 | 0,9681 |
| `ledger` (10.000 query) | 0,2465 | 0,2647 | 0,2112 | 0,8962 |

Sono le stesse cifre della tabella del README, a quattro decimali.

### 5.3 Leggere un `EvalRun`

Questo e' un risultato vero, con le annotazioni aggiunte accanto ai campi:

```jsonc
{
  "run_id": "9b04cd6b-...",
  "timestamp": "2026-08-23T10:05:43Z",
  "git_commit": "6078f7f6...",          // HEAD, con suffisso -dirty se c'erano modifiche
  "config_hash": "2a069d31",            // vedi §5.4
  "dataset_id": "open_ragbench",        // mai una riga senza questo
  "model": "retrieval_only",            // una misura di recupero non genera niente
  "quantization": "none",
  "context_window": 0,
  "temperature": 0.0,
  "reasoning_enabled": false,
  "pipeline_mode": "generic",           // l'asse del routing: generic | routed
  "config": {                           // i flag, come dati e non come stringa
    "retrieval_mode": "hybrid", "top_k": 5, "eval_depth": 10,
    "rerank": true, "query_rewrite": false, "filter_content_type": null,
    "collection": "open_ragbench", "n_queries": 3045,
    "embedding_model": "intfloat/multilingual-e5-large",
    "search_exact": true, "hnsw_ef": null,
    "reranker_model": "BAAI/bge-reranker-base"
  },
  "metrics": { "nDCG@10": 0.8053, "R@5": 0.8939, "doc_R@5": 0.9915, ... }
}
```

Tre campi meritano una nota, perché sono il punto in cui questo formato risponde
a un difetto vero.

- **`git_commit` porta `-dirty`** quando la run è girata con modifiche a file
  tracciati. Senza quel suffisso, un risultato registrerebbe uno sha che descrive
  codice mai esistito in quella forma. Si legge all'inizio della run: un commit
  fatto durante i quaranta minuti di generazione veniva registrato come quello
  che aveva prodotto le risposte.
- **`pipeline_mode` è binario per contratto.** Prima erano finiti lì dentro
  valori come `generic_filtered_text`, e la domanda «mostrami tutte le run
  instradate» era diventata impossibile. I flag stanno in `config`.
- **`reasoning_enabled` è dedotto, mai asserito.** Scritto a mano come `false`, è
  stato falso in ogni run per un periodo: il modello ragionava attraverso
  l'intero budget di token mentre il risultato diceva di no.

Le run di generazione hanno in `config` due campi in più, `prompt_hash` e
`user_template_hash`: sono l'identità del prompt che ha girato. Cambiare il testo
del prompt cambia l'hash, ed è voluto, perché una misura fatta con un altro
prompt non è la stessa misura.

### 5.4 Quando due numeri sono confrontabili

`config_hash` è l'identità di una configurazione: **stesso hash significa numeri
direttamente confrontabili**. Ci entra ciò che cambia *quello che il sistema
calcola*:

```
embedding_model, top_k, pipeline_mode, retrieval_mode, qdrant_url, eval_depth
+ sparse_idf, sparse_query_embed   (solo per le modalità che leggono i vettori sparsi)
+ search_exact, hnsw_ef            (solo quando sono accesi)
```

Non ci entra il **numero di query**: quello cambia solo quanto precisamente si
osserva, non cosa si osserva. E non ci entra `git_commit`, che infatti è
registrato a parte.

La funzione è stata cambiata tre volte, ogni volta perché una correzione aveva
alterato ciò che il sistema calcolava: le run precedenti **non dovevano** più
condividere il nome con quelle successive. Le run archiviate tengono il loro hash
originale, e `eval/results/archive/` è di sola lettura.

> **Il limite noto**: `config_hash` nomina la configurazione, non lo stato
> dell'indice. Due run con lo stesso hash possono aver interrogato indici
> diversi. È successo (OQ-09), ed è la ragione per cui il primo sospetto del §5.9
> è il conteggio dei punti.

### 5.5 La precisione di citazione, senza generare niente

Questa è la misura dell'affermazione 1, e **non richiede un LLM**. Le generazioni
di C-01 sono committate in `eval/results/generations/`, ognuna con i `chunk_id`
che aveva in contesto: la precisione si ricalcola da lì.

```bash
python scripts/eval_citation_precision.py --limit 5   # smoke test
python scripts/eval_citation_precision.py             # l'ultimo dump per dataset
```

Serve Qdrant (per il testo dei chunk) e il verificatore NLI
(`MoritzLaurer/bge-m3-zeroshot-v2.0`, ~1 GB di ONNX scaricato al primo uso). Lo
smoke test da cinque risposte costa ~45 secondi per corpus, caricamento del
modello compreso; il ricalcolo completo cresce con il numero di coppie da
verificare, non di risposte.

**Cinque risposte non danno il numero di duecento**, e vale la pena dirlo perché
lo scarto è grande: lo smoke test qui sopra riporta `citation_precision` 0,4348
su `open_ragbench` contro lo 0,6573 della misura completa. Serve a sapere che
l'impianto gira, non a confrontarsi con la tabella del README.

Che sia un ricalcolo e non una rigenerazione non è una scorciatoia: significa che
la metrica di formato e quella di citazione sono misurate **sulle stesse
risposte**, quindi un cambiamento nell'una non può essere confuso con un campione
diverso nell'altra.

Per generare risposte nuove serve invece la GPU e l'endpoint:

```bash
python scripts/eval_citations.py --dataset open_ragbench --limit 200
```

**È una run lunga**: una generazione costa ~20 secondi di GPU, quindi 200
domande sono circa un'ora, e il golden set completo sarebbe ~17 ore per corpus.
Il limite di 200 non è timidezza: è la taglia minima con cui un 98% osservato
sostiene il criterio del 95%.

### 5.6 La linea di rumore, e cosa dice davvero

```bash
make noise-floor    # python scripts/eval_noise.py --mode retrieval --n-runs 5
```

Ripete la stessa configurazione cinque volte e riporta media, deviazione
standard, minimo e massimo per ogni metrica. La regola del progetto è che
**nessun miglioramento sotto σ può essere dichiarato tale**.

Sul recupero, misurato il 2026-08-07 su cinque ripetizioni per corpus, **σ è
zero su tutte e sette le metriche**: la pipeline di recupero è deterministica.
Il che va letto per quello che è, e non per qualcosa di più: significa che una
differenza fra due configurazioni non è rumore di esecuzione, **non** che sia
significativa. L'incertezza che resta è su *quali domande* sono state scelte, e
quella la misura il test appaiato. Per la generazione σ non è zero e la misura si
rifà con `--mode generation`.

La dashboard mostra il rumore come whisker ±σ e colora un delta solo se lo
supera; quando il rumore non è mai stato misurato dice «non misurato» invece di
tacere, perché non misurato è diverso da non significativo.

### 5.7 Il test appaiato

Due medie non rispondono alla domanda «l'altra configurazione è migliore»: lo fa
il confronto sulle **stesse query**, che conta quante cambiano in ciascuna
direzione e chiede a McNemar se lo squilibrio è credibile.

**Questo confronto non richiede niente**, nemmeno Qdrant: i dump per query di
diciannove run sono committati, e lo strumento lavora su quelli.

```bash
python scripts/compare_retrieved.py   eval/results/retrieved/20260822_112954_open_ragbench_generic_dense.jsonl   eval/results/retrieved/20260823_092325_open_ragbench_generic_hybrid-rerank.jsonl   --level doc
```

```
3045 query,  hit@5 a livello doc
  A ..._generic_dense.jsonl            0.9642
  B ..._generic_hybrid-rerank.jsonl    0.9898
  delta +0.0256
  solo A 13   solo B 91   discordanti 104   p = 0.0000
  -> differenza reale (p=0.0000), vince B
```

Lo script **si rifiuta di procedere se i due dump non coprono le stesse query**,
invece di intersecare in silenzio: un test appaiato su una popolazione decisa
dalla differenza fra due file non è un test appaiato.

L'altro strumento, `compare_runs.py`, fa lo stesso confronto **rieseguendo il
recupero** su due collection: serve quando una delle due non è mai stata
misurata, e per questo ha bisogno di Qdrant.

```bash
python scripts/compare_runs.py --dataset ledger   --collection-a ledger --collection-b ledger_routed --retrieval-mode dense
```

È la forma del comando che ha prodotto il verdetto sull'affermazione 2. Il
numero da confrontare è quello in **ricerca esatta**: `doc_R@5` da 0,8962 a
0,7590, cioè **−13,72 punti**, p < 0,0001. I numeri in ricerca approssimata
della stessa giornata **non si riproducono più** (OQ-09), ed è il motivo per
cui il §5.9 mette lo stato dell'indice al primo posto fra i sospetti.

### 5.8 Guardare i risultati

```bash
make dashboard      # python -m streamlit run dashboard/app.py, su :8501
```

Quattro pagine: confronto fra `EvalRun` (con il rumore disegnato accanto ai
delta), esplorazione dei chunk, esplorazione dei fallimenti ordinati dal
peggiore, e un playground per interrogare una collection. Il dataset è una
scelta singola e non multipla: un delta fra due corpus **non è esprimibile**
nell'interfaccia, ed è deliberato.

Per una domanda singola dalla riga di comando:

```bash
python scripts/query.py --dataset open_ragbench --rerank "What is the SD of RMSE for Ridge Regression?"
```

### 5.9 Se il numero non torna

In ordine di probabilità.

1. **L'indice non è quello.** Contare i punti (§4.2). Un indice costruito con una
   segmentazione diversa, o parziale, dà numeri plausibili e sbagliati.
2. **Ricerca approssimata contro esatta.** Senza `SEARCH_EXACT=1` la ricerca
   percorre un grafo di prossimità e può fermarsi in un vicinato plausibile. Su
   `ledger_routed` (228.331 punti in una banda di similarità larga 0,0085) la
   ricerca esatta recupera **857 query su 10.000** che quella approssimata
   perdeva. **Confrontare due indici di densità diversa con una ricerca
   approssimata non è un confronto fra pipeline**: otto dei ventidue punti di
   regresso attribuiti al routing erano l'indice.
3. **La versione di `fastembed`.** L'embedder ha cambiato pooling fra versioni
   (da CLS a media): con una versione diversa da quella che ha costruito
   l'indice, le query finiscono in uno spazio leggermente diverso e il recupero
   peggiora senza errori. La libreria stessa lo avvisa a schermo.
4. **La profondità di valutazione.** Le 16 run in `eval/results/archive/` hanno
   metriche `@10` calcolate su liste di 5 documenti, ed è il motivo per cui sono
   archiviate. `eval_depth` è dentro `config_hash` proprio per non farle
   sembrare confrontabili con le altre.
5. **Il prompt, per le misure di generazione.** `prompt_hash` e
   `user_template_hash` sono in `config`: se differiscono, le due run hanno
   chiesto due cose diverse.
6. **Il motore, per le misure di latenza.** Finestra di contesto, flash
   attention, runner orfani rimasti in VRAM da un riavvio precedente. Il sintomo
   non è un errore: la risposta arriva, giusta, solo lenta. Diagnosi e comandi in
   [`hardware.md`](hardware.md).
7. **`-dirty` in `git_commit`.** La run è girata su codice non committato.

### 5.10 Le regole con cui questi numeri sono stati raccolti

Non sono stile: sono vincolanti, e violarle ha già prodotto un risultato
sbagliato in questo repo.

- **Mai due modifiche dentro una misura sola.** Una modifica, una misura, poi la
  successiva.
- **Nessuna metrica senza `dataset_id`, mai una media fra generi documentali.**
  L'affermazione 2 ha segno opposto sui due corpus: una media (circa −6) avrebbe
  nascosto sia il segno sia il fatto che le due metà hanno forza statistica
  incomparabile.
- **Nessun miglioramento dichiarato senza il confronto con la linea di rumore.**
  Un «+4 punti» di conformità è già stato dichiarato come risultato ed era
  rumore: il test appaiato lo ha smontato dopo.
- **La soglia di astensione e il formato delle citazioni si decidono nel codice**,
  mai lasciati al modello. La soglia è derivata dai dati da
  `scripts/calibrate_abstention.py` a partire da un budget scelto da una persona
  (l'1% di domande rispondibili che il sistema può rifiutare), e va ricalibrata
  dopo ogni re-ingestione o cambio di embedder.
- **Le soglie non si tarano sul campione su cui la metrica viene riportata.**
  `ENTAILMENT_THRESHOLD` è il confine naturale del modello (0,5) e non un valore
  scelto guardando i nostri dati: a 0,5 il verificatore è pessimista, quindi la
  precisione riportata è un **limite inferiore**, che è la direzione sicura.

---

## 6. Le metriche

### Recupero

Calcolate con `ir_measures`. Ogni run le riporta tutte, così che due run siano
sempre confrontabili sulla stessa riga.

| metrica | definizione |
|---|---|
| `R@5`, `R@10` | quota dei chunk rilevanti che compaiono nei primi 5 o 10 |
| `nDCG@10` | guadagno cumulato scontato: premia il rilevante in alto, tiene conto del grado |
| `RR@10` | reciproco del rango del primo rilevante, mediato sulle query |
| `Success@1` | quota di query in cui il primo risultato è rilevante |
| `doc_R@5`, `doc_R@10` | le stesse, aggregate a **documento**: i chunk di un documento collassano in una voce sola con il punteggio massimo |

`doc_R@5` è la metrica su cui si giudica il routing, ed è la domanda «la lista
dei documenti mostrata all'utente contiene quello giusto». `R@5` è la domanda
diversa «il chunk esatto è finito nel contesto del modello». Su `ledger` la prima
sta sopra 0,89 mentre la seconda sta sotto 0,25: sono due obiettivi distinti, e
confonderli fa sembrare rotto un recupero che per la lista funziona.

### Citazione e generazione

| metrica | definizione |
|---|---|
| `format_compliance` | quota di risposte i cui marcatori rispettano il formato imposto. Misurata sul **testo grezzo** |
| `citation_precision` | delle coppie *(affermazione, chunk citato)* prodotte, quante il chunk implica davvero |
| `citation_recall` | delle affermazioni verificabili, quante hanno almeno una citazione che regge |
| `uncited_claim_rate` | delle affermazioni verificabili, quante non citano niente |
| `numeric_citation_precision` | per il genere tabellare: la cella viene cercata e il valore confrontato, invece di chiedere a un modello NLI se un `<table>` implichi un numero |
| `windowed_rate` | quota di coppie la cui premessa ha dovuto essere spezzata. Attesa vicino a zero: un massimo su N finestre cresce con N |
| `abstention_rate` | quota di domande in cui il sistema si è rifiutato di rispondere |
| `truncation_rate`, `empty_answer_rate` | risposte tagliate dal budget di token, risposte vuote |
| `latency_p50_s`, `latency_p90_s` | latenza a orologio, mediana e novantesimo percentile |
| `violation_*` | i modi di sbagliare il formato, uno per tipo (lista con virgole, intervallo, congiunzione, marcatori spaziati, fuori intervallo) |

**L'unità di `citation_precision` è la coppia, non la frase**, ed è di proposito
più severa dell'unione delle citazioni di una frase: un modello che affianca a
una citazione giusta due irrilevanti sta facendo esattamente ciò che il progetto
esiste per scoprire, e un punteggio sull'unione gli darebbe il massimo.

**`uncited_claim_rate` va letto accanto alla precisione**, perché la precisione
si alza citando di meno: una citazione sicura e nient'altro fa 1,0.

---

## 7. I contratti dati

Definiti in `ROADMAP.md` §3 e in `src/datasets/schema.py`. **Non si rinominano né
si aggiungono campi senza aggiornare la ROADMAP**: sono ciò che rende
confrontabili misure prese a settimane di distanza.

### `Chunk`

| campo | tipo | nota |
|---|---|---|
| `chunk_id` | `str` | `{dataset_id}:{doc_id}:{seq}` |
| `dataset_id` | `str` | **richiesto su ogni record**: è ciò che rende impossibile una metrica senza dataset |
| `doc_id` | `str` | |
| `doc_genre` | `str` | `academic_pdf`, `table_heavy`, `continuous_text`: è l'asse su cui il routing decide |
| `pipeline` | `str` | la pipeline che ha davvero prodotto il chunk, o `generic` se non ne ha girata nessuna |
| `section_path` | `str` | la gerarchia di titoli in cui il chunk si trova |
| `page` | `int` | |
| `bbox` | `tuple \| None` | oggi sempre nullo: nessuno dei due corpus distribuisce i PDF originali |
| `content_type` | `str` | `text`, `table`, `figure_caption`, `mixed` |
| `text`, `source_uri` | `str` | |

### Il formato delle citazioni

**È imposto dal codice, non suggerito al modello.** Si accettano solo marcatori
contigui `[n][m]`:

```
Il valore massimo è 400ms [2][3].
```

Le forme `[2, 3]`, `[2 e 3]`, `[2]-[3]` sono rifiutate. Le varianti note vengono
**riparate** da un parser prima che il testo raggiunga il lettore, e i marcatori
che puntano a chunk non presenti in contesto vengono scartati. Da qui la
differenza fra le due colonne del README: `format_compliance` grezza misura il
modello, quella dopo il parser misura il sistema.

### `EvalRun`

Campi obbligatori: `run_id`, `timestamp`, `git_commit`, `config_hash`,
`dataset_id`, `model`, `quantization`, `context_window`, `temperature`,
`reasoning_enabled`, `pipeline_mode`, più `config` e `metrics`. La temperatura di
valutazione è **sempre 0** e la finestra **32768**, e tutti e due vanno annotati
nel risultato: una misura di cui non si sa in che condizioni è stata presa non è
una misura.

### L'API

`QueryRequest` porta la domanda e, opzionali, i parametri della richiesta:
`dataset_id`, `collection`, `top_k`, `retrieval_mode`, `rerank`, `query_rewrite`,
`filter_content_type`, `search_exact`, `hnsw_ef`, `model`, `temperature`,
`max_new_tokens`, `reasoning_effort`, `rag`, `baseline_prompt`, `verify`. Ogni
campo assente prende il default del server: **nessun controllo dell'interfaccia
gira a vuoto**, e ciò che ha girato davvero torna in `AnswerResponse.config`.

`AnswerResponse` porta il testo (riparato e grezzo), i chunk che erano in
contesto, le citazioni con il loro verdetto e punteggio, le affermazioni non
citate, lo stato del gate di astensione e i tempi.

I tipi TypeScript del frontend sono **generati** da `src/api/schema.py`
(`make ui-types`), e la suite Python fallisce se i due lati divergono.

---

## 8. L'architettura

### Il percorso di una domanda

| stadio | dove | manopola |
|---|---|---|
| richiesta | `src/api/main.py`, `src/service/answer.py` | i campi di `QueryRequest` |
| riscrittura della query | `src/retrieval/query_rewrite.py` | `query_rewrite` (costa ~2,8 s a query) |
| embedding della query | `src/index/embed.py` | nessuna: il modello è legato all'indice |
| ricerca | `src/retrieval/backends.py`, `hybrid.py`, `src/index/store.py` | `retrieval_mode`, `top_k`, `search_exact`, `hnsw_ef`, `filter_content_type` |
| rerank | `src/retrieval/reranker.py` | `rerank`, `rerank_fetch_k` |
| gate di astensione | `src/retrieval/abstention.py` | soglia calibrata, per collection |
| prompt e generazione | `src/generation/prompt.py`, `chat.py` | `model`, `temperature`, `max_new_tokens`, `reasoning_effort` |
| parsing e riparazione dei marcatori | `src/generation/citations.py`, `citation_format.py` | nessuna: il formato è deciso nel codice |
| divisione in affermazioni | `src/generation/claims.py` | |
| verifica | `src/generation/entailment.py`, `numeric_verify.py` | `verify`, `ENTAILMENT_THRESHOLD` |

Una valutazione di **recupero** si ferma al rerank: non genera niente, e infatti
registra `model: "retrieval_only"`.

### Il routing, che è la cosa che l'affermazione 2 mette alla prova

Succede in **ingestione**, non in interrogazione: il profilatore calcola le
caratteristiche di un documento, il genere viene assegnato, e il genere sceglie
la pipeline che lo spezza in chunk.

| `doc_genre` | pipeline |
|---|---|
| `academic_pdf` | `structured_hierarchical` |
| `table_heavy` | `table_heavy` |
| `continuous_text` | `continuous_text` |

Il genere e la pipeline che ha davvero girato restano nel payload di ogni chunk,
e sono quello che l'interfaccia mostra come targhetta. Nella modalità generica
non gira nessuna delle tre: si prende l'unità che il documento offre già (una
pagina per `ledger`, una sezione per `open_ragbench`), e il campo `pipeline` dice
`generic`, che non è un'assenza di dato ma ciò che ha prodotto quel chunk.

### La mappa dei moduli

| cartella | cosa contiene |
|---|---|
| `src/datasets/` | i loader dei corpus, il golden set, il registro dei dataset, i contratti |
| `src/profiling/` | il profilatore dei documenti e l'assegnazione del genere |
| `src/ingestion/` | le tre pipeline di chunking scritte a mano e il router che sceglie |
| `src/index/` | embedding (denso e sparso) e operazioni su Qdrant |
| `src/retrieval/` | le tre modalità, la fusione RRF, il reranker, i filtri, l'astensione |
| `src/generation/` | prompt, chiamata all'LLM, parser delle citazioni, entailment, verifica numerica |
| `src/service/` | il caso d'uso: una domanda entra, una risposta citata esce |
| `src/api/` | gli endpoint HTTP e lo schema |
| `src/eval/` | gli harness, le metriche, i test appaiati, il rumore, la provenienza |
| `scripts/` | i comandi: ingestione, valutazione, sonde, migrazioni |
| `dashboard/` | l'app Streamlit interna |
| `ui/` | il frontend React |

### Dove vive una decisione

`src/config.py` tiene i parametri, divisi in quattro categorie che decidono chi
può cambiarli:

1. **Per richiesta**: profondità, modalità, reranker, modello, temperatura. Non
   stanno nel modulo, stanno in `RequestConfig`, che è immutabile. Due richieste
   concorrenti con `top_k` diverso condividerebbero altrimenti la stessa
   costante.
2. **Legati all'indice**: `EMBEDDING_MODEL`, `SPARSE_EMBEDDING_MODEL`. Metterli
   nella richiesta renderebbe esprimibile una richiesta sbagliata.
3. **Di deployment**: `QDRANT_URL`, `LLM_BASE_URL`, `ONNX_PROVIDERS`. Una
   richiesta HTTP non può spostare la macchina.
4. **Calibrati sui dati**: soglie di astensione e di entailment. Sono derivate da
   misure, non preferenze, e lasciarle scegliere a chi chiama permetterebbe di
   tarare la soglia sulla stessa risposta che deve giudicare.

**Un'ablation è un ciclo sulla configurazione, non una modifica al codice.** È il
motivo per cui ogni funzionalità sta dietro un flag: i contributi individuali
restano isolabili combinandoli.

### Gli endpoint

| metodo | percorso | cosa fa |
|---|---|---|
| `GET` | `/health` | vivo o no |
| `GET` | `/datasets` | cosa si può interrogare, e con quali modelli e finestre |
| `GET` | `/documents`, `/document/{id}/chunks`, `/chunk/{id}` | rileggere una fonte citata |
| `POST` | `/retrieve` | solo recupero, anche in batch |
| `POST` | `/query` | risposta completa |
| `POST` | `/query/stream` | la stessa, in SSE |
| `GET` | `/config` | i default in vigore sul server |

---

## 9. Estendere il progetto

### Aggiungere un dataset

Tre passi, e **nessuno script va toccato**: leggono tutti dal registro.

1. `src/datasets/<nome>.py` con la stessa forma degli altri due: `DATASET_ID`,
   `REPO_ID`, `download()`, `iter_chunks()`, `iter_chunks_routed()`.
2. Un caricatore del golden set in `src/datasets/golden.py` che restituisca
   `GoldenQuery`.
3. Una voce nel dizionario `REGISTRY` di `src/datasets/registry.py`.

Aggiungere la licenza e l'attribuzione in [`data/README.md`](../data/README.md)
non è facoltativo: è il prerequisito legale per distribuire qualunque indice che
ne derivi.

### Aggiungere una configurazione di recupero

Un flag in `scripts/eval.py`, il parametro corrispondente in `RequestConfig`, e
la decisione se entra in `config_hash`. La regola: **ci entra se cambia ciò che
il sistema calcola**, e in quel caso le run precedenti smettono giustamente di
condividere il nome con quelle successive.

### Cambiare il modello di embedding

Comporta la re-ingestione completa, e non è negoziabile: le collection
contengono vettori nello spazio del modello corrente. Vanno anche ricalibrate le
soglie di astensione, che sono derivate dai punteggi di quell'indice.

### Aggiungere una dipendenza

La licenza va verificata e registrata nella tabella di
[`STACK.md`](../STACK.md) **prima** di introdurla. Il progetto è MIT e nessuna
dipendenza copyleft può entrare nell'albero. In particolare **PyMuPDF non va
aggiunto**: è AGPL-3.0, e la sua clausola di rete costringerebbe l'intero
progetto, immagini Docker comprese, a diventare AGPL.

---

## 10. Guasti comuni

**`UnicodeEncodeError: 'charmap' codec can't encode character`** su Windows. La
console usa cp1252 e gli script stampano caratteri che non ci stanno. Non è un
difetto della misura, ma uccide il processo:

```powershell
$env:PYTHONIOENCODING = "utf-8"
```

**Tutto va dieci volte più lento del previsto.** L'acceleratore ONNX non è
attivo. `python -c "import src.providers as p; print(p.describe())"` lo dice; il
modulo avvisa anche da solo quando non trova nessun acceleratore, perché
scoprirlo a run finita costa sei ore.

**`NO_SUCHFILE` a metà run, sui pesi dei modelli.** La cache di fastembed stava
sotto `%TEMP%`, che il sistema ha il diritto di svuotare, e Windows lo ha fatto
durante una run. Il default del progetto è `~/.cache/fastembed`: se una
installazione precedente ha lasciato `FASTEMBED_CACHE_PATH` altrove, va spostata.

**Qdrant riparte all'infinito dopo aver ricreato il container**, con
`Can not create shard holder: Failed to (de)serialize from/to json`. Non sono i
dati: è un volume scritto da una versione di Qdrant più recente di quella che il
container sta usando, e il formato dello storage non si legge all'indietro.
`compose.yml` fissa la versione apposta perché questo non capiti per caso; se si
eredita un volume da un'installazione precedente, va allineata a quella che lo ha
scritto. È successo il 2026-08-26 con un pin fermo alla `v1.12.4` su un volume
scritto dalla `v1.19.0`.

**`Connection refused` su :6333.** Qdrant non è acceso, o è su un'altra porta
(`QDRANT_PORT`). Dall'interno di un container l'host non è `localhost` ma
`host.docker.internal`.

**La collection non esiste.** Il nome di default è il `dataset_id`; le varianti
instradate hanno il suffisso `_routed` e si passano con `--collection`.

**Le risposte arrivano giuste ma lente, e la GPU dice di avere spazio.** È
contesa di memoria: pesi in VRAM ma qualcos'altro (una sessione ONNX rimasta
aperta, un runner orfano di un riavvio precedente) spinge parte del lavoro nella
memoria condivisa. `ollama ps` e i log di llama.cpp non possono vederlo, perché
guardano i pesi e non la contesa. Il comando che lo vede, e le tre regole che ne
sono uscite, stanno in [`hardware.md`](hardware.md).

**Il modello risponde in inglese a una domanda italiana, o viceversa.** È
misurato e ha una metrica dedicata (C-05): non è un guasto della pipeline.

---

## 11. Cosa non c'è in questa pagina

| dove | cosa ci si trova |
|---|---|
| [`../README.md`](../README.md) | i risultati, con le tabelle per dataset e i limiti |
| [`../ROADMAP.md`](../ROADMAP.md) | le decisioni, i contratti, i task con i loro criteri di accettazione |
| [`../STACK.md`](../STACK.md) | le scelte tecniche e la tabella delle licenze |
| [`progress.md`](progress.md) | il quaderno di lavoro: ogni task, ogni misura, comprese quelle andate male |
| [`open-questions.md`](open-questions.md) | le domande aperte, ognuna col protocollo per chiuderla |
| [`hardware.md`](hardware.md) | dove va il tempo di una risposta, il budget di una scheda da 12 GB, i confonditori |
| [`contamination.md`](contamination.md) | il controllo di contaminazione fatto prima di adottare i due corpus |

Sono in italiano, come i commenti nel codice.
