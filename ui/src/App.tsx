/**
 * Lo scheletro di U-00: prova che la catena regge, e nient'altro.
 *
 * Le quattro schermate sono U-01…U-07. Qui c'e' solo cio' che serve a sapere
 * che il frontend parla con l'API viva: se questa pagina elenca i dataset con i
 * loro conteggi, allora proxy, tipi generati, client e stato del backend
 * funzionano davvero — e i task successivi partono da terra ferma invece che da
 * un'ipotesi.
 */
import type { ReactNode } from "react";

import { ProvvedeBackend, usaBackend } from "./app/backend";
import { ProvvedeLingua, usaLingua } from "./app/i18n";
import { ProvvedeTema, usaTema } from "./app/theme";
import type { SceltaTema } from "./app/theme";
import { LINGUE } from "./i18n/strings";
import type { Lingua } from "./i18n/strings";

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
    <div className="min-h-dvh bg-ground text-ink">
      <Intestazione />
      <main className="mx-auto max-w-3xl px-6 py-10">
        <h1 className="text-3xl font-semibold tracking-tight">ibid</h1>
        <p className="mt-1 text-muted">{t("app.tagline")}</p>
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
        <span className="font-mono text-sm text-accent">ibid</span>
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
    <div className="flex items-center gap-1" role="group" aria-label={etichetta}>
      {children}
    </div>
  );
}

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
      className={`rounded-md px-2 py-1 text-xs transition-colors ${
        attivo
          ? "bg-accent text-accent-ink"
          : "bg-surface-2 text-muted hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

function StatoDelBackend() {
  const { t } = usaLingua();
  const { backend, ricarica } = usaBackend();

  if (backend.stato === "caricamento") {
    return <p className="mt-8 text-muted">{t("backend.loading")}</p>;
  }

  if (backend.stato === "guasto") {
    return (
      <section className="mt-8 rounded-lg border border-line bg-surface p-4">
        <h2 className="font-medium text-unsupported">{t("backend.down")}</h2>
        <p className="mt-1 text-sm text-muted">{t("backend.hint")}</p>
        <p className="mt-2 font-mono text-xs break-all text-muted">{backend.errore}</p>
        <button
          type="button"
          onClick={ricarica}
          className="mt-3 rounded-md bg-accent px-3 py-1.5 text-sm text-accent-ink"
        >
          {t("backend.retry")}
        </button>
      </section>
    );
  }

  const { datasets, models } = backend.capabilities;
  return (
    <div className="mt-8 grid gap-4 sm:grid-cols-2">
      <section className="rounded-lg border border-line bg-surface p-4">
        <h2 className="text-sm font-medium">{t("datasets.title")}</h2>
        <ul className="mt-2 space-y-1.5">
          {datasets.map((d) => (
            <li key={d.dataset_id} className="flex items-baseline justify-between gap-3">
              <span className="font-mono text-sm">{d.dataset_id}</span>
              <span className="text-xs text-muted tabular-nums">
                {d.ready
                  ? `${d.n_chunks.toLocaleString()} ${t("datasets.chunks")}`
                  : t("datasets.empty")}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-lg border border-line bg-surface p-4">
        <h2 className="text-sm font-medium">{t("models.title")}</h2>
        {models.length === 0 ? (
          // Vuota non e' un guasto: `/datasets` risponde comunque, perche' i
          // dataset non dipendono dall'LLM. Dichiararlo, non simularlo.
          <p className="mt-2 text-xs text-muted">{t("models.none")}</p>
        ) : (
          <ul className="mt-2 space-y-1.5">
            {models.map((m) => (
              <li key={m} className="font-mono text-sm">
                {m}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
