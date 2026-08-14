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
import type { Risposta } from "../app/conversazione";
import { usaDataset } from "../app/dataset";
import { esempiDi } from "../app/esempi";
import { usaLingua } from "../app/i18n";
import type { Scambio } from "../app/chat";
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
        {scambi.length === 0 ? (
          <Vuoto />
        ) : (
          scambi.map((s) => <Turno key={s.id} scambio={s} />)
        )}
        <div ref={fondo} />
      </div>
      <Campo />
    </div>
  );
}

/* --- lo stato iniziale --------------------------------------------------- */

function Vuoto() {
  const { t } = usaLingua();
  const { scelto } = usaDataset();
  const { invia } = usaChat();
  const esempi = esempiDi(scelto?.dataset_id ?? null);

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
              {e.query}
              <span className="mt-1 block text-[11px] text-muted">{t(e.nota)}</span>
            </span>
          </button>
        ))}
      </div>
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
    r.fase === "attesa" ? t("stato.attesa")
    : r.fase === "fonti" ? `${r.chunks.length} ${t("sources.title").toLowerCase()} · ${t("stato.fonti")}`
    : r.fase === "scrittura" ? t("stato.scrittura")
    : r.fase === "risposta" ? t("stato.risposta")
    : r.fase === "citazioni" ? t("stato.citazioni")
    : r.fase === "conclusa" ? tempi
    : r.fase === "interrotta" ? t("stato.interrotta")
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
  const { invia, occupato } = usaChat();
  const r = scambio.risposta;
  const astensione = chiSiEAstenuto(r);

  return (
    <>
      {r.testo === "" && inCorso(r) ? (
        <Scheletro righe={r.fase === "attesa" ? 3 : 2} />
      ) : (
        r.testo !== "" && <Testo testo={r.testo} vivi={r.definitivo} />
      )}

      {astensione !== null && (
        <Avviso tono="neutro" glifo="⌀">
          {astensione === "gate" ? t("abstention.gate") : t("abstention.model")}
        </Avviso>
      )}

      {r.troncato && <Avviso glifo="⋯">{t("stato.troncato")}</Avviso>}
      {r.riparato && (
        <p className="font-mono text-[10px] text-muted">{t("stato.riparato")}</p>
      )}

      {r.errore !== null && <Avviso glifo="!">{r.errore.message}</Avviso>}

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
    </>
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

function Avviso({
  tono = "attenzione",
  glifo,
  children,
}: {
  tono?: "attenzione" | "neutro";
  glifo: string;
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
      <span aria-hidden="true" className="font-mono text-[13px] leading-[1.3]">
        {glifo}
      </span>
      <p className="text-[11.5px] leading-[1.5] text-ink-2">{children}</p>
    </div>
  );
}

/* --- il campo ------------------------------------------------------------ */

function Campo() {
  const { t } = usaLingua();
  const { scelto } = usaDataset();
  const { occupato, invia, ferma } = usaChat();
  const [testo, setTesto] = useState("");

  const spedisci = () => {
    if (testo.trim() === "") return;
    invia(testo);
    setTesto("");
  };

  const bloccato = scelto === null;

  return (
    <div className="border-t border-line bg-surface px-[22px] pt-3 pb-3.5">
      <div className="flex items-end gap-3 rounded-[9px] border border-line-2 bg-paper px-3 py-2.5 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent">
        <textarea
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
          placeholder={bloccato ? t("chat.noDataset") : t("chat.placeholder")}
          // `fuoco-delegato`: l'anello di fuoco lo disegna la cornice attorno,
          // che reagisce a `focus-within`. Non si rinuncia al fuoco visibile,
          // si sceglie dove disegnarlo.
          className="fuoco-delegato max-h-40 min-h-[22px] flex-1 resize-none bg-transparent text-[12.5px] text-ink placeholder:text-muted disabled:cursor-not-allowed"
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
            {/* Disegnata, non scritta: `↑` e' un glifo di sistema, e come il
                caret arriva sottile e piu' piccolo della sua dimensione
                nominale. Un tratto ha lo spessore che gli si da'. */}
            <svg
              aria-hidden="true"
              viewBox="0 0 16 16"
              className="h-3.5 w-3.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M8 12.5 L8 4" />
              <path d="M4 8 L8 4 L12 8" />
            </svg>
          </button>
        )}
      </div>
      <p className="mt-2 font-mono text-[10px] text-muted">{t("chat.hint.invio")}</p>
    </div>
  );
}
