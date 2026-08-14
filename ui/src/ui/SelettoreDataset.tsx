/**
 * Il selettore dataset del mockup: nome a sinistra, conteggio a destra.
 *
 * La meccanica — `<select>` nativo trasparente sopra il disegno — sta in
 * `SelettoreNativo`, che la spiega. Qui restano le decisioni sui dataset.
 *
 * I dataset con l'indice vuoto **compaiono, disabilitati, col motivo scritto**.
 * Toglierli direbbe che non esistono; lasciarli scegliere farebbe leggere come
 * ignoranza del modello cio' che e' assenza di dati.
 *
 * Il conteggio e' formattato nella lingua dell'interfaccia — `18.840` in
 * italiano, `18,840` in inglese. E' l'unico posto in cui il selettore lingua
 * tocca un numero, ed e' legittimo: e' cornice, non contenuto del corpus.
 */
import { usaBackend } from "../app/backend";
import { usaDataset } from "../app/dataset";
import { usaLingua } from "../app/i18n";
import type { DatasetView } from "../api/types";
import { SelettoreNativo } from "./SelettoreNativo";
import type { Voce } from "./SelettoreNativo";

const LOCALE = { it: "it-IT", en: "en-US" } as const;

export function SelettoreDataset() {
  const { t, lingua } = usaLingua();
  const { backend } = usaBackend();
  const { elenco, scelto, imposta } = usaDataset();

  const numero = (n: number) => n.toLocaleString(LOCALE[lingua]);
  const interrogabile = (d: DatasetView) => d.ready && d.n_chunks > 0;

  // «Non ho ancora chiesto» e «nessun indice pronto» non sono la stessa frase:
  // la seconda accusa l'ingestione di non essere stata fatta, e detta mentre la
  // risposta e' ancora in volo sarebbe un'accusa falsa. Stessa cosa col backend
  // caduto — li' il motivo sta nella colonna accanto, e ripeterlo qui darebbe
  // la colpa ai dati invece che al servizio.
  if (backend.stato !== "pronto") {
    return (
      <div className="rounded-[7px] border border-line-2 bg-surface px-[9px] py-[7px] text-[12px] text-muted">
        {backend.stato === "caricamento" ? (
          <span className="block h-[15px] w-2/3 animate-pulse rounded bg-surface-2" />
        ) : (
          <span aria-hidden="true">—</span>
        )}
      </div>
    );
  }

  if (elenco.length === 0 || scelto === null) {
    // Nessun indice pronto: uno stato, non un guasto. Un selettore vuoto e
    // cliccabile fingerebbe che ci sia qualcosa da scegliere.
    return (
      <div className="rounded-[7px] border border-line-2 border-dashed px-[9px] py-[7px] text-[12px] text-muted">
        {t("datasets.none")}
        <p className="mt-1 text-[10.5px] leading-snug">{t("datasets.none.hint")}</p>
      </div>
    );
  }

  const voci: Voce<string>[] = elenco.map((d) => ({
    valore: d.dataset_id,
    testo: interrogabile(d)
      ? `${d.dataset_id} · ${numero(d.n_chunks)} ${t("datasets.chunks")}`
      : `${d.dataset_id} · ${t("datasets.notQueryable")}`,
    disabilitata: !interrogabile(d),
  }));

  return (
    <SelettoreNativo
      etichetta={t("datasets.change")}
      valore={scelto.dataset_id}
      voci={voci}
      onCambia={imposta}
      className="flex items-center justify-between gap-2 rounded-[7px] border border-line-2 bg-surface px-[9px] py-[7px] text-[12px]"
    >
      <span className="truncate">{scelto.dataset_id}</span>
      <span className="font-mono text-[10px] text-muted tabular-nums">
        {numero(scelto.n_chunks)}
      </span>
    </SelettoreNativo>
  );
}
