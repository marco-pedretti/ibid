/**
 * La mappa di un documento: quanto e' grande ciascun pezzo, davvero.
 *
 * **Perche' le proporzioni.** «Com'e' stato spezzato» non e' «in quanti pezzi»:
 * e' *quanto sono disuguali*. Su `NYSE_SHW_2017` il chunk piu' grande e' 6.302
 * caratteri e il piu' piccolo 19 — cioe' 330 volte meno — e con tessere tutte
 * larghe uguali quella differenza spariva, che era esattamente la cosa da
 * mostrare. La pipeline `table_heavy` esiste perche' una tabella non si spezza:
 * il risultato e' un documento fatto di pezzi molto diversi, e la mappa deve
 * farlo vedere senza che nessuno lo scriva.
 *
 * **E' una striscia continua, mandata a capo.** Non una griglia di tessere: il
 * documento e' una cosa sola, e i pezzi si susseguono. Quando un pezzo non entra
 * nella riga, **passa a capo come una parola lunga** invece di essere spostato
 * intero alla riga dopo: spostarlo lascerebbe un buco a fine riga, e un buco in
 * una mappa di proporzioni si legge come «qui non c'e' niente».
 *
 * **La scala viene dal pezzo piu' piccolo di questo documento.** Gli si da' una
 * misura minima e tutto il resto sta in proporzione a lui: e' il numero di righe
 * a seguire, non il contrario. Due documenti diversi non sono percio'
 * confrontabili fra loro, ed e' accettato — la mappa risponde a «com'e' fatto
 * questo documento». Vedi `quanteRighe`.
 *
 * Le frazioni qui sono **esatte**: un pezzo da 19 caratteri su 348.942 esce
 * larghissimo quanto niente, ed e' vero. Che si veda comunque e' un problema di
 * chi disegna — una larghezza minima in CSS — e non di questo conto, che se la
 * prendesse in carico smetterebbe di essere una proporzione.
 */

/** Un tratto di riga: da quale chunk viene, e quanta parte della riga occupa. */
export interface Pezzo {
  /** L'indice del chunk nell'elenco del documento. */
  indice: number;
  /** Frazione della **riga**, fra 0 e 1. */
  frazione: number;
  /** Il pezzo continua nella riga seguente: e' un chunk andato a capo. */
  spezzato: boolean;
  /** Il pezzo **viene** dalla riga precedente. Serve a chi disegna: un chunk
   *  spezzato va arrotondato solo dalla parte in cui finisce davvero, altrimenti
   *  un pezzo solo sembra due. */
  continuazione: boolean;
}

/**
 * Un chunk che non ha niente da leggere.
 *
 * Misurato sull'indice: l'1,13% dei chunk di `ledger` sta in 60 caratteri, e i
 * piu' frequenti sono `Powered by TCPDF (www.tcpdf.org)` (una pagina di
 * filigrana del generatore di PDF), `This page intentionally left blank` e
 * `![](images/0_0.jpg)` — una copertina che e' solo un'immagine. Su
 * `open_ragbench` sono lo 0,23% e sono veri: ringraziamenti, conflitti di
 * interesse, sezioni corte davvero.
 *
 * Serve **solo a scegliere la scala**: questi chunk restano sulla mappa, perche'
 * sono nell'indice e la mappa dice cosa c'e' nell'indice. Ma lasciare che una
 * filigrana decida quanto e' grande un pezzo del documento vuol dire scalare
 * tutto su un artefatto — e sono i due casi in cui il conto passava da 22 righe
 * a 147.
 *
 * La soglia e' 40 caratteri **dopo** aver tolto i riferimenti alle immagini: la
 * filigrana ne ha 32, «pagina lasciata bianca» 34, e il piu' corto con del testo
 * vero nei documenti guardati ne ha 100.
 */
const SENZA_TESTO = 40;
const IMMAGINE = /!\[[^\]]*\]\([^)]*\)/g;

export function haContenuto(testo: string): boolean {
  return testo.replace(IMMAGINE, "").trim().length >= SENZA_TESTO;
}

/** Quanta parte di una riga deve occupare, come minimo, il pezzo piu' piccolo
 *  con del testo. Su una colonna da ~500 px sono quattro pixel. */
const MINIMA = 0.008;

/** Meno di cosi' la mappa non ha presenza: e' una striscia sottile in cima a una
 *  colonna vuota, e chi la guarda non capisce che e' il documento. */
const RIGHE_MINIME = 6;

/** Piu' di cosi' smette di essere un colpo d'occhio e diventa una parete da
 *  scorrere. Quando il tetto morde, i pezzi piu' piccoli scendono sotto la
 *  misura minima e si fermano al fondo che gli da' il disegno. */
const RIGHE_MASSIME = 24;

/**
 * Quante righe, **scalando dal pezzo piu' piccolo di questo documento**.
 *
 * La regola e' quella e non un numero fisso: il pezzo piu' piccolo con del testo
 * riceve una misura minima, e tutti gli altri stanno in proporzione a lui. Ne
 * segue che due documenti non sono confrontabili fra loro — un chunk largo
 * uguale su due mappe puo' essere lungo il doppio — ed e' accettato: la mappa
 * risponde a «com'e' fatto **questo** documento», non a «quale dei due ha i
 * pezzi piu' grandi».
 *
 * Quanto costa, misurato sui documenti veri: `2401.02564v2` (15 chunk, il piu'
 * piccolo e' 1/18 del piu' grande) chiederebbe **una** riga, e prende le sei del
 * minimo; `NYSE_SHW_2017` ne chiede 22 e le ottiene; `NASDAQ_LOOP_2017` ne
 * chiederebbe 37 e si ferma a 24.
 */
export function quanteRighe(testi: readonly string[]): number {
  if (testi.length === 0) return 0;

  const totale = testi.reduce((a, t) => a + t.length, 0);
  const conTesto = testi.filter(haContenuto).map((t) => t.length);
  const base = Math.min(...(conTesto.length > 0 ? conTesto : testi.map((t) => t.length)));
  if (totale <= 0 || base <= 0) return RIGHE_MINIME;

  const servono = Math.ceil((totale / base) * MINIMA);
  return Math.min(Math.max(servono, RIGHE_MINIME), RIGHE_MASSIME);
}

/**
 * Le righe della mappa: ogni riga un elenco di tratti che la riempiono.
 *
 * `lunghezze` sono i caratteri di ciascun chunk, nell'ordine del documento.
 *
 * Un chunk lungo **zero** compare lo stesso, con frazione zero: e' un pezzo del
 * documento e la mappa dice quanti pezzi ci sono. Toglierlo perche' non si vede
 * sarebbe far decidere alla larghezza cosa esiste.
 */
export function righeMappa(lunghezze: readonly number[], righe: number): Pezzo[][] {
  if (lunghezze.length === 0 || righe <= 0) return [];

  const totale = lunghezze.reduce((a, b) => a + Math.max(b, 0), 0);
  // Tutti i chunk vuoti: non c'e' una proporzione da mostrare, e si ripiega su
  // pezzi uguali. Dividere per zero darebbe `NaN` in ogni larghezza.
  const capacita = totale > 0 ? totale / righe : lunghezze.length / righe;

  const fuori: Pezzo[][] = [];
  let riga: Pezzo[] = [];
  let riempita = 0;

  const aCapo = () => {
    fuori.push(riga);
    riga = [];
    riempita = 0;
  };

  // **Una tolleranza, e non zero.** Con `capacita = totale / righe` la somma dei
  // pezzi di una riga non torna mai esatta in virgola mobile: l'ultimo chunk
  // avanzava di un milionesimo di riga e quel milionesimo andava a capo,
  // aprendo una riga in piu' con dentro un filo largo due pixel. Si vedeva, ed
  // era un errore di arrotondamento travestito da dato.
  const tolleranza = capacita * 1e-6;

  for (let i = 0; i < lunghezze.length; i += 1) {
    let resto = totale > 0 ? Math.max(lunghezze[i], 0) : 1;
    let continuazione = false;
    // `do` e non `while`: un chunk lungo zero deve comparire una volta, e con
    // `while` non entrerebbe mai nel corpo.
    do {
      const spazio = capacita - riempita;
      const parte = Math.min(resto, spazio);
      resto -= parte;
      riempita += parte;
      const pieno = riempita >= capacita - tolleranza;
      riga.push({
        indice: i,
        frazione: parte / capacita,
        spezzato: resto > tolleranza,
        continuazione,
      });
      continuazione = true;
      if (pieno) aCapo();
    } while (resto > tolleranza);
  }

  if (riga.length > 0) fuori.push(riga);
  return fuori;
}
