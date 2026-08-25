import { useCallback } from "react";

import { usaEsploratore } from "../app/esploratore";
import { usaPresentazione } from "../app/presentazione";

/**
 * Chiude le pagine che stanno **sopra** la conversazione: l'esploratore del
 * corpus e «Che cos'e'».
 *
 * **La regola c'era gia', e non arrivava fin qui.** `chat.tsx` la dichiara per
 * il confronto, con queste parole: *«le tre azioni della corsia riportano al
 * filo… cambiare conversazione lasciando aperte due colonne che parlano di una
 * domanda dell'altra sarebbe la peggiore delle due uscite»*. Vale identica per
 * le due pagine — si apre una conversazione e si resta a guardare il corpus —
 * ma `nuova` e `apri` non potevano applicarla: `ProvvedeEsploratore` e
 * `ProvvedePresentazione` stanno **dentro** `ProvvedeChat`, e un provider non
 * legge i contesti dei suoi figli. Quindi lo dichiara chi naviga, come per
 * `usaChiudiCassetto`.
 *
 * Chiude tutt'e due anche quando una sola e' aperta: `chiudi` e' uno
 * `setState(false)`, e su uno stato gia' falso React non ridisegna. Distinguere
 * costerebbe due letture di contesto in piu' per non fare niente di diverso.
 *
 * **Non e' l'inverso di `apri`.** Le due pagine restano volutamente non
 * distruttive — si aprono sopra il confronto e sopra la chat senza toccarli, e
 * chiudendole si torna dov'eravamo. Qui a cambiare non e' la pagina: e' la
 * conversazione sotto, e guardare il corpus di una domanda che non e' piu'
 * quella aperta non e' «tornare dov'eravamo».
 */
export function usaChiudiPagine(): () => void {
  const { chiudi: chiudiCorpus } = usaEsploratore();
  const { chiudi: chiudiPresentazione } = usaPresentazione();

  return useCallback(() => {
    chiudiCorpus();
    chiudiPresentazione();
  }, [chiudiCorpus, chiudiPresentazione]);
}
