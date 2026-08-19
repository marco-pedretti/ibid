/**
 * I controlli della barra, per tutta l'applicazione.
 *
 * Sta accanto a `opzioni.ts` come `chat.tsx` sta accanto a `conversazione.ts`:
 * li' la forma del dato e cosa finisce sul filo, qui lo stato di React che la
 * tiene. In un contesto e non in `Chat` perche' la schermata di confronto di
 * U-03 la legge senza passare di li': il confronto rilancia la stessa domanda
 * col RAG invertito, e per farlo deve sapere da quali opzioni partiva.
 *
 * **Non si chiude durante una generazione.** I controlli decidono la prossima
 * domanda, non quella in corso: bloccarli mentre il modello parla toglierebbe
 * la possibilita' di preparare la domanda dopo, senza proteggere niente.
 *
 * Cosa vuol dire ogni opzione, e cosa finisce sul filo, sta in `opzioni.ts`.
 */
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

import type { ConfigView } from "../api/types";
import { usaBackend } from "./backend";
import { modelli, risolvi } from "./catalogo";
import { opzioniDa } from "./opzioni";
import type { Opzioni } from "./opzioni";

interface Barra {
  /** `null` finche' non si sa da quali valori si parte: i controlli non hanno
   *  niente da mostrare, e inventarglielo e' proprio cio' che si e' tolto. */
  opzioni: Opzioni | null;
  predefiniti: ConfigView | null;
  /** Cambia **una** voce. Un `setOpzioni` esposto intero lascerebbe a chi chiama
   *  il compito di ricopiare le altre, che e' il modo in cui una si perde. */
  cambia: <K extends keyof Opzioni>(chiave: K, valore: Opzioni[K]) => void;
}

const Contesto = createContext<Barra | null>(null);

export function ProvvedeBarra({ children }: { children: ReactNode }) {
  const { backend } = usaBackend();
  // **Solo cio' che e' stato toccato.** Le altre voci si prendono dai
  // predefiniti a ogni render, senza un effetto che le copi nello stato: cosi'
  // non esiste il render in cui le due sorgenti non concordano, ed e' lo stesso
  // motivo per cui `dataset.tsx` deriva la scelta invece di sincronizzarla.
  const [mosse, setMosse] = useState<Partial<Opzioni>>({});

  const predefiniti = backend.stato === "pronto" ? backend.predefiniti : null;
  const catalogo = backend.stato === "pronto" ? backend.capabilities.model_catalog : [];

  const opzioni = useMemo(() => {
    if (predefiniti === null) return null;
    const partenza = opzioniDa(predefiniti);
    // `/config` restituisce il **modello base**, che da U-16 non e' una finestra
    // scegliibile: senza risolverlo, la barra si aprirebbe su un modello di cui
    // nessuna taglia risulta selezionata. Si parte dalla finestra con cui il
    // progetto misura -- vedi `PREFERITA`.
    const modello = risolvi(modelli(catalogo), partenza.modello);
    return { ...partenza, modello, ...mosse };
  }, [predefiniti, catalogo, mosse]);

  const cambia = useCallback(
    <K extends keyof Opzioni>(chiave: K, valore: Opzioni[K]) =>
      setMosse((m) => ({ ...m, [chiave]: valore })),
    [],
  );

  const valore = useMemo(() => ({ opzioni, predefiniti, cambia }), [opzioni, predefiniti, cambia]);
  return <Contesto.Provider value={valore}>{children}</Contesto.Provider>;
}

export function usaBarra(): Barra {
  const o = useContext(Contesto);
  if (!o) throw new Error("usaBarra fuori da <ProvvedeBarra>");
  return o;
}
