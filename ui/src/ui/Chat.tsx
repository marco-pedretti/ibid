/**
 * La colonna centrale: le domande, le risposte mentre si formano, il campo.
 *
 * **Nessun selettore di modalita'** (U-02): non c'e' un «modo documenti» e un
 * «modo risposta». Le fonti stanno sempre nella colonna accanto, la sintesi
 * sempre qui, e non c'e' niente da scegliere per vedere l'una o l'altra.
 *
 * Ogni fase del §3.5 ha una riga di stato sua. Otto stati e non «carica / non
 * carica»: chi guarda deve sapere se il ritardo e' il retrieval, il modello o
 * la verifica, altrimenti undici secondi di attesa si leggono tutti come un
 * blocco.
 */
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

import { usaChat } from "../app/chat";
import { chiSiEAstenuto, inCorso } from "../app/conversazione";
import type { Risposta, Scambio } from "../app/conversazione";
import { usaDataset } from "../app/dataset";
import { esempiDi } from "../app/esempi";
import { usaLingua } from "../app/i18n";
import { riepilogo } from "../app/verdetti";
import type { Riepilogo } from "../app/verdetti";
import { Barra } from "./Barra";
import {
  Astensione,
  Avvertimento,
  Discordi,
  DueColonne,
  FrecciaSu,
  NonCitata,
  NonSostiene,
  NonVerificata,
  Troncato,
} from "./Icona";
import { Suggerimento } from "./Suggerimento";
import { Testo } from "./Testo";

export function Chat() {
  const { scambi } = usaChat();
  const fondo = useRef<HTMLDivElement>(null);

  // Segue il testo mentre arriva. Senza, i token scorrono sotto il bordo e chi
  // guarda crede che la risposta si sia fermata.
  useEffect(() => {
    fondo.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [scambi]);

  return (
    <div className="flex h-full min-h-0 flex-col bg-paper">
      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-[22px] py-5">
        {scambi.length === 0 ? <Vuoto /> : scambi.map((s) => <Turno key={s.id} scambio={s} />)}
        <div ref={fondo} />
      </div>
      <Campo />
    </div>
  );
}

/* --- lo stato iniziale --------------------------------------------------- */

function Vuoto() {
  const { t, lingua } = usaLingua();
  const { scelto } = usaDataset();
  const { invia } = usaChat();
  const esempi = esempiDi(scelto?.dataset_id ?? null);
  // Vero quando la lingua dell'interfaccia non e' quella del corpus: solo
  // allora la riga in mono aggiunge qualcosa, e solo allora la nota va spiegata.
  const tradotti = esempi.some((e) => e.testo[lingua] !== e.query);

  return (
    <div className="my-auto py-2">
      <h2 className="mb-1.5 font-serif text-[21px] font-semibold tracking-[-0.01em]">
        {t("chat.empty.title")}
      </h2>
      <p className="mb-[18px] max-w-[62ch] text-[12.5px] text-muted">{t("chat.empty.hint")}</p>

      <div className="flex flex-col gap-2">
        {esempi.map((e, i) => (
          <button
            key={e.query}
            type="button"
            onClick={() => invia(e.query)}
            className="flex items-start gap-[11px] rounded-lg border border-line bg-surface px-[13px] py-[11px] text-left transition-colors hover:border-line-2"
          >
            <span className="mt-px font-mono text-[10px] text-accent tabular-nums">{i + 1}</span>
            <span className="text-[12.5px] text-ink">
              {e.testo[lingua]}
              {/* La query com'e' scritta sul filo. In mono perche' nel §12 il
                  mono e' il ruolo dei dati, e questo e' letteralmente il dato
                  che parte: si vede prima di cliccare, non dopo. */}
              {e.testo[lingua] !== e.query && (
                <span className="mt-1 block font-mono text-[10.5px] text-ink-2">{e.query}</span>
              )}
              <span className="mt-1 block text-[11px] text-muted">{t(e.nota)}</span>
            </span>
          </button>
        ))}
      </div>

      {/* Spiega **le due righe** di ogni esempio, che e' la cosa che si vede qui.
          Prima diceva «la risposta segue la lingua della domanda, non questo
          selettore», e quel «questo» non aveva un referente: il selettore e' una
          pastiglia in fondo alla corsia, lontana e senza un nome scritto. Quella
          frase e' ora il suggerimento del selettore, dove «questo» si vede. */}
      {tradotti && <p className="mt-3 max-w-[62ch] text-[11px] text-muted">{t("example.lang")}</p>}
    </div>
  );
}

/* --- una domanda e la sua risposta --------------------------------------- */

function Turno({ scambio }: { scambio: Scambio }) {
  const { risposta } = scambio;

  return (
    <div className="flex flex-col gap-4">
      <div className="max-w-[78%] self-end rounded-[12px_12px_3px_12px] border border-line bg-accent-soft px-[13px] py-[9px] text-[13px] text-ink">
        {scambio.domanda}
      </div>

      <div className="flex max-w-[92%] flex-col gap-[9px]">
        <RigaStato risposta={risposta} />
        <Corpo scambio={scambio} />
      </div>
    </div>
  );
}

function RigaStato({ risposta }: { risposta: Risposta }) {
  const { t, lingua } = usaLingua();
  const r = risposta;

  // I nomi arrivano dal server (`retrieval_s`, `generation_s`, ...) e restano i
  // suoi: tradurli qui vorrebbe dire tenere un elenco di chiavi del backend nel
  // frontend, e una chiave nuova comparirebbe senza nome. Si toglie solo il
  // suffisso `_s`, che altrimenti si leggerebbe due volte accanto a « s».
  const tempi = Object.entries(r.tempi)
    .map(
      ([nome, secondi]) =>
        `${nome.replace(/_s$/, "")} ${secondi.toLocaleString(lingua === "it" ? "it-IT" : "en-US", { maximumFractionDigits: 2 })} s`,
    )
    .join(" · ");

  const testo =
    r.fase === "attesa"
      ? t("stato.attesa")
      : r.fase === "fonti"
        ? `${r.chunks.length} ${t("sources.title").toLowerCase()} · ${t("stato.fonti")}`
        : r.fase === "scrittura"
          ? t("stato.scrittura")
          : r.fase === "risposta"
            ? t("stato.risposta")
            : r.fase === "citazioni"
              ? t("stato.citazioni")
              : r.fase === "conclusa"
                ? tempi
                : r.fase === "interrotta"
                  ? t("stato.interrotta")
                  : `${t("stato.errore")} · ${r.errore?.stage ?? ""}`;

  return (
    <p className="flex items-center gap-2 font-mono text-[11px] tracking-[0.02em] text-muted">
      <Puntino stato={r.fase === "errore" ? "guasto" : inCorso(r) ? "vivo" : "fermo"} />
      <span>{testo}</span>
    </p>
  );
}

/** Il pallino del mockup: pulsa mentre qualcosa sta arrivando, si ferma quando
 *  non arriva piu' niente, e cambia colore se il motivo e' un guasto. */
function Puntino({ stato }: { stato: "vivo" | "fermo" | "guasto" }) {
  const colore =
    stato === "vivo" ? "bg-accent animate-pulse" : stato === "fermo" ? "bg-ok" : "bg-warn";
  return <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${colore}`} />;
}

function Corpo({ scambio }: { scambio: Scambio }) {
  const { t } = usaLingua();
  const { invia, occupato, confronta } = usaChat();
  const r = scambio.risposta;
  const astensione = chiSiEAstenuto(r);

  return (
    <>
      {r.testo === "" && inCorso(r) ? (
        <Scheletro righe={r.fase === "attesa" ? 3 : 2} />
      ) : (
        r.testo !== "" && <Testo risposta={r} />
      )}

      {astensione !== null && (
        <Avviso tono="neutro" icona={<Astensione size={13} />}>
          {astensione === "gate" ? t("abstention.gate") : t("abstention.model")}
        </Avviso>
      )}

      {/* Il riepilogo dei verdetti (U-07): la **parola**, che sul marcatore in
          mezzo alla prosa non ci sta. Sta sotto la risposta e non nel pannello
          perche' parla della risposta, e compare solo quando c'e' qualcosa da
          dire — un avviso che c'e' sempre smette di essere letto. */}
      <Verdetti riepilogo={riepilogo(r)} />

      {r.troncato && <Avviso icona={<Troncato size={13} />}>{t("stato.troncato")}</Avviso>}
      {r.riparato && <p className="font-mono text-[10px] text-muted">{t("stato.riparato")}</p>}

      {r.errore !== null && <Avviso icona={<Avvertimento size={13} />}>{r.errore.message}</Avviso>}

      {(r.fase === "errore" || r.fase === "interrotta") && (
        <div>
          <button
            type="button"
            disabled={occupato}
            onClick={() => invia(scambio.domanda)}
            className="rounded-md border border-accent bg-accent-soft px-[9px] py-[5px] text-[11px] font-medium text-accent disabled:opacity-50"
          >
            {t("backend.retry")}
          </button>
        </div>
      )}

      {/* Solo su una risposta **conclusa**: il confronto riparte dalla sua
          configurazione, e senza `config` non si saprebbe nemmeno da quale dei
          due bracci si sta partendo — una colonna intitolata a caso e' peggio di
          un comando assente. */}
      {r.fase === "conclusa" && r.config !== null && (
        <div>
          <Suggerimento
            testo={occupato ? t("compare.busy") : t("compare.action.hint")}
            fuoco={false}
          >
            <button
              type="button"
              aria-disabled={occupato}
              onClick={() => !occupato && confronta(scambio.id)}
              className="flex items-center gap-1.5 rounded-md border border-line-2 px-[9px] py-[5px] text-[11px] text-ink-2 transition-colors hover:border-accent-2 hover:text-ink aria-disabled:opacity-45 aria-disabled:hover:border-line-2 aria-disabled:hover:text-ink-2"
            >
              <DueColonne size={12} />
              {r.config.rag ? t("compare.action.bare") : t("compare.action.sourced")}
            </button>
          </Suggerimento>
        </div>
      )}
    </>
  );
}

/**
 * Cosa i verdetti hanno trovato, in parole.
 *
 * L'icona e il tono seguono **il fatto piu' grave**, e la scala non e' di gusto:
 * una citazione che non regge dice qualcosa sulla risposta, una frase scoperta
 * dice qualcosa su cosa la risposta ha evitato di dichiarare, e un marcatore
 * senza verdetto non dice niente su nessuno dei due — e' solo una cosa che non e'
 * stata misurata. Il glifo e' lo stesso che sta sul marcatore nel testo: cosi'
 * questa frase fa anche da legenda, senza esserne una.
 *
 * L'ultima riga e' la tesi, e sta nell'interfaccia e non solo nel README: qui una
 * citazione che non regge e' il dato, non un errore. Senza scriverlo, un avviso
 * ocra si legge come un guasto — che e' l'esatto contrario di U-07.
 */
function Verdetti({ riepilogo: r }: { riepilogo: Riepilogo | null }) {
  const { t } = usaLingua();
  if (r === null) return null;

  // Se **tutte** le non sostenute sono confermate dal verificatore numerico, «non
  // tutte le citazioni reggono» e' la frase sbagliata: non e' la citazione a non
  // reggere, sono i due verificatori a non concordare — e su una tabella quello
  // giusto e' il secondo. Un titolo che dicesse il contrario metterebbe in bocca
  // all'interfaccia un giudizio che il progetto stesso ha misurato falso.
  const grave =
    r.nonSostenute > 0 && r.discordanti === r.nonSostenute
      ? "disagreement"
      : r.nonSostenute > 0
        ? "unsupported"
        : r.senzaCitazione > 0
          ? "uncited"
          : "unverified";

  const Glifo = {
    disagreement: Discordi,
    unsupported: NonSostiene,
    uncited: NonCitata,
    unverified: NonVerificata,
  }[grave];

  return (
    <Avviso
      // «Non verificata» e «i due non concordano» non sono rilievi: la prima e'
      // una misura che non e' stata fatta, la seconda un limite noto del
      // verificatore di prosa. Un fondo d'attenzione le trasformerebbe in guasti.
      tono={grave === "unverified" || grave === "disagreement" ? "neutro" : "attenzione"}
      icona={<Glifo size={13} />}
      titolo={t(`report.title.${grave}`)}
    >
      {r.nonSostengono.length > 0 && (
        <span className="block">
          {t("report.marks", { marcatori: r.nonSostengono.map((n) => `[${n}]`).join(" ") })}
        </span>
      )}
      {r.discordanti > 0 && (
        <span className="block">{t("report.numeric", { quante: r.discordanti })}</span>
      )}
      {r.senzaCitazione > 0 && (
        <span className="block">{t("report.uncited", { quante: r.senzaCitazione })}</span>
      )}
      {r.nonVerificate > 0 && (
        <span className="block">{t("report.unverified", { quante: r.nonVerificate })}</span>
      )}
      <span className="mt-1 block text-muted">{t("report.why")}</span>
    </Avviso>
  );
}

function Scheletro({ righe }: { righe: number }) {
  return (
    <div className="flex flex-col gap-[7px]" aria-hidden="true">
      {Array.from({ length: righe }, (_, i) => (
        <span
          key={i}
          className={`h-[9px] animate-pulse rounded bg-surface-2 ${i === righe - 1 ? "w-[55%]" : ""}`}
        />
      ))}
    </div>
  );
}

/**
 * Il `titolo` e' quello del mockup: 12 px, semibold, colore dell'inchiostro.
 * Serve quando l'avviso dice **due** cose — cosa e' successo e cosa farne — e
 * senza di lui le due si leggono come una frase sola piu' lunga.
 */
function Avviso({
  tono = "attenzione",
  icona,
  titolo,
  children,
}: {
  tono?: "attenzione" | "neutro";
  icona: ReactNode;
  titolo?: string;
  children: ReactNode;
}) {
  const stile =
    tono === "neutro"
      ? "border-l-wait bg-wait-soft text-wait"
      : "border-l-warn bg-warn-soft text-warn";
  return (
    <div
      className={`flex items-start gap-2.5 rounded-[7px] border border-line-2 border-l-[3px] px-3 py-2.5 ${stile}`}
    >
      <span className="mt-px">{icona}</span>
      <div>
        {titolo !== undefined && (
          <p className="mb-[3px] text-[12px] font-semibold text-ink">{titolo}</p>
        )}
        <p className="text-[11.5px] leading-[1.5] text-ink-2">{children}</p>
      </div>
    </div>
  );
}

/* --- il campo ------------------------------------------------------------ */

/** Quante righe prima che il campo smetta di crescere e cominci a scorrere.
 *  Otto perche' e' l'altezza oltre la quale il campo mangia le fonti e la
 *  risposta: cresce finche' vedere cio' che si scrive conta piu' di vedere cio'
 *  a cui si sta rispondendo. */
const RIGHE_MASSIME = 8;

function Campo() {
  const { t } = usaLingua();
  const { occupato, invia, ferma, impedimento } = usaChat();
  const [testo, setTesto] = useState("");
  const campo = useRef<HTMLTextAreaElement>(null);

  // Un `<textarea>` non cresce col contenuto: `rows` fissa l'altezza e basta.
  // Si azzera e si rimisura, perche' senza `auto` lo `scrollHeight` non cala
  // mai — cancellando una riga il campo resterebbe alto.
  //
  // In CSS esisterebbe `field-sizing: content`, che fa esattamente questo senza
  // JavaScript, ma non e' ancora ovunque: la demo deve aprirsi su qualunque
  // browser, e un campo che non cresce e' un difetto visibile. Quando sara'
  // diffuso, queste dieci righe diventano una dichiarazione.
  useEffect(() => {
    const el = campo.current;
    if (!el) return;
    const stile = getComputedStyle(el);
    const riga = parseFloat(stile.lineHeight) || 19;
    const bordi = parseFloat(stile.paddingTop) + parseFloat(stile.paddingBottom);
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, riga * RIGHE_MASSIME + bordi)}px`;
  }, [testo]);

  const spedisci = () => {
    if (testo.trim() === "") return;
    invia(testo);
    setTesto("");
  };

  // Il segnaposto **e'** il messaggio: chiudere il campo senza dire quale
  // precondizione manca lascia solo un campo che non risponde.
  const bloccato = impedimento !== null;
  const segnaposto =
    impedimento === "dataset"
      ? t("chat.noDataset")
      : impedimento === "modello"
        ? t("chat.noModel")
        : t("chat.placeholder");

  return (
    <div className="border-t border-line bg-surface px-[22px] pt-3 pb-3.5">
      {/* Sopra il campo, non sotto la barra: e' un'istruzione per il campo, e
          sotto stava accanto a quattro comandi che decidono la risposta — due
          cose che non si somigliano. Sparisce quando il campo e' chiuso: dire
          come si manda una domanda che non si puo' mandare e' un invito a
          provare, e il segnaposto sta gia' spiegando perche' no. */}
      {!bloccato && (
        <p className="mb-2 text-right font-mono text-[10px] text-muted">{t("chat.hint.invio")}</p>
      )}

      <div className="flex items-end gap-3 rounded-[9px] border border-line-2 bg-paper px-3 py-2.5 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent">
        <textarea
          ref={campo}
          rows={1}
          value={testo}
          disabled={bloccato}
          onChange={(e) => setTesto(e.target.value)}
          onKeyDown={(e) => {
            // Invio manda, Maiusc+Invio va a capo: e' la convenzione che chi
            // arriva da qualsiasi altra chat ha gia' in mano.
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              spedisci();
            }
          }}
          placeholder={segnaposto}
          // `fuoco-delegato`: l'anello di fuoco lo disegna la cornice attorno,
          // che reagisce a `focus-within`. Non si rinuncia al fuoco visibile,
          // si sceglie dove disegnarlo.
          // `leading-[1.5]` esplicito: senza, l'altezza di riga calcolata e'
          // `normal` e la misura sopra dovrebbe indovinarla. Il massimo lo mette
          // il JavaScript, quindi qui non c'e' `max-h`: due limiti che possono
          // divergere sono un limite che prima o poi sbaglia.
          //
          // `py-[3.6px]` non e' un ritocco a occhio: la riga di testo e' alta
          // 18,75 px (12,5 x 1,5) e il bottone 26, quindi con `items-end` il
          // testo si allineava al **fondo** del bottone invece che al suo centro.
          // 3,6 px per parte pareggiano le due altezze — e quando il campo
          // cresce restano, perche' il bottone deve restare in basso.
          className="fuoco-delegato min-h-[26px] flex-1 resize-none overflow-y-auto bg-transparent py-[3.6px] text-[12.5px] leading-[1.5] text-ink placeholder:text-muted disabled:cursor-not-allowed"
        />

        {occupato ? (
          <button
            type="button"
            onClick={ferma}
            className="grid h-[26px] shrink-0 place-items-center rounded-md border border-line-2 px-2.5 text-[11px] text-ink-2"
          >
            {t("chat.stop")}
          </button>
        ) : (
          <button
            type="button"
            onClick={spedisci}
            disabled={bloccato || testo.trim() === ""}
            aria-label={t("chat.send")}
            className="grid h-[26px] w-[26px] shrink-0 place-items-center rounded-md bg-accent text-accent-ink disabled:opacity-40"
          >
            <FrecciaSu size={14} />
          </button>
        )}
      </div>
      <Barra />
    </div>
  );
}
