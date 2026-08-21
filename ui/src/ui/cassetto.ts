/**
 * Il gesto che chiude il cassetto della corsia (U-21).
 *
 * A colonna sola la corsia non e' una colonna: e' uno strato che si apre sopra
 * il lavoro. Un comando che **cambia schermata** — nuova conversazione, una
 * voce di cronologia, l'esploratore, «Che cos'e'» — deve quindi anche togliere
 * di mezzo lo strato, altrimenti apre una cosa e la copre nello stesso gesto.
 * Uno che cambia **un'impostazione** — dataset, lingua, tema — no: lo si cambia
 * *per* guardare quel che c'e' sotto, e chiudersi addosso costringerebbe a
 * riaprire il cassetto per cambiare la seconda cosa.
 *
 * La distinzione la dichiara chi naviga, chiamando questo hook: e' la stessa
 * forma di `zona()` in U-20, dove a dichiararsi bersaglio della guida e' il
 * componente che disegna la zona e non un selettore indovinato da fuori.
 *
 * **Sta in un file suo per non fare un anello.** Il contesto lo provvede il
 * telaio, ma a leggerlo sono i comandi della corsia — e il telaio importa loro.
 * Con la coppia scritta dentro `Telaio.tsx` i due moduli si importerebbero a
 * vicenda: un anello che oggi il bundler scioglie e domani, con una costante
 * valutata al caricamento invece di una funzione, non scioglierebbe piu'.
 *
 * Il valore predefinito e' una funzione vuota. E' cio' che permette agli stessi
 * comandi di stare in tutte e due le forme senza saperlo: nelle colonne il
 * cassetto non c'e', e chiuderlo non fa niente.
 */
import { createContext, useContext } from "react";

export const Chiusura = createContext<() => void>(() => {});

export function usaChiudiCassetto(): () => void {
  return useContext(Chiusura);
}
