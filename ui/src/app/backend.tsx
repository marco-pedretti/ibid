/**
 * `/datasets` e `/config` all'avvio, e nient'altro scritto a mano.
 *
 * Modalita' di retrieval, prompt del baseline, livelli di ragionamento, modelli,
 * dataset e collection arrivano tutti da qui. E' la lezione di Q-06 applicata
 * all'altro lato: un elenco copiato nel frontend diverge, e il valore nuovo
 * arriva senza che nessuno se ne accorga.
 *
 * **Due domande e non una**, perche' sono due cose diverse: `/datasets` dice
 * quali valori sono *ammessi*, `/config` quali sono *in vigore*. Con la sola
 * prima la barra di U-03 poteva elencare le scelte ma non dire da quale si
 * parte, e ogni controllo doveva aprirsi su una voce «come configurato» — cioe'
 * l'interfaccia dichiarava di non sapere una cosa che il servizio pubblica da
 * A-04. Non serviva un campo nuovo: serviva chiedere.
 *
 * Vanno insieme in un `Promise.all`, e se `/config` cade si e' guasti: non tocca
 * ne' Qdrant ne' l'LLM, legge la configurazione del processo. Un suo errore non
 * e' una dipendenza che manca, e' il servizio che non sta in piedi.
 *
 * Tre stati e non due. «Sto contattando» non e' «e' rotto», e mostrare subito
 * l'errore per poi toglierlo fa lampeggiare un guasto che non c'era. E la lista
 * dei modelli **vuota non e' un guasto**: `/datasets` risponde comunque, perche'
 * i dataset non dipendono dall'LLM.
 */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { api } from "../api/client";
import type { Capabilities, ConfigView } from "../api/types";

export type StatoBackend =
  | { stato: "caricamento" }
  /** `capabilities` = cosa e' ammesso, `predefiniti` = cosa e' in vigore. */
  | { stato: "pronto"; capabilities: Capabilities; predefiniti: ConfigView }
  | { stato: "guasto"; errore: string };

interface Backend {
  backend: StatoBackend;
  ricarica: () => void;
}

const Contesto = createContext<Backend | null>(null);

export function ProvvedeBackend({ children }: { children: ReactNode }) {
  const [backend, setBackend] = useState<StatoBackend>({ stato: "caricamento" });
  const [tentativo, setTentativo] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setBackend({ stato: "caricamento" });

    Promise.all([
      api.capabilities({ signal: controller.signal }),
      api.config({ signal: controller.signal }),
    ])
      .then(([capabilities, predefiniti]) =>
        setBackend({ stato: "pronto", capabilities, predefiniti }),
      )
      .catch((e: unknown) => {
        // Un fetch annullato non e' un guasto: e' React che smonta, o un
        // secondo tentativo che parte. Mostrarlo direbbe che il backend e'
        // caduto proprio mentre si stava riprovando.
        if (controller.signal.aborted) return;
        setBackend({ stato: "guasto", errore: e instanceof Error ? e.message : String(e) });
      });

    return () => controller.abort();
  }, [tentativo]);

  const ricarica = useCallback(() => setTentativo((n) => n + 1), []);

  return <Contesto.Provider value={{ backend, ricarica }}>{children}</Contesto.Provider>;
}

export function usaBackend(): Backend {
  const b = useContext(Contesto);
  if (!b) throw new Error("usaBackend fuori da <ProvvedeBackend>");
  return b;
}
