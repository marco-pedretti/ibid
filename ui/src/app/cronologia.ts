/**
 * Le conversazioni di **questo** browser.
 *
 * Nessun endpoint, nessuna sessione lato server: §14 tiene autenticazione e
 * database fuori dallo stack, e una demo che ha bisogno di un database per
 * ricordarsi e' un altro progetto. Il criterio di U-13 chiede pero' che questo
 * sia **dichiarato** e non lasciato dedurre — chi cambia macchina non ritrova
 * le sue conversazioni — e quella frase sta nella corsia, non qui.
 *
 * Cronologia non significa multi-turno: ogni domanda resta indipendente, e
 * riusare i messaggi precedenti per il retrieval e' X-02. Qui si ricorda cio'
 * che e' stato chiesto e cio' che e' arrivato, niente di piu'.
 *
 * **Non si ricorda quale conversazione era aperta**, e non e' una dimenticanza:
 * riaprendo si comincia da una conversazione **nuova**, e la cronologia sta li'
 * accanto per chi voglia tornarci. Avevo salvato anche quel dato, ragionando che
 * altrimenti la cronologia sopravvive al ricaricamento ma la lettura no —
 * decisione ribaltata da Marco alla revisione, ed e' la lettura giusta: il caso
 * frequente e' aprire per **chiedere qualcosa**, e ritrovarsi in fondo a una
 * conversazione di ieri costringe a un clic per fare la cosa piu' comune. Da qui
 * il campo non c'e' proprio: un dato scritto che nessuno rilegge invecchia
 * peggio di un dato assente. Chi rilegge un deposito piu' vecchio lo trova
 * comunque — un campo di troppo viene ignorato, non fa scartare niente, che e'
 * la stessa proprieta' che rende `VERSIONE` una risorsa per le rotture vere.
 *
 * **Una risposta a meta' torna sigillata.** Chiudendo la scheda durante gli ~11 s
 * di generazione, cio' che finisce nel deposito ha `fase: "scrittura"`: al
 * ricaricamento il pallino pulserebbe per sempre in attesa di uno stream che non
 * esiste piu'. `interrompi` la porta nello stesso stato di «Ferma», che e'
 * l'unico onesto — lo stream e' finito senza che il server dicesse niente, e il
 * parziale resta con il suo «Riprova».
 *
 * **L'ordine e' quello di creazione, la piu' nuova per prima, e non cambia mai.**
 * Un elenco ordinato per ultimo uso si riordinerebbe sotto il cursore ogni volta
 * che si fa una domanda in una conversazione vecchia: nella corsia si vedrebbe
 * una voce saltare in cima da sola.
 *
 * **Un campo aggiunto dopo prende il suo default.** Le risposte salvate si
 * rileggono come `{ ...inizio(), ...salvata }`: `Risposta` cresce a ogni task
 * (U-05 la targhetta pipeline, U-06 i link profondi), e una versione nuova che
 * buttasse la cronologia a ogni campo aggiunto la butterebbe praticamente sempre.
 * `VERSIONE` resta per una rottura vera — un campo che cambia significato — e
 * allora scartare e' giusto.
 */
import type { ConfigView } from "../api/types";
import { inizio, interrompi } from "./conversazione";
import type { Risposta, Scambio } from "./conversazione";

/** La stessa forma di `ibid.theme` e `ibid.dataset`: un prefisso solo. */
export const CHIAVE_CRONOLOGIA = "ibid.history";

export const VERSIONE = 1;

/**
 * Quante conversazioni si ricordano.
 *
 * Uno scambio porta con se' **le fonti intere** — il testo dei chunk recuperati,
 * che e' cio' che rende un pannello fonti ricostruibile invece di vuoto — quindi
 * si misura in decine di KB, non in caratteri. Venti conversazioni stanno larghe
 * nei ~5 MB di un'origine; il resto lo copre il ciclo di `salvaCronologia`.
 */
export const MASSIME = 20;

export interface Conversazione {
  id: string;
  /** Il dataset della prima domanda, o `null` finche' non ce n'e' una: riaprendo
   *  una conversazione ci si torna sopra, altrimenti la domanda seguente
   *  cadrebbe su un corpus diverso senza dirlo. */
  dataset_id: string | null;
  scambi: Scambio[];
}

/** Il minimo di `localStorage` che serve qui. Un'interfaccia invece del globale
 *  perche' e' cio' che rende provabile il caso «deposito pieno». */
export interface Deposito {
  getItem: (chiave: string) => string | null;
  setItem: (chiave: string, valore: string) => void;
  removeItem: (chiave: string) => void;
}

function locale(): Deposito | null {
  try {
    return window.localStorage;
  } catch {
    // Negato (finestra privata, iframe) o assente (i test girano in `node`):
    // non ricordare e' meno grave che rifiutare di partire.
    return null;
  }
}

export function nuovoId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

export function nuovaConversazione(): Conversazione {
  return { id: nuovoId(), dataset_id: null, scambi: [] };
}

/** Senza domande dentro: non si ricorda, e nella corsia non ha una voce — la
 *  voce «Nuova conversazione» e' quella. */
export function vuota(c: Conversazione): boolean {
  return c.scambi.length === 0;
}

/**
 * Il nome della conversazione: la sua prima domanda, o `null`.
 *
 * Derivato e non salvato. Un titolo nel deposito sarebbe una seconda copia di
 * un dato che c'e' gia', e le due divergono — qui in silenzio, perche' nessuno
 * riguarda una riga di cronologia dopo averla scritta.
 */
export function titoloDi(c: Conversazione): string | null {
  return c.scambi[0]?.domanda ?? null;
}

export function trova(cs: readonly Conversazione[], id: string): Conversazione | null {
  return cs.find((c) => c.id === id) ?? null;
}

/** Sostituisce la conversazione di `id`, e lascia stare le altre. */
export function conConversazione(
  cs: readonly Conversazione[],
  id: string,
  f: (c: Conversazione) => Conversazione,
): Conversazione[] {
  return cs.map((c) => (c.id === id ? f(c) : c));
}

/** Quelle che vale la pena scrivere: con almeno una domanda, e non piu' di
 *  `MASSIME`. Si taglia dalla coda, cioe' dalle piu' vecchie. */
export function daRicordare(cs: readonly Conversazione[]): Conversazione[] {
  return cs.filter((c) => !vuota(c)).slice(0, MASSIME);
}

export function serializza(cs: readonly Conversazione[]): string {
  return JSON.stringify({ v: VERSIONE, conversazioni: daRicordare(cs) });
}

/** Cio' che c'era nel deposito: vuoto se non c'era niente di usabile. */
export function deserializza(json: string | null): Conversazione[] {
  if (json === null) return [];

  let letto: unknown;
  try {
    letto = JSON.parse(json);
  } catch {
    return [];
  }
  if (typeof letto !== "object" || letto === null) return [];

  const s = letto as Record<string, unknown>;
  if (s.v !== VERSIONE || !Array.isArray(s.conversazioni)) return [];

  return s.conversazioni.map(comeConversazione).filter((c): c is Conversazione => c !== null);
}

function comeConversazione(x: unknown): Conversazione | null {
  if (typeof x !== "object" || x === null) return null;
  const c = x as Record<string, unknown>;
  if (typeof c.id !== "string" || !Array.isArray(c.scambi)) return null;

  const scambi = c.scambi.map(comeScambio).filter((s): s is Scambio => s !== null);
  if (scambi.length === 0) return null;

  return {
    id: c.id,
    dataset_id: typeof c.dataset_id === "string" ? c.dataset_id : null,
    scambi,
  };
}

function comeScambio(x: unknown): Scambio | null {
  if (typeof x !== "object" || x === null) return null;
  const s = x as Record<string, unknown>;
  if (typeof s.id !== "string" || typeof s.domanda !== "string") return null;
  return {
    id: s.id,
    domanda: s.domanda,
    risposta: comeRisposta(s.risposta),
    // Un deposito scritto prima di U-15 non ce l'ha: `null` e' il valore giusto
    // per «non si sa cosa era stato chiesto», e la riga tace invece di inventare.
    chiesto: typeof s.chiesto === "object" && s.chiesto !== null ? (s.chiesto as ConfigView) : null,
  };
}

/**
 * Una risposta riletta dal deposito: i campi che non ci sono prendono il loro
 * default, quelli che non hanno piu' il tipo giusto tornano al default, e lo
 * stream — che non esiste piu' — viene chiuso.
 *
 * I quattro controlli di tipo non sono paranoia generica: sono esattamente i
 * campi su cui l'interfaccia **itera**. Un `chunks` che non e' un array fa
 * cadere il pannello fonti, e un deposito si puo' modificare a mano.
 */
function comeRisposta(x: unknown): Risposta {
  const d = inizio();
  if (typeof x !== "object" || x === null) return d;

  const r: Risposta = { ...d, ...(x as Partial<Risposta>) };
  if (!Array.isArray(r.chunks)) r.chunks = d.chunks;
  if (!Array.isArray(r.citazioni)) r.citazioni = d.citazioni;
  if (!Array.isArray(r.senzaCitazione)) r.senzaCitazione = d.senzaCitazione;
  if (typeof r.tempi !== "object" || r.tempi === null) r.tempi = d.tempi;

  return interrompi(r);
}

export function leggiCronologia(deposito: Deposito | null = locale()): Conversazione[] {
  if (deposito === null) return [];
  try {
    return deserializza(deposito.getItem(CHIAVE_CRONOLOGIA));
  } catch {
    return [];
  }
}

/**
 * Scrive, e se non ci sta scrive **meno**.
 *
 * `localStorage` solleva `QuotaExceededError` quando l'origine e' piena, e la
 * cosa sbagliata da fare e' ignorarlo: da quel momento la cronologia non
 * cambierebbe piu', e chi guarda vedrebbe le conversazioni nuove sparire a ogni
 * ricaricamento senza un motivo visibile. Si sacrificano le piu' vecchie, che e'
 * cio' che il tetto fa comunque, solo prima del previsto.
 */
export function salvaCronologia(
  conversazioni: readonly Conversazione[],
  deposito: Deposito | null = locale(),
): void {
  if (deposito === null) return;

  const cs = daRicordare(conversazioni);
  for (let n = cs.length; n > 0; n -= 1) {
    try {
      deposito.setItem(CHIAVE_CRONOLOGIA, serializza(cs.slice(0, n)));
      return;
    } catch {
      /* pieno: si riprova con una conversazione in meno */
    }
  }

  // Niente da ricordare (o nemmeno una ci sta): meglio togliere la chiave che
  // lasciare nel deposito una cronologia piu' vecchia di quella in memoria.
  try {
    deposito.removeItem(CHIAVE_CRONOLOGIA);
  } catch {
    /* vedi `locale` */
  }
}
