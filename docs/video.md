# Il video di U-10: come si rifà, e le due trappole che nasconde

Il criterio di U-10 è breve e vincola più di quanto sembri:

> ≤ 90 secondi, mostra query → risposta citata → apertura della fonte, **senza
> tagli che nascondano la latenza reale**.

L'ultima parte è la difficile. Una risposta di questo sistema costa una decina
di secondi, e la tentazione di tagliarli è esattamente ciò che il criterio
vieta: il progetto misura una pipeline che gira su una scheda da 12 GB, e un
video che finge il contrario mente sulla cosa che il README dichiara.

La ripresa quindi **non ha un montaggio**: è il browser che esegue il copione
dal vivo, con la registrazione aperta dal primo clic all'ultimo.

```bash
cd ui
npm run video              # italiano  -> docs/demo.webm
npm run video -- --en      # inglese   -> docs/demo.en.webm
npm run video -- --scatto  # la schermata ferma invece del video

cd ..
python scripts/video_gif.py docs/demo.webm      # -> docs/demo.gif
python scripts/video_gif.py docs/demo.en.webm   # -> docs/demo.en.gif
```

Servono il backend e Vite accesi (`make dev`), l'indice costruito e l'endpoint
LLM in ascolto. Il `.webm` grezzo non si committa: lo rifà il comando.

---

## 1. Prima di registrare

### I servizi

```bash
curl http://localhost:6333/collections      # Qdrant
curl http://localhost:11434/v1/models       # l'endpoint LLM
curl http://127.0.0.1:8000/health           # il backend
```

### Gli esempi devono ancora fare quello che dichiarano

```bash
python scripts/verify_esempi.py
```

Deve chiudere con `Ogni esempio fa quel che dichiara, in ANN e in esatta`.
Verificato il 2026-08-26: sei su sei, con i margini di astensione identici a
quelli registrati (+0,0227 su `open_ragbench`, +0,0078 su `ledger`).

**Non è una formalità.** Il copione clicca le domande d'esempio: se una smette
di funzionare, la ripresa mostra un'astensione dove dovrebbe esserci una
risposta. Prima di D-17 è già successo che la demo si astenesse su una domanda
che proponeva lei.

### La macchina

Il backend tiene circa 3,5 GB fra embedder, reranker e verificatore. Con
`gemma4:latest` (E4B, 3,3 GB) ci si sta comodi; con il 12B no, e il sintomo non
è un errore ma una risposta lenta il doppio. Il conto e il comando che lo
verifica stanno in [`hardware.md`](hardware.md), sezione «Il budget di una
scheda da 12 GB».

---

## 2. Le due trappole, che sono la parte interessante

### La cache del prefill: un taglio senza forbici

Ollama tiene la cache del prompt, e **una domanda già fatta non paga il
prefill**. Misurato sulla domanda del copione, nello stesso pomeriggio:

| stato del motore | `generation` |
|---|---|
| prima volta, modello caricato | **16,9 s** |
| dopo averla ripetuta qualche volta | **3,9 s** |
| modello scaricato e ricaricato con **un'altra** domanda | **8,0 s** |

La riga di mezzo è quella pericolosa: una ripresa fatta in quello stato
scriverebbe `generation 3,91 s` sullo schermo **senza che nessuno abbia tagliato
un fotogramma**. Sarebbe esattamente ciò che il criterio vieta, ottenuto per via
di una cache invece che di un montaggio.

E non basta scaldare con una domanda diversa: le cache sono più d'una e quella
della domanda del copione sopravvive. Perciò lo script **scarica il modello**
(`keep_alive: 0`) e lo ricarica con una domanda che nel video non compare. È
un'operazione dell'API nativa di Ollama, quindi si tenta e non si pretende: con
`llama-server` non esiste, e in quel caso lo script avvisa invece di fingere.

### Il freddo, che è l'errore opposto

La prima domanda dopo una pausa costa circa il doppio, e non per colpa della
pipeline: **24,8 s a freddo contro 14,3 s subito dopo**, stessa domanda. Anche
Vite compila i moduli al primo caricamento, e senza un giro di riscaldamento la
registrazione si aprirebbe su tre secondi di scheletro.

Lo script fa entrambe le cose in un colpo solo: carica la pagina una volta in un
contesto senza registrazione, e manda una domanda che il video non userà. Chi
volesse invece riprendere il primo avvio di tutto passa `--freddo`.

---

## 3. Il copione

Un dataset solo, `open_ragbench`, nessun cambio di corpus. Le battute e i
secondi in cui cadono li scrive la ripresa stessa in `docs/demo.tempi.json`;
questi sono quelli della ripresa italiana del 2026-08-26.

| a | battuta | cosa si vede |
|---|---|---|
| 3,0 s | stato vuoto | l'applicazione ha finito di caricare: le tre domande d'esempio, con la query vera in mono sotto la traduzione |
| 7,2 s | domanda inviata | clic sul primo esempio (MLMM e RMSE) |
| 8,0 s | fonti arrivate | **la colonna delle fonti si riempie prima che il modello scriva una parola** |
| 18,5 s | risposta finita | dieci secondi di attesa veri, con i marcatori nel testo e i verdetti per frase |
| 26,3 s | fonte aperta | la scheda fonte apre l'esploratore sul documento, con il chunk citato evidenziato |
| 35,4 s | conversazione nuova | si torna e si ricomincia |
| 36,4 s | astensione | la domanda fuori corpus: **il gate chiude in mezzo secondo**, e dice perché |
| 44,1 s | fine | |

**Quarantaquattro secondi**, la metà del tetto. Il margine non è sprecato: è ciò
che permette a una risposta lenta il doppio di restare dentro il criterio senza
toccare niente.

I tempi che il video mostra a schermo, letti dal fotogramma:

| | recupero | generazione | verifica | totale |
|---|---|---|---|---|
| ripresa italiana | 0,19 s | 8,03 s | 2,6 s | **10,82 s** |
| ripresa inglese | 0,11 s | 7,76 s | 2,12 s | **9,99 s** |

### Cosa il copione non fa

- **Non accelera e non taglia l'attesa.** Il criterio nomina proprio questo.
- **Non nasconde una citazione non sostenuta** se capita di vederne una: è il
  dato, non un difetto da montare via (U-07).
- **Non apre «Avanzate»**: in quaranta secondi una fila di parametri sembra
  complessità, non controllo.

---

## 4. Dalla ripresa alla GIF

Una GIF committata si vede sempre dentro un README; un mp4 con percorso relativo
dentro un tag `<video>` no. Quindi la GIF è l'artefatto, e il `.webm` resta
fuori dal repository.

```bash
python scripts/video_gif.py docs/demo.webm
# docs\demo.gif  3.48 MB  41.0 s  494 fotogrammi -> 315 distinti  1000x625, 128 colori
```

**Il solo taglio è in testa**, e non si indovina: si parte dalla battuta «stato
vuoto», cioè da quando l'applicazione ha finito di caricare, e il momento esatto
lo dichiara il `*.tempi.json` che la ripresa lascia accanto al video. Dentro il
copione non si taglia niente.

L'`ffmpeg` che Playwright si porta dietro ha **dodici filtri e nessun encoder
GIF**: serve solo a decodificare in PNG, e palette e animazione le fa Pillow,
che c'è già come dipendenza di Streamlit. Se sul PATH c'è un `ffmpeg` completo
viene preferito.

### Le tre scelte che decidono il peso

Misurate su questa ripresa:

| | peso |
|---|---|
| 1000 px, 128 colori, **senza dithering** | **4,5 MB** (la scelta) |
| 1000 px, 128 colori, con dithering | 8,0 MB |
| 1000 px, 64 colori, senza dithering | 3,6 MB |
| `disposal=2` invece di `1` | **40,5 MB** |

Il **dithering** su un'interfaccia di colori piatti aggiunge rumore che LZW non
comprime, e in cambio non migliora niente. Il **disposal** è la leva grossa: con
`1` Pillow scrive solo il rettangolo che cambia, e su una schermata ferma quel
rettangolo è vuoto; con `2` riscrive tutto ogni volta. E i **fotogrammi identici
si fondono**: una pausa di sette secondi costa un fotogramma lungo invece di
ottantaquattro uguali.

Il tetto che lo script segnala è **10 MB**. Se una ripresa lo supera si accorcia
il copione, non si abbassa la qualità: una GIF illeggibile non dimostra niente.

---

## 5. Dove stanno, nei due README

| file | dove | peso |
|---|---|---|
| `docs/demo.gif` | `README.md`, subito dopo i paragrafi di apertura | 3,48 MB |
| `docs/demo.en.gif` | `README.en.md`, nello stesso punto | 3,57 MB |
| `docs/screenshot.png` | `README.md`, in cima a «Cosa dimostra» | 0,31 MB |
| `docs/screenshot.en.png` | `README.en.md`, in cima a «What it demonstrates» | 0,30 MB |

Due riprese e non una: il README principale è italiano e quello accanto è
inglese, e mostrare un'interfaccia nell'altra lingua a chi legge la propria è
proprio la cosa che i due README esistono per evitare.

La didascalia sotto la GIF dice che l'attesa è vera. Non è decorazione: è la
frase che rende verificabile ciò che il criterio protegge, e il video la
sostiene mostrando la riga dei tempi.

---

## 6. La schermata ferma

```bash
npm run video -- --scatto        # docs/screenshot.png
npm run video -- --scatto --en   # docs/screenshot.en.png
```

Stesso copione, fermato a risposta verificata: è **l'unico fotogramma in cui
testo con i marcatori, verdetti per frase e colonna delle fonti si vedono
insieme**. Il puntatore disegnato viene tolto prima dello scatto (in un video
dice chi sta cliccando, in un'immagine ferma sarebbe un cerchio in mezzo al
testo) e la densità raddoppia: 2560 × 1600, ~300 kB.

---

## 7. Quando va rifatto

Il video invecchia con l'interfaccia, e uno che mostra una schermata che non
esiste più è peggio di nessun video. Va rifatto quando cambia:

- **gli esempi** (`ui/src/app/esempi.ts`): sono il copione, e
  `scripts/verify_esempi.py` dice se sono ancora validi;
- **le tre colonne**: U-13 (cronologia), U-17 (il testo indicizzato), U-18 (la
  corsia che si comprime), U-19 (la pagina «Che cos'è»);
- **le quattro etichette** che lo script cerca per nome (`chat.send`,
  `chat.stop`, `history.new`, `corpus.back`): se cambiano, la ripresa fallisce
  con un timeout invece di registrare qualcosa di sbagliato, ed è il verso
  giusto in cui rompersi;
- **il modello di default**: i tempi mostrati sono suoi;
- **l'indice**: OQ-09 ha mostrato che può cambiare da solo, e con lui cambia
  quale esempio risponde.

Rifarlo costa due comandi e cinque minuti. È il motivo per cui la ripresa è uno
script e non una registrazione a mano: una GIF che nessuno rifà è una GIF che fra
tre task mostra un prodotto che non esiste.
