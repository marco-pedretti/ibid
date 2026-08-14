/**
 * Lo scheletro di U-00: prova che la catena regge, e nient'altro.
 *
 * Le quattro schermate sono U-01…U-07, e il loro aspetto e' gia' deciso in
 * `docs/ui-mockup.html`. Qui c'e' solo cio' che serve a sapere che il frontend
 * parla con l'API viva: se questa pagina elenca i dataset con i loro conteggi,
 * allora proxy, tipi generati, client e stato del backend funzionano davvero —
 * e i task successivi partono da terra ferma invece che da un'ipotesi.
 *
 * Ma i **token** sono gia' quelli definitivi: colori, tipografia e marchio
 * vengono dal mockup, non da un provvisorio che poi qualcuno dovra' ricordarsi
 * di sostituire.
 */
import type { ReactNode } from "react";

import { ProvvedeBackend, usaBackend } from "./app/backend";
import { ProvvedeLingua, usaLingua } from "./app/i18n";
import { ProvvedeTema, usaTema } from "./app/theme";
import type { SceltaTema } from "./app/theme";
import { LINGUE } from "./i18n/strings";
import type { Lingua } from "./i18n/strings";
import { Marchio } from "./ui/Marchio";

export function App() {
  return (
    <ProvvedeLingua>
      <ProvvedeTema>
        <ProvvedeBackend>
          <Pagina />
        </ProvvedeBackend>
      </ProvvedeTema>
    </ProvvedeLingua>
  );
}

function Pagina() {
  const { t } = usaLingua();
  return (
    <div className="min-h-dvh bg-paper text-ink">
      <Intestazione />
      <main className="mx-auto max-w-3xl px-6 py-12">
        <h1 className="font-serif text-4xl font-semibold tracking-[-0.018em]">ibid</h1>
        <p className="mt-2 max-w-[60ch] text-ink-2">{t("app.tagline")}</p>
        <StatoDelBackend />
      </main>
    </div>
  );
}

function Intestazione() {
  const { t, lingua, imposta: impostaLingua } = usaLingua();
  const { scelta, imposta: impostaTema } = usaTema();

  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-4 px-6 py-3">
        <Marchio className="text-[19px]" />
        <div className="ml-auto flex items-center gap-4">
          <Gruppo etichetta={t("lang.label")}>
            {LINGUE.map((l: Lingua) => (
              <Bottone key={l} attivo={l === lingua} onClick={() => impostaLingua(l)}>
                {l.toUpperCase()}
              </Bottone>
            ))}
          </Gruppo>
          <Gruppo etichetta={t("theme.label")}>
            {(["light", "dark", "system"] as SceltaTema[]).map((s) => (
              <Bottone key={s} attivo={s === scelta} onClick={() => impostaTema(s)}>
                {t(`theme.${s}`)}
              </Bottone>
            ))}
          </Gruppo>
        </div>
      </div>
      <p className="mx-auto max-w-3xl px-6 pb-3 text-xs text-muted">{t("lang.note")}</p>
    </header>
  );
}

function Gruppo({ etichetta, children }: { etichetta: string; children: ReactNode }) {
  return (
    <div className="flex items-center gap-1.5" role="group" aria-label={etichetta}>
      {children}
    </div>
  );
}

/** La pillola del mockup: bordo sottile, e in accento quando e' quella scelta. */
function Bottone({
  attivo,
  onClick,
  children,
}: {
  attivo: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={attivo}
      className={`rounded-full border px-2.5 py-1 text-[11px] transition-colors ${
        attivo
          ? "border-accent bg-accent-soft font-medium text-accent"
          : "border-line-2 text-ink-2 hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

/** L'etichetta del mockup: mono, maiuscoletto, spaziata. */
function Etichetta({ children }: { children: ReactNode }) {
  return (
    <h2 className="font-mono text-[9.5px] font-semibold tracking-[0.12em] text-muted uppercase">
      {children}
    </h2>
  );
}

function StatoDelBackend() {
  const { t } = usaLingua();
  const { backend, ricarica } = usaBackend();

  if (backend.stato === "caricamento") {
    return (
      <p className="mt-10 flex items-center gap-2 font-mono text-xs text-muted">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
        {t("backend.loading")}
      </p>
    );
  }

  if (backend.stato === "guasto") {
    return (
      <section className="mt-10 rounded-lg border border-line-2 border-l-[3px] border-l-warn bg-warn-soft p-4">
        <h2 className="text-sm font-semibold">{t("backend.down")}</h2>
        <p className="mt-1 text-xs text-ink-2">{t("backend.hint")}</p>
        <p className="mt-2 font-mono text-[11px] break-all text-muted">{backend.errore}</p>
        <button
          type="button"
          onClick={ricarica}
          className="mt-3 rounded-md border border-accent bg-accent-soft px-3 py-1.5 text-xs font-medium text-accent"
        >
          {t("backend.retry")}
        </button>
      </section>
    );
  }

  const { datasets, models } = backend.capabilities;
  return (
    <div className="mt-10 grid gap-4 sm:grid-cols-2">
      <section className="rounded-lg border border-line bg-surface p-4 shadow-carta">
        <Etichetta>{t("datasets.title")}</Etichetta>
        <ul className="mt-3 space-y-2">
          {datasets.map((d) => (
            <li key={d.dataset_id} className="flex items-baseline justify-between gap-3">
              <span className="font-mono text-[12.5px]">{d.dataset_id}</span>
              <span className="font-mono text-[10.5px] text-muted tabular-nums">
                {d.ready
                  ? `${d.n_chunks.toLocaleString()} ${t("datasets.chunks")}`
                  : t("datasets.empty")}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border border-line bg-surface p-4 shadow-carta">
        <Etichetta>{t("models.title")}</Etichetta>
        {models.length === 0 ? (
          // Vuota non e' un guasto: `/datasets` risponde comunque, perche' i
          // dataset non dipendono dall'LLM. Dichiararlo, non simularlo.
          <p className="mt-3 text-[11px] text-muted">{t("models.none")}</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {models.map((m) => (
              <li key={m} className="font-mono text-[12.5px]">
                {m}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
