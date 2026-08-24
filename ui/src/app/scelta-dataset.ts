/**
 * Quale dataset e' selezionato, e perche' quello.
 *
 * E' la regola di U-01 («cambio dataset senza riavvio») scritta come funzioni
 * pure, separate dal componente che le mostra. Non e' pulizia architetturale:
 * e' l'unico modo di **provarle**. I test girano in ambiente `node`, senza DOM,
 * quindi cio' che sta in un componente React non e' verificabile senza tirare
 * dentro jsdom e una libreria di rendering — due dipendenze da giustificare in
 * `STACK.md` per controllare una condizione che qui e' una `if`.
 *
 * Tre decisioni, e nessuna e' arbitraria:
 *
 * **Un dataset con l'indice vuoto si vede ma non si sceglie.** `DatasetView`
 * tiene `ready` e `n_chunks` separati apposta (§3.5): una collection che esiste
 * ed e' vuota e' uno stato reale, diverso dall'assenza. Nasconderlo direbbe una
 * bugia; renderlo selezionabile ne direbbe una peggiore, perche' ogni domanda
 * tornerebbe un'astensione e chi guarda leggerebbe «il modello non sa» dove la
 * verita' e' «non e' stato ingerito niente».
 *
 * **L'id ricordato vale solo se il server lo elenca ancora.** Il frontend non
 * porta nessuna costante del backend — e' il criterio di U-00 — e un id in
 * `localStorage` e' esattamente questo: una costante scritta mesi fa. Se non
 * c'e' piu' fra i dataset di `/datasets`, si butta, non si resuscita.
 *
 * **Nessuno pronto e' `null`, non il primo della lista.** Un indice non ancora
 * costruito e' la condizione normale di chi clona il repo, e va detta. Fingere
 * una selezione manderebbe query contro una collection vuota.
 */
import type { DatasetView } from "../api/types";
import { CHIAVI, ricorda, ricordato } from "./deposito";

/** Quelli su cui ha senso fare una domanda: indice presente e non vuoto. */
export function interrogabili(datasets: readonly DatasetView[]): DatasetView[] {
  return datasets.filter((d) => d.ready && d.n_chunks > 0);
}

/**
 * L'id da selezionare all'avvio, o `null` se nessun dataset e' interrogabile.
 *
 * L'ordine della lista non e' casuale ed e' quello del server (`REGISTRY` in
 * ordine di dichiarazione), quindi «il primo interrogabile» significa «il
 * principale, se e' pronto» senza che il frontend sappia quale sia.
 */
export function sceltaIniziale(
  datasets: readonly DatasetView[],
  salvato: string | null,
): string | null {
  const validi = interrogabili(datasets);
  if (salvato !== null && validi.some((d) => d.dataset_id === salvato)) return salvato;
  return validi.length > 0 ? validi[0].dataset_id : null;
}

/** L'id ricordato, o `null` — anche quando il deposito non c'e'. Un id di un
 *  dataset che non esiste piu' non fa danno: `sceltaIniziale` lo scarta. */
export function leggiSalvato(): string | null {
  return ricordato(CHIAVI.dataset);
}

/** Ricorda l'id scelto, e non si lamenta se non puo'. */
export function salva(dataset_id: string): void {
  ricorda(CHIAVI.dataset, dataset_id);
}
