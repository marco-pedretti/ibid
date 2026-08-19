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

import { PREDEFINITE } from "./opzioni";
import type { Opzioni } from "./opzioni";

interface Barra {
  opzioni: Opzioni;
  /** Cambia **una** voce. Un `setOpzioni` esposto intero lascerebbe a chi chiama
   *  il compito di ricopiare le altre, che e' il modo in cui una si perde. */
  cambia: <K extends keyof Opzioni>(chiave: K, valore: Opzioni[K]) => void;
}

const Contesto = createContext<Barra | null>(null);

export function ProvvedeBarra({ children }: { children: ReactNode }) {
  const [opzioni, setOpzioni] = useState<Opzioni>(PREDEFINITE);

  const cambia = useCallback(
    <K extends keyof Opzioni>(chiave: K, valore: Opzioni[K]) =>
      setOpzioni((o) => ({ ...o, [chiave]: valore })),
    [],
  );

  const valore = useMemo(() => ({ opzioni, cambia }), [opzioni, cambia]);
  return <Contesto.Provider value={valore}>{children}</Contesto.Provider>;
}

export function usaBarra(): Barra {
  const o = useContext(Contesto);
  if (!o) throw new Error("usaBarra fuori da <ProvvedeBarra>");
  return o;
}
