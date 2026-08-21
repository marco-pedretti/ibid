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
 *
 * **A colonna sola le due si impilano** (U-21), e non diventano due schede fra
 * cui scegliere. Affiancate si leggono con un colpo d'occhio; impilate si
 * leggono una dopo l'altra, che è meno — ma restano **la stessa pagina**, sotto
 * la stessa domanda, e scorrere da una all'altra è un gesto che non chiede di
 * decidere niente. Due linguette invece nascondono una delle due dietro un clic
 * e la fanno tornare a essere una seconda risposta, cioè esattamente i «due
 * messaggi consecutivi» che questa schermata esiste per non essere.
 *
 * **Il prompt si sceglie qui dentro, e solo qui** (U-04). Col recupero acceso
 * non e' una scelta di nessuno — il prompt e' quello che impone il formato delle
 * citazioni, ed e' cio' che C-01 misura. Spento, i due prompt sono i bracci di
 * E-04 ed E-05, e la differenza fra loro e' il 45%→17% di risposte inventate:
 * qui diventa una pastiglia che rifa' **quella colonna sola**, con la risposta
 * documentata ferma accanto a fare da paragone.
 */
import { usaBackend } from "../app/backend";
import { usaChat } from "../app/chat";
import { PERMISSIVO, bracci, promptNudo, scelteDiPrompt } from "../app/confronto";
import type { Confronto as DueColonne } from "../app/confronto";
import { inCorso } from "../app/conversazione";
import type { Risposta } from "../app/conversazione";
import { usaLingua } from "../app/i18n";
import { Etichetta } from "./Etichetta";
import { Avvertimento, Indietro } from "./Icona";
import { FORMA, MOSSA, RIPOSO } from "./pastiglia";
import { Schede } from "./PannelloFonti";
import { Suggerimento } from "./Suggerimento";
import { usaForma } from "./Telaio";
import { Testo } from "./Testo";

export function Confronto({ confronto }: { confronto: DueColonne }) {
  const { t } = usaLingua();
  const { chiudiConfronto, occupato } = usaChat();
  const impilate = usaForma() === "stretta";

  // Da che parte va ciascuna e' deciso all'apertura e non si ricalcola: mentre
  // la colonna nuda si rifa' con l'altro prompt il suo `config` torna `null`, e
  // leggerlo qui le farebbe scambiare di posto a meta' generazione. Vedi
  // `confronto.ts`.
  const { conFonti, senzaFonti } = bracci(confronto);

  return (
    <div className="flex h-full min-h-0 flex-col bg-paper">
      <div className="flex shrink-0 items-start gap-3 border-b border-line px-[22px] py-3">
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

      {/* `grid-rows-[minmax(0,1fr)]` non e' decorazione: senza una riga
          dichiarata la riga implicita e' `auto`, cioe' **alta quanto il
          contenuto**. Le due colonne prendevano quell'altezza invece di quella
          dello schermo, quindi il loro `overflow-y-auto` non aveva mai niente
          da far scorrere e a crescere era la pagina intera — con la barra di
          scorrimento del documento che portava via anche la corsia. Con la riga
          fissata all'altezza disponibile, ogni colonna scorre per conto suo e
          il telaio resta fermo. */}
      <div
        className={
          impilate
            ? // Impilate, a scorrere e' **il contenitore** e non le due sezioni:
              // due riquadri di scorrimento uno sopra l'altro dentro uno schermo
              // alto quanto uno solo darebbero mezzo schermo a testa, ed e' la
              // forma in cui nessuna delle due si legge.
              "flex min-h-0 flex-1 flex-col divide-y divide-line overflow-y-auto"
            : "grid min-h-0 flex-1 grid-cols-2 grid-rows-[minmax(0,1fr)] divide-x divide-line overflow-hidden"
        }
      >
        <Colonna titolo={t("compare.withSources")} risposta={conFonti} fonti impilata={impilate} />
        <Colonna
          titolo={t("compare.withoutSources")}
          risposta={senzaFonti}
          fonti={false}
          impilata={impilate}
        />
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

/**
 * Come e' stata posta la domanda al modello che non ha fonti.
 *
 * **Due pastiglie e non un interruttore.** «Severo» acceso farebbe di
 * «permissivo» la sua assenza, e permissivo non e' l'assenza di niente: e' un
 * prompt che dice *rispondi comunque*, cioe' un capo dell'asse quanto l'altro.
 * Sono i due bracci di E-04 ed E-05, e su un asse i due capi si vedono insieme.
 *
 * **Si leggono per cosa fanno, non per come si chiamano.** «Permissivo» e
 * «severo» sono i nomi delle due run e stanno nel suggerimento; sulle pastiglie
 * c'e' cio' che cambia per chi legge — risponde comunque, oppure si astiene. E'
 * anche il modo piu' corto di dire l'affermazione 1 del §0.
 *
 * Sparisce se il servizio non offre entrambi i capi: un comando che gira a
 * vuoto e' lo stesso difetto dell'interruttore del ragionamento.
 */
function PromptDelModello() {
  const { t } = usaLingua();
  const { backend } = usaBackend();
  const { confronto, cambiaPrompt, occupato } = usaChat();
  if (confronto === null) return null;

  const scelte = scelteDiPrompt(
    backend.stato === "pronto" ? backend.capabilities.baseline_prompts : [],
  );
  if (scelte.length < 2) return null;

  const attuale = promptNudo(confronto);

  return (
    <Suggerimento testo={occupato ? t("compare.busy") : t("compare.prompt.hint")} fuoco={false}>
      <div role="group" aria-label={t("compare.prompt")} className="flex items-center gap-1">
        {scelte.map((p) => (
          <button
            key={p}
            type="button"
            aria-pressed={p === attuale}
            // Non `disabled`: mentre una risposta arriva la bolla che spiega
            // perche' non risponde ha bisogno del puntatore, e senza eventi il
            // gruppo li lascia passare al suggerimento che lo avvolge.
            aria-disabled={occupato}
            onClick={() => cambiaPrompt(p)}
            className={`${FORMA} px-2.5 py-1 ${p === attuale ? MOSSA : RIPOSO} aria-disabled:pointer-events-none aria-disabled:opacity-45`}
          >
            {t(p === PERMISSIVO ? "compare.prompt.permissive" : "compare.prompt.strict")}
          </button>
        ))}
      </div>
    </Suggerimento>
  );
}

function Colonna({
  titolo,
  risposta,
  fonti,
  impilata,
}: {
  titolo: string;
  risposta: Risposta;
  fonti: boolean;
  impilata: boolean;
}) {
  const { t, lingua } = usaLingua();

  // L'unita' del verdetto e' la coppia (frase, chunk) e non il marcatore (§12):
  // lo stesso [3] puo' comparire in tre frasi e reggerne due, e contare i
  // marcatori aggregherebbe proprio la granularita' che l'affermazione 1 del §0
  // esiste per misurare.
  const sostenute = risposta.citazioni.filter((c) => c.supported).length;

  return (
    <section
      className={`flex flex-col gap-[11px] px-[18px] py-4 ${
        impilata ? "" : "min-h-0 overflow-y-auto"
      }`}
    >
      {/* A destra del titolo: di qua quanti verdetti reggono, di la' con quale
          prompt e' stata posta la domanda. Non e' una simmetria cercata — sono
          le due cose che si guardano per prime nelle rispettive colonne, e
          nessuna delle due esiste nell'altra. */}
      <div className="flex min-h-[26px] items-center justify-between gap-2">
        <Etichetta>{titolo}</Etichetta>
        {fonti ? (
          risposta.verificate &&
          risposta.citazioni.length > 0 && (
            <span className="font-mono text-[10px] text-muted tabular-nums">
              {t("compare.verdicts", {
                sostenute,
                citazioni: risposta.citazioni.length,
              })}
            </span>
          )
        ) : (
          <PromptDelModello />
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
