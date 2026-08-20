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
 * **Il numero di righe viene dal numero di pezzi.** Un documento da dieci chunk
 * in dodici righe sarebbe una riga ogni pezzo; uno da 261 in tre righe darebbe
 * pezzi da mezzo pixel. Vedi `quanteRighe`.
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
}

/**
 * Quante righe per un documento di `n` pezzi.
 *
 * Un pezzo ogni venti per riga e' la densita' a cui, in una colonna da ~600 px,
 * il pezzo mediano resta largo una trentina di pixel: abbastanza da vederlo e da
 * prenderlo col puntatore. Il minimo di tre viene dal mockup, che ne disegna
 * tre; il massimo di dodici e' dove la mappa smette di essere un colpo d'occhio
 * e diventa una parete.
 */
export function quanteRighe(n: number): number {
  if (n <= 0) return 0;
  return Math.min(Math.max(Math.ceil(n / 20), 3), 12);
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

  for (let i = 0; i < lunghezze.length; i += 1) {
    let resto = totale > 0 ? Math.max(lunghezze[i], 0) : 1;
    // `do` e non `while`: un chunk lungo zero deve comparire una volta, e con
    // `while` non entrerebbe mai nel corpo.
    do {
      const spazio = capacita - riempita;
      const parte = Math.min(resto, spazio);
      resto -= parte;
      riempita += parte;
      const pieno = riempita >= capacita - 1e-9;
      riga.push({ indice: i, frazione: parte / capacita, spezzato: resto > 0 });
      if (pieno) aCapo();
    } while (resto > 0);
  }

  if (riga.length > 0) fuori.push(riga);
  return fuori;
}
