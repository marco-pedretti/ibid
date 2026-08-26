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

## 2. Le quattro trappole, che sono la parte interessante

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

### Lo schermo fermo, che nel video non esiste

**Il filmato riceve un fotogramma solo quando la pagina ne dipinge uno**, e per
il resto ripete l'ultimo che ha. Un'interfaccia appena caricata e ferma non
dipinge niente: il video continuava a mostrare lo scheletro del caricamento
**fino al primo clic**, cioè fino al primo momento in cui qualcosa si muoveva.

Misurato: la ripresa registra lo stato vuoto a 3,00 s e il video lo mostra a
6,50. Allungando la pausa a 6,5 s la comparsa si è spostata a 10,13, cioè di
nuovo esattamente al clic: la prova che a dipingere era il gesto, non
l'applicazione.

Il rimedio è una pausa che **respira**: il puntatore disegnato si sposta di un
pixel ogni 250 ms, un ridisegno per battito. Non è finzione, è il contrario:
senza, il video mostra uno stato che a schermo era già passato.

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
| 3,0 s | stato vuoto | l'interfaccia carica e ferma: le tre domande d'esempio, con la query vera in mono sotto la traduzione |
| 5,8 s | domanda inviata | clic sul primo esempio (MLMM e RMSE) |
| 6,6 s | fonti arrivate | **la colonna delle fonti si riempie prima che il modello scriva una parola** |
| 15,2 s | risposta finita | otto secondi di attesa veri, con i marcatori nel testo e i verdetti per frase |
| **21,5 s** | | **il confine fra le due GIF**: la prima finisce sulla risposta, la seconda comincia da qui |
| 22,9 s | fonte aperta | la scheda fonte apre l'esploratore sul documento, con il chunk citato evidenziato |
| 32,0 s | conversazione nuova | si torna e si ricomincia |
| 33,6 s | astensione | la domanda fuori corpus: **il gate chiude in mezzo secondo**, e dice perché |
| 45,1 s | fine | |

Le due GIF che ne escono durano **18,3 e 23,5 secondi**: insieme meno della metà
del tetto, e ciascuna un ciclo corto abbastanza da vedersi intero.

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
# docs\demo.gif   3.49 MB  18.3 s  da  3.15 a 21.41 s  1280x800, 256 colori
# docsonte.gif  5.29 MB  23.5 s  da 21.48 a 44.97 s  1280x800, 256 colori
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

Il punto **si cerca nei fotogrammi**: finché l'applicazione carica lo schermo non
cambia, quindi il primo fotogramma diverso da quello del caricamento è l'inizio
del copione. La prima battuta della ripresa **non si può usare al suo posto**, e
il perché è la trappola descritta nel §2: il video riceve un fotogramma solo
quando la pagina ne dipinge uno.

Tutte le **altre** battute invece cadono dove il video le mostra, ed è per questo
che `--da` e `--a` accettano un nome: verificato su una ripresa, domanda inviata
7,25 contro 7,25, fonte aperta 24,34 contro 24,33, conversazione nuova 33,44
contro 33,42.

L'`ffmpeg` che Playwright si porta dietro ha **dodici filtri e nessun encoder
GIF**: serve solo a decodificare in PNG, e palette e animazione le fa Pillow,
che c'è già come dipendenza di Streamlit. Se sul PATH c'è un `ffmpeg` completo
viene preferito.

### Le scelte che decidono qualità e peso

Misurate sui venti secondi della prima GIF:

| | peso |
|---|---|
| **1280 px, 256 colori, senza dithering** | **3,21 MB** (la scelta) |
| 1280 px, 128 colori | 2,77 MB |
| 1000 px, 256 colori | 2,03 MB |
| 1000 px, 128 colori | 1,77 MB (com'era) |
| WebP 1280 px, qualità 90 | 2,94 MB |
| APNG 1280 px, senza perdita | 18,7 MB |
| `disposal=2` invece di `1` | dieci volte tanto |

**La larghezza conta più dei colori.** Ridurre 1280 a 1000 ricampiona ogni
lettera, ed è ciò che faceva sembrare le GIF «compresse»: a dimensione nativa il
testo è esattamente quello che il browser ha disegnato. I 256 colori sono il
massimo che il formato regge, e tolgono le bande dalle superfici scure, che con
128 si appiattivano l'una sull'altra.

**Non WebP, che a parità di qualità pesa meno ed è a 24 bit**: perché una GIF la
disegna qualunque cosa apra un README, e un'immagine rotta in cima alla pagina
costa più del megabyte risparmiato. APNG sarebbe senza perdita e pesa sei volte
tanto.

Il **dithering** su un'interfaccia di colori piatti aggiunge rumore che LZW non
comprime, e in cambio non migliora niente. Il **disposal** è la leva grossa: con
`1` Pillow scrive solo il rettangolo che cambia, e su una schermata ferma quel
rettangolo è vuoto; con `2` riscrive tutto ogni volta. E i **fotogrammi identici
si fondono**: una pausa di sette secondi costa un fotogramma lungo invece di
ottantaquattro uguali.

**Meno fotogrammi al secondo non vuol dire meno peso**, ed è il contrario di
quello che sembra. Sulla seconda GIF: 12 fps 4,90 MB, 10 fps 4,99, 8 fps 5,31,
15 fps 5,41, 20 fps 6,38. Sotto i dodici i campioni cadono più lontani fra loro,
quindi **si somigliano di meno**: se ne fondono meno e ognuno porta un rettangolo
di differenza più grande. Dodici è il minimo di quella curva, non un
compromesso.

Il tetto che lo script segnala è **10 MB**. Se una ripresa lo supera si accorcia
il copione, non si abbassa la qualità: una GIF illeggibile non dimostra niente.

---

## 5. Dove stanno, nei due README

| file | dove | durata | peso |
|---|---|---|---|
| `docs/demo.gif` | `README.md`, dopo i paragrafi di apertura | 18,3 s | 3,49 MB |
| `docs/fonte.gif` | `README.md`, in «Come funziona» | 23,5 s | 5,29 MB |
| `docs/demo.en.gif` | `README.en.md`, stesso punto | 17,9 s | 3,34 MB |
| `docs/fonte.en.gif` | `README.en.md`, stesso punto | 24,0 s | 4,78 MB |
| `docs/screenshot.png` | `README.md`, in cima a «Cosa dimostra» | | 0,31 MB |
| `docs/screenshot.en.png` | `README.en.md`, stesso punto | | 0,30 MB |

Due lingue e non una: il README principale è italiano e quello accanto è
inglese, e mostrare un'interfaccia nell'altra lingua a chi legge la propria è
proprio la cosa che i due README esistono per evitare. **Diciassette megabyte in
tutto**, nove per pagina: è il prezzo della dimensione nativa, ed è stato pagato
di proposito dopo che le prime versioni, a 1000 px, si leggevano come
compresse.

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
