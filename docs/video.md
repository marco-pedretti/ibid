# Il video di U-10: come si rifà, e le tre trappole che nasconde

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
npm run video              # italiano, tema scuro -> docs/demo.webm
npm run video -- --en      # inglese              -> docs/demo.en.webm
npm run video -- --chiaro  # tema chiaro
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

### La macchina, e il riavvio che vale tre volte la velocità

**Riavviare il backend prima di registrare.** Non è scaramanzia: le sessioni
ONNX (embedder, reranker, verificatore) restano residenti in VRAM per tutta la
vita del processo, e su una scheda da 12 GB spingono il resto nella memoria
condivisa. Misurato durante questo lavoro, con i contatori per processo:

| | dedicata | condivisa | la stessa domanda |
|---|---|---|---|
| dopo mezza giornata di sessione | 10,1 GB | **5,1 GB** | **26,0 s** |
| subito dopo aver riavviato il backend | 5,9 GB | 1,1 GB | **7,8 s** |

Il sintomo non è un errore: la risposta arriva, giusta, e ci mette tre volte
tanto. È lo stesso confonditore descritto in [`hardware.md`](hardware.md),
sezione «Il budget di una scheda da 12 GB», e la regola che ne era uscita vale
anche qui: **liberare batte ridurre**.

Da qui una riga di protocollo e un controllo automatico: se la risposta ha
impiegato più di quindici secondi, `npm run video` lo dice a fine ripresa
invece di lasciare pubblicare una latenza che non è quella del sistema.

---

## 2. Le trappole, che sono la parte interessante

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

### La VRAM occupata, che è l'errore nella direzione opposta

Se la cache regala una latenza più bassa del vero, la memoria contesa ne
produce una più alta: 26 secondi contro 8, per la ragione del paragrafo qui
sopra. **Nessuna delle due è la latenza del sistema**, e pubblicarle sarebbe
sbagliato in tutti e due i versi.

### Il freddo, che è l'altro modo di gonfiarla

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
| 8,1 s | fonti arrivate | **la colonna delle fonti si riempie prima che il modello scriva una parola** |
| 16,5 s | risposta finita | otto secondi di attesa veri, con i marcatori nel testo e i verdetti per frase |
| **22,9 s** | | **il confine fra le due GIF**: la prima finisce sulla risposta, la seconda comincia da qui |
| 24,3 s | fonte aperta | la scheda fonte apre l'esploratore sul documento, con il chunk citato evidenziato |
| 33,4 s | conversazione nuova | si torna e si ricomincia |
| 35,0 s | astensione | la domanda fuori corpus: **il gate chiude in mezzo secondo**, e dice perché |
| 46,5 s | fine | |

Le due GIF che ne escono durano **19,8 e 23,3 secondi**: insieme meno della
metà del tetto, e ciascuna un ciclo corto abbastanza da vedersi intero. Il margine non è
sprecato: è ciò che permette a una risposta lenta il doppio di restare dentro il
criterio senza toccare niente.

I tempi che il video mostra a schermo, letti dal fotogramma:

| | recupero | generazione | verifica | totale |
|---|---|---|---|---|
| ripresa italiana | 0,20 s | 7,77 s | 0,82 s | **8,80 s** |
| ripresa inglese | 0,15 s | 7,71 s | 0,59 s | **8,45 s** |

Le due riprese sono due esecuzioni diverse, quindi i numeri non coincidono: è
esattamente ciò che ci si aspetta da una latenza misurata invece che
dichiarata.

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
python scripts/video_gif.py docs/demo.webm --a "fonte aperta-1.4" -o docs/demo.gif
python scripts/video_gif.py docs/demo.webm --da "fonte aperta-1.4" -o docs/fonte.gif
# docs\demo.gif   1.79 MB  19.8 s  da  3.00 a 22.84 s
# docsonte.gif  2.84 MB  23.3 s  da 22.94 a 46.26 s
```

**Due GIF, una ripresa sola.** Il README mostra la chat con le citazioni in
cima e l'apertura della fonte in «Come funziona»: quaranta secondi sono un ciclo
lungo, e chi guarda una GIF in cima a una pagina ne vede i primi dieci. Non sono
due riprese: sono due finestre sullo stesso video continuo, ed è la ragione per
cui restano oneste. Due riprese separate obbligherebbero la seconda a partire da
una risposta già pronta, cioè a mostrare la schermata senza l'attesa che l'ha
prodotta.

`--da` e `--a` prendono un secondo oppure il **nome di una battuta**, con uno
scostamento facoltativo: `"fonte aperta-1.4"` taglia un secondo e quattro prima
che l'esploratore compaia, così il primo pezzo finisce sulla risposta e il
secondo comincia da lì.

**Il solo taglio è in testa**: la registrazione si apre sull'applicazione che
carica, e quei secondi di scheletro non sono il copione. Dentro il copione non
si taglia niente.

Il punto lo dichiara la prima battuta della ripresa, «stato vuoto», e **le
battute sono già sull'orologio del video**: verificato cercando nel filmato i
cambi di schermata più grossi, che cadono a 7,25 s, 24,33 s e 33,42 s contro
7,25 / 24,34 / 33,44 registrati dalla ripresa.

Senza il file dei tempi si ripiega su una ricerca nei fotogrammi (finché
l'applicazione carica lo schermo non cambia). **Quel ripiego era la strada
principale, e sbagliava**: in tema scuro la comparsa dell'applicazione sposta
meno pixel, la soglia non scattava e il taglio scivolava tre secondi più in là.
Da lì era nata anche la convinzione, sbagliata, che il video fosse in ritardo
sull'orologio dello script.

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

| file | dove | durata | peso |
|---|---|---|---|
| `docs/demo.gif` | `README.md`, dopo i paragrafi di apertura | 19,8 s | 1,79 MB |
| `docs/fonte.gif` | `README.md`, in «Come funziona» | 23,3 s | 2,84 MB |
| `docs/demo.en.gif` | `README.en.md`, stesso punto | 19,8 s | 1,92 MB |
| `docs/fonte.en.gif` | `README.en.md`, stesso punto | 22,3 s | 2,64 MB |
| `docs/screenshot.png` | `README.md`, in cima a «Cosa dimostra» | | 0,31 MB |
| `docs/screenshot.en.png` | `README.en.md`, stesso punto | | 0,30 MB |

Due lingue e non una: il README principale è italiano e quello accanto è
inglese, e mostrare un'interfaccia nell'altra lingua a chi legge la propria è
proprio la cosa che i due README esistono per evitare. Quattro file, quindi, ma
il peso totale è quello di prima: spezzare non aggiunge byte, li divide.

**Tutte e quattro in tema scuro**, che è la scelta di Marco per come il progetto
si presenta. Il chiaro resta a un flag di distanza (`--chiaro`), e il tema si
scrive nel deposito prima che la pagina si dipinga: lo stesso valore che legge
lo script in testa a `index.html`, così non c'è il lampo bianco all'avvio.

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
