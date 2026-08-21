/**
 * Chi risponde e su quale corpus: le due cose che una dimostrazione deve dire
 * di se'.
 *
 * **Nessun valore scritto a mano.** E' il punto in cui e' piu' facile mentire
 * senza volerlo: un nome di modello copiato in una stringa resta li' quando il
 * servizio ne carica un altro, e la pagina che spiega il progetto diventa la
 * sola parte dell'interfaccia che racconta una configurazione che non esiste.
 * Qui arrivano da `/config` e da `/datasets`, le stesse due risposte che gia'
 * governano la barra.
 *
 * **O si sanno tutte e due, o non si dice.** E' la regola del menu dei modelli
 * (A-07): quando l'endpoint non dice chi risponde, l'elenco resta vuoto invece
 * di mostrare il configurato — elencarlo affermerebbe che esiste, che e'
 * precisamente cio' che non si e' potuto verificare. Una frase con un trattino
 * al posto del nome e' la stessa affermazione mancata, scritta piu' piano;
 * quindi o la frase porta i due nomi, o e' un'altra frase.
 *
 * **Sono un limite, non una scheda tecnica.** Finiscono dentro «cosa questa demo
 * non e'» — «non e' un panorama: risponde un modello solo, su un corpus solo» —
 * e non in una tabella di configurazione: quella c'e' gia' due volte, nella
 * barra sotto il campo e in «Dettagli della run», ed e' li' che serve mentre si
 * lavora. Qui serve la cosa che quelle due non dicono, cioe' che sono **una**.
 */
import type { ConfigView, DatasetView } from "../api/types";

export type Scheda =
  /** Il servizio ha detto tutte e due le cose. */
  | { noti: true; modello: string; corpus: string }
  /** Ne manca almeno una, e allora non se ne afferma nessuna. */
  | { noti: false };

export function scheda(config: ConfigView | null, dataset: DatasetView | null): Scheda {
  if (config === null || config.model === "" || dataset === null) return { noti: false };
  return { noti: true, modello: config.model, corpus: dataset.dataset_id };
}
