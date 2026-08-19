/**
 * Le conversazioni: quelle di questo browser, e quella aperta.
 *
 * Tiene insieme le tre cose che il §3.5 impone e che il reducer da solo non
 * puo' fare — la richiesta, l'`AbortController` che rende «Ferma» un pulsante
 * vero, e la distinzione fra uno stream **annullato** e uno **caduto**.
 *
 * Da U-13 tiene anche la cronologia, e nello stesso posto e non in un contesto
 * accanto: la conversazione aperta e' **una voce dell'elenco**, non un'altra
 * cosa. All'avvio pero' e' sempre una nuova — vedi `statoIniziale`. Due contesti dovrebbero scambiarsi continuamente la stessa lista — uno
 * per leggerla, l'altro per riscriverla a ogni token — e il primo bug sarebbe
 * una delle due copie in ritardo di un render. Cosa si ricorda e come si rilegge
 * sta in `cronologia.ts`, che e' provato; qui c'e' solo lo stream.
 *
 * **Non si cambia stanza mentre il modello parla.** «Nuova conversazione» e le
 * voci della cronologia non rispondono finche' una generazione e' in corso: lo
 * stream scrive in **una** conversazione, e permettere di andarsene lascerebbe
 * dei token ad arrivare in una stanza vuota mentre chi guarda ne sta guardando
 * un'altra. La via d'uscita c'e' e si vede — e' «Ferma», e lascia il parziale
 * dov'e'.
 *
 * Una domanda per volta. Non perche' sia difficile fare altrimenti, ma perche'
 * ogni generazione occupa la GPU per ~11 s: due in parallelo non sarebbero due
 * volte piu' veloci, sarebbero due volte piu' lente ciascuna, e chi guarda
 * leggerebbe la coda come un blocco.
 */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import { streamQuery } from "../api/sse";
import type { QueryRequest } from "../api/types";
import { usaDataset } from "./dataset";
import { applica, guasto, inizio, interrompi } from "./conversazione";
import type { Risposta, Scambio } from "./conversazione";
import {
  MASSIME,
  conConversazione,
  leggiCronologia,
  nuovaConversazione,
  nuovoId,
  salvaCronologia,
  trova,
  vuota,
} from "./cronologia";
import type { Conversazione } from "./cronologia";
import { usaBarra } from "./barra";
import { campiRichiesta, stessaConfigurazione } from "./opzioni";

/**
 * Quanto si aspetta prima di scrivere nel deposito.
 *
 * Non e' prudenza: durante la generazione lo stato cambia a ogni token, e
 * scrivere subito significherebbe serializzare **tutta** la cronologia trenta
 * volte al secondo. Con questa pausa una risposta costa una scrittura sola —
 * quella che parte quando i token smettono di arrivare.
 *
 * Resta breve perche' copre anche il caso opposto: la domanda appena mandata
 * viene scritta prima che il primo token arrivi (il retrieval da solo ne prende
 * ~0,3 s), quindi chiudendo la scheda a meta' generazione la domanda non si
 * perde — torna con la sua risposta parziale, sigillata.
 */
const RITARDO_SALVATAGGIO_MS = 400;

/**
 * Le due risposte alla stessa domanda, e null quando non se ne sta guardando
 * nessuna.
 *
 * **Non e' uno scambio della conversazione.** Il §12 dice che «affiancate, dalla
 * stessa query, nella stessa sessione» non si ottiene con due messaggi
 * consecutivi: il braccio nudo dentro il filo sarebbe una seconda risposta alla
 * stessa domanda, e nella cronologia diventerebbe una conversazione che si
 * contraddice da sola. Vive qui accanto, e chiudendolo sparisce.
 */
export interface Confronto {
  domanda: string;
  /** Quella gia' data, da cui si e' partiti. Il suo `config` dice **quale** dei
   *  due bracci e', quindi da che parte va messa: non serve ricordarlo, e cosi'
   *  la colonna la decide cio' che ha girato davvero. */
  data: Risposta;
  /** La stessa domanda col solo RAG invertito, mentre arriva. */
  nuova: Risposta;
}

interface Chat {
  /** Gli scambi della conversazione aperta. */
  scambi: Scambio[];
  /** Tutte, la piu' recente per prima. Comprende quella aperta. */
  conversazioni: Conversazione[];
  corrente: string;
  /** Una generazione sta girando: chiude il campo, accende «Ferma», e blocca il
   *  passaggio a un'altra conversazione. */
  occupato: boolean;
  invia: (domanda: string) => void;
  ferma: () => void;
  nuova: () => void;
  apri: (id: string) => void;
  svuota: () => void;
  /** Le due colonne, o `null` quando si sta guardando la conversazione. */
  confronto: Confronto | null;
  /** Rilancia lo scambio col RAG invertito e apre le due colonne. */
  confronta: (idScambio: string) => void;
  chiudiConfronto: () => void;
}

const Contesto = createContext<Chat | null>(null);

/** Le conversazioni e quale e' aperta. Solo in memoria: nel deposito va la
 *  cronologia, non il punto in cui si stava leggendo. */
interface Stato {
  conversazioni: Conversazione[];
  corrente: string;
}

/**
 * Si riapre **sempre** su una conversazione nuova, con la cronologia accanto.
 *
 * Il campo che diceva quale conversazione era aperta c'era, ed e' stato tolto:
 * chi apre `ibid` lo fa per **chiedere qualcosa**, e ritrovarsi in fondo a una
 * conversazione di ieri mette un clic davanti alla cosa piu' comune. Tornarci e'
 * una voce della corsia, cioe' un clic davanti a quella meno comune — che e' il
 * verso giusto.
 */
function statoIniziale(): Stato {
  const n = nuovaConversazione();
  // Il tetto conta anche qui, come in `nuova`: la corsia non mostra
  // conversazioni che un ricaricamento farebbe sparire.
  return {
    conversazioni: [n, ...leggiCronologia().slice(0, MASSIME - 1)],
    corrente: n.id,
  };
}

/**
 * Guida uno stream fino alla fine, e ci scrive dentro attraverso `aggiorna`.
 *
 * Non sa **dove** finisca la risposta che sta costruendo: quello lo decide chi
 * chiama, passando la funzione che la va a prendere. Serve perche' gli stream
 * non sono uno solo — una domanda nella conversazione e, dal confronto, la
 * stessa domanda rilanciata a RAG invertito — e le tre righe che distinguono
 * uno stream **annullato** da uno **caduto** non vanno ricopiate: sono la parte
 * che a mano si sbaglia, e sbagliarla significa mostrare un guasto a chi ha solo
 * premuto «Ferma».
 */
async function guida(
  richiesta: QueryRequest,
  ctrl: AbortController,
  aggiorna: (f: (r: Risposta) => Risposta) => void,
): Promise<void> {
  try {
    for await (const evento of streamQuery(richiesta, { signal: ctrl.signal })) {
      aggiorna((r) => applica(r, evento));
    }
  } catch (e: unknown) {
    // Annullato da «Ferma» non e' caduto: il primo l'ha deciso chi guarda, il
    // secondo e' successo. Mostrarli uguali farebbe cercare un guasto a chi ha
    // solo premuto un pulsante.
    const messaggio = e instanceof Error ? e.message : String(e);
    aggiorna((r) => (ctrl.signal.aborted ? interrompi(r) : guasto(r, messaggio)));
  }
}

function conRisposta(
  cs: readonly Conversazione[],
  idConversazione: string,
  idScambio: string,
  f: (r: Risposta) => Risposta,
): Conversazione[] {
  return conConversazione(cs, idConversazione, (c) => ({
    ...c,
    scambi: c.scambi.map((s) => (s.id === idScambio ? { ...s, risposta: f(s.risposta) } : s)),
  }));
}

export function ProvvedeChat({ children }: { children: ReactNode }) {
  const { scelto, imposta } = usaDataset();
  const { opzioni, predefiniti } = usaBarra();
  const [stato, setStato] = useState<Stato>(statoIniziale);
  const [confronto, setConfronto] = useState<Confronto | null>(null);
  const [occupato, setOccupato] = useState(false);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => {
    const t = setTimeout(() => salvaCronologia(stato.conversazioni), RITARDO_SALVATAGGIO_MS);
    return () => clearTimeout(t);
  }, [stato]);

  const invia = useCallback(
    (domanda: string) => {
      const testo = domanda.trim();
      // Senza i predefiniti non si sa cosa la barra sta mostrando, quindi non si
      // sa nemmeno cosa manderebbe: e' lo stesso motivo per cui il campo e'
      // chiuso finche' non c'e' un dataset.
      if (testo === "" || scelto === null || controller.current !== null) return;
      if (opzioni === null || predefiniti === null) return;

      const conversazione = stato.corrente;
      const id = nuovoId();
      setStato((s) => ({
        ...s,
        conversazioni: conConversazione(s.conversazioni, conversazione, (c) => ({
          ...c,
          // Il dataset e' quello della **prima** domanda e non si aggiorna:
          // riaprendo la conversazione ci si torna sopra, e riscriverlo direbbe
          // che risposte gia' date vengono da un corpus che non le ha prodotte.
          dataset_id: c.dataset_id ?? scelto.dataset_id,
          scambi: [...c.scambi, { id, domanda: testo, risposta: inizio() }],
        })),
      }));

      const ctrl = new AbortController();
      controller.current = ctrl;
      setOccupato(true);

      // Il `dataset_id` viene dal selettore di U-01 e non da un default del
      // server: e' cio' che rende vero «cambio dataset senza riavvio» anche per
      // una domanda gia' in coda. I campi della barra sono quelli di **quando
      // si e' premuto invio**: `opzioni` e' la costante del render in cui
      // `invia` e' nata, quindi toccare un controllo mentre il modello parla non
      // riscrive una richiesta gia' partita.
      void guida(
        { query: testo, dataset_id: scelto.dataset_id, ...campiRichiesta(opzioni, predefiniti) },
        ctrl,
        (f) =>
          setStato((s) => ({
            ...s,
            conversazioni: conRisposta(s.conversazioni, conversazione, id, f),
          })),
      ).finally(() => {
        if (controller.current === ctrl) {
          controller.current = null;
          setOccupato(false);
        }
      });
    },
    [scelto, stato.corrente, opzioni, predefiniti],
  );

  const ferma = useCallback(() => controller.current?.abort(), []);

  /**
   * La stessa domanda, col RAG invertito, accanto a quella gia' data.
   *
   * Parte dalla configurazione **che ha girato** e non dalla barra: rilanciare
   * con le opzioni correnti metterebbe nelle due colonne anche un modello
   * diverso o un `top_k` cambiato nel frattempo, e il confronto direbbe «guarda
   * cosa fa il RAG» mostrando l'effetto di tre cose. E' il §15 dentro
   * l'interfaccia — mai due cambiamenti insieme.
   *
   * Solo su una risposta **conclusa**: senza `config` non si sa da quale dei due
   * bracci si sta partendo, e una colonna intitolata a caso e' peggio di un
   * comando assente.
   */
  const confronta = useCallback(
    (idScambio: string) => {
      if (controller.current !== null) return;
      const c = trova(stato.conversazioni, stato.corrente);
      const s = c?.scambi.find((x) => x.id === idScambio) ?? null;
      const config = s?.risposta.config ?? null;
      if (s === null || config === null) return;

      setConfronto({ domanda: s.domanda, data: s.risposta, nuova: inizio() });

      const ctrl = new AbortController();
      controller.current = ctrl;
      setOccupato(true);

      void guida(
        {
          query: s.domanda,
          // Il corpus e' quello della conversazione, non quello scelto adesso:
          // il confronto parla della domanda gia' fatta.
          ...(c?.dataset_id ? { dataset_id: c.dataset_id } : {}),
          ...stessaConfigurazione(config),
          rag: !config.rag,
        },
        ctrl,
        (f) => setConfronto((x) => (x === null ? x : { ...x, nuova: f(x.nuova) })),
      ).finally(() => {
        if (controller.current === ctrl) {
          controller.current = null;
          setOccupato(false);
        }
      });
    },
    [stato.conversazioni, stato.corrente],
  );

  /** Si torna al filo. Non mentre il modello parla: la via d'uscita e' «Ferma»,
   *  come per tutto il resto — vedi la nota in testa al file. */
  const chiudiConfronto = useCallback(() => {
    if (controller.current !== null) return;
    setConfronto(null);
  }, []);

  const nuova = useCallback(() => {
    if (controller.current !== null) return;
    // Le tre azioni della corsia riportano al filo: si vedono anche dal
    // confronto, e cambiare conversazione lasciando aperte due colonne che
    // parlano di una domanda dell'altra sarebbe la peggiore delle due uscite.
    setConfronto(null);
    setStato((s) => {
      const c = trova(s.conversazioni, s.corrente);
      // Gia' in una conversazione nuova: non se ne apre una seconda. Sarebbero
      // due voci identiche e senza nome, e nessuna delle due direbbe quale.
      if (c !== null && vuota(c)) return s;
      const n = nuovaConversazione();
      // Il tetto vale **anche in memoria**, non solo nel deposito: senza, in una
      // sessione lunga la corsia mostrerebbe conversazioni che un ricaricamento
      // fa sparire, ed e' il modo peggiore in cui un limite si annuncia.
      return {
        conversazioni: [n, ...s.conversazioni.filter((x) => !vuota(x)).slice(0, MASSIME - 1)],
        corrente: n.id,
      };
    });
  }, []);

  const apri = useCallback(
    (id: string) => {
      if (controller.current !== null) return;
      const c = trova(stato.conversazioni, id);
      if (c === null) return;

      // Si torna anche sul corpus su cui le domande erano state fatte. Senza,
      // la prossima domanda cadrebbe su un altro dataset dentro la stessa
      // conversazione, e nel filo non ci sarebbe niente che lo dice.
      if (c.dataset_id !== null) imposta(c.dataset_id);
      setConfronto(null);

      // La conversazione vuota che si lascia non serve piu': la sua voce nella
      // corsia e' «Nuova conversazione», che c'e' comunque.
      setStato((s) => ({
        conversazioni: s.conversazioni.filter((x) => !vuota(x) || x.id === id),
        corrente: id,
      }));
    },
    [stato.conversazioni, imposta],
  );

  /**
   * Via tutte, **compresa quella aperta**: «cancella la cronologia» che lasciasse
   * sullo schermo la conversazione che si stava leggendo avrebbe cancellato tutto
   * tranne l'unica cosa visibile. Si resta in una conversazione nuova, che e' lo
   * stato di chi arriva per la prima volta.
   *
   * Il deposito si allinea da se': senza niente da ricordare, `salvaCronologia`
   * toglie la chiave invece di lasciare una cronologia piu' vecchia di quella in
   * memoria.
   */
  const svuota = useCallback(() => {
    if (controller.current !== null) return;
    const n = nuovaConversazione();
    setConfronto(null);
    setStato({ conversazioni: [n], corrente: n.id });
  }, []);

  const scambi = trova(stato.conversazioni, stato.corrente)?.scambi ?? [];

  return (
    <Contesto.Provider
      value={{
        scambi,
        conversazioni: stato.conversazioni,
        corrente: stato.corrente,
        occupato,
        invia,
        ferma,
        nuova,
        apri,
        svuota,
        confronto,
        confronta,
        chiudiConfronto,
      }}
    >
      {children}
    </Contesto.Provider>
  );
}

export function usaChat(): Chat {
  const c = useContext(Contesto);
  if (!c) throw new Error("usaChat fuori da <ProvvedeChat>");
  return c;
}
