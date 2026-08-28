/**
 * Il dataset scelto, per tutta l'applicazione.
 *
 * Sta in un contesto e non in `App` perche' il criterio di U-01 e' «cambio
 * dataset senza riavvio»: la scelta finisce nel corpo di ogni `QueryRequest` e
 * di ogni `/documents`, cioe' in schermate che non sono ancora scritte. Un
 * `prop` passato di mano in mano arriverebbe a destinazione lo stesso, ma
 * lascerebbe a chi scrive la prossima schermata la possibilita' di dimenticarlo
 * e di usare un default del server — che e' esattamente il riavvio che il
 * criterio vuole togliere.
 *
 * **Nessun `useEffect` che sincronizza.** L'id selezionato e' *derivato* a ogni
 * render da `sceltaIniziale(lista, ricordato)`: quando le capabilities
 * arrivano, la scelta si risolve da sola; quando il dataset ricordato sparisce
 * dal server, ripiega senza che nessuno debba accorgersene. Un effetto che
 * scrivesse lo stato in risposta a un altro stato avrebbe due sorgenti di
 * verita' e un render in cui non concordano.
 *
 * Si **ricorda** solo la scelta esplicita, mai il ripiego: salvare il fallback
 * lo trasformerebbe in una decisione dell'utente che l'utente non ha preso, e
 * al prossimo avvio con l'indice tornato pronto vincerebbe sul dataset giusto.
 */
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

import type { DatasetView } from "../api/types";
import { usaBackend } from "./backend";
import { leggiSalvato, salva, sceltaIniziale } from "./scelta-dataset";

interface Dataset {
  /** Tutti quelli che il server elenca, **anche i vuoti**: sono uno stato da
   *  mostrare, non da nascondere. */
  elenco: DatasetView[];
  /** Quello su cui si sta lavorando, o `null` se nessun indice e' pronto. */
  scelto: DatasetView | null;
  imposta: (dataset_id: string) => void;
}

const Contesto = createContext<Dataset | null>(null);

//: L'elenco vuoto, una volta sola. Vedi il commento in `ProvvedeDataset`.
const VUOTO: DatasetView[] = [];

export function ProvvedeDataset({ children }: { children: ReactNode }) {
  const { backend } = usaBackend();
  const [ricordato, setRicordato] = useState<string | null>(leggiSalvato);

  // **`VUOTO` e non `[]`.** Un letterale qui e' un array nuovo a ogni render,
  // quindi il `useMemo` sotto si rifaceva ogni volta finche' il backend non era
  // pronto: memoizzava contro una dipendenza che cambiava sempre. Trovato da
  // `react-hooks/exhaustive-deps` (D-13), che e' il difetto per cui esiste.
  const elenco = backend.stato === "pronto" ? backend.capabilities.datasets : VUOTO;

  const scelto = useMemo(() => {
    const id = sceltaIniziale(elenco, ricordato);
    return elenco.find((d) => d.dataset_id === id) ?? null;
  }, [elenco, ricordato]);

  const imposta = useCallback((dataset_id: string) => {
    setRicordato(dataset_id);
    salva(dataset_id);
  }, []);

  return <Contesto.Provider value={{ elenco, scelto, imposta }}>{children}</Contesto.Provider>;
}

export function usaDataset(): Dataset {
  const d = useContext(Contesto);
  if (!d) throw new Error("usaDataset fuori da <ProvvedeDataset>");
  return d;
}
