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
import { usaBackend } from "../app/backend";
import { usaBarra } from "../app/barra";
import { usaLingua } from "../app/i18n";
import { ragionamentoDisponibile } from "../app/opzioni";
import type { Opzioni } from "../app/opzioni";
import { Suggerimento } from "./Suggerimento";

export function Barra() {
  const { t } = usaLingua();
  const { backend } = usaBackend();
  const sforzi = backend.stato === "pronto" ? backend.capabilities.reasoning_efforts : [];

  return (
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

      <p className="ml-auto font-mono text-[10px] text-muted">{t("chat.hint.invio")}</p>
    </div>
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
 *
 * Il fuoco del passaggio del mouse porta l'accento **in tutti e due gli stati**,
 * acceso o spento: un comando che si illumina solo quando e' gia' acceso non
 * dice a chi non l'ha mai toccato che si puo' toccare.
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
        className={`inline-flex items-center gap-1.5 rounded-full border py-1 pl-[7px] pr-2.5 text-[11px] transition-colors ${
          acceso
            ? "border-accent bg-accent-soft text-accent hover:border-accent-2"
            : "border-line-2 bg-surface text-ink-2 hover:border-accent-2 hover:text-ink"
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
