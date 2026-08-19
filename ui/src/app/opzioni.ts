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
import type { ConfigView, QueryRequest } from "../api/types";

export interface Opzioni {
  /** Il recupero dal corpus. Spento, il modello risponde da solo: e' la meta'
   *  nuda del confronto di U-03, non un guasto. */
  rag: boolean;
  /** Il ragionamento esteso. Acceso/spento e non cinque livelli: cinque livelli
   *  sono un'ablation, che e' il lavoro della dashboard. */
  ragionamento: boolean;
  /** Il modello che risponde, o `COME_CONFIGURATO` per non scegliere. */
  modello: string;
  /** I parametri di ricerca, chiusi sotto «Avanzate». */
  avanzate: Avanzate;
}

/**
 * «Non scelgo io»: il campo non parte, e decide il servizio.
 *
 * Serve perche' il frontend **non sa** cosa il servizio userebbe. `Capabilities`
 * elenca i modelli disponibili e le modalita' ammesse, non quelli configurati, e
 * preselezionare il primo dell'elenco scriverebbe una scelta che nessuno ha
 * fatto sopra quella del deployment — con l'aggravante che l'ordine e'
 * alfabetico, quindi il primo non ha alcun rapporto con niente. Qui tacere e'
 * l'unico modo di dire il vero, ed e' l'eccezione alla regola di
 * `campiRichiesta`.
 */
export const COME_CONFIGURATO = "";

/**
 * Le manopole del retrieval.
 *
 * Stanno chiuse, e il §12 dice perche': un muro di manopole mostra l'ablation,
 * che e' il lavoro della dashboard. Restano pero' **raggiungibili**, perche' la
 * demo le accetta gia' e nasconderle del tutto significherebbe avere un'API piu'
 * espressiva dell'interfaccia che la presenta.
 *
 * Ogni voce parte da «non scelto» — `""` o `null` — per lo stesso motivo del
 * modello: il frontend non conosce i default del servizio, e riempire i campi
 * con dei numeri scriverebbe sopra la configurazione del deployment dei valori
 * che nessuno ha deciso. Si manda solo cio' che si tocca.
 */
export interface Avanzate {
  retrieval_mode: string;
  rerank: boolean | null;
  top_k: number | null;
  hnsw_ef: number | null;
}

export const AVANZATE_INTATTE: Avanzate = {
  retrieval_mode: COME_CONFIGURATO,
  rerank: null,
  top_k: null,
  hnsw_ef: null,
};

/** Qualcuno ha toccato qualcosa: la pastiglia lo dice, altrimenti «Avanzate»
 *  chiuso nasconderebbe una configurazione diversa da quella che sembra. */
export function avanzateToccate(a: Avanzate): boolean {
  return (
    a.retrieval_mode !== COME_CONFIGURATO ||
    a.rerank !== null ||
    a.top_k !== null ||
    a.hnsw_ef !== null
  );
}

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
  avanzate: AVANZATE_INTATTE,
};

/**
 * Cosa la barra mette nella richiesta.
 *
 * Esplicito anche quando coincide col default: il campo che parte e' quello che
 * torna in `ConfigView`, e una richiesta che tace lascia decidere al server una
 * cosa che sullo schermo appare gia' decisa.
 *
 * Le eccezioni sono il modello e le avanzate, e per il motivo opposto: la'
 * sullo schermo c'e' scritto «come configurato», cioe' *non l'ho deciso io*, e
 * mandare un valore lo smentirebbe. Vedi `COME_CONFIGURATO`.
 */
export function campiRichiesta(o: Opzioni): Partial<QueryRequest> {
  const a = o.avanzate;
  return {
    rag: o.rag,
    reasoning_effort: o.ragionamento ? SFORZO.acceso : SFORZO.spento,
    ...(o.modello !== COME_CONFIGURATO && { model: o.modello }),
    ...(a.retrieval_mode !== COME_CONFIGURATO && { retrieval_mode: a.retrieval_mode }),
    ...(a.rerank !== null && { rerank: a.rerank }),
    ...(a.top_k !== null && { top_k: a.top_k }),
    ...(a.hnsw_ef !== null && { hnsw_ef: a.hnsw_ef }),
  };
}

/**
 * La configurazione che **ha girato**, rimessa in una richiesta.
 *
 * Serve al confronto, e la ragione e' il §15: *mai due cambiamenti insieme*.
 * Rilanciare la domanda con le opzioni della barra invece che con quelle della
 * risposta gia' data metterebbe nelle due colonne anche un modello diverso, o
 * un `top_k` cambiato nel frattempo — e il confronto direbbe «guarda cosa fa il
 * RAG» mostrando l'effetto di tre cose. Qui si copia tutto e si inverte una cosa
 * sola, che e' la definizione dell'esperimento.
 *
 * Copia **tutti** i campi di `ConfigView`, e un test lo verifica contando le
 * chiavi: un campo aggiunto al contratto e non aggiunto qui uscirebbe dal
 * confronto in silenzio, cioe' diventerebbe la seconda variabile che questa
 * funzione esiste per impedire.
 */
export function stessaConfigurazione(c: ConfigView): Partial<QueryRequest> {
  return {
    top_k: c.top_k,
    retrieval_mode: c.retrieval_mode,
    rerank: c.rerank,
    query_rewrite: c.query_rewrite,
    filter_content_type: c.filter_content_type,
    search_exact: c.search_exact,
    hnsw_ef: c.hnsw_ef,
    model: c.model,
    temperature: c.temperature,
    max_new_tokens: c.max_new_tokens,
    reasoning_effort: c.reasoning_effort,
    rag: c.rag,
    baseline_prompt: c.baseline_prompt,
    verify: c.verify,
  };
}
