/**
 * La barra sotto il campo: come nasce la prossima risposta.
 *
 * E' la fila di pastiglie del mockup (`.toggles`), e la forma viene da li' —
 * pillola, bordo sottile, 11 px, e un led che si accende. Il led non e'
 * decorazione: le pastiglie sono cinque una accanto all'altra, e a quel punto
 * acceso e spento devono distinguersi **anche senza confrontare due colori
 * vicini**.
 *
 * Ogni controllo qui manda un campo di `QueryRequest` e nessuno gira a vuoto:
 * e' il criterio di U-03, e la ragione per cui questa barra non e' arrivata
 * prima che l'API accettasse tutti i suoi campi (A-07).
 *
 * **Ogni controllo si apre sul valore in vigore**, letto da `/config`, e nei
 * menu quella voce e' marcata «predefinito». Non c'e' una voce «come
 * configurato»: era un modo di dire «non lo so», e il servizio lo pubblica.
 * Quando un valore si allontana dal predefinito il controllo diventa accento —
 * cosi' cio' che e' stato mosso si vede senza aprire niente, che e' l'unica cosa
 * che «Avanzate» chiuso potrebbe nascondere.
 *
 * «Invio per mandare» non sta qui: e' un'istruzione per **il campo**, e sta
 * sopra il campo. Era in fondo a questa riga, e le metteva accanto due cose che
 * non si somigliano — quattro comandi che decidono la risposta e una frase che
 * ricorda una scorciatoia da tastiera.
 */
import { useState } from "react";
import type { ReactNode } from "react";

import type { ModelView } from "../api/types";
import { usaBackend } from "../app/backend";
import { usaBarra } from "../app/barra";
import { usaLingua } from "../app/i18n";
import {
  comeTaglia,
  conModello,
  daNomi,
  finestraDi,
  modelli as modelliDelCatalogo,
  modelloDi,
} from "../app/catalogo";
import { avanzateToccate, modelloInstallato, ragionamentoDisponibile } from "../app/opzioni";
import type { Opzioni } from "../app/opzioni";
import { Meno, Piu, Ritorno } from "./Icona";
import { CaretTendina, Selettore } from "./Selettore";
import type { Voce } from "./Selettore";
import { Suggerimento } from "./Suggerimento";

/**
 * La pastiglia del mockup (`.tg`): pillola, bordo sottile, 11 px.
 *
 * Il passaggio del mouse porta l'accento in **tutti** gli stati: un comando che
 * si illumina solo quando e' gia' acceso non dice a chi non l'ha mai toccato che
 * si puo' toccare. E' la correzione che U-13 ha imposto sul pulsante della
 * cronologia, applicata qui prima di riceverla.
 */
const FORMA = "inline-flex items-center rounded-full border text-[11px] transition-colors";
const PASTIGLIA = `${FORMA} gap-1.5 py-1 pr-2.5 pl-[7px]`;
const RIPOSO = "border-line-2 bg-surface text-ink-2 hover:border-accent-2 hover:text-ink";
const MOSSA = "border-accent bg-accent-soft text-accent hover:border-accent-2";

export function Barra() {
  const { t } = usaLingua();
  const { backend } = usaBackend();
  const { opzioni, predefiniti } = usaBarra();
  const [aperte, setAperte] = useState(false);

  // Prima che `/config` risponda non c'e' niente da mostrare: i controlli non
  // saprebbero su quale valore aprirsi, e inventarglielo e' proprio cio' che si
  // e' tolto. Dura quanto il caricamento, che ha gia' la sua riga di stato.
  if (opzioni === null || predefiniti === null) return null;

  const capacita = backend.stato === "pronto" ? backend.capabilities : null;

  return (
    <>
      {/* Il pannello si apre **sopra** la barra e non sopra la conversazione:
          un riquadro flottante coprirebbe proprio la risposta di cui si sta
          cambiando la ricerca, e resterebbe da posizionare rispetto a un bordo
          che non c'e'. Qui spinge il filo in su di una striscia e resta visibile
          mentre si scrive la domanda seguente. */}
      {aperte && <PannelloAvanzate modalita={capacita?.retrieval_modes ?? []} />}

      <div className="mt-[9px] flex flex-wrap items-center gap-1.5">
        <Interruttore chiave="rag" etichetta={t("bar.rag")} suggerimento={t("bar.rag.hint")} />

        {/* Sparisce se il server non offre piu' i due capi dell'asse. Mostrarlo
            comunque darebbe un comando che risponde con un 422 — cioe' un guasto
            nostro presentato come un errore di chi clicca. */}
        {ragionamentoDisponibile(capacita?.reasoning_efforts ?? []) && (
          <Interruttore
            chiave="ragionamento"
            etichetta={t("bar.reasoning")}
            suggerimento={t("bar.reasoning.hint")}
          />
        )}

        <MenuModelli nomi={capacita?.models ?? []} catalogo={capacita?.model_catalog ?? []} />
        <MenuFinestre catalogo={capacita?.model_catalog ?? []} />

        <Suggerimento testo={t("bar.advanced.hint")} fuoco={false}>
          <button
            type="button"
            aria-expanded={aperte}
            onClick={() => setAperte((x) => !x)}
            // Mosso e richiuso, la pastiglia resta accesa: e' l'unico controllo
            // che puo' nascondere una configurazione diversa da quella che sembra.
            className={`${PASTIGLIA} ${avanzateToccate(opzioni, predefiniti) ? MOSSA : RIPOSO}`}
          >
            {t("bar.advanced")}
            <CaretTendina aperto={aperte} />
          </button>
        </Suggerimento>
      </div>
    </>
  );
}

/** Le voci di `Opzioni` che sono un acceso/spento: `chiave` non puo' puntare a
 *  un menu, e il compilatore lo dice invece del browser. */
type Interruttori = {
  [K in keyof Opzioni]: Opzioni[K] extends boolean ? K : never;
}[keyof Opzioni];

/**
 * Una pastiglia che commuta.
 *
 * `aria-pressed` e non un `aria-label` che dice lo stato: e' il ruolo che il
 * lettore di schermo annuncia da se', e una parola scritta a mano andrebbe
 * tenuta d'accordo con il colore per sempre.
 */
function Interruttore({
  chiave,
  etichetta,
  suggerimento,
}: {
  chiave: Interruttori;
  etichetta: string;
  suggerimento: string;
}) {
  const { opzioni, cambia } = usaBarra();
  if (opzioni === null) return null;
  const acceso = opzioni[chiave];

  return (
    <Suggerimento testo={suggerimento} fuoco={false}>
      <button
        type="button"
        aria-pressed={acceso}
        onClick={() => cambia(chiave, !acceso)}
        className={`${PASTIGLIA} ${acceso ? MOSSA : RIPOSO}`}
      >
        <span
          aria-hidden="true"
          className={`h-1.5 w-1.5 rounded-full ${acceso ? "bg-accent" : "bg-line-2"}`}
        />
        {etichetta}
      </button>
    </Suggerimento>
  );
}

/**
 * Un menu di valori, aperto su quello in vigore.
 *
 * Il predefinito porta la parola accanto, in mono nella colonna dei dettagli
 * (`Voce.dettaglio`): senza, «dense» e «hybrid» sarebbero due voci pari, e da
 * quale si e' partiti resterebbe una cosa da ricordare invece che da leggere.
 */
function Menu<T extends string>({
  etichetta,
  valore,
  predefinito,
  voci,
  onCambia,
  tono,
  children,
}: {
  etichetta: string;
  valore: T;
  predefinito: T;
  voci: readonly Voce<T>[];
  onCambia: (v: T) => void;
  /** Sostituisce il tono normale quando la voce scelta e' un problema. */
  tono?: string;
  children: ReactNode;
}) {
  const { t } = usaLingua();
  // Il dettaglio che c'e' gia' vince: «non installato» dice di piu' che
  // «predefinito», e sulla stessa voce sono tutti e due veri.
  const marcate = voci.map((v) =>
    v.valore === predefinito && v.dettaglio === undefined
      ? { ...v, dettaglio: t("bar.default") }
      : v,
  );

  return (
    <Selettore
      etichetta={etichetta}
      valore={valore}
      voci={marcate}
      onCambia={onCambia}
      verso="su"
      className={`${PASTIGLIA} ${tono ?? (valore === predefinito ? RIPOSO : MOSSA)}`}
    >
      {children}
    </Selettore>
  );
}

/**
 * Quale modello risponde — cioe' l'**affermazione 3 del §0** resa toccabile:
 * cambiare taglia sulla stessa domanda, col confronto affiancato li' accanto, e'
 * il modo in cui «con un buon retrieval la taglia conta meno del previsto»
 * smette di essere una tabella nel README.
 *
 * **Elenco vuoto non e' elenco assente.** Il servizio chiede i modelli a
 * `LLM_BASE_URL` e puo' non raggiungerlo; in quel caso A-07 restituisce `[]`
 * invece di inventare una lista. Il nome del modello configurato pero' si sa lo
 * stesso — `/config` lo dice — quindi la pastiglia resta **visibile e
 * attenuata** col nome dentro e il motivo nel suggerimento: cio' che manca non
 * e' sapere chi risponde, e' poterlo cambiare.
 *
 * Attenuata e non `disabled`: un elemento disabilitato non riceve il puntatore,
 * quindi la bolla che spiega non si aprirebbe — la lezione delle voci di
 * cronologia in U-13.
 */
function MenuModelli({
  nomi,
  catalogo,
}: {
  nomi: readonly string[];
  catalogo: readonly ModelView[];
}) {
  const { t } = usaLingua();
  const { opzioni, predefiniti, cambia } = usaBarra();
  if (opzioni === null || predefiniti === null) return null;

  if (nomi.length === 0) {
    return (
      <Suggerimento testo={t("bar.model.none")}>
        <span
          aria-disabled="true"
          className={`${PASTIGLIA} border-line-2 font-mono text-muted opacity-45`}
        >
          {opzioni.modello}
        </span>
      </Suggerimento>
    );
  }

  // Il primo selettore sceglie fra i **modelli**, non fra le voci del catalogo:
  // `gemma4-8k` e `gemma4-32k` sono la stessa scelta di modello con finestre
  // diverse, e metterle qui come due voci sarebbe mostrare il catalogo invece
  // della scelta. Senza catalogo, ogni nome e' un modello con una finestra sola.
  const elenco = catalogo.length > 0 ? modelliDelCatalogo(catalogo) : daNomi(nomi);
  const attuale = modelloDi(elenco, opzioni.modello);

  // Il predefinito puo' non essere fra gli installati: `/config` dice come il
  // deployment e' configurato, non cosa e' stato scaricato. Allora compare in
  // elenco lo stesso, **disabilitato**, perche' l'assenza di una voce non
  // spiegherebbe perche' non e' selezionata niente.
  const assente = !modelloInstallato(predefiniti.model, nomi);
  const voci = [
    ...(assente
      ? [
          {
            valore: predefiniti.model,
            testo: predefiniti.model,
            dettaglio: t("bar.model.notInstalled"),
            disabilitata: true,
          },
        ]
      : []),
    ...elenco.map((m) => ({ valore: m.nome, testo: m.nome })),
  ];

  const rotto = !modelloInstallato(opzioni.modello, nomi);

  return (
    <Suggerimento testo={rotto ? t("bar.model.missing") : t("bar.model.hint")} fuoco={false}>
      <Menu
        etichetta={t("bar.model")}
        valore={attuale?.nome ?? opzioni.modello}
        predefinito={modelloDi(elenco, predefiniti.model)?.nome ?? predefiniti.model}
        voci={voci}
        // Cambiando modello si tiene la finestra piu' vicina a quella che si
        // aveva: chi confronta due modelli sulla stessa domanda sta cambiando
        // **una** cosa.
        onCambia={(m) => cambia("modello", conModello(elenco, m, opzioni.modello))}
        // Non `danger`: non c'e' niente da distruggere, c'e' qualcosa da
        // sistemare — ed e' lo stesso tono degli altri rilievi (§12).
        tono={rotto ? "border-warn bg-warn-soft text-warn hover:border-warn" : undefined}
      >
        <span className="font-mono">{attuale?.nome ?? opzioni.modello}</span>
      </Menu>
    </Suggerimento>
  );
}

/**
 * Quanto testo entra nel modello scelto.
 *
 * **Compare solo quando c'e' una scelta**: se quel modello ha una finestra sola
 * — perche' nessuno ne ha create altre, o perche' il motore non pubblica il
 * catalogo — un menu da una voce non e' un controllo, e' un'etichetta che
 * assomiglia a un controllo. Sparisce, come sparisce il ragionamento quando
 * l'asse non c'e'.
 *
 * Le taglie offerte sono solo quelle **che quel modello regge**: il massimo non
 * e' uno solo (131.072 per `gemma4:e2b`, 262.144 per `gemma4:12b`), e una taglia
 * che compare e poi fallisce fa scoprire il limite dopo l'attesa, per giunta
 * come un errore invece che come un vincolo.
 */
function MenuFinestre({ catalogo }: { catalogo: readonly ModelView[] }) {
  const { t } = usaLingua();
  const { opzioni, predefiniti, cambia } = usaBarra();
  if (opzioni === null || predefiniti === null || catalogo.length === 0) return null;

  const elenco = modelliDelCatalogo(catalogo);
  const attuale = modelloDi(elenco, opzioni.modello);
  if (attuale === null) return null;

  const scelta = finestraDi(elenco, opzioni.modello);

  // **Con una finestra sola la pastiglia resta, attenuata.** Nasconderla era la
  // prima scelta, col ragionamento che un menu da una voce non e' un controllo:
  // vero, ma il risultato era che la funzione non esisteva finche' non si
  // lanciava uno script che nessuno aveva detto di lanciare. Qui il comando c'e'
  // e dice **perche'** non si puo' scegliere, che e' lo stesso rimedio gia' usato
  // sul menu dei modelli quando l'elenco non arriva: cio' che manca non e' la
  // scelta, e' che le taglie non sono state create.
  if (attuale.finestre.length < 2) {
    return (
      <Suggerimento testo={t("bar.context.only")}>
        <span
          aria-disabled="true"
          className={`${PASTIGLIA} border-line-2 font-mono text-muted opacity-45`}
        >
          {comeTaglia(scelta?.token ?? null, t("bar.context.default"))}
        </span>
      </Suggerimento>
    );
  }
  const nome = (f: { token: number | null }) => comeTaglia(f.token, t("bar.context.default"));

  // Su «non fissata» il suggerimento cambia: quella voce non e' una misura ma
  // **l'assenza** di una, e spiegarla insieme alle altre vorrebbe dire scrivere
  // una frase che vale per due cose diverse -- cioe' per nessuna delle due.
  const spiegazione = scelta?.token == null ? "bar.context.unset" : "bar.context.hint";

  return (
    <Suggerimento testo={t(spiegazione)} fuoco={false}>
      <Menu
        etichetta={t("bar.context")}
        valore={opzioni.modello}
        predefinito={finestraDi(elenco, predefiniti.model)?.modello ?? attuale.finestre[0].modello}
        voci={attuale.finestre.map((f) => ({
          valore: f.modello,
          testo: nome(f),
          // Il nome vero del catalogo sta nel dettaglio e non nella voce: e' cio'
          // che parte sul filo, e nasconderlo del tutto renderebbe impossibile
          // capire da «Dettagli della run» quale voce ha girato.
          dettaglio: f.modello,
        }))}
        onCambia={(m) => cambia("modello", m)}
      >
        <span className="font-mono">
          {comeTaglia(scelta?.token ?? null, t("bar.context.default"))}
        </span>
      </Menu>
    </Suggerimento>
  );
}

/**
 * `retrieval_mode`, `rerank`, `top_k`, `hnsw_ef`: i quattro che l'API accetta e
 * che il §12 tiene chiusi.
 *
 * Chiusi perche' un muro di manopole mostra l'ablation, che e' il lavoro della
 * dashboard. Raggiungibili perche' la demo li accetta gia', e nasconderli del
 * tutto significherebbe avere un'API piu' espressiva dell'interfaccia che la
 * presenta.
 *
 * **Senza una riga che spieghi le regole del pannello.** C'era, e diceva che
 * ogni manopola parte dal valore configurato e che il segno la riporta
 * indietro: due cose che il pannello **mostra gia'** — la voce marcata nel menu,
 * il segno che compare solo quando serve. Scrivere accanto a un'interfaccia cio'
 * che l'interfaccia sta facendo la appesantisce e non la spiega, e questo e' il
 * posto dove peserebbe di piu': quattro manopole che stanno chiuse proprio per
 * non diventare un muro.
 */
function PannelloAvanzate({ modalita }: { modalita: readonly string[] }) {
  const { t } = usaLingua();
  const { opzioni, predefiniti, cambia } = usaBarra();
  if (opzioni === null || predefiniti === null) return null;

  const SI = "si";
  const NO = "no";
  const comeSN = (b: boolean) => (b ? SI : NO);

  return (
    <div className="mt-[9px] flex flex-wrap items-end gap-x-4 gap-y-2.5 rounded-[7px] border border-line-2 bg-paper px-3 py-2.5">
      <Campo etichetta={t("bar.advanced.mode")}>
        <Menu
          etichetta={t("bar.advanced.mode")}
          valore={opzioni.retrieval_mode}
          predefinito={predefiniti.retrieval_mode}
          voci={modalita.map((m) => ({ valore: m, testo: m }))}
          onCambia={(m) => cambia("retrieval_mode", m)}
        >
          <span className="font-mono">{opzioni.retrieval_mode}</span>
        </Menu>
      </Campo>

      <Campo etichetta={t("bar.advanced.rerank")}>
        <Menu
          etichetta={t("bar.advanced.rerank")}
          valore={comeSN(opzioni.rerank)}
          predefinito={comeSN(predefiniti.rerank)}
          voci={[
            { valore: SI, testo: t("bar.advanced.on") },
            { valore: NO, testo: t("bar.advanced.off") },
          ]}
          onCambia={(v) => cambia("rerank", v === SI)}
        >
          {opzioni.rerank ? t("bar.advanced.on") : t("bar.advanced.off")}
        </Menu>
      </Campo>

      <Campo etichetta="top_k">
        <Passo
          valore={opzioni.top_k}
          predefinito={predefiniti.top_k}
          minimo={1}
          onCambia={(n) => cambia("top_k", n ?? predefiniti.top_k)}
        />
      </Campo>

      <Campo etichetta="hnsw_ef">
        <Passo
          valore={opzioni.hnsw_ef}
          predefinito={predefiniti.hnsw_ef}
          // Sotto il numero di candidati che l'indice deve visitare non ha senso
          // scendere: `null` non e' «zero», e' «decidi tu».
          minimo={16}
          passo={16}
          onCambia={(n) => cambia("hnsw_ef", n)}
        />
      </Campo>
    </div>
  );
}

function Campo({ etichetta, children }: { etichetta: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="font-mono text-[9.5px] tracking-[0.04em] text-muted uppercase">
        {etichetta}
      </span>
      {children}
    </div>
  );
}

/**
 * Un numero che si muove a passi, nella forma delle altre pastiglie.
 *
 * Era un `<input type="number">`, e non reggeva: le frecce native sono diverse
 * su ogni browser, non appartengono a questo vocabolario di pillole, e lasciano
 * scrivere un campo vuoto — cioe' uno stato che il valore non ha. Qui il numero
 * c'e' **sempre**, perche' si parte dal predefinito e non da niente.
 *
 * `null` resta possibile solo dove e' un valore vero: `hnsw_ef` non impostato
 * significa lasciar decidere l'indice, e si raggiunge scendendo sotto il minimo.
 * Non e' «vuoto», ed e' per questo che si legge `auto` e non uno spazio bianco.
 *
 * Quando ci si allontana dal predefinito compare il segno che riporta indietro:
 * una manopola senza ritorno costringe a ricordare da dove si era partiti, e
 * ricordare un numero e' esattamente cio' che «marcato come predefinito» esiste
 * per evitare.
 */
function Passo({
  valore,
  predefinito,
  minimo,
  passo = 1,
  onCambia,
}: {
  valore: number | null;
  predefinito: number | null;
  minimo: number;
  passo?: number;
  onCambia: (n: number | null) => void;
}) {
  const { t } = usaLingua();
  const mosso = valore !== predefinito;

  // Sotto il minimo si finisce su `null` solo se `null` e' un valore ammesso qui,
  // cioe' se e' il predefinito del servizio: altrimenti ci si ferma al minimo.
  const nullAmmesso = predefinito === null;
  const giu = () => {
    if (valore === null) return;
    const n = valore - passo;
    onCambia(n < minimo ? (nullAmmesso ? null : minimo) : n);
  };
  const su = () => onCambia(valore === null ? minimo : valore + passo);

  // `FORMA` e non `PASTIGLIA`: stessa pillola, ma i margini interni sono quelli
  // dei bottoncini, e due utility di padding nella stessa classe non si
  // annullano nell'ordine in cui sono scritte.
  return (
    <div className={`${FORMA} justify-between px-1 py-0.5 ${mosso ? MOSSA : RIPOSO}`}>
      <BottonePasso etichetta={t("bar.advanced.less")} onClick={giu} spento={valore === null}>
        <Meno size={11} />
      </BottonePasso>

      <span className="min-w-[3.5ch] text-center font-mono text-[11px] tabular-nums">
        {valore === null ? t("bar.advanced.auto") : valore}
      </span>

      {mosso ? (
        <BottonePasso etichetta={t("bar.advanced.reset")} onClick={() => onCambia(predefinito)}>
          <Ritorno size={11} />
        </BottonePasso>
      ) : (
        <span className="w-[18px]" aria-hidden="true" />
      )}

      <BottonePasso etichetta={t("bar.advanced.more")} onClick={su}>
        <Piu size={11} />
      </BottonePasso>
    </div>
  );
}

function BottonePasso({
  etichetta,
  onClick,
  spento = false,
  children,
}: {
  etichetta: string;
  onClick: () => void;
  spento?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={etichetta}
      aria-disabled={spento}
      onClick={() => !spento && onClick()}
      className="grid h-[18px] w-[18px] place-items-center rounded-full transition-colors hover:bg-accent-soft aria-disabled:opacity-30 aria-disabled:hover:bg-transparent"
    >
      {children}
    </button>
  );
}
