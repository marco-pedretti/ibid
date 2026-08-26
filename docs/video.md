# Il video di U-10: copione, tempi misurati, esportazione

Il criterio di U-10 è breve e vincola più di quanto sembri:

> ≤ 90 secondi, mostra query → risposta citata → apertura della fonte, **senza
> tagli che nascondano la latenza reale**.

L'ultima parte è la difficile. Una risposta di questo sistema costa una decina
di secondi, e la tentazione di tagliarli è esattamente ciò che il criterio
vieta: il progetto misura una pipeline che gira su una scheda da 12 GB, e un
video che finge il contrario mente sulla cosa che il README dichiara. **Una
ripresa sola, nessuna accelerazione, nessun taglio sull'attesa.**

Questa pagina esiste perché la ripresa vada bene al primo tentativo, e perché
possa essere rifatta identica quando l'interfaccia cambierà.

---

## 1. Prima di premere REC

### I servizi

```bash
curl http://localhost:6333/collections      # Qdrant: le sette collection
curl http://localhost:11434/v1/models       # l'endpoint LLM
curl http://127.0.0.1:8000/health           # il backend: {"status":"ok"}
make dev                                    # backend + interfaccia, su :5173
```

### Gli esempi devono ancora fare quello che dichiarano

```bash
python scripts/verify_esempi.py
```

Deve chiudere con `Ogni esempio fa quel che dichiara, in ANN e in esatta`.
Verificato il 2026-08-26: sei esempi su sei, con i due margini di astensione
identici a quelli registrati (+0,0227 su `open_ragbench`, +0,0078 su `ledger`).

**Non è una formalità.** Prima di D-17 la demo si asteneva su una domanda che
proponeva lei, e su `ledger` solo il 35% delle query d'oro porta il proprio
chunk nei primi cinque: un esempio che smette di funzionare è il modo più
facile di sprecare una ripresa.

### Il riscaldamento, che vale dieci secondi

**La prima domanda dopo un periodo di inattività costa circa il doppio.**
Misurato oggi sulla stessa domanda, due chiamate consecutive: **24,8 s a
freddo, 14,3 s a caldo.** Il tempo in più non è la pipeline, è il motore che
rimette il modello dove serve.

Quindi: **fare girare il copione intero una volta, e solo dopo registrare.**
Vale anche per la fonte da aprire, perché la prima apertura dell'esploratore
scarica l'elenco dei documenti.

### La macchina

Il backend tiene circa 3,5 GB fra embedder, reranker e verificatore. Con
`gemma4:latest` (E4B, 3,3 GB) ci si sta comodi; con il 12B no, e il sintomo non
è un errore ma una risposta lenta il doppio. Il conto completo e il comando che
lo verifica stanno in [`hardware.md`](hardware.md), sezione «Il budget di una
scheda da 12 GB». Prima della ripresa vale la pena controllare che non ci siano
runner orfani:

```powershell
"orfani: $((Get-Process llama-server -ErrorAction SilentlyContinue | Measure-Object).Count)"
```

### L'inquadratura

- **Finestra del browser attorno a 1440 × 900**, così che le tre colonne stiano
  tutte dentro e il testo resti leggibile una volta scalato a ~1000 px.
- **Lingua e tema**: quelli che si vogliono mostrare, scelti *prima* di
  registrare. Cambiarli durante la ripresa spende secondi e non dimostra niente
  che il README non dica già.
- **Corsia aperta**, così che si veda che i dataset e l'esploratore esistono.
- Niente notifiche di sistema, niente barra dei preferiti con roba personale.

---

## 2. I tempi, misurati

Le quattro domande d'esempio che rispondono, misurate il 2026-08-26 attraverso
`/query/stream`, due chiamate consecutive ciascuna, a motore caldo:

| esempio | prima parola | risposta finita | token |
|---|---|---|---|
| `open_ragbench` 1, MLMM e RMSE | 2,5 / 4,2 s | **14,2 / 15,8 s** | 123 |
| `open_ragbench` 2, location-class independence | 2,5 / 2,6 s | 24,5 / 24,6 s | 235 |
| `ledger` 1, spese SG&A di Sherwin-Williams | 2,4 / 2,6 s | **6,2 / 6,4 s** | 35 |
| `ledger` 2, dividendi 2017 | 2,5 / 16,0 s | 5,7 / 19,1 s | 27 |

Le due domande fuori corpus non generano niente: **il gate chiude in 0,3
secondi**, prima di qualunque token (su `ledger`, punteggio 0,8160 contro una
soglia di 0,8289).

Tre cose che questi numeri dicono e che cambiano il copione:

1. **Le fonti compaiono prima della prima parola.** L'evento `chunks` arriva a
   0,3 s, il primo token fra i 2 e i 4. La colonna di destra si riempie mentre
   il modello sta ancora leggendo, ed è la cosa da inquadrare durante l'attesa:
   l'attesa si riempie invece di essere subita.
2. **La seconda domanda di `open_ragbench` costa 24 secondi** perché la risposta
   è lunga il doppio (235 token contro 123). Va bene come contenuto, male come
   copione: fuori dai 90 secondi non ci si arriva, ma il ritmo sì.
3. **Il valore anomalo esiste e va conosciuto**: `ledger` 2 ha dato 16 s alla
   prima parola in una delle due chiamate e 2,5 s nell'altra. È il motivo per
   cui il riscaldamento non è un consiglio.

---

## 3. Il copione

Un dataset solo, `open_ragbench`, nessun cambio di corpus: il cambio costa
secondi e non mostra niente che il resto non mostri già. Tutti i tempi sono
quelli misurati sopra, più il tempo di lettura umana.

| da | a | cosa si vede |
|---|---|---|
| 0:00 | 0:05 | Lo stato vuoto: le tre domande d'esempio, con la query vera in mono sotto la traduzione. Si legge che il corpus è `open_ragbench` |
| 0:05 | 0:08 | Clic sul **primo esempio** (MLMM e RMSE). La domanda entra nel campo e parte |
| 0:08 | 0:11 | **Le fonti si riempiono a destra**, prima che il modello scriva una parola |
| 0:11 | 0:25 | La risposta scorre, con i marcatori `[1]` e `[2]` dentro il testo. **Nessun taglio qui**: sono i quattordici secondi veri |
| 0:25 | 0:33 | I verdetti per frase: pastiglia, glifo e parola. Tre citazioni, tutte sostenute (0,749, 0,839, 0,537) |
| 0:33 | 0:45 | Clic su una scheda fonte: si apre **l'esploratore del corpus** sul documento giusto, con il chunk citato selezionato. È l'«apertura della fonte» che il criterio chiede |
| 0:45 | 0:50 | Ritorno alla conversazione |
| 0:50 | 0:55 | Clic sul **terzo esempio**, quello fuori corpus |
| 0:55 | 1:05 | **Il sistema si astiene in mezzo secondo**, e dice perché. Nessuna risposta inventata |
| 1:05 | 1:10 | Fine |

**Settanta secondi, con venti di margine.** Il margine serve: un clic che manca
il bersaglio, mezzo secondo di esitazione, e si resta comunque sotto i 90.

Se si vuole una versione più corta, la sostituzione è una sola: il primo
esempio di `ledger` (6,2 s, una frase sola con un numero e due citazioni) al
posto di quello di `open_ragbench`. Si perde la risposta lunga con tre
affermazioni verificate e si guadagnano otto secondi. **Non si sostituisce
invece l'astensione**: è metà della dimostrazione, e il README la dichiara.

### Cosa non fare

- **Non accelerare, non tagliare l'attesa, non stringere lo zoom sul testo che
  scorre per far sembrare che scorra più in fretta.** Il criterio nomina proprio
  questo.
- **Non nascondere una citazione non sostenuta** se capita di vederne una: è il
  dato, non un difetto da montare via (U-07).
- Non mostrare «Avanzate» a meno di non spiegarlo: in novanta secondi una fila
  di parametri sembra complessità, non controllo.

---

## 4. Registrare

Su questa macchina **`ffmpeg` non c'è** (verificato il 2026-08-26), e nemmeno
ImageMagick o gifsicle. Le due strade che non richiedono di installarne uno:

| strumento | cosa produce | note |
|---|---|---|
| **Xbox Game Bar** (`Win + Alt + R`) | mp4 in `Video/Acquisizioni` | è già in Windows 11, registra una finestra sola, nessuna installazione |
| **ScreenToGif** | GIF, direttamente | portabile, esporta GIF senza passare da `ffmpeg`, e permette di scegliere fotogrammi e palette |

Se si registra in mp4 e serve la GIF, allora `ffmpeg` va installato, e la
conversione con palette dedicata è quella che regge la qualità:

```bash
ffmpeg -i demo.mp4 -vf "fps=12,scale=1000:-1:flags=lanczos,palettegen=stats_mode=diff" -y palette.png
ffmpeg -i demo.mp4 -i palette.png -lavfi "fps=12,scale=1000:-1:flags=lanczos,paletteuse=dither=bayer:bayer_scale=3" -y demo.gif
```

**Non sono state provate su questa macchina**, perché `ffmpeg` non c'è: sono la
forma standard in due passaggi, e vanno verificate guardando il risultato.

### Le dimensioni

Il file finisce **dentro il repository**, quindi il peso è per sempre.

- larghezza **1000 px**, che su GitHub si legge senza ingrandire;
- **10-12 fotogrammi al secondo**: l'interfaccia non ha animazioni che ne
  chiedano di più, e il testo che scorre resta leggibile;
- obiettivo **sotto i 10 MB**. Se non ci si sta, si accorcia il copione prima di
  abbassare la qualità: un video illeggibile non dimostra niente.

---

## 5. Dove va, e in che forma

**Una GIF committata si vede sempre**, dentro il README, senza dipendere da
nulla. Un mp4 nel repository no: GitHub lo rende quando è un file caricato
(release o commento), e un percorso relativo dentro un tag `<video>` non è
garantito. Quindi: **GIF nel README**, e l'mp4, se lo si vuole tenere, come
allegato di una release.

Il posto è **subito dopo i due paragrafi di apertura e prima di «Avvio»**: il
video è l'amo, e chi scorre oltre ha già visto la cosa.

```markdown
![Una domanda, la risposta con le citazioni verificate, e la fonte aperta sul chunk citato](docs/demo.gif)

<sub>Ripresa unica, nessun taglio: i quattordici secondi di attesa sono quelli veri, su una RX 6750 XT.</sub>
```

E in `README.en.md`, con lo stesso file:

```markdown
![A question, the answer with verified citations, and the source opened at the cited chunk](docs/demo.gif)

<sub>Single take, no cuts: the fourteen seconds of waiting are the real ones, on an RX 6750 XT.</sub>
```

La didascalia non è decorazione: dice al lettore che l'attesa è vera, che è
esattamente ciò che il criterio protegge.

---

## 6. Lo screenshot che U-11 ha lasciato indietro

Si cattura nella stessa sessione, perché serve la stessa macchina nello stesso
stato. Il fotogramma giusto è quello del **minuto 0:33**: risposta completa con
i marcatori, verdetti per frase visibili, colonna delle fonti piena. È l'unica
immagine che mostra le tre cose insieme.

- `docs/screenshot.png`, larghezza 1400 px, PNG;
- va in `README.md` e `README.en.md` accanto alla sezione «Cosa dimostra», o al
  posto della GIF per chi legge da un client che non anima le immagini.

---

## 7. Quando va rifatto

Il video invecchia con l'interfaccia, e un video che mostra una schermata che
non esiste più è peggio di nessun video. Va rifatto quando cambia una di queste
cose:

- **gli esempi** (`ui/src/app/esempi.ts`): sono il copione, e `verify_esempi.py`
  è ciò che dice se sono ancora validi;
- **le tre colonne**: U-13 (cronologia nella corsia), U-17 (il testo indicizzato
  accanto alla mappa), U-18 (la corsia che si comprime), U-19 (la pagina «Che
  cos'è»);
- **il modello di default**: i tempi mostrati sono suoi, e con un modello più
  lento il copione non sta più in 90 secondi;
- **l'indice**: OQ-09 ha mostrato che può cambiare da solo, e con lui cambia
  quale esempio risponde.

Rifarlo costa venti minuti se questa pagina è aggiornata, e mezza giornata se
non lo è.
