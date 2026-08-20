/**
 * Quanto e' larga ciascuna delle tre colonne dell'esploratore.
 *
 * **Perche' si spostano.** Le tre colonne servono a cose che cambiano di
 * dimensione a seconda di cosa si sta guardando: la mappa di un documento da
 * dieci chunk sta in tre righe, quella di uno da 261 ne prende venti; un chunk
 * di prosa e' corto, uno che e' una tabella di bilancio vuole tutta la larghezza
 * che gli si puo' dare. Una misura fissa va bene per uno dei casi e stretta per
 * gli altri, e quale sia il caso lo sa solo chi guarda.
 *
 * **Le due esterne hanno una misura, quella di mezzo prende il resto.** Non e'
 * simmetrico apposta: cosi' allargando la finestra cresce la mappa, che e'
 * l'unica delle tre che sa usare lo spazio in piu' — le altre due sono un elenco
 * e una colonna di lettura, e oltre una certa larghezza peggiorano invece di
 * migliorare.
 *
 * **Nessuna scende sotto il proprio minimo, nemmeno quella che non si sta
 * trascinando.** E' la parte che vale la pena provare: tirando il manico di
 * destra verso sinistra si spinge la mappa, non la colonna di destra, e senza un
 * limite la si farebbe sparire tirando abbastanza. Una colonna a zero non e'
 * «chiusa», e' rotta — e per riaprirla servirebbe un manico che non si vede piu'.
 */

export interface Larghezze {
  /** L'elenco dei documenti, a sinistra. */
  documenti: number;
  /** Il chunk scelto, a destra. */
  dettaglio: number;
}

/**
 * Le misure di partenza.
 *
 * `documenti` viene dal mockup e regge: un elenco di nomi come `NYSE_SHW_2017`
 * ci sta senza troncare. `dettaglio` no — nel mockup e' 250 px, e li' dentro c'e'
 * una tabella di bilancio: il testo veniva fuori una colonna di parole singole.
 * Parte largo abbastanza da leggere una tabella, e chi vuole piu' mappa lo
 * stringe.
 */
export const PREDEFINITE: Larghezze = { documenti: 210, dettaglio: 440 };

/**
 * Sotto queste, una colonna smette di fare il proprio lavoro.
 *
 * Non sono numeri tondi presi a caso: `documenti` e' quanto serve al nome di un
 * documento piu' il conteggio dei chunk senza troncare; `mappa` e' circa dieci
 * tessere per riga, sotto cui la forma dello spezzettamento non si legge piu';
 * `dettaglio` e' la larghezza minima perche' una tabella a tre colonne resti
 * incolonnata invece di andare a capo dentro ogni cella.
 */
export const MINIME = { documenti: 150, mappa: 200, dettaglio: 260 } as const;

function entro(v: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, v));
}

/**
 * Sposta un manico di `delta` pixel, dentro i limiti di tutte e tre.
 *
 * `totale` e' la larghezza che le tre colonne hanno insieme: serve perche' il
 * limite di una dipende dalle altre due — allargare a sinistra restringe la
 * mappa, e quando la mappa e' al minimo il manico deve fermarsi.
 *
 * Un `totale` troppo piccolo per i tre minimi non e' un errore da sollevare: e'
 * una finestra stretta. Le misure si riportano ai minimi e la pagina scorrera' —
 * meglio tre colonne che sporgono di tre colonne schiacciate a niente.
 */
export function ridimensiona(
  l: Larghezze,
  quale: keyof Larghezze,
  delta: number,
  totale: number,
): Larghezze {
  if (quale === "documenti") {
    const max = totale - l.dettaglio - MINIME.mappa;
    return {
      ...l,
      documenti: entro(l.documenti + delta, MINIME.documenti, Math.max(max, MINIME.documenti)),
    };
  }
  // Il manico di destra si trascina **verso** la colonna: tirandolo a sinistra
  // (`delta` negativo) il dettaglio si allarga. Senza questo segno il manico
  // andrebbe dalla parte opposta al dito.
  const max = totale - l.documenti - MINIME.mappa;
  return {
    ...l,
    dettaglio: entro(l.dettaglio - delta, MINIME.dettaglio, Math.max(max, MINIME.dettaglio)),
  };
}

/** Cosa finisce in `grid-template-columns`: due misure e il resto. */
export function griglia(l: Larghezze): string {
  return `${l.documenti}px 5px minmax(0, 1fr) 5px ${l.dettaglio}px`;
}

/**
 * Le misure ricordate, o quelle di partenza.
 *
 * Si ricordano perche' sono una **preferenza** e non un esperimento: «voglio piu'
 * spazio per leggere un chunk» vale anche domani, come il tema e il dataset. La
 * barra di composizione non si ricorda per la ragione opposta, ed e' scritta li'.
 *
 * Qualunque cosa di storto nel deposito si ignora e si riparte dai predefiniti:
 * un numero fuori scala scritto a mano nel `localStorage` non deve poter lasciare
 * una colonna invisibile.
 */
export function leggi(grezzo: string | null): Larghezze {
  if (grezzo === null) return { ...PREDEFINITE };
  try {
    const v: unknown = JSON.parse(grezzo);
    if (typeof v !== "object" || v === null) return { ...PREDEFINITE };
    const { documenti, dettaglio } = v as Partial<Larghezze>;
    return {
      documenti: numero(documenti, PREDEFINITE.documenti, MINIME.documenti),
      dettaglio: numero(dettaglio, PREDEFINITE.dettaglio, MINIME.dettaglio),
    };
  } catch {
    return { ...PREDEFINITE };
  }
}

function numero(v: unknown, predefinito: number, minimo: number): number {
  return typeof v === "number" && Number.isFinite(v) && v >= minimo ? v : predefinito;
}
