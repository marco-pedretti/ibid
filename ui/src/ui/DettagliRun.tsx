/**
 * «Dettagli della run» (D-5): dove ha cercato, come, e chi ha scritto.
 *
 * **E' uno strato in tutte e due le forme del telaio**, e non una quarta
 * colonna. U-21 usa gli strati per la corsia e le fonti *a colonna sola*,
 * perche' li' sostituiscono qualcosa; questo non sostituisce niente — e' un
 * riferimento che si consulta e si chiude, e una colonna permanente per
 * qualcosa che si guarda due volte a sessione toglierebbe spazio alla
 * conversazione ogni volta che non lo si guarda.
 *
 * **Appartiene a una risposta, non alla sessione.** Il modello e le opzioni si
 * cambiano fra una domanda e l'altra, quindi «la configurazione che ha girato»
 * e' una proprieta' dello scambio: il comando che apre questo foglio sta sotto
 * la sua risposta, accanto a «Confronta», ed e' la ragione per cui non e' un
 * pannello sempre presente che mostrerebbe solo l'ultima.
 *
 * **Non c'e' niente da toccare qui dentro**, e la sezione «Avanzate» resta
 * l'unico posto in cui si cambiano le cose. Un foglio che rilanciasse la
 * domanda con parametri diversi sarebbe un secondo comando di confronto, con la
 * differenza che nasconderebbe il fatto che sta cambiando due cose.
 */
import { usaBackend } from "../app/backend";
import type { Risposta } from "../app/conversazione";
import { gruppiDellaRun, indiceDi, type Valore } from "../app/dettagli";
import { usaLingua } from "../app/i18n";
import type { Chiave } from "../i18n/strings";
import { Chiudi } from "./Icona";
import { Strato } from "./Strato";

/** La larghezza del foglio. Piu' delle fonti (272) perche' qui le righe sono
 *  coppie nome-valore e non testo che va a capo: a 272 px le etichette lunghe
 *  si spezzerebbero tutte, e una tabella che va a capo smette di essere una
 *  tabella. */
const LARGHEZZA = 320;

/**
 * Un valore com'e' sul filo, come si scrive nella lingua scelta.
 *
 * **Le stringhe vuote e i `null` non si mostrano cosi'**: `filter_content_type`
 * vale `""` quando non filtra niente e `hnsw_ef` vale `null` quando lascia
 * decidere Qdrant, e in tutti e due i casi una cella vuota si legge come un
 * dato che manca invece che come una scelta fatta. Sono i due modi in cui
 * questa tabella potrebbe mentire tacendo.
 */
function scrivi(v: Valore, t: (c: Chiave) => string, locale: string): string {
  if (v === null || v === "") return t("run.valore.predefinito");
  if (typeof v === "boolean") return t(v ? "run.valore.si" : "run.valore.no");
  if (typeof v === "number") return v.toLocaleString(locale);
  return v;
}

export function DettagliRun({ risposta, chiudi }: { risposta: Risposta; chiudi: () => void }) {
  const { t, lingua } = usaLingua();
  const { backend } = usaBackend();
  const locale = lingua === "it" ? "it-IT" : "en-US";

  if (risposta.config === null) return null;
  const collections = backend.stato === "pronto" ? backend.capabilities.collections : [];
  const gruppi = gruppiDellaRun(
    risposta.config,
    risposta.collection,
    indiceDi(risposta.collection, collections),
  );

  return (
    <Strato lato="destra" larghezza={LARGHEZZA} chiudi={chiudi} nome={t("run.close")}>
      <div className="flex h-full flex-col border-l border-line bg-carta">
        <header className="flex shrink-0 items-center justify-between border-b border-line px-3 py-2">
          <h2 className="text-[12px] font-medium text-ink">{t("run.title")}</h2>
          <button
            type="button"
            onClick={chiudi}
            aria-label={t("run.close")}
            className="rounded p-1 text-muted transition-colors hover:bg-wait-soft hover:text-ink"
          >
            <Chiudi size={13} />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
          {gruppi.map((g) => (
            <section key={g.nome} className="mb-3 last:mb-0">
              <h3 className="mb-1 text-[10px] uppercase tracking-wide text-muted">
                {t(`run.gruppo.${g.nome}` as Chiave)}
              </h3>
              <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-[3px]">
                {g.righe.map((r) => (
                  <div key={r.nome} className="contents">
                    <dt className="truncate text-[11px] text-ink-2">
                      {t(`run.campo.${r.nome}` as Chiave)}
                    </dt>
                    <dd className="text-right font-mono text-[11px] tabular-nums text-ink">
                      {scrivi(r.valore, t, locale)}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}

          {/* La sezione dell'indice manca quando la risposta non dice su quale
              collection ha cercato — quelle salvate prima di D-5 — o quando il
              backend non la pubblica piu'. Tacere sarebbe corretto ma muto: chi
              guarda vedrebbe due sezioni invece di tre senza sapere perche'. */}
          {gruppi[0].nome !== "indice" && (
            <p className="border-t border-line pt-2 text-[10px] leading-relaxed text-muted">
              {t("run.indice.assente")}
            </p>
          )}
        </div>
      </div>
    </Strato>
  );
}
