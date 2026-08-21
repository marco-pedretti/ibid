/**
 * «Che cos'e'»: cosa fa il progetto, cosa vuole dimostrare, e cosa non e' (U-19).
 *
 * **I numeri non ci sono, ed e' la meta' del criterio.** Il task ne ammette due
 * strade — quelli del README, da una fonte sola, oppure nessuno — e qui vale la
 * seconda. Le misure delle tre affermazioni vanno rifatte col prompt cambiato da
 * U-14: una copia scritta a mano in questa pagina resterebbe ferma a quelle
 * vecchie senza dirlo, e una pagina che spiega il progetto e' l'ultimo posto in
 * cui ci si puo' permettere un numero che era vero l'altro ieri. Cio' che manca
 * viene dichiarato invece che simulato: le tabelle stanno nel repository.
 *
 * **La configurazione invece si mostra, e non e' una misura.** Chi ha risposto e
 * su quale corpus sono le due cose che il criterio chiede per nome, e arrivano
 * vive da `/config` e da `/datasets` — le stesse due risposte che governano la
 * barra. La regola di quali righe esistono sta in `app/scheda.ts`, dove si puo'
 * provare senza un browser.
 *
 * **Le tre affermazioni portano un verdetto, con la grammatica dei verdetti.**
 * Stesso glifo, stesso tono, stessa pastiglia con cui `Verdetto` giudica una
 * citazione — perche' e' lo stesso gesto: dire se una cosa regge, e dirlo anche
 * quando non regge. La seconda affermazione **non regge**, ed e' scritta in ocra
 * dentro la pagina che presenta il progetto. Nasconderla avrebbe reso questa
 * pagina una pubblicita', che e' esattamente il contrario di cio' per cui il
 * progetto esiste.
 *
 * **Non e' una finestra sopra la chat, e' una schermata dentro il telaio.** Come
 * l'esploratore: si apre sopra cio' che c'era e chiudendola si torna li', perche'
 * leggere cosa fa il programma non deve costare la conversazione in corso. E come
 * l'esploratore non porta il pannello fonti: qui non c'e' una risposta di cui
 * chiedere l'origine.
 */
import type { ReactNode } from "react";

import { usaBackend } from "../app/backend";
import { usaDataset } from "../app/dataset";
import { usaLingua } from "../app/i18n";
import type { Traduci } from "../app/i18n";
import { usaPresentazione } from "../app/presentazione";
import { scheda } from "../app/scheda";
import type { Voce } from "../app/scheda";
import type { Chiave } from "../i18n/strings";
import { Etichetta } from "./Etichetta";
import { InAttesa, Indietro, NonSostiene, Sostiene } from "./Icona";
import type { PropsIcona } from "./Icona";
import { MISURA } from "./misura";
import { TONO } from "./Verdetto";
import type { Tono } from "./Verdetto";

/** Un'affermazione del §0, con l'esito che ha oggi. */
interface Affermazione {
  testo: Chiave;
  stato: Chiave;
  dettaglio: Chiave;
  glifo: (p: PropsIcona) => ReactNode;
  tono: Tono;
}

/**
 * Le tre, nell'ordine in cui il piano le numera.
 *
 * L'ordine non e' «prima quelle che reggono»: sono numerate 1, 2 e 3 in tutto il
 * progetto, e riordinarle qui vorrebbe dire che «l'affermazione 2» indica cose
 * diverse a seconda di dove la si legge. Che poi la 2 sia anche quella che non
 * regge e' un caso, e metterla in fondo l'avrebbe fatta sembrare una postilla.
 */
const AFFERMAZIONI: Affermazione[] = [
  {
    testo: "about.claim1",
    stato: "about.claim1.state",
    dettaglio: "about.claim1.detail",
    glifo: Sostiene,
    tono: "ok",
  },
  {
    testo: "about.claim2",
    stato: "about.claim2.state",
    dettaglio: "about.claim2.detail",
    glifo: NonSostiene,
    tono: "warn",
  },
  {
    testo: "about.claim3",
    stato: "about.claim3.state",
    dettaglio: "about.claim3.detail",
    glifo: InAttesa,
    tono: "wait",
  },
];

const LIMITI: Chiave[] = [
  "about.not.product",
  "about.not.world",
  "about.not.truth",
  "about.not.measure",
];

export function Presentazione() {
  const { t } = usaLingua();
  const { chiudi } = usaPresentazione();
  const { backend } = usaBackend();
  const { scelto } = usaDataset();

  const voci = scheda(backend.stato === "pronto" ? backend.predefiniti : null, scelto);

  return (
    <div className="flex h-full min-h-0 flex-col bg-paper">
      <div className="flex shrink-0 items-start gap-3 border-b border-line px-[22px] py-3">
        <div className="min-w-0 flex-1">
          <Etichetta>{t("about.title")}</Etichetta>
          <p className="mt-1 text-[13px] text-ink">{t("about.subtitle")}</p>
        </div>
        <button
          type="button"
          onClick={chiudi}
          className="flex shrink-0 items-center gap-1.5 rounded-md border border-line-2 px-[9px] py-[5px] text-[11px] text-ink-2 transition-colors hover:border-accent-2 hover:text-ink"
        >
          <Indietro size={12} />
          {t("about.back")}
        </button>
      </div>

      {/* Il contenitore che scorre resta largo quanto la colonna — e' lui che
          porta la barra di scorrimento — e la misura di lettura sta nel figlio.
          E' la stessa impaginazione della chat, per la stessa ragione. */}
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto px-[22px] py-5">
        <div className={`${MISURA} flex flex-col gap-7 pb-4`}>
          <Sezione titolo={t("about.what.title")}>
            <p className="text-[13px] leading-[1.65] text-ink">{t("about.what")}</p>
            <p className="text-[12.5px] leading-[1.65] text-ink-2">{t("about.name")}</p>
          </Sezione>

          <Sezione titolo={t("about.claims.title")}>
            <ol className="flex flex-col gap-2.5">
              {AFFERMAZIONI.map((a, i) => (
                <Riga key={a.testo} numero={i + 1} affermazione={a} t={t} />
              ))}
            </ol>
            <p className="text-[11.5px] leading-[1.6] text-muted">{t("about.claims.note")}</p>
          </Sezione>

          <Sezione titolo={t("about.now.title")}>
            {voci.length === 0 ? (
              <p className="text-[12.5px] leading-[1.65] text-ink-2">{t("about.now.missing")}</p>
            ) : (
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 rounded-lg border border-line-2 bg-surface px-3.5 py-3">
                {voci.map((v) => (
                  <Coppia key={v.nome} voce={v} t={t} />
                ))}
              </dl>
            )}
            <p className="text-[11.5px] leading-[1.6] text-muted">{t("about.now.note")}</p>
            {/* Il punto che il piano chiede di dire qui per nome: e' l'unica
                differenza fra come e' configurata la demo e come e' configurata
                la valutazione. Sta sotto la scheda e non dentro, perche' e' una
                ragione e non un valore. */}
            <p className="border-l-2 border-line-2 pl-3 text-[11.5px] leading-[1.6] text-ink-2">
              {t("about.now.exact.note")}
            </p>
          </Sezione>

          <Sezione titolo={t("about.not.title")}>
            <ul className="flex flex-col gap-2">
              {LIMITI.map((k) => (
                <li key={k} className="flex gap-2.5 text-[12.5px] leading-[1.65] text-ink-2">
                  {/* Un trattino disegnato, non un pallino di lista: sono quattro
                      frasi intere, e un elenco puntato le farebbe leggere come
                      voci di un menu. */}
                  <span aria-hidden="true" className="mt-[10px] h-px w-2.5 shrink-0 bg-line-2" />
                  <span>{t(k)}</span>
                </li>
              ))}
            </ul>
          </Sezione>
        </div>
      </div>
    </div>
  );
}

/** Titolo di prosa e non `Etichetta`: nel §12 il mono e' il ruolo dei dati, e
 *  questi titoletti aprono dei paragrafi. */
function Sezione({ titolo, children }: { titolo: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2.5">
      <h3 className="text-[12.5px] font-semibold text-ink">{titolo}</h3>
      {children}
    </section>
  );
}

function Riga({
  numero,
  affermazione,
  t,
}: {
  numero: number;
  affermazione: Affermazione;
  t: Traduci;
}) {
  const { testo, stato, dettaglio, glifo: Glifo, tono } = affermazione;

  return (
    <li className="rounded-lg border border-line-2 bg-surface px-3.5 py-3">
      <div className="flex items-baseline gap-2.5">
        {/* Il numero e' mono: e' l'identificativo con cui il progetto chiama
            questa affermazione ovunque, non un ornamento di lista. */}
        <span className="font-mono text-[11px] text-muted tabular-nums">{numero}</span>
        <p className="min-w-0 flex-1 text-[12.5px] leading-[1.6] text-ink">{t(testo)}</p>
        <span
          className={`inline-flex shrink-0 items-center gap-[5px] self-start rounded border px-1.5 py-px font-mono text-[10px] ${TONO[tono]}`}
        >
          <Glifo size={11} />
          {t(stato)}
        </span>
      </div>
      <p className="mt-1.5 pl-[22px] text-[11.5px] leading-[1.6] text-muted">{t(dettaglio)}</p>
    </li>
  );
}

/** Una riga della scheda. Cio' che arriva dal servizio si stampa in mono — il
 *  ruolo dei dati — e uno stato tradotto no: `hybrid` e' la parola che finisce
 *  sul filo, «acceso» e' una parola nostra. */
function Coppia({ voce, t }: { voce: Voce; t: Traduci }) {
  return (
    <>
      <dt className="text-[11.5px] text-ink-2">{t(voce.nome)}</dt>
      {"dato" in voce ? (
        <dd className="font-mono text-[11.5px] break-all text-ink">{voce.dato}</dd>
      ) : (
        <dd className="text-[11.5px] text-ink">{t(voce.testo)}</dd>
      )}
    </>
  );
}
