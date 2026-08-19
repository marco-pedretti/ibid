/**
 * Come nasce la **prossima** risposta: i controlli della barra sotto il campo.
 *
 * Ogni voce qui e' un campo di `QueryRequest` che l'API accetta gia' — la barra
 * non aggiunge potere al servizio, gli da' una manopola. Il vocabolario dei
 * valori ammessi (`retrieval_modes`, `models`, `reasoning_efforts`,
 * `baseline_prompts`) viene da `Capabilities` e non da un elenco scritto qui:
 * e' la lezione di Q-06, e A-07 ha aggiunto due di quei campi guardando proprio
 * questa barra.
 *
 * **Niente di questa barra si ricorda oltre la sessione**, ed e' l'unica
 * decisione di stato che contiene. Il dataset si ricorda perche' e' una
 * preferenza — su quale corpus sto lavorando. «RAG spento, prompt permissivo,
 * `top_k` a 20» non e' una preferenza: e' un **esperimento**, e ritrovarlo
 * ancora impostato domani e' il modo in cui un risultato si legge come il
 * prodotto. Un ricaricamento riporta la barra al modo in cui il progetto e'
 * pensato per funzionare, che e' anche quello in cui e' stato misurato. Stessa
 * lettura di U-13: il caso frequente vince sul raro.
 *
 * La barra decide la prossima domanda; **cosa ha girato davvero** lo dice la
 * risposta, che porta il proprio `ConfigView`. Sono due dati diversi e non vanno
 * confusi: cambiare un controllo non riscrive le risposte gia' sullo schermo.
 */
import type { QueryRequest } from "../api/types";

export interface Opzioni {
  /** Il recupero dal corpus. Spento, il modello risponde da solo: e' la meta'
   *  nuda del confronto di U-03, non un guasto. */
  rag: boolean;
}

/**
 * Da dove si parte, e a dove si torna ricaricando.
 *
 * `rag: true` non e' una copia del default del server — quello non lo
 * conosciamo, e U-00 vieta di tenerne una costante qui. E' la decisione della
 * barra: si comincia dal modo in cui il progetto funziona.
 */
export const PREDEFINITE: Opzioni = { rag: true };

/**
 * Cosa la barra mette nella richiesta.
 *
 * Esplicito anche quando coincide col default: il campo che parte e' quello che
 * torna in `ConfigView`, e una richiesta che tace lascia decidere al server una
 * cosa che sullo schermo appare gia' decisa.
 */
export function campiRichiesta(o: Opzioni): Partial<QueryRequest> {
  return { rag: o.rag };
}
