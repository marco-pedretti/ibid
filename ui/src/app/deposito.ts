/**
 * Cio' che il browser ricorda di questo progetto: un posto solo.
 *
 * **Era in sei.** `avvio.ts`, `corsia.ts`, `Corpus.tsx`, `i18n.tsx`,
 * `theme.tsx` e `scelta-dataset.ts` aprivano `localStorage` per conto proprio,
 * ognuno col suo `try/catch` e con lo stesso commento riscritto: *«deposito
 * negato (finestra privata, iframe): si parte…»*. Sei copie di tre righe non
 * sono un problema di lunghezza — sono un invariante che nessuno controlla, e
 * si vedeva: due di quei file portavano in nota l'elenco **scritto a mano**
 * delle chiavi degli altri («come `ibid.theme`, `ibid.history` e
 * `ibid.corsia`»), che e' il modo in cui un progetto dichiara di avere un
 * registro senza averlo.
 *
 * Qui l'elenco e' `CHIAVI`, e c'e' un test che ne verifica il prefisso e
 * l'unicita': l'invariante smette di essere un commento.
 *
 * **Il deposito si passa per parametro.** E' la scelta che `cronologia.ts`
 * aveva gia' preso da sola, ed e' l'unico motivo per cui di quel modulo si
 * poteva provare il caso «origine piena» mentre degli altri cinque no: chi
 * chiama il globale dentro un componente non e' raggiungibile da nessun test.
 * Il valore predefinito resta il deposito vero, quindi al richiamo non si vede.
 *
 * **Niente qui solleva mai.** Non ricordare una preferenza e' meno grave che
 * rifiutarsi di disegnare la pagina, e i due casi in cui succede — finestra
 * privata, origine piena — non sono guasti da segnalare a chi guarda: sono
 * condizioni normali del browser.
 */

/** Il minimo di `localStorage` che serve. Un'interfaccia invece del globale
 *  perche' e' cio' che rende provabili «negato» e «pieno». */
export interface Deposito {
  getItem: (chiave: string) => string | null;
  setItem: (chiave: string, valore: string) => void;
  removeItem: (chiave: string) => void;
}

/**
 * Tutte le chiavi, e sono tutte qui.
 *
 * Un prefisso solo perche' il deposito e' per **origine**, non per
 * applicazione: in sviluppo `localhost:5173` ospita anche altro, e una chiave
 * `theme` senza prefisso e' un nome che chiunque puo' aver preso.
 *
 * `tema` la legge anche lo script in testa a `index.html`, che decide il colore
 * di fondo prima che React parta: e' l'unica di queste che esiste **in due
 * linguaggi**, e cambiarla qui senza cambiarla li' fa ricomparire il lampo
 * bianco all'avvio in tema scuro.
 */
export const CHIAVI = {
  avvio: "ibid.avvio",
  colonne: "ibid.corpus.colonne",
  corsia: "ibid.corsia",
  cronologia: "ibid.history",
  dataset: "ibid.dataset",
  lingua: "ibid.lang",
  tema: "ibid.theme",
} as const;

/** Il tipo si chiama `ChiaveDeposito` e non `Chiave` perche' `Chiave`, in
 *  questo progetto, e' gia' la chiave di una stringa tradotta: due file che
 *  importano tutti e due «una chiave» e ne intendono due cose diverse. */
export type ChiaveDeposito = (typeof CHIAVI)[keyof typeof CHIAVI];

/**
 * Il deposito del browser, o `null` se non c'e'.
 *
 * `null` e non un oggetto finto che ingoia tutto: chi scrive puo' voler sapere
 * che non e' stato ricordato niente — `leggiCronologia` ci distingue «vuota» da
 * «non leggibile» — e un finto silenzioso toglierebbe quella differenza a tutti
 * per comodita' di qualcuno.
 *
 * L'accesso e' dentro `try` perche' in una finestra privata **il solo
 * riferimento** puo' sollevare, non la lettura. Nei test, che girano in `node`,
 * `window` non esiste affatto.
 */
export function locale(): Deposito | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/** Cio' che era stato ricordato sotto `chiave`, o `null` — anche quando il
 *  deposito non c'e' o rifiuta di rispondere. */
export function ricordato(
  chiave: ChiaveDeposito,
  deposito: Deposito | null = locale(),
): string | null {
  if (deposito === null) return null;
  try {
    return deposito.getItem(chiave);
  } catch {
    return null;
  }
}

/**
 * Ricorda `valore` sotto `chiave`. `null` dimentica.
 *
 * **`null` toglie la chiave invece di scrivere la parola «null»**, ed e' il
 * caso del tema: «segui il sistema» non e' un tema salvato, e lasciare un
 * valore la' dentro farebbe seguire per sempre quello che il sistema aveva
 * quando si e' scelto.
 */
export function ricorda(
  chiave: ChiaveDeposito,
  valore: string | null,
  deposito: Deposito | null = locale(),
): void {
  if (deposito === null) return;
  try {
    if (valore === null) deposito.removeItem(chiave);
    else deposito.setItem(chiave, valore);
  } catch {
    /* negato o pieno: vale per questa sessione, e non e' una cosa da dire. */
  }
}
