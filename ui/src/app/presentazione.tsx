/**
 * La pagina «Che cos'e'»: aperta o no.
 *
 * Un contesto per un booleano, e non uno stato dentro `App`, per la stessa
 * ragione dell'esploratore: chi lo **apre** sta nella corsia, che e' dentro il
 * telaio, e chi lo **disegna** e' la colonna accanto. Passarlo come prop
 * vorrebbe dire far attraversare al telaio una cosa che non lo riguarda, in due
 * stati diversi (corsia larga e striscia) e in tre schermate.
 *
 * **Non si ricorda.** Le larghezze dell'esploratore e la corsia chiusa si
 * ricordano perche' sono preferenze — «lo schermo che ho, lo voglio cosi'» —
 * mentre questa e' una pagina che si legge e si chiude. Ritrovarla aperta al
 * prossimo avvio metterebbe una spiegazione davanti a chi l'ha gia' letta, che
 * e' il difetto che U-20 esiste apposta per evitare.
 */
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

interface Presentazione {
  /** La pagina e' sullo schermo, sopra qualunque cosa ci fosse. */
  aperta: boolean;
  apri: () => void;
  chiudi: () => void;
}

const Contesto = createContext<Presentazione | null>(null);

export function ProvvedePresentazione({ children }: { children: ReactNode }) {
  const [aperta, setAperta] = useState(false);
  const apri = useCallback(() => setAperta(true), []);
  const chiudi = useCallback(() => setAperta(false), []);
  const valore = useMemo(() => ({ aperta, apri, chiudi }), [aperta, apri, chiudi]);
  return <Contesto.Provider value={valore}>{children}</Contesto.Provider>;
}

export function usaPresentazione(): Presentazione {
  const p = useContext(Contesto);
  if (!p) throw new Error("usaPresentazione fuori da <ProvvedePresentazione>");
  return p;
}
