/**
 * Il verdetto di una citazione, in forma leggibile (U-07).
 *
 * **Glifo, colore e parola insieme** — e' la regola del §12, e sta scritta qui
 * come una tabella invece che come una catena di `if`: aggiungere uno stato
 * significa aggiungere una riga con tutte e tre le cose, quindi non esiste il
 * caso di uno stato che ha il colore e non la parola.
 *
 * Il colore non fa il lavoro da solo per una ragione che non e' di stile: chi non
 * distingue l'ocra dal verde vedrebbe due pastiglie identiche, e in questo
 * progetto la differenza fra le due **e' la tesi**. Il glifo la porta nella forma
 * e la parola nel testo, cosi' la pastiglia resta vera anche in bianco e nero.
 *
 * `warn` e non un rosso: U-07 dice che una citazione che non regge non e' un
 * errore da nascondere, e' il dato. Un rosso contraddirebbe il §0 nel punto in
 * cui il progetto vuole essere misurato.
 */
import type { ReactNode } from "react";

import { usaLingua } from "../app/i18n";
import type { EsitoScheda } from "../app/verdetti";
import type { Chiave } from "../i18n/strings";
import { InAttesa, NonCitata, NonSostiene, NonVerificata, Sostiene } from "./Icona";
import type { PropsIcona } from "./Icona";

/** I tre toni semantici, tenuti separati dall'accento: un verdetto colorato con
 *  l'accento smette di essere un verdetto e diventa decorazione (§12). */
type Tono = "ok" | "warn" | "wait";

const TONO: Record<Tono, string> = {
  ok: "border-ok bg-ok-soft text-ok",
  warn: "border-warn bg-warn-soft text-warn",
  // `line-2` e non `wait`: il bordo di uno stato che non afferma niente non deve
  // pesare come quello di uno che afferma.
  wait: "border-line-2 bg-wait-soft text-wait",
};

interface Forma {
  glifo: (p: PropsIcona) => ReactNode;
  parola: Chiave;
  tono: Tono;
}

const FORMA: Record<EsitoScheda["tipo"], Forma> = {
  sostiene: { glifo: Sostiene, parola: "verdict.supported", tono: "ok" },
  nonSostiene: { glifo: NonSostiene, parola: "verdict.unsupported", tono: "warn" },
  // Il glifo di «misto» e' la croce di proposito: qualcosa non regge, e quel
  // fatto non va attenuato. Quanto non regge lo dice la **parola**, che porta il
  // conteggio — e' il caso che dimostra perche' il glifo da solo non basta.
  misto: { glifo: NonSostiene, parola: "verdict.mixed", tono: "warn" },
  attesa: { glifo: InAttesa, parola: "verdict.pending", tono: "wait" },
  nonVerificata: { glifo: NonVerificata, parola: "verdict.unverified", tono: "wait" },
  nonCitata: { glifo: NonCitata, parola: "verdict.notCited", tono: "wait" },
};

/** Il verdetto in parole, senza glifo: serve agli `aria-label` e ai `title`. */
export function parolaDelVerdetto(
  esito: EsitoScheda,
  t: (c: Chiave, v?: Record<string, string | number>) => string,
): string {
  if (esito.tipo === "misto") {
    return t("verdict.mixed", { quante: esito.nonSostengono, su: esito.su });
  }
  return t(FORMA[esito.tipo].parola);
}

/**
 * Il numero accanto alla parola, e quale numero sia dipende da quante frasi
 * citano questa fonte.
 *
 * Con **una** citazione e' il punteggio di implicazione, e non e' un ornamento:
 * un «non sostiene» a 0,49 e uno a 0,02 sono due cose diverse, e senza il numero
 * il verdetto sembra categorico dove invece c'e' una soglia.
 *
 * Con **piu'** citazioni e' il conteggio, perche' allora il punteggio riguarda
 * una frase sola e mostrarlo da solo farebbe credere che riguardi tutte. Il
 * conteggio dice invece su quante il verdetto vale, che e' l'informazione che
 * cambia quando le frasi sono tre.
 */
function dettaglioDi(
  esito: EsitoScheda,
  locale: string,
  t: (c: Chiave) => string,
): { valore: string; perche: string } | null {
  if (esito.tipo !== "sostiene" && esito.tipo !== "nonSostiene") return null;
  if (esito.su > 1) {
    const sostenute = esito.tipo === "sostiene" ? esito.su : 0;
    return { valore: `${sostenute}/${esito.su}`, perche: t("verdict.count") };
  }
  return {
    valore: esito.punteggio.toLocaleString(locale, {
      minimumFractionDigits: 3,
      maximumFractionDigits: 3,
    }),
    perche: t("verdict.score"),
  };
}

export function Verdetto({ esito }: { esito: EsitoScheda }) {
  const { t, lingua } = usaLingua();
  const { glifo: Glifo, tono } = FORMA[esito.tipo];
  const dettaglio = dettaglioDi(esito, lingua === "it" ? "it-IT" : "en-US", t);

  return (
    <span
      className={`inline-flex items-center gap-[5px] rounded border px-1.5 py-px font-mono text-[10px] tabular-nums ${TONO[tono]}`}
    >
      <Glifo size={11} />
      <span>{parolaDelVerdetto(esito, t)}</span>
      {dettaglio !== null && (
        <span className="text-muted" title={dettaglio.perche}>
          {dettaglio.valore}
        </span>
      )}
    </span>
  );
}
