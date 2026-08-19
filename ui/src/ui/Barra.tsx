/**
 * La barra sotto il campo: come nasce la prossima risposta.
 *
 * E' la fila di pastiglie del mockup (`.toggles`), e la forma viene da li' —
 * pillola, bordo sottile, 11 px, e un led che si accende. Il led non e'
 * decorazione: con una pastiglia sola il colore direbbe «acceso», ma queste
 * saranno cinque una accanto all'altra, e a quel punto acceso e spento devono
 * distinguersi **anche senza confrontare due colori vicini**.
 *
 * Ogni controllo qui manda un campo di `QueryRequest` e nessuno gira a vuoto:
 * e' il criterio di U-03, e la ragione per cui questa barra non e' arrivata
 * prima che l'API accettasse tutti i suoi campi (A-07).
 *
 * Il suggerimento «Invio per mandare» sta in fondo alla stessa riga e non piu'
 * su una sua: e' una frase che si legge una volta e poi smette di essere letta,
 * e non vale una riga di altezza tolta alla risposta. Qui occupa lo spazio che
 * la fila lascia libero comunque.
 */
import { useState } from "react";
import type { ReactNode } from "react";

import { usaBackend } from "../app/backend";
import { usaBarra } from "../app/barra";
import { usaLingua } from "../app/i18n";
import { COME_CONFIGURATO, avanzateToccate, ragionamentoDisponibile } from "../app/opzioni";
import type { Avanzate, Opzioni } from "../app/opzioni";
import { Caret } from "./Icona";
import { Selettore } from "./Selettore";
import { Suggerimento } from "./Suggerimento";

/**
 * La pastiglia del mockup (`.tg`): pillola, bordo sottile, 11 px.
 *
 * Il passaggio del mouse porta l'accento in **tutti** gli stati, acceso o
 * spento: un comando che si illumina solo quando e' gia' acceso non dice a chi
 * non l'ha mai toccato che si puo' toccare. E' la correzione che U-13 ha
 * imposto sul pulsante della cronologia, applicata qui prima di riceverla.
 */
const PASTIGLIA =
  "inline-flex items-center gap-1.5 rounded-full border py-1 pl-[7px] pr-2.5 text-[11px] transition-colors";
const SPENTA = "border-line-2 bg-surface text-ink-2 hover:border-accent-2 hover:text-ink";

export function Barra() {
  const { t } = usaLingua();
  const { backend } = usaBackend();
  const { opzioni } = usaBarra();
  const [aperte, setAperte] = useState(false);
  const capacita = backend.stato === "pronto" ? backend.capabilities : null;
  const sforzi = capacita?.reasoning_efforts ?? [];

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
      {ragionamentoDisponibile(sforzi) && (
        <Interruttore
          chiave="ragionamento"
          etichetta={t("bar.reasoning")}
          suggerimento={t("bar.reasoning.hint")}
        />
      )}

        <MenuModelli modelli={capacita?.models ?? []} />

        <Suggerimento testo={t("bar.advanced.hint")} fuoco={false}>
          <button
            type="button"
            aria-expanded={aperte}
            onClick={() => setAperte((x) => !x)}
            className={`${PASTIGLIA} ${
              // Toccato e chiuso, la pastiglia lo dice: «Avanzate» che tornasse
              // neutro nasconderebbe una configurazione diversa da quella che
              // sembra, ed e' l'unico controllo che puo' farlo.
              avanzateToccate(opzioni.avanzate)
                ? "border-accent bg-accent-soft text-accent hover:border-accent-2"
                : SPENTA
            }`}
          >
            {t("bar.advanced")}
            <Caret className={`transition-transform ${aperte ? "rotate-180" : ""}`} size={9} />
          </button>
        </Suggerimento>

        <p className="ml-auto font-mono text-[10px] text-muted">{t("chat.hint.invio")}</p>
      </div>
    </>
  );
}

/**
 * `retrieval_mode`, `rerank`, `top_k`, `hnsw_ef`: i quattro che l'API accetta e
 * che il §12 tiene chiusi.
 *
 * Ognuno parte da «come configurato» e resta muto finche' non lo si tocca —
 * stessa ragione del menu dei modelli: i default del servizio non li conosciamo,
 * e riempire i campi con dei numeri scriverebbe sopra la configurazione del
 * deployment dei valori che nessuno ha deciso.
 */
function PannelloAvanzate({ modalita }: { modalita: readonly string[] }) {
  const { t } = usaLingua();
  const { opzioni, cambia } = usaBarra();
  const a = opzioni.avanzate;
  const scrivi = (p: Partial<Avanzate>) => cambia("avanzate", { ...a, ...p });

  return (
    <div className="mt-[9px] flex flex-wrap items-end gap-x-4 gap-y-2.5 rounded-[7px] border border-line-2 bg-paper px-3 py-2.5">
      <Campo etichetta={t("bar.advanced.mode")}>
        <Selettore
          etichetta={t("bar.advanced.mode")}
          valore={a.retrieval_mode}
          voci={[
            { valore: COME_CONFIGURATO, testo: t("bar.model.default") },
            ...modalita.map((m) => ({ valore: m, testo: m })),
          ]}
          onCambia={(m) => scrivi({ retrieval_mode: m })}
          verso="su"
          className={`${PASTIGLIA} ${SPENTA}`}
        >
          {a.retrieval_mode === COME_CONFIGURATO ? (
            t("bar.model.default")
          ) : (
            <span className="font-mono">{a.retrieval_mode}</span>
          )}
        </Selettore>
      </Campo>

      <Campo etichetta={t("bar.advanced.rerank")}>
        <Selettore
          etichetta={t("bar.advanced.rerank")}
          valore={a.rerank === null ? "" : a.rerank ? "si" : "no"}
          voci={[
            { valore: "", testo: t("bar.model.default") },
            { valore: "si", testo: t("bar.advanced.on") },
            { valore: "no", testo: t("bar.advanced.off") },
          ]}
          onCambia={(v) => scrivi({ rerank: v === "" ? null : v === "si" })}
          verso="su"
          className={`${PASTIGLIA} ${SPENTA}`}
        >
          {a.rerank === null ?
            t("bar.model.default")
          : a.rerank ? t("bar.advanced.on")
          : t("bar.advanced.off")}
        </Selettore>
      </Campo>

      <Campo etichetta="top_k">
        <Numero valore={a.top_k} onCambia={(n) => scrivi({ top_k: n })} />
      </Campo>

      <Campo etichetta="hnsw_ef">
        <Numero valore={a.hnsw_ef} onCambia={(n) => scrivi({ hnsw_ef: n })} />
      </Campo>

      <p className="w-full text-[10.5px] leading-[1.5] text-muted">{t("bar.advanced.note")}</p>
    </div>
  );
}

function Campo({ etichetta, children }: { etichetta: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="font-mono text-[9.5px] tracking-[0.04em] text-muted uppercase">
        {etichetta}
      </span>
      {children}
    </label>
  );
}

/**
 * Un numero, o niente.
 *
 * Vuoto significa «come configurato», quindi non e' uno stato da correggere: il
 * segnaposto lo dice invece di lasciarlo indovinare. Un valore non intero o
 * minore di uno torna a vuoto, che e' l'unico modo di rifiutarlo senza inventare
 * un numero al posto di chi scrive.
 */
function Numero({
  valore,
  onCambia,
}: {
  valore: number | null;
  onCambia: (n: number | null) => void;
}) {
  const { t } = usaLingua();
  return (
    <input
      type="number"
      min={1}
      inputMode="numeric"
      value={valore ?? ""}
      placeholder={t("bar.model.default")}
      onChange={(e) => {
        const n = Number.parseInt(e.target.value, 10);
        onCambia(Number.isFinite(n) && n >= 1 ? n : null);
      }}
      className="w-[86px] rounded-full border border-line-2 bg-surface px-2.5 py-1 font-mono text-[11px] text-ink transition-colors placeholder:font-sans placeholder:text-muted hover:border-accent-2 focus:outline-2 focus:outline-offset-2 focus:outline-accent"
    />
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
 * invece del modello configurato, perche' elencarlo affermerebbe che esiste, che
 * e' precisamente cio' che non si e' potuto verificare. Qui la pastiglia resta
 * quindi **visibile e attenuata**, e il suggerimento dice perche': nasconderla
 * farebbe sparire insieme al comando anche il motivo per cui non c'e'.
 *
 * Attenuata e non `disabled`: un elemento disabilitato non riceve il puntatore,
 * quindi la bolla che spiega non si aprirebbe — la lezione delle voci di
 * cronologia in U-13.
 */
function MenuModelli({ modelli }: { modelli: readonly string[] }) {
  const { t } = usaLingua();
  const { opzioni, cambia } = usaBarra();

  if (modelli.length === 0) {
    return (
      <Suggerimento testo={t("bar.model.none")}>
        <span aria-disabled="true" className={`${PASTIGLIA} border-line-2 text-muted opacity-45`}>
          {t("bar.model")}
        </span>
      </Suggerimento>
    );
  }

  const voci = [
    { valore: COME_CONFIGURATO, testo: t("bar.model.default") },
    ...modelli.map((m) => ({ valore: m, testo: m })),
  ];

  return (
    <Suggerimento testo={t("bar.model.hint")} fuoco={false}>
      <Selettore
        etichetta={t("bar.model")}
        valore={opzioni.modello}
        voci={voci}
        onCambia={(m) => cambia("modello", m)}
        verso="su"
        className={`${PASTIGLIA} ${SPENTA}`}
      >
        {/* Finche' nessuno ha scelto, la pastiglia porta il **nome** del
            comando e non un modello: mostrare un id la' significherebbe dire
            «risponde questo», che e' l'unica cosa che qui non si sa. */}
        {opzioni.modello === COME_CONFIGURATO ? (
          t("bar.model")
        ) : (
          <span className="font-mono">{opzioni.modello}</span>
        )}
      </Selettore>
    </Suggerimento>
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
  const acceso = opzioni[chiave];

  return (
    <Suggerimento testo={suggerimento} fuoco={false}>
      <button
        type="button"
        aria-pressed={acceso}
        onClick={() => cambia(chiave, !acceso)}
        className={`${PASTIGLIA} ${
          acceso ? "border-accent bg-accent-soft text-accent hover:border-accent-2" : SPENTA
        }`}
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
