/**
 * Il selettore dataset del mockup: nome a sinistra, conteggio a destra.
 *
 * La meccanica — apertura, tastiera, ARIA, animazione — sta in `Selettore`,
 * che la spiega. Qui restano le decisioni sui dataset.
 *
 * I dataset con l'indice vuoto **compaiono, disabilitati, col motivo scritto**.
 * Toglierli direbbe che non esistono; lasciarli scegliere farebbe leggere come
 * ignoranza del modello cio' che e' assenza di dati.
 *
 * Il conteggio e' formattato nella lingua dell'interfaccia — `18.840` in
 * italiano, `18,840` in inglese. E' l'unico posto in cui il selettore lingua
 * tocca un numero, ed e' legittimo: e' cornice, non contenuto del corpus.
 *
 * **A corsia chiusa resta la tendina, non il nome** (U-18). Il nome di un
 * dataset in 34 px si potrebbe solo troncare, e qui sopra c'e' gia' scritto
 * perche' non lo si fa col conteggio: un numero troncato non e' un numero, e un
 * `open_ragb…` non e' un nome. Il pannello pero' si apre largo quanto le voci,
 * quindi il nome corrente si legge — col pallino d'accento accanto — con lo
 * stesso gesto con cui lo si cambia. Chi ascolta lo trova nell'`aria-label`, che
 * lo porta sempre. **Cio' che si perde e' la sua presenza fissa sullo schermo**,
 * e la perde chi ha scelto di chiudere la corsia.
 */
import { usaBackend } from "../app/backend";
import { usaDataset } from "../app/dataset";
import { usaLingua } from "../app/i18n";
import type { DatasetView } from "../api/types";
import { Indice } from "./Icona";
import { Selettore } from "./Selettore";
import type { Voce } from "./Selettore";
import { Suggerimento } from "./Suggerimento";

const LOCALE = { it: "it-IT", en: "en-US" } as const;

export function SelettoreDataset({ compatta = false }: { compatta?: boolean }) {
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
      <div
        className={`rounded-[7px] border border-line-2 bg-surface text-[12px] text-muted ${
          compatta ? "flex h-[34px] items-center justify-center" : "px-[9px] py-[7px]"
        }`}
      >
        {backend.stato === "caricamento" ? (
          <span
            className={`block h-[15px] animate-pulse rounded bg-surface-2 ${
              compatta ? "w-4" : "w-2/3"
            }`}
          />
        ) : (
          <span aria-hidden="true">—</span>
        )}
      </div>
    );
  }

  if (elenco.length === 0 || scelto === null) {
    // Nessun indice pronto: uno stato, non un guasto. Un selettore vuoto e
    // cliccabile fingerebbe che ci sia qualcosa da scegliere.
    //
    // Nella striscia le due frasi diventano una bolla: sono una spiegazione, e
    // una spiegazione che non ci sta si sposta, non si accorcia fino a non dire
    // piu' niente.
    if (compatta) {
      return (
        <Suggerimento testo={`${t("datasets.none")}. ${t("datasets.none.hint")}`}>
          <span className="flex h-[34px] items-center justify-center rounded-[7px] border border-line-2 border-dashed text-muted">
            <Indice size={13} />
          </span>
        </Suggerimento>
      );
    }
    return (
      <div className="rounded-[7px] border border-line-2 border-dashed px-[9px] py-[7px] text-[12px] text-muted">
        {t("datasets.none")}
        <p className="mt-1 text-[10.5px] leading-snug">{t("datasets.none.hint")}</p>
      </div>
    );
  }

  // Nome e conteggio separati, come sul bottone: nella corsia da 200 px una
  // riga sola andrebbe troncata a meta' del numero, e un numero troncato non e'
  // un numero -- e' un numero sbagliato.
  const voci: Voce<string>[] = elenco.map((d) => ({
    valore: d.dataset_id,
    testo: d.dataset_id,
    // Il secondo posto in cui la demo si dichiara (U-08): lo stato vuoto lo
    // dice per esteso, ma sparisce dopo la prima domanda, e questa tendina no.
    dettaglio: interrogabile(d)
      ? `${numero(d.n_chunks)} ${t("datasets.chunks")}${d.ridotto ? ` · ${t("datasets.reduced")}` : ""}`
      : t("datasets.empty"),
    disabilitata: !interrogabile(d),
  }));

  if (compatta) {
    return (
      <Selettore
        // Il nome sta nell'etichetta e non sul bottone: e' l'unico posto in cui
        // ci sta per intero.
        etichetta={`${t("datasets.change")}: ${scelto.dataset_id}`}
        valore={scelto.dataset_id}
        voci={voci}
        onCambia={imposta}
        className="flex h-[34px] items-center justify-center rounded-[7px] border border-line-2 bg-surface px-1"
      >
        <Indice size={13} className="text-ink-2" />
      </Selettore>
    );
  }

  return (
    <Selettore
      etichetta={t("datasets.change")}
      valore={scelto.dataset_id}
      voci={voci}
      onCambia={imposta}
      larghezza="bottone"
      className="flex items-center gap-2 rounded-[7px] border border-line-2 bg-surface px-[9px] py-[7px] text-[12px]"
    >
      <span className="truncate">{scelto.dataset_id}</span>
      {/* `ml-auto` e non `justify-between` sul contenitore: il caret arriva dopo
          questi due, e con `justify-between` finirebbe da solo a destra con il
          conteggio staccato in mezzo. */}
      <span className="ml-auto font-mono text-[10px] text-muted tabular-nums">
        {numero(scelto.n_chunks)}
      </span>
    </Selettore>
  );
}
