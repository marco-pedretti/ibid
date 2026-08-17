/**
 * La conversazione: le domande fatte, e lo stato di ogni risposta.
 *
 * Tiene insieme le tre cose che il §3.5 impone e che il reducer da solo non
 * puo' fare — la richiesta, l'`AbortController` che rende «Ferma» un pulsante
 * vero, e la distinzione fra uno stream **annullato** e uno **caduto**.
 *
 * **La cronologia non e' qui.** Vive nel browser (`localStorage`) e arrivera'
 * con la corsia laterale che la mostra; questo contesto tiene la sessione
 * corrente. Separarli e' voluto: nessun endpoint, nessuna sessione lato server,
 * e §14 tiene autenticazione e database fuori dallo stack.
 *
 * Una domanda per volta. Non perche' sia difficile fare altrimenti, ma perche'
 * ogni generazione occupa la GPU per ~11 s: due in parallelo non sarebbero due
 * volte piu' veloci, sarebbero due volte piu' lente ciascuna, e chi guarda
 * leggerebbe la coda come un blocco.
 */
import { createContext, useCallback, useContext, useRef, useState } from "react";
import type { ReactNode } from "react";

import { streamQuery } from "../api/sse";
import { usaDataset } from "./dataset";
import { applica, guasto, inizio, interrompi } from "./conversazione";
import type { Risposta, Scambio } from "./conversazione";

interface Chat {
  scambi: Scambio[];
  /** Una generazione sta girando: chiude il campo e accende «Ferma». */
  occupato: boolean;
  invia: (domanda: string) => void;
  ferma: () => void;
}

const Contesto = createContext<Chat | null>(null);

function conRisposta(scambi: Scambio[], id: string, f: (r: Risposta) => Risposta): Scambio[] {
  return scambi.map((s) => (s.id === id ? { ...s, risposta: f(s.risposta) } : s));
}

export function ProvvedeChat({ children }: { children: ReactNode }) {
  const { scelto } = usaDataset();
  const [scambi, setScambi] = useState<Scambio[]>([]);
  const [occupato, setOccupato] = useState(false);
  const controller = useRef<AbortController | null>(null);

  const invia = useCallback(
    (domanda: string) => {
      const testo = domanda.trim();
      if (testo === "" || scelto === null || controller.current !== null) return;

      const id = `${Date.now()}-${scambi.length}`;
      setScambi((s) => [...s, { id, domanda: testo, risposta: inizio() }]);

      const ctrl = new AbortController();
      controller.current = ctrl;
      setOccupato(true);

      void (async () => {
        try {
          // Il `dataset_id` viene dal selettore di U-01 e non da un default del
          // server: e' cio' che rende vero «cambio dataset senza riavvio» anche
          // per una domanda gia' in coda.
          for await (const evento of streamQuery(
            { query: testo, dataset_id: scelto.dataset_id },
            { signal: ctrl.signal },
          )) {
            setScambi((s) => conRisposta(s, id, (r) => applica(r, evento)));
          }
        } catch (e: unknown) {
          // Annullato da «Ferma» non e' caduto: il primo l'ha deciso chi
          // guarda, il secondo e' successo. Mostrarli uguali farebbe cercare un
          // guasto a chi ha solo premuto un pulsante.
          const messaggio = e instanceof Error ? e.message : String(e);
          setScambi((s) =>
            conRisposta(s, id, (r) =>
              ctrl.signal.aborted ? interrompi(r) : guasto(r, messaggio),
            ),
          );
        } finally {
          if (controller.current === ctrl) {
            controller.current = null;
            setOccupato(false);
          }
        }
      })();
    },
    [scelto, scambi.length],
  );

  const ferma = useCallback(() => controller.current?.abort(), []);

  return (
    <Contesto.Provider value={{ scambi, occupato, invia, ferma }}>{children}</Contesto.Provider>
  );
}

export function usaChat(): Chat {
  const c = useContext(Contesto);
  if (!c) throw new Error("usaChat fuori da <ProvvedeChat>");
  return c;
}
