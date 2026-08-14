/**
 * La colonna di lavoro. Oggi mostra il dataset scelto; domani sara' la chat.
 *
 * U-01 chiede «cambio dataset senza riavvio», e un criterio del genere si
 * verifica solo se qualcosa **cambia sotto gli occhi** quando si sceglie:
 * collection, conteggio, forma dell'indice. Sono i dati che il backend gia'
 * risponde, non un segnaposto — quando arrivera' la chat prenderanno il loro
 * posto sotto «Dettagli della run», che il §12 vuole comunque leggibili.
 *
 * Gli stati del backend restano tre e non due: «sto contattando» non e' «e'
 * rotto», e la lista dei modelli **vuota non e' un guasto** — i dataset non
 * dipendono dall'endpoint di inferenza.
 */
import type { ReactNode } from "react";

import { ProvvedeBackend, usaBackend } from "./app/backend";
import { ProvvedeDataset, usaDataset } from "./app/dataset";
import { ProvvedeLingua, usaLingua } from "./app/i18n";
import { ProvvedeTema } from "./app/theme";
import type { CollectionView } from "./api/types";
import { Etichetta } from "./ui/Etichetta";
import { Telaio } from "./ui/Telaio";

export function App() {
  return (
    <ProvvedeLingua>
      <ProvvedeTema>
        <ProvvedeBackend>
          <ProvvedeDataset>
            <Telaio>
              <Colonna />
            </Telaio>
          </ProvvedeDataset>
        </ProvvedeBackend>
      </ProvvedeTema>
    </ProvvedeLingua>
  );
}

function Colonna() {
  const { t } = usaLingua();
  const { backend, ricarica } = usaBackend();

  if (backend.stato === "caricamento") {
    return (
      <div className="px-[22px] py-5">
        <p className="flex items-center gap-2 font-mono text-[11px] tracking-[0.02em] text-muted">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
          {t("backend.loading")}
        </p>
      </div>
    );
  }

  if (backend.stato === "guasto") {
    return (
      <div className="px-[22px] py-5">
        <section className="rounded-lg border border-line-2 border-l-[3px] border-l-warn bg-warn-soft p-4">
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
      </div>
    );
  }

  return <Pronto collections={backend.capabilities.collections} models={backend.capabilities.models} />;
}

function Pronto({
  collections,
  models,
}: {
  collections: CollectionView[];
  models: string[];
}) {
  const { t, lingua } = usaLingua();
  const { elenco, scelto } = usaDataset();
  const numero = (n: number) => n.toLocaleString(lingua === "it" ? "it-IT" : "en-US");
  const collection = collections.find((c) => c.name === scelto?.collection) ?? null;

  return (
    <div className="flex flex-col gap-5 px-[22px] py-5">
      <div>
        <h1 className="font-serif text-[21px] font-semibold tracking-[-0.01em]">
          {t("chat.soon")}
        </h1>
        <p className="mt-1.5 max-w-[62ch] text-[12.5px] text-muted">{t("chat.soon.hint")}</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Scheda titolo={t("datasets.title")}>
          <ul className="space-y-2">
            {elenco.map((d) => {
              const attivo = d.dataset_id === scelto?.dataset_id;
              return (
                <li key={d.dataset_id} className="flex items-baseline justify-between gap-3">
                  <span className="flex items-baseline gap-2 truncate">
                    {/* Il pallino dice quale sta girando: il selettore e questa
                        lista devono concordare a colpo d'occhio. */}
                    <span
                      aria-hidden="true"
                      className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                        attivo ? "bg-accent" : "bg-line-2"
                      }`}
                    />
                    <span
                      className={`font-mono text-[12.5px] ${attivo ? "text-ink" : "text-ink-2"}`}
                    >
                      {d.dataset_id}
                    </span>
                  </span>
                  <span className="font-mono text-[10.5px] text-muted tabular-nums">
                    {d.ready && d.n_chunks > 0
                      ? `${numero(d.n_chunks)} ${t("datasets.chunks")}`
                      : t("datasets.empty")}
                  </span>
                </li>
              );
            })}
          </ul>
        </Scheda>

        <Scheda titolo={t("index.title")}>
          {scelto === null ? (
            <p className="text-[11px] text-muted">{t("datasets.none")}</p>
          ) : collection === null ? (
            // La collection e' nominata dal dataset ma il server non la elenca:
            // succede fra un `make ingest` e l'altro, e dirlo costa una riga.
            <p className="text-[11px] text-muted">{t("index.missing")}</p>
          ) : (
            <ul className="space-y-2">
              <Riga chiave={t("index.collection")} valore={collection.name} />
              <Riga chiave={t("index.points")} valore={numero(collection.points)} />
              <Riga chiave={t("index.dense")} valore={collection.dense_size} />
              <Riga
                chiave={t("index.sparse")}
                valore={collection.has_sparse ? t("yes") : t("no")}
              />
            </ul>
          )}
        </Scheda>

        <Scheda titolo={t("models.title")}>
          {models.length === 0 ? (
            <p className="text-[11px] text-muted">{t("models.none")}</p>
          ) : (
            <ul className="space-y-2">
              {models.map((m) => (
                <li key={m} className="font-mono text-[12.5px]">
                  {m}
                </li>
              ))}
            </ul>
          )}
        </Scheda>
      </div>
    </div>
  );
}

function Scheda({ titolo, children }: { titolo: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-surface p-4 shadow-carta">
      <Etichetta>{titolo}</Etichetta>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Riga({ chiave, valore }: { chiave: string; valore: ReactNode }) {
  return (
    <li className="flex items-baseline justify-between gap-3">
      <span className="text-[11.5px] text-ink-2">{chiave}</span>
      <span className="font-mono text-[11px] tabular-nums">{valore}</span>
    </li>
  );
}
