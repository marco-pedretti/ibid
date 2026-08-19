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
  /** Il ragionamento esteso. Acceso/spento e non cinque livelli: cinque livelli
   *  sono un'ablation, che e' il lavoro della dashboard. */
  ragionamento: boolean;
  /** Il modello che risponde, o `COME_CONFIGURATO` per non scegliere. */
  modello: string;
}

/**
 * «Non scelgo io»: il campo non parte e risponde il modello del servizio.
 *
 * Serve perche' il frontend **non sa** quale sia. `Capabilities` elenca i
 * modelli disponibili, non quello configurato, e preselezionare il primo
 * dell'elenco scriverebbe una scelta che nessuno ha fatto sopra quella del
 * deployment — con l'aggravante che l'ordine e' alfabetico, quindi il primo non
 * ha alcun rapporto con niente. Qui tacere e' l'unico modo di dire il vero, ed
 * e' l'eccezione alla regola di `campiRichiesta`.
 */
export const COME_CONFIGURATO = "";

/**
 * I due capi dell'asse che C-07 ha misurato.
 *
 * Non sono una scelta di comodo: il suggerimento del controllo porta i numeri
 * di quella misura, e un interruttore che mandasse un livello diverso farebbe
 * descrivere a quei numeri un'altra cosa. Sul modello l'asse e' davvero binario
 * — `low` gia' produce lo stesso ragionamento di `high` (1410 token contro 267
 * di `none`), quindi «acceso» ha un solo significato.
 *
 * Sono due valori del server scritti qui, ed e' il motivo di
 * `ragionamentoDisponibile`: se `Capabilities` smette di offrirli, il comando
 * sparisce invece di mandare un 422. Una copia con la sua verifica accanto, non
 * una copia e basta.
 */
export const SFORZO = { spento: "none", acceso: "high" } as const;

/** Il server offre ancora tutti e due i capi dell'asse? Se no, l'interruttore
 *  non ha niente da mandare, e un comando che gira a vuoto e' il difetto che il
 *  criterio di U-03 nomina. */
export function ragionamentoDisponibile(sforzi: readonly string[]): boolean {
  return sforzi.includes(SFORZO.spento) && sforzi.includes(SFORZO.acceso);
}

/**
 * Da dove si parte, e a dove si torna ricaricando.
 *
 * `rag: true` non e' una copia del default del server — quello non lo
 * conosciamo, e U-00 vieta di tenerne una costante qui. E' la decisione della
 * barra: si comincia dal modo in cui il progetto funziona.
 *
 * Il ragionamento parte **spento**, e per una volta il default non e' «il modo
 * migliore» ma il modo misurato: C-07 dice che acceso compra +0,6 punti di
 * conformita' pagando 9,5x i token e trentaquattro astensioni in piu' su 200.
 * Accenderlo di partenza consegnerebbe come predefinito cio' che il progetto ha
 * misurato non convenire.
 */
export const PREDEFINITE: Opzioni = {
  rag: true,
  ragionamento: false,
  modello: COME_CONFIGURATO,
};

/**
 * Cosa la barra mette nella richiesta.
 *
 * Esplicito anche quando coincide col default: il campo che parte e' quello che
 * torna in `ConfigView`, e una richiesta che tace lascia decidere al server una
 * cosa che sullo schermo appare gia' decisa.
 *
 * L'unica eccezione e' il modello, e per il motivo opposto: la' sullo schermo
 * c'e' scritto «come configurato», cioe' *non l'ho deciso io*, e mandare un
 * valore lo smentirebbe. Vedi `COME_CONFIGURATO`.
 */
export function campiRichiesta(o: Opzioni): Partial<QueryRequest> {
  return {
    rag: o.rag,
    reasoning_effort: o.ragionamento ? SFORZO.acceso : SFORZO.spento,
    ...(o.modello !== COME_CONFIGURATO && { model: o.modello }),
  };
}
