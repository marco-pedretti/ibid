/**
 * Le conversazioni di questo browser, nella corsia.
 *
 * **«Nuova conversazione» ha la forma delle azioni della corsia**, quella che nel
 * mockup ha «Esplora il corpus» (`.bottone-esplora`): bordo e testo d'accento su
 * fondo accento tenue. Come riga della cronologia era leggibile ma piatta — la
 * voce piu' usata della corsia aveva lo stesso peso della meno usata — e non e'
 * un'eccezione decorativa: e' l'unico controllo qui che **crea** invece di
 * riportare, e nel §12 l'accento e' il colore di cio' che si opera. Il segno `+`
 * resta, ed e' cio' che la distinguera' da «Esplora il corpus» quando saranno una
 * sopra l'altra.
 *
 * Ne segue che una conversazione **vuota non ha una voce sua**: il bottone e' il
 * suo posto, e due controlli con le stesse parole uno sull'altro non direbbero
 * quale si sta usando.
 *
 * **«Cronologia locale» dice il fatto, il suggerimento lo spiega.** Il criterio di
 * U-13 chiede che la localita' sia **dichiarata** e non dedotta, e prima la frase
 * intera stava sotto l'elenco: vera, e scollegata da cio' di cui parlava — una
 * riga che comincia con «Solo in questo browser» non dice *cosa* sta solo qui.
 * Nel nome della sezione la parola ha un referente, e la spiegazione e' a un
 * passaggio di distanza invece di occupare cinque righe di una corsia larga
 * 200 px.
 *
 * **Cancellare e' a due tempi**, e il comando sta nella riga dell'etichetta in
 * 9,5 px: e' la via d'uscita da una cronologia che si e' riempita provando, non
 * un comando del lavoro normale. Vedi `Cancella` per il perche' dei due tempi.
 *
 * **L'elenco compare quando c'e' qualcosa dentro.** Al primo avvio ci sarebbero
 * un'etichetta e il vuoto; il bottone invece c'e' sempre, perche' e' un comando e
 * non un riepilogo.
 *
 * **Le voci non rispondono mentre una risposta arriva.** Non sono `disabled`: un
 * elemento disabilitato non riceve gli eventi del puntatore, quindi il
 * suggerimento che spiega **perche'** non si aprirebbe — cioe' l'unica cosa utile
 * in quei secondi. `aria-disabled` lo dice a chi ascolta, il tono attenuato a chi
 * guarda, e il clic e' una guardia nel provider.
 *
 * **Il titolo di una voce e' la prima domanda, troncata.** In 176 px ci stanno
 * ~28 caratteri: il suggerimento non spiega niente, mostra cio' che il taglio ha
 * nascosto — la stessa regola del nome del documento nel pannello fonti.
 */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { usaChat } from "../app/chat";
import { titoloDi, vuota } from "../app/cronologia";
import type { Conversazione } from "../app/cronologia";
import { usaLingua } from "../app/i18n";
import { Etichetta } from "./Etichetta";
import { Piu } from "./Icona";
import { Suggerimento } from "./Suggerimento";

/** Quanto resta armato «Cancella» prima di tornare innocuo. Abbastanza per un
 *  secondo clic voluto, troppo poco per uno dato mezz'ora dopo. */
const DISARMO_MS = 4000;

export function Cronologia() {
  const { t } = usaLingua();
  const { conversazioni, corrente } = usaChat();
  const voci = conversazioni.filter((c) => !vuota(c));

  return (
    <>
      <BottoneNuova />

      {voci.length > 0 && (
        <section className="flex min-h-0 flex-1 flex-col">
          <div className="mb-[7px] flex items-baseline justify-between gap-2 px-1">
            {/* Il suggerimento sta **dentro** l'etichetta e non attorno: il
                bersaglio di `Suggerimento` e' uno `<span>`, e un titolo dentro
                uno span non e' annidamento valido. */}
            <Etichetta>
              <Suggerimento testo={t("history.hint")}>{t("history.title")}</Suggerimento>
            </Etichetta>
            <Cancella />
          </div>

          {/* Scorre l'elenco, non la corsia: la tendina del dataset sta sopra e
              fuori da qui, quindi nessun contenitore di scorrimento la puo'
              ritagliare. */}
          <nav
            aria-label={t("history.title")}
            className="flex min-h-0 flex-1 flex-col gap-px overflow-y-auto"
          >
            {voci.map((c) => (
              <Voce key={c.id} conversazione={c} attiva={c.id === corrente} />
            ))}
          </nav>
        </section>
      )}
    </>
  );
}

/**
 * Le misure sono quelle di `.bottone-esplora` nel mockup: 12 px, raggio 7,
 * padding 8/10, e il glifo staccato di 7.
 *
 * **Al passaggio si riempie d'accento**, e il testo passa ad `accent-ink`: e' la
 * stessa coppia del bottone d'invio della chat, cioe' come questa palette dice
 * «azione principale». Prima non aveva nessuno stato al passaggio — la forma
 * diceva che era un comando, ma restava immobile sotto il puntatore, che e'
 * esattamente cio' che fa dubitare che sia cliccabile. Il resto della corsia lo
 * fa piu' piano (`hover:bg-surface-2`, `hover:border-line`) perche' il resto
 * della corsia non e' l'azione principale.
 */
function BottoneNuova() {
  const { t } = usaLingua();
  const { occupato, nuova } = usaChat();

  return (
    <Attivabile
      bloccato={occupato}
      suggerimento={occupato ? t("history.busy") : null}
      onClick={nuova}
      className={`flex w-full items-center gap-[7px] rounded-[7px] border border-accent bg-accent-soft px-2.5 py-2 text-left text-[12px] font-medium text-accent transition-colors ${
        occupato ? "" : "hover:bg-accent hover:text-accent-ink"
      }`}
    >
      <Piu size={12} />
      <span className="truncate">{t("history.new")}</span>
    </Attivabile>
  );
}

/**
 * «Cancella», e al secondo clic cancella davvero.
 *
 * **A due tempi, e non un `confirm()` del browser**: colori e forma del sistema
 * operativo in mezzo a un'interfaccia che ha i propri, cioe' lo stesso difetto
 * del `title` nativo che `Suggerimento` ha sostituito. E nemmeno un clic solo: la
 * cronologia non e' recuperabile, perche' non c'e' nessun server che ne tenga una
 * copia — e' precisamente cio' che «locale» significa. Il secondo clic va dato
 * entro pochi secondi, poi il comando si disarma da se': un bottone che resta
 * armato aspetta un clic che qualcuno dara' mezz'ora dopo senza ricordarsi.
 *
 * Sta nella riga dell'etichetta e in 9,5 px perche' non e' una cosa da fare
 * spesso: e' la via d'uscita da una cronologia che si e' riempita provando, non
 * un comando del lavoro normale.
 */
function Cancella() {
  const { t } = usaLingua();
  const { occupato, svuota } = usaChat();
  const [armato, setArmato] = useState(false);

  useEffect(() => {
    if (!armato) return;
    const x = setTimeout(() => setArmato(false), DISARMO_MS);
    return () => clearTimeout(x);
  }, [armato]);

  return (
    <Attivabile
      bloccato={occupato}
      suggerimento={armato ? t("history.clear.again") : t("history.clear.hint")}
      onClick={() => {
        if (armato) svuota();
        setArmato(!armato);
      }}
      className={`shrink-0 rounded px-1 py-px font-mono text-[9.5px] tracking-[0.06em] uppercase transition-colors ${
        armato ? "bg-warn-soft font-semibold text-warn"
        : occupato ? "text-muted"
        : "text-muted hover:text-ink-2"
      }`}
    >
      {armato ? t("history.clear.confirm") : t("history.clear")}
    </Attivabile>
  );
}

/** Una voce dell'elenco: le misure sono quelle di `.crono-voce` nel mockup —
 *  11,5 px, l'attiva su `surface-2` con l'inchiostro pieno, le altre attenuate. */
function Voce({ conversazione, attiva }: { conversazione: Conversazione; attiva: boolean }) {
  const { t } = usaLingua();
  const { occupato, apri } = usaChat();
  const titolo = titoloDi(conversazione) ?? t("history.new");

  return (
    <Attivabile
      bloccato={occupato}
      suggerimento={occupato ? t("history.busy") : titolo}
      onClick={() => apri(conversazione.id)}
      attiva={attiva}
      className={`w-full truncate rounded-md px-2 py-1.5 text-left text-[11.5px] transition-colors ${
        attiva ? "bg-surface-2 font-medium text-ink"
        : occupato ? "text-ink-2"
        : "text-ink-2 hover:bg-surface-2"
      }`}
    >
      {titolo}
    </Attivabile>
  );
}

/**
 * Un comando della corsia: bloccabile senza essere `disabled`, e col suo
 * suggerimento quando ne ha uno.
 *
 * `disabled` toglierebbe gli eventi del puntatore, e con loro la spiegazione di
 * perche' non risponde. Qui il tono lo dice a chi guarda, `aria-disabled` a chi
 * ascolta, e il clic non fa niente.
 */
function Attivabile({
  bloccato,
  suggerimento,
  attiva = false,
  onClick,
  className,
  children,
}: {
  bloccato: boolean;
  suggerimento: string | null;
  attiva?: boolean;
  onClick: () => void;
  className: string;
  children: ReactNode;
}) {
  const bottone = (
    <button
      type="button"
      aria-current={attiva ? "true" : undefined}
      aria-disabled={bloccato ? true : undefined}
      onClick={() => {
        if (!bloccato) onClick();
      }}
      className={`${className} ${bloccato ? "cursor-not-allowed opacity-50" : ""}`}
    >
      {children}
    </button>
  );

  if (suggerimento === null) return bottone;
  return (
    <Suggerimento testo={suggerimento} fuoco={false} className="block min-w-0">
      {bottone}
    </Suggerimento>
  );
}
