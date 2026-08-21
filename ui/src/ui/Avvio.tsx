/**
 * L'avvio guidato: una striscia in cima alla colonna di lavoro (U-20).
 *
 * **Non e' una finestra modale, e questo e' il criterio, non lo stile.** U-20
 * chiede che la guida non impedisca di fare la prima domanda mentre e' aperta:
 * il modo di ottenerlo non e' un velo che si lascia attraversare, e' non
 * metterlo. Sta sopra la conversazione, il campo resta dov'era, e chi vuole
 * ignorarla scrive e manda. Chi invece la legge la tiene aperta **durante** la
 * prima risposta, che e' il solo momento in cui i primi due passi hanno
 * qualcosa da mostrare — le fonti che compaiono prima del testo, i verdetti che
 * arrivano dopo. Chiuderla alla prima domanda avrebbe tolto la guida esattamente
 * quando serviva.
 *
 * **Fuori dal contenitore che scorre**, quindi resta ferma mentre la risposta
 * cresce sotto. Dentro, sparirebbe dopo tre frasi di testo: una guida che si
 * porta via da sola non e' una guida che si e' saltata.
 *
 * **Un glifo per passo, e sono i glifi delle cose di cui parla.** Il quarto e'
 * quello del bottone «Che cos'e'» che nomina, il terzo e' il segno
 * dell'astensione che si vedra' rispondendo alla terza domanda d'esempio. E' il
 * modo di indicare senza disegnare una freccia sopra l'interfaccia: una guida
 * che evidenzia le regioni dello schermo va tenuta allineata a un'impaginazione
 * che cambia, e sbaglia in silenzio il giorno in cui qualcosa si sposta.
 *
 * **«Salta» e «Avanti» hanno la stessa veste, e nessuna delle due e' d'accento.**
 * L'unico bottone pieno di questa colonna e' «Invia», ed e' giusto che resti
 * l'unico: una guida che si presenta con un richiamo piu' forte di quello del
 * campo starebbe chiedendo di essere letta prima che si faccia la cosa per cui
 * si e' aperta la pagina. Fra i due nemmeno c'e' un primario — chi salta e chi
 * prosegue fanno due scelte legittime, e vestirne una meglio dell'altra sarebbe
 * un'opinione travestita da disegno.
 *
 * **La riga in fondo dichiara le due cose che il criterio chiede** — che si puo'
 * chiedere mentre e' aperta, e che saltarla si ricorda in questo browser — e sta
 * nella striscia, non in un suggerimento: la localita' della cronologia (U-13)
 * ha lo stesso posto, sotto gli occhi, perche' e' una promessa sul dato e non
 * una nota d'aiuto.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { DEPOSITO, PASSI, avanti, primoPasso, scrivi } from "../app/avvio";
import type { Passo } from "../app/avvio";
import { leggiCronologia } from "../app/cronologia";
import { usaLingua } from "../app/i18n";
import { Astensione, Indice, Informazioni, Sostiene } from "./Icona";
import type { PropsIcona } from "./Icona";
import { MISURA } from "./misura";

/** Il disegno di ogni passo: il glifo della cosa di cui parla, mai un glifo
 *  nuovo. Sta qui e non in `avvio.ts` perche' e' l'unica parte di quel modulo
 *  che non si puo' provare senza guardarla. */
const GLIFO: Record<Passo["id"], (p: PropsIcona) => ReactNode> = {
  fonti: Indice,
  verdetti: Sostiene,
  corpus: Astensione,
  resta: Informazioni,
};

/** Quello che serve per disegnare la striscia, e per sapere che c'e'. */
export interface Guida {
  /** Il passo sullo schermo, o `null` se la guida e' finita o saltata. */
  passo: number | null;
  salta: () => void;
  prosegui: () => void;
}

/**
 * Lo stato della guida, tenuto **da chi disegna la colonna** e non qui dentro.
 *
 * Serve in due posti: la striscia, e lo stato vuoto sotto — che finche' la guida
 * c'e' tace la propria riga di spiegazione, perche' e' la versione in una frase
 * di cio' che i primi due passi dicono per esteso. Due copie della stessa cosa a
 * cinque righe di distanza, sulla primissima schermata, sono il difetto che
 * questa guida dovrebbe evitare e non introdurre.
 *
 * Un hook e non un contesto: i due che lo leggono stanno nello stesso
 * componente, e un provider in piu' in `App` direbbe che qualcun altro potrebbe
 * volerlo — mentre lo stato non deve uscire dalla chat.
 */
export function usaAvvio(): Guida {
  const [passo, setPasso] = useState<number | null>(() => {
    try {
      // Una cronologia non vuota e' la prova che la prima volta e' gia' passata:
      // la chiave e' nuova, e senza questa domanda il primo avvio dopo U-20
      // accoglierebbe con un tour chi usa la demo da settimane.
      return primoPasso(localStorage.getItem(DEPOSITO), leggiCronologia().length > 0);
    } catch {
      // Deposito negato (finestra privata, iframe): si mostra la guida, che e'
      // il caso in cui non si perde niente.
      return primoPasso(null, false);
    }
  });

  // Scrive **anche al primo disegno**, e non solo quando si clicca. Senza, chi
  // apre la guida e chiede qualcosa senza toccarla lascia il deposito vuoto e
  // la cronologia piena: tornando dalla pagina «Che cos'e'» la guida sarebbe
  // sparita da sola, a meta' lettura, per la regola qui sopra.
  useEffect(() => {
    try {
      localStorage.setItem(DEPOSITO, scrivi(passo));
    } catch {
      // Vale per questa sessione: non ricordarla e' meno grave che non mostrarla.
    }
  }, [passo]);

  const salta = useCallback(() => setPasso(null), []);
  const prosegui = useCallback(() => setPasso((p) => (p === null ? null : avanti(p))), []);

  return useMemo(() => ({ passo, salta, prosegui }), [passo, salta, prosegui]);
}

export function Avvio({ guida }: { guida: Guida }) {
  const { t } = usaLingua();
  const { passo, salta, prosegui } = guida;

  if (passo === null) return null;

  const { id, titolo, testo } = PASSI[passo];
  const Glifo = GLIFO[id];
  const ultimo = passo === PASSI.length - 1;

  return (
    <section
      aria-label={t("start.title")}
      className="shrink-0 border-b border-line bg-surface px-[22px] py-3"
    >
      <div className={`${MISURA} flex items-start gap-[11px]`}>
        <Glifo size={14} className="mt-[3px] shrink-0 text-accent" />

        {/* `aria-live`: cambiando passo cambia il testo di una regione che era
            gia' sullo schermo, e senza questo chi ascolta sentirebbe solo il
            proprio clic. */}
        <div aria-live="polite" className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <h2 className="min-w-0 text-[12.5px] font-semibold text-ink">{t(titolo)}</h2>
            {/* Mono e tabellare: e' una posizione in una serie, e cambiando passo
                le cifre non devono spostare il titolo. */}
            <span className="shrink-0 font-mono text-[10px] text-muted tabular-nums">
              {t("start.step", { n: passo + 1, tot: PASSI.length })}
            </span>
          </div>
          {/* Un'altezza minima di **tre righe**, che e' quanto occupa il passo
              piu' lungo alla misura di lettura. Senza, la striscia si alza e si
              abbassa di una riga a ogni «Avanti» e la conversazione qui sotto
              salta con lei: un oggetto che cambia di misura mentre lo si legge
              e' lo stesso difetto che vieta le transizioni sulla griglia del
              telaio, solo piu' piccolo. */}
          <p className="mt-1 min-h-[4.8em] text-[12px] leading-[1.6] text-ink-2">{t(testo)}</p>
          <p className="mt-1.5 text-[11px] leading-[1.5] text-muted">{t("start.local")}</p>
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          <Comando onClick={salta}>{t("start.skip")}</Comando>
          <Comando onClick={prosegui}>{ultimo ? t("start.done") : t("start.next")}</Comando>
        </div>
      </div>
    </section>
  );
}

/** La veste dei due comandi: quella neutra della colonna — bordo sottile, testo
 *  attenuato — ed e' la stessa per tutti e due apposta. */
function Comando({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-md border border-line-2 px-[9px] py-[5px] text-[11px] whitespace-nowrap text-ink-2 transition-colors hover:border-accent-2 hover:text-ink"
    >
      {children}
    </button>
  );
}
