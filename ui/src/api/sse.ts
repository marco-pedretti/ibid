/**
 * Lo stream del §3.5, letto a mano.
 *
 * **Perche' non `EventSource`.** `/query/stream` e' una `POST` e l'`EventSource`
 * del browser fa solo `GET`. Accettare anche `GET` per poterlo usare
 * costringerebbe a serializzare quindici parametri in query string, e a
 * dichiarare cacheabile una richiesta che accende una GPU. Quindi `fetch` +
 * `ReadableStream`, e un parser SSE scritto qui.
 *
 * **Conseguenza voluta: nessuna riconnessione automatica.** `EventSource`
 * riconnette da solo, ed e' proprio cio' che non deve accadere: rilanciare una
 * generazione da ~11 s produce una risposta **diversa**, e l'utente vedrebbe il
 * testo cambiargli sotto senza aver chiesto niente. Su caduta si mostra il
 * parziale marcato incompleto, con un «Riprova» esplicito.
 *
 * Due livelli, e la divisione non e' estetica: `frames()` e' trasporto puro
 * (byte -> riquadri) e si prova senza rete; `events()` aggiunge il contratto
 * (JSON, nomi noti). Un guasto nel primo e' un bug di parsing, nel secondo una
 * divergenza dall'API: chi legge un test fallito deve poterli distinguere.
 */
import type { QueryRequest, SseEvent } from "./types";
import { SSE_EVENTS } from "./types";

/** Un riquadro SSE grezzo: il nome dell'evento e il suo `data`, ancora testo. */
export interface Frame {
  event: string;
  data: string;
}

const NOTI: ReadonlySet<string> = new Set(SSE_EVENTS);

/**
 * I riquadri di uno stream `text/event-stream`.
 *
 * La riga vuota **e'** il terminatore, ed e' l'unica regola che conta: un
 * riquadro senza riga vuota finale non e' un riquadro corto, e' un riquadro che
 * non e' arrivato. Quando lo stream si chiude a meta', quel resto viene
 * **scartato** — emetterlo significherebbe consegnare come completo qualcosa
 * che e' stato interrotto.
 */
export async function* frames(corpo: ReadableStream<Uint8Array>): AsyncGenerator<Frame> {
  const decoder = new TextDecoder();
  const lettore = corpo.getReader();
  let resto = "";

  try {
    for (;;) {
      const { done, value } = await lettore.read();
      // `stream: true` perche' un carattere UTF-8 puo' essere spezzato fra due
      // pacchetti: senza, un accento a cavallo diventa un carattere di
      // sostituzione, e il JSON che lo contiene smette di essere leggibile.
      resto += done ? decoder.decode() : decoder.decode(value, { stream: true });

      let taglio: number;
      while ((taglio = indiceRigaVuota(resto)) !== -1) {
        const riquadro = leggi(resto.slice(0, taglio));
        resto = resto.slice(taglio + lunghezzaSeparatore(resto, taglio));
        if (riquadro) yield riquadro;
      }
      if (done) return;
    }
  } finally {
    lettore.releaseLock();
  }
}

/** Dove finisce il riquadro corrente: `\n\n` o `\r\n\r\n`. */
function indiceRigaVuota(testo: string): number {
  const a = testo.indexOf("\n\n");
  const b = testo.indexOf("\r\n\r\n");
  if (a === -1) return b;
  if (b === -1) return a;
  return Math.min(a, b);
}

function lunghezzaSeparatore(testo: string, taglio: number): number {
  return testo.startsWith("\r\n\r\n", taglio) ? 4 : 2;
}

/**
 * Un riquadro dalle sue righe, o `null` se non porta dati.
 *
 * Segue la specifica invece del solo formato che il nostro server produce: le
 * righe `data:` multiple si uniscono con `\n`, i commenti (`:`) si ignorano, e
 * lo spazio dopo i due punti e' facoltativo. Costa dieci righe, e toglie di
 * mezzo la classe di guasti in cui il client funziona finche' il server non
 * cambia dettaglio di formattazione.
 */
function leggi(blocco: string): Frame | null {
  let event = "message";
  const dati: string[] = [];

  for (const riga of blocco.split(/\r?\n/)) {
    if (riga === "" || riga.startsWith(":")) continue;
    const duePunti = riga.indexOf(":");
    const campo = duePunti === -1 ? riga : riga.slice(0, duePunti);
    let valore = duePunti === -1 ? "" : riga.slice(duePunti + 1);
    if (valore.startsWith(" ")) valore = valore.slice(1);

    if (campo === "event") event = valore;
    else if (campo === "data") dati.push(valore);
    // `id` e `retry` esistono nella specifica e non servono qui: senza
    // riconnessione automatica non c'e' un punto a cui tornare.
  }

  return dati.length === 0 ? null : { event, data: dati.join("\n") };
}

/**
 * Gli eventi del contratto, tipizzati.
 *
 * Un nome che il contratto non conosce viene **saltato**, non tradotto in
 * `error`: il server non ha segnalato un guasto, e inventarne uno mostrerebbe
 * all'utente un errore che nessuno ha commesso. `onSconosciuto` esiste perche'
 * saltare in silenzio e' l'altro modo di sbagliare.
 *
 * Un `data` che non e' JSON, invece, **solleva**: li' il contratto e' rotto
 * davvero, e proseguire significherebbe consegnare eventi buoni pescati fra
 * eventi illeggibili.
 */
export async function* events(
  corpo: ReadableStream<Uint8Array>,
  onSconosciuto: (nome: string) => void = (nome) => console.warn(`evento SSE sconosciuto: ${nome}`),
): AsyncGenerator<SseEvent> {
  for await (const riquadro of frames(corpo)) {
    if (!NOTI.has(riquadro.event)) {
      onSconosciuto(riquadro.event);
      continue;
    }
    let data: unknown;
    try {
      data = JSON.parse(riquadro.data);
    } catch {
      throw new Error(
        `evento ${riquadro.event}: data non e' JSON (${riquadro.data.slice(0, 120)})`,
      );
    }
    yield { event: riquadro.event, data } as SseEvent;
  }
}

/** Dove sta l'API. In sviluppo e' il proxy di Vite; in produzione, la stessa origine. */
export const BASE: string = import.meta.env.VITE_API_BASE ?? "/api";

export interface OpzioniStream {
  /** Da un `AbortController`: e' cio' che rende «Ferma» un pulsante vero. */
  signal?: AbortSignal;
  base?: string;
  onSconosciuto?: (nome: string) => void;
}

/**
 * Una domanda, e gli eventi mentre la risposta si forma.
 *
 * Non riprova, non riconnette, non accumula: chi chiama decide cosa fare del
 * parziale. E' un generatore e non una serie di callback perche' l'ordine degli
 * eventi **e'** il contratto (`chunks` prima dei token, che e' cio' che rende
 * realizzabile U-02), e un `for await` lo rende evidente invece di ricostruibile.
 */
export async function* streamQuery(
  richiesta: QueryRequest,
  opzioni: OpzioniStream = {},
): AsyncGenerator<SseEvent> {
  const risposta = await fetch(`${opzioni.base ?? BASE}/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(richiesta),
    signal: opzioni.signal,
  });

  // Un 422 arriva **prima** che lo stream cominci, quindi qui uno stato HTTP
  // esiste ancora ed e' l'informazione migliore disponibile: il corpo porta il
  // nome del campo rifiutato. Da qui in poi non ce ne saranno piu' — a stream
  // aperto un guasto puo' solo essere un evento `error`.
  if (!risposta.ok) {
    const corpo = await risposta.text().catch(() => "");
    throw new Error(`HTTP ${risposta.status}: ${corpo.slice(0, 300)}`);
  }
  if (!risposta.body) throw new Error("risposta senza corpo: streaming non disponibile");

  yield* events(risposta.body, opzioni.onSconosciuto);
}
