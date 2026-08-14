/**
 * Il selettore dataset del mockup: nome a sinistra, conteggio a destra.
 *
 * **Dentro c'e' un `<select>` nativo, reso trasparente sopra il disegno.** Non
 * e' un trucco: e' il modo di avere la forma del mockup senza riscrivere a mano
 * tastiera, ruolo ARIA, chiusura al clic fuori e voci disabilitate — quattro
 * cose che un menu fatto in casa sbaglia quasi sempre, e che qui non
 * costerebbero un componente ma un difetto di accessibilita'. Il mockup non
 * disegna la lista aperta, quindi lasciarla al sistema non tradisce niente.
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

  return (
    <div className="relative flex items-center justify-between gap-2 rounded-[7px] border border-line-2 bg-surface px-[9px] py-[7px] text-[12px] focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent">
      {/* Il disegno. Nascosto agli assistivi perche' il `<select>` qui sotto
          dice gia' le stesse cose, e sentirle due volte e' peggio che non
          vederle. */}
      <span aria-hidden="true" className="truncate">
        {scelto.dataset_id}
      </span>
      <span aria-hidden="true" className="font-mono text-[10px] text-muted tabular-nums">
        {numero(scelto.n_chunks)}
      </span>

      {/* `bg-surface text-ink` su un elemento a `opacity: 0` non e' una
          dimenticanza da ripulire: **la tendina e' un widget nativo a parte**, e
          l'opacita' non la tocca. Senza colori dichiarati eredita il testo
          (`--ink`, quasi bianco nel tema scuro) e dipinge il fondo col default
          dell'agente utente, che resta chiaro: bianco su bianco per ogni voce
          non evidenziata. Il colore va detto qui anche se qui non si vede. */}
      <select
        aria-label={t("datasets.change")}
        value={scelto.dataset_id}
        onChange={(e) => imposta(e.target.value)}
        className="absolute inset-0 w-full cursor-pointer bg-surface text-ink opacity-0"
      >
        {elenco.map((d) => (
          <option
            key={d.dataset_id}
            value={d.dataset_id}
            disabled={!interrogabile(d)}
            // Ripetuti sull'opzione perche' Chromium dipinge le voci col loro
            // stile, non con quello del `<select>`. Il disabilitato resta
            // leggibile e non invisibile: e' uno stato da capire, non da
            // indovinare.
            className={interrogabile(d) ? "bg-surface text-ink" : "bg-surface text-muted"}
          >
            {interrogabile(d)
              ? `${d.dataset_id} · ${numero(d.n_chunks)} ${t("datasets.chunks")}`
              : `${d.dataset_id} · ${t("datasets.notQueryable")}`}
          </option>
        ))}
      </select>
    </div>
  );
}
