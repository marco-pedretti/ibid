/**
 * Le due risposte alla stessa domanda, affiancate.
 *
 * **E' un layout, non un interruttore** (§12). Il toggle RAG della barra decide
 * la prossima domanda; questa schermata e' un'azione su una risposta **gia'
 * data**, che la rilancia col RAG invertito e mette le due una accanto
 * all'altra. Due messaggi consecutivi nel filo non sono la stessa cosa: si
 * leggono uno dopo l'altro, e la domanda in mezzo si dimentica.
 *
 * La domanda sta **in cima e una volta sola**, che e' cio' che rende le due
 * colonne confrontabili invece che semplicemente vicine: ripetuta due volte
 * lascerebbe il dubbio che siano due domande simili.
 *
 * **Le fonti stanno dentro la colonna**, e il pannello di fianco qui non c'e':
 * la loro presenza da una parte e la loro assenza dall'altra e' esattamente
 * l'argomento della schermata, e in una colonna sola di fianco si vedrebbero le
 * fonti di uno dei due bracci senza sapere di quale.
 *
 * La colonna nuda **non dice «sbagliato»**. Il mockup ci aveva scritto
 * «Plausibile, e sbagliato», che e' vero dell'esempio disegnato e non di ogni
 * risposta: senza fonti non si puo' sapere se e' giusta — e' proprio quello il
 * punto. L'avviso dice cio' che si sa, cioe' che non c'e' niente da aprire.
 */
import { usaChat } from "../app/chat";
import type { Confronto as DueColonne } from "../app/chat";
import { inCorso } from "../app/conversazione";
import type { Risposta } from "../app/conversazione";
import { usaLingua } from "../app/i18n";
import { Etichetta } from "./Etichetta";
import { Avvertimento, Indietro } from "./Icona";
import { Schede } from "./PannelloFonti";
import { Testo } from "./Testo";

export function Confronto({ confronto }: { confronto: DueColonne }) {
  const { t } = usaLingua();
  const { chiudiConfronto, occupato } = usaChat();

  // Da che parte va ciascuna lo dice `config`, cioe' cio' che ha girato davvero,
  // e non un dato tenuto a parte che potrebbe smentirlo.
  const dataConFonti = confronto.data.config?.rag ?? true;
  const conFonti = dataConFonti ? confronto.data : confronto.nuova;
  const senzaFonti = dataConFonti ? confronto.nuova : confronto.data;

  return (
    <div className="flex h-full min-h-0 flex-col bg-paper">
      <div className="flex items-start gap-3 border-b border-line px-[22px] py-3">
        <div className="min-w-0 flex-1">
          <Etichetta>{t("compare.title")}</Etichetta>
          <p className="mt-1 text-[13px] text-ink">{confronto.domanda}</p>
        </div>
        <button
          type="button"
          onClick={chiudiConfronto}
          // Non `disabled`: la bolla che spiega perche' non risponde ha bisogno
          // del puntatore. Stessa lezione delle voci di cronologia in U-13.
          aria-disabled={occupato}
          className="flex shrink-0 items-center gap-1.5 rounded-md border border-line-2 px-[9px] py-[5px] text-[11px] text-ink-2 transition-colors hover:border-accent-2 hover:text-ink aria-disabled:opacity-45 aria-disabled:hover:border-line-2 aria-disabled:hover:text-ink-2"
        >
          <Indietro size={12} />
          {t("compare.back")}
        </button>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-2 divide-x divide-line overflow-hidden">
        <Colonna titolo={t("compare.withSources")} risposta={conFonti} fonti />
        <Colonna titolo={t("compare.withoutSources")} risposta={senzaFonti} fonti={false} />
      </div>
    </div>
  );
}

/** Il totale della run in secondi. Le voci di `tempi` sono le fasi del §3.5, e
 *  qui interessa quanto e' costata la risposta intera: e' il numero che le due
 *  colonne mettono a paragone. */
function secondi(r: Risposta, lingua: string): string {
  const totale = Object.values(r.tempi).reduce((a, b) => a + b, 0);
  return `${totale.toLocaleString(lingua === "it" ? "it-IT" : "en-US", { maximumFractionDigits: 1 })} s`;
}

function Colonna({
  titolo,
  risposta,
  fonti,
}: {
  titolo: string;
  risposta: Risposta;
  fonti: boolean;
}) {
  const { t, lingua } = usaLingua();

  // L'unita' del verdetto e' la coppia (frase, chunk) e non il marcatore (§12):
  // lo stesso [3] puo' comparire in tre frasi e reggerne due, e contare i
  // marcatori aggregherebbe proprio la granularita' che l'affermazione 1 del §0
  // esiste per misurare.
  const sostenute = risposta.citazioni.filter((c) => c.supported).length;

  return (
    <section className="flex min-h-0 flex-col gap-[11px] overflow-y-auto px-[18px] py-4">
      <div className="flex items-baseline justify-between gap-2">
        <Etichetta>{titolo}</Etichetta>
        {risposta.verificate && risposta.citazioni.length > 0 && (
          <span className="font-mono text-[10px] text-muted tabular-nums">
            {t("compare.verdicts", {
              sostenute,
              citazioni: risposta.citazioni.length,
            })}
          </span>
        )}
      </div>

      {/* L'avviso sta **prima** del testo, e le fonti dopo. Non e' simmetria
          rotta per caso: le fonti sono cio' che si va a controllare *dopo* aver
          letto, mentre «niente di questo e' verificabile» e' la premessa con cui
          va letto. In fondo alla colonna arrivava dopo una risposta lunga e ben
          formattata — cioe' si scopriva che non c'era niente da aprire solo dopo
          essersi convinti. */}
      {!fonti && (
        <div className="flex items-start gap-2.5 rounded-[7px] border border-line-2 border-l-[3px] border-l-warn bg-warn-soft px-3 py-2.5 text-warn">
          <span className="mt-px">
            <Avvertimento size={13} />
          </span>
          <div>
            <p className="mb-[3px] text-[12px] font-semibold text-ink">{t("compare.bare.title")}</p>
            <p className="text-[11.5px] leading-[1.5] text-ink-2">{t("compare.bare.body")}</p>
          </div>
        </div>
      )}

      {risposta.testo === "" && inCorso(risposta) ? (
        <p className="font-mono text-[11px] text-muted">
          <span className="mr-2 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-accent align-middle" />
          {/* Nella colonna nuda non si sta cercando niente: `fonti` e' proprio
              il RAG di questo braccio, quindi la riga d'attesa dice cosa sta
              davvero succedendo -- il modello che pensa da solo. */}
          {t(fonti ? "stato.attesa" : "stato.attesa.modello")}
        </p>
      ) : (
        <Testo risposta={risposta} />
      )}

      {fonti && <Schede risposta={risposta} />}

      {/* Tempo e modello in fondo, come nel mockup: i due bracci della stessa
          domanda costano diverso, e quanto costano e' parte di cio' che si sta
          confrontando -- senza fonti non c'e' retrieval da pagare. */}
      {risposta.fase === "conclusa" && (
        <p className="mt-auto pt-1 font-mono text-[10px] text-muted tabular-nums">
          {secondi(risposta, lingua)} · {risposta.config?.model}
        </p>
      )}
    </section>
  );
}
