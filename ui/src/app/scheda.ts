/**
 * Cosa sta girando adesso: la scheda che la pagina «Che cos'e'» mostra in fondo.
 *
 * **Nessun valore scritto a mano.** Chi risponde e su quale corpus sono le due
 * cose che una dimostrazione deve dire di se', ed e' esattamente il punto in cui
 * e' piu' facile mentire senza volerlo: un nome di modello copiato in una
 * stringa resta li' quando il servizio ne carica un altro, e la pagina che
 * spiega il progetto diventa la sola parte dell'interfaccia che racconta una
 * configurazione che non esiste. Qui arrivano da `/config` e da `/datasets`, le
 * stesse due risposte che gia' governano la barra.
 *
 * **Un campo vuoto non diventa una riga.** E' la stessa regola del menu dei
 * modelli (A-07): quando l'endpoint non dice chi risponde, l'elenco resta vuoto
 * invece di mostrare il configurato: elencarlo affermerebbe che esiste, che e'
 * precisamente cio' che non si e' potuto verificare. Una riga «Chi risponde: —»
 * e' la stessa affermazione con un trattino davanti.
 *
 * **Due generi di valore, e si vedono diversi.** Cio' che arriva dal servizio si
 * stampa com'e', in mono, che in questa interfaccia e' il ruolo dei dati: e'
 * letteralmente la parola che finisce sul filo. Un interruttore no — `true` non
 * e' un dato da leggere, e' uno stato da dire in italiano.
 */
import type { ConfigView, DatasetView } from "../api/types";
import type { Chiave } from "../i18n/strings";

export type Voce =
  /** Viene dal servizio: si stampa com'e'. */
  | { nome: Chiave; dato: string }
  /** Uno stato, non un dato: si traduce. */
  | { nome: Chiave; testo: Chiave };

const ACCESO = "bar.advanced.on" as const;
const SPENTO = "bar.advanced.off" as const;

export function scheda(config: ConfigView | null, dataset: DatasetView | null): Voce[] {
  if (config === null) return [];

  const voci: Voce[] = [];
  if (config.model !== "") voci.push({ nome: "about.now.model", dato: config.model });
  if (dataset !== null) voci.push({ nome: "about.now.corpus", dato: dataset.dataset_id });
  if (config.retrieval_mode !== "")
    voci.push({ nome: "about.now.mode", dato: config.retrieval_mode });
  voci.push({ nome: "about.now.rerank", testo: config.rerank ? ACCESO : SPENTO });
  voci.push({ nome: "about.now.exact", testo: config.search_exact ? ACCESO : SPENTO });
  voci.push({ nome: "about.now.verify", testo: config.verify ? ACCESO : SPENTO });
  return voci;
}
