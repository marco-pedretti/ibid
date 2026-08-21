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
import type { Esito, EsitoNumerico, EsitoScheda, Marcato } from "../app/verdetti";
import type { Chiave } from "../i18n/strings";
import { InAttesa, NonCitata, NonSostiene, NonVerificata, Sostiene } from "./Icona";
import type { PropsIcona } from "./Icona";
import { Suggerimento } from "./Suggerimento";

/** I tre toni semantici, tenuti separati dall'accento: un verdetto colorato con
 *  l'accento smette di essere un verdetto e diventa decorazione (§12). */
export type Tono = "ok" | "warn" | "wait";

/** Esportata perche' la pagina «Che cos'e'» (U-19) giudica le tre affermazioni
 *  del progetto con la stessa grammatica con cui questo file giudica una
 *  citazione: un tono che diventa classi in due posti sarebbe due tabelle. */
export const TONO: Record<Tono, string> = {
  ok: "border-ok bg-ok-soft text-ok",
  warn: "border-warn bg-warn-soft text-warn",
  // `line-2` e non `wait`: il bordo di uno stato che non afferma niente non deve
  // pesare come quello di uno che afferma.
  wait: "border-line-2 bg-wait-soft text-wait",
};

interface Forma {
  glifo: (p: PropsIcona) => ReactNode;
  parola: Chiave;
  /** **Perche'** e' quel verdetto. Sta nella tabella accanto alla parola e non
   *  altrove: e' la spiegazione piu' utile del pannello, e finche' l'unico
   *  suggerimento stava sul numero accanto non c'era affatto. */
  perche: Chiave;
  tono: Tono;
}

const FORMA: Record<EsitoScheda["tipo"], Forma> = {
  sostiene: {
    glifo: Sostiene,
    parola: "verdict.supported",
    perche: "verdict.why.supported",
    tono: "ok",
  },
  nonSostiene: {
    glifo: NonSostiene,
    parola: "verdict.unsupported",
    perche: "verdict.why.unsupported",
    tono: "warn",
  },
  // Il glifo di «misto» e' la croce di proposito: qualcosa non regge, e quel
  // fatto non va attenuato. Quanto non regge lo dice la **parola**, che porta il
  // conteggio — e' il caso che dimostra perche' il glifo da solo non basta.
  misto: {
    glifo: NonSostiene,
    parola: "verdict.mixed",
    perche: "verdict.why.mixed",
    tono: "warn",
  },
  attesa: {
    glifo: InAttesa,
    parola: "verdict.pending",
    perche: "verdict.why.pending",
    tono: "wait",
  },
  nonVerificata: {
    glifo: NonVerificata,
    parola: "verdict.unverified",
    perche: "verdict.why.unverified",
    tono: "wait",
  },
  nonCitata: {
    glifo: NonCitata,
    parola: "verdict.notCited",
    perche: "verdict.why.notCited",
    tono: "wait",
  },
};

/* --- il marcatore in mezzo alla prosa -------------------------------------
   Lo stesso verdetto, dove la citazione **e'**: senza aprire nulla, che e'
   letteralmente il criterio di U-07.

   `attesa` qui e' **accento** e non `wait`, mentre nella pastiglia e' `wait`, e
   non e' un'incoerenza: sono due domande diverse. Sul marcatore la domanda e' «e'
   un riferimento valido?», e da `answer` in poi la risposta e' si' — il §3.5 lo
   chiama proprio il momento in cui il marcatore smette di essere inerte, e nel
   mockup e' `.mk.viva`. Nella pastiglia la domanda e' «qual e' il verdetto?», e
   li' non c'e' ancora.

   L'accento resta percio' fuori dai verdetti veri, come vuole il §12: un verdetto
   colorato con l'accento smette di essere un verdetto e diventa decorazione. Da
   qui una **divergenza dichiarata dal mockup**: li' un `[1]` verificato restava
   accento, perche' la bozza non modellava lo stato «non verificata». Con tutti e
   cinque gli stati sullo schermo, un marcatore sostenuto accento e uno non
   verificato accento sarebbero indistinguibili — cioe' il criterio di U-07
   mancato. */

const PAROLA: Record<Esito, Chiave> = {
  inerte: "verdict.inert",
  attesa: "verdict.pending",
  sostenuta: "verdict.supported",
  nonSostiene: "verdict.unsupported",
  nonVerificata: "verdict.unverified",
};

const GLIFO: Record<Esito, ((p: PropsIcona) => ReactNode) | null> = {
  // Inerte non ha glifo di proposito: non c'e' niente da dire di lui, e un segno
  // qualunque si leggerebbe come un verdetto arrivato prima del suo tempo.
  inerte: null,
  attesa: InAttesa,
  sostenuta: Sostiene,
  nonSostiene: NonSostiene,
  nonVerificata: NonVerificata,
};

const VESTE: Record<Esito, string> = {
  inerte: "border-b border-dotted border-line-2 px-px text-muted",
  attesa: "rounded-[3px] border-b border-accent bg-accent-soft px-[3px] text-accent",
  sostenuta: "rounded-[3px] border-b border-ok bg-ok-soft px-[3px] text-ok",
  nonSostiene: "rounded-[3px] border-b border-warn bg-warn-soft px-[3px] text-warn",
  nonVerificata: "rounded-[3px] border-b border-line-2 bg-wait-soft px-[3px] text-wait",
};

export function Marcatore({ marcato }: { marcato: Marcato }) {
  const { t, lingua } = usaLingua();
  const Glifo = GLIFO[marcato.esito];
  const parola = t(PAROLA[marcato.esito]);
  const punteggio = marcato.citazione?.score;

  // Il glifo e il colore non arrivano a chi ascolta, e il numero da solo non dice
  // niente: qui la parola non e' un extra, e' l'unica cosa che resta. Il
  // `Suggerimento` la porta in due modi insieme — la bolla per chi guarda,
  // `aria-describedby` per chi ascolta — quindi non serve un `aria-label`, che
  // sostituirebbe il `[3]` invece di aggiungersi.
  //
  // Due frasi intere invece di una frase piu' un pezzo attaccato in coda: il
  // punteggio non e' un'appendice, cambia dove va nella frase, e comporla a pezzi
  // la renderebbe intraducibile.
  const spiegazione =
    // Inerte non parla della citazione, parla del **testo**: dire «questa frase
    // cita la fonte 3» quando il parser puo' ancora scartare quel `[3]` sarebbe
    // promettere la cosa che il §3.5 vieta di promettere.
    marcato.esito === "inerte"
      ? t("verdict.marker.inert")
      : punteggio === undefined
        ? t("verdict.marker", { marker: marcato.marker, verdetto: parola })
        : t("verdict.marker.score", {
            marker: marcato.marker,
            verdetto: parola,
            punteggio: punteggio.toLocaleString(lingua === "it" ? "it-IT" : "en-US", {
              minimumFractionDigits: 3,
              maximumFractionDigits: 3,
            }),
          });

  return (
    <Suggerimento
      dato
      testo={spiegazione}
      className={`inline-flex items-center gap-[2px] py-px align-[0.32em] font-mono text-[10px] tabular-nums ${VESTE[marcato.esito]}`}
    >
      {`[${marcato.marker}]`}
      {Glifo && <Glifo size={9} />}
    </Suggerimento>
  );
}

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
 * Il punteggio, e quante frasi citano questa fonte.
 *
 * **Il punteggio c'e' sempre**, e non e' un ornamento: un «non sostiene» a 0,49 e
 * uno a 0,02 sono due cose diverse, e senza il numero il verdetto sembra
 * categorico dove invece c'e' una soglia.
 *
 * **Il conteggio e' `×n` e non `n/m`**, ed e' una correzione a una prima versione
 * che sbagliava in due modi. Metteva una probabilita' e un conteggio nello stesso
 * posto senza etichetta — distinguibili solo perche' una ha la virgola e l'altro
 * la barra, cioe' una cosa da decifrare — e per farci stare il conteggio faceva
 * **sparire** il punteggio proprio dove le frasi erano piu' d'una. `×2` non si
 * puo' leggere come una probabilita', e la frazione era comunque ridondante: se
 * il verdetto e' «sostiene» sono sostenute tutte per costruzione, e quando non
 * concordano lo dice la parola («1 su 3 non sostiene»).
 */
function dettaglioDi(
  esito: EsitoScheda,
  locale: string,
  t: (c: Chiave) => string,
): { punteggio: string; perche: string; quante: string | null } | null {
  if (esito.tipo !== "sostiene" && esito.tipo !== "nonSostiene") return null;
  return {
    punteggio: esito.punteggio.toLocaleString(locale, {
      minimumFractionDigits: 3,
      maximumFractionDigits: 3,
    }),
    // Il punteggio mostrato e' quello della citazione piu' vicina alla linea, e
    // con piu' di una frase questo va detto: altrimenti si legge come se
    // riguardasse tutte allo stesso modo.
    perche: t(esito.su > 1 ? "verdict.score.many" : "verdict.score"),
    quante: esito.su > 1 ? `×${esito.su}` : null,
  };
}

const PASTIGLIA =
  "inline-flex items-center gap-[5px] rounded border px-1.5 py-px font-mono text-[10px] tabular-nums";

/**
 * Il verdetto **numerico** di C-09, accanto a quello dell'NLI e non al suo posto.
 *
 * `schema.py` lo dichiara additivo, e la ragione e' misurata: su `ledger` il
 * 96,7% dei claim e' numerico, e un modello NLI addestrato su prosa non verifica
 * un'asserzione numerica contro una tabella. Visto dal vivo il 17 agosto — capex
 * di Sherwin-Williams, NLI «non sostiene» a 0,208, numerico che trova il 222,8
 * **dentro la tabella citata**: mostrando solo il primo si darebbe per verdetto
 * cio' che il progetto stesso documenta come debole li'.
 *
 * La parola dice **cosa** ha guardato («la tabella lo conferma») e non il nome del
 * verificatore: «numerico» richiederebbe una legenda, la tabella no.
 */
export function VerdettoNumerico({ esito }: { esito: EsitoNumerico }) {
  const { t } = usaLingua();
  const Glifo = esito.tipo === "sostiene" ? Sostiene : NonSostiene;
  const parola =
    esito.tipo === "misto"
      ? t("verdict.numeric.mixed", { quante: esito.nonSostengono, su: esito.su })
      : t(`verdict.numeric.${esito.tipo === "sostiene" ? "supported" : "unsupported"}`);

  return (
    <span className={`${PASTIGLIA} ${esito.tipo === "sostiene" ? TONO.ok : TONO.warn}`}>
      <Glifo size={11} />
      <Suggerimento dato testo={t("verdict.numeric.what")}>
        {parola}
      </Suggerimento>
    </span>
  );
}

export function Verdetto({ esito }: { esito: EsitoScheda }) {
  const { t, lingua } = usaLingua();
  const { glifo: Glifo, perche, tono } = FORMA[esito.tipo];
  const dettaglio = dettaglioDi(esito, lingua === "it" ? "it-IT" : "en-US", t);

  return (
    <span className={`${PASTIGLIA} ${TONO[tono]}`}>
      <Glifo size={11} />
      {/* Il suggerimento sta sulla **parola** e non sulla pastiglia intera: dentro
          ci sono due o tre cose diverse, e una bolla sola che copre tutto direbbe
          di ciascuna qualcosa che vale per un'altra. */}
      <Suggerimento dato testo={t(perche)}>
        {parolaDelVerdetto(esito, t)}
      </Suggerimento>
      {dettaglio !== null && (
        <>
          <Suggerimento dato testo={dettaglio.perche} className="text-muted">
            {dettaglio.punteggio}
          </Suggerimento>
          {dettaglio.quante !== null && (
            <Suggerimento dato testo={t("verdict.count")} className="text-muted opacity-70">
              {dettaglio.quante}
            </Suggerimento>
          )}
        </>
      )}
    </span>
  );
}
