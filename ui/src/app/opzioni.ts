/**
 * Come nasce la **prossima** risposta: i controlli della barra sotto il campo.
 *
 * Ogni voce qui e' un campo di `QueryRequest` che l'API accetta gia' — la barra
 * non aggiunge potere al servizio, gli da' una manopola. E ogni voce **parte dal
 * valore in vigore**, letto da `/config`: i controlli si aprono su cio' che
 * girerebbe comunque, e nel menu quella voce e' marcata «predefinito».
 *
 * Non era cosi' alla prima stesura, e vale la pena scrivere perche'. `/datasets`
 * elenca i valori *ammessi* e non quelli *configurati*, quindi ogni menu apriva
 * su una voce «come configurato» che significava «non lo mando e decidi tu». Era
 * onesto e sbagliato: l'interfaccia dichiarava di non sapere una cosa che il
 * servizio pubblica da A-04, e chi guardava non poteva vedere da dove stava
 * partendo. Bastava chiedere. Da qui **tutto parte esplicito**, e l'eccezione
 * non esiste piu'.
 *
 * Il vocabolario dei valori ammessi (`retrieval_modes`, `models`,
 * `reasoning_efforts`) resta quello di `Capabilities`, mai un elenco scritto
 * qui: e' la lezione di Q-06, e A-07 ha aggiunto due di quei campi guardando
 * proprio questa barra.
 *
 * **Niente di questa barra si ricorda oltre la sessione**, ed e' l'unica
 * decisione di stato che contiene. Il dataset si ricorda perche' e' una
 * preferenza — su quale corpus sto lavorando. «RAG spento, `top_k` a 20,
 * ragionamento acceso» non e' una preferenza: e' un **esperimento**, e
 * ritrovarlo ancora impostato domani e' il modo in cui un risultato si legge
 * come il prodotto. Un ricaricamento riporta la barra al modo in cui il servizio
 * e' configurato, che e' anche quello in cui e' stato misurato. Stessa lettura
 * di U-13: il caso frequente vince sul raro.
 *
 * La barra decide la prossima domanda; **cosa ha girato davvero** lo dice la
 * risposta, che porta il proprio `ConfigView`. Sono due dati diversi e non vanno
 * confusi: cambiare un controllo non riscrive le risposte gia' sullo schermo.
 */
import type { ConfigView, QueryRequest } from "../api/types";

/**
 * Piatta, e non con le avanzate in un oggetto annidato.
 *
 * «Avanzate» e' un raggruppamento dell'interfaccia — quattro controlli dietro
 * una pastiglia — non una proprieta' del dato: sul filo sono campi come gli
 * altri. Piatta si sovrappone ai predefiniti una chiave per volta, che e' il
 * modo in cui `ProvvedeBarra` tiene solo cio' che e' stato toccato.
 */
export interface Opzioni {
  /** Il recupero dal corpus. Spento, il modello risponde da solo: e' la meta'
   *  nuda del confronto di U-03, non un guasto. */
  rag: boolean;
  /** Il ragionamento esteso. Acceso/spento e non cinque livelli: cinque livelli
   *  sono un'ablation, che e' il lavoro della dashboard. */
  ragionamento: boolean;
  modello: string;
  retrieval_mode: string;
  rerank: boolean;
  top_k: number;
  /** `null` e' un valore vero e non «non scelto»: significa lasciare decidere
   *  l'indice, ed e' il predefinito di questo servizio. */
  hnsw_ef: number | null;
}

/** Le quattro che stanno chiuse sotto «Avanzate». Un elenco e non un oggetto
 *  annidato: vedi la nota su `Opzioni`. */
const AVANZATE = ["retrieval_mode", "rerank", "top_k", "hnsw_ef"] as const;

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
 * Che livello vuol dire «acceso» su questo deployment.
 *
 * Se il servizio e' configurato con un ragionamento acceso, accendere
 * l'interruttore deve tornare **al suo**, non al capo di C-07: altrimenti il
 * predefinito marcato nel menu e il valore che parte non sarebbero lo stesso, e
 * il controllo mentirebbe sul proprio stato di riposo.
 */
export function sforzoAcceso(c: ConfigView): string {
  return c.reasoning_effort === SFORZO.spento ? SFORZO.acceso : c.reasoning_effort;
}

/**
 * Il modello scelto c'e' davvero sul servizio di inferenza?
 *
 * Il caso che conta e' il **predefinito assente**: `/config` dice
 * `gemma4:latest` perche' e' cosi' che il deployment e' configurato, ma nessuno
 * garantisce che sia stato scaricato. Senza questo controllo la pastiglia
 * mostrerebbe un nome, il menu ne evidenzierebbe un altro — il primo
 * dell'elenco, per ripiego — e la domanda partirebbe lo stesso, per fallire dopo
 * l'attesa con un errore del modello.
 *
 * **Scaricarlo non e' un'opzione.** `POST /api/pull` e' l'API nativa di Ollama,
 * e STACK.md tiene l'inferenza dietro un endpoint OpenAI-compatibile proprio
 * perche' il repo giri anche su vLLM o llama.cpp server: un comando che scarica
 * ci inchioderebbe a un motore solo. E sono gigabyte su una macchina che puo'
 * non essere questa — mentre U-08 chiede che la demo si apra «in meno di 2
 * minuti **senza download**».
 *
 * Elenco vuoto vuol dire `true`: l'endpoint dei modelli non ha risposto, quindi
 * non si sa, e dichiarare assente cio' che non si e' potuto verificare e' lo
 * stesso errore che `catalog.models()` evita restituendo `[]`.
 */
export function modelloInstallato(modello: string, modelli: readonly string[]): boolean {
  return modelli.length === 0 || modelli.includes(modello);
}

/** I controlli aperti su cio' che girerebbe comunque. */
export function opzioniDa(c: ConfigView): Opzioni {
  return {
    rag: c.rag,
    ragionamento: c.reasoning_effort !== SFORZO.spento,
    modello: c.model,
    retrieval_mode: c.retrieval_mode,
    rerank: c.rerank,
    top_k: c.top_k,
    hnsw_ef: c.hnsw_ef,
  };
}

/** Qualcosa sotto «Avanzate» e' stato mosso: la pastiglia chiusa lo dice,
 *  altrimenti nasconderebbe una configurazione diversa da quella che sembra. */
export function avanzateToccate(o: Opzioni, c: ConfigView): boolean {
  return AVANZATE.some((k) => o[k] !== c[k]);
}

/**
 * Cosa la barra mette nella richiesta: **tutto**, esplicito.
 *
 * Anche quando coincide col predefinito. Il campo che parte e' quello che torna
 * in `ConfigView`, e una richiesta che tace lascerebbe decidere al server una
 * cosa che sullo schermo appare gia' decisa — con la differenza, ora che i
 * controlli mostrano i valori veri, che sullo schermo c'e' scritto **quale**.
 */
export function campiRichiesta(o: Opzioni, predefiniti: ConfigView): Partial<QueryRequest> {
  const k = configChiesta(o, predefiniti);
  return {
    rag: k.rag,
    reasoning_effort: k.reasoning_effort,
    model: k.model,
    retrieval_mode: k.retrieval_mode,
    rerank: k.rerank,
    top_k: k.top_k,
    hnsw_ef: k.hnsw_ef,
  };
}

/**
 * La configurazione **che questa domanda chiede**, intera.
 *
 * I sette campi della barra sopra i predefiniti del servizio: gli altri sette
 * non li tocca nessuno da qui, quindi restano quelli in vigore. Serve a U-15,
 * che vuole mostrare cosa e' cambiato **premendo invio** e non a generazione
 * finita — `ConfigView` arriva con `done`, cioe' dopo ~11 s.
 *
 * `campiRichiesta` ne e' derivata e non parallela, ed e' il punto: cio' che si
 * mostra come chiesto e cio' che parte sul filo sono lo stesso oggetto letto due
 * volte. Due funzioni separate si sarebbero allontanate al primo campo aggiunto
 * alla barra, e la riga avrebbe dichiarato una configurazione che non e' quella
 * mandata — un errore che nessuno vedrebbe, perche' il numero sbagliato sarebbe
 * *plausibile*.
 */
export function configChiesta(o: Opzioni, predefiniti: ConfigView): ConfigView {
  return {
    ...predefiniti,
    rag: o.rag,
    reasoning_effort: o.ragionamento ? sforzoAcceso(predefiniti) : SFORZO.spento,
    model: o.modello,
    retrieval_mode: o.retrieval_mode,
    rerank: o.rerank,
    top_k: o.top_k,
    hnsw_ef: o.hnsw_ef,
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
 * Copia tutti i campi di `ConfigView` **tranne quelli di `NON_RICHIEDIBILI`**, e
 * un test lo verifica contando le chiavi: un campo aggiunto al contratto e non
 * aggiunto qui uscirebbe dal confronto in silenzio, cioe' diventerebbe la
 * seconda variabile che questa funzione esiste per impedire.
 */

/**
 * I campi di `ConfigView` che una richiesta **non puo' portare**, e che quindi
 * il confronto non copia.
 *
 * Oggi ce n'e' uno, `entailment_threshold` (D-7), e non copiarlo e' sicuro per
 * la ragione precisa per cui non e' richiedibile: e' una costante del backend,
 * quindi vale identica nei due bracci del confronto **per costruzione**. Non e'
 * un'eccezione alla regola del §15 — e' un campo che non puo' variare, e la
 * regola parla di cio' che varia.
 *
 * Sta qui come elenco e non come `omit` scritto a mano dentro la funzione
 * perche' il test lo legge: cosi' aggiungere un campo non richiedibile domani
 * chiede di dichiararlo qui, invece di far passare in silenzio la rete che
 * conta le chiavi.
 */
export const NON_RICHIEDIBILI = [
  "entailment_threshold",
] as const satisfies readonly (keyof ConfigView)[];
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
