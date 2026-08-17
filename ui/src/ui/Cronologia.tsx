/**
 * L'elenco delle conversazioni, nella corsia.
 *
 * **«Nuova conversazione» e' la prima voce, non un pulsante accanto.** E' la
 * forma del mockup (`.crono-voce.attiva`), e regge per una ragione che si vede
 * provando l'alternativa: un pulsante che dice «Nuova conversazione» sopra una
 * voce attiva che dice «Nuova conversazione» sono due controlli con le stesse
 * parole, uno sull'altro, e nessuno dei due dice quale dei due si sta usando.
 * Come voce invece la regola e' una sola — **ogni riga porta in una
 * conversazione**, e la prima porta in una che non esiste ancora. Il segno `+`
 * la distingue: e' l'unica che crea.
 *
 * **Non compare quando la cronologia e' vuota**, tranne la prima voce: al primo
 * avvio ci sarebbero un'etichetta, una riga sola e una dichiarazione di
 * localita' su niente. La frase «solo in questo browser» arriva insieme alla
 * prima cosa che si puo' perdere.
 *
 * **Le voci non rispondono mentre una risposta arriva.** Non sono `disabled`:
 * un elemento disabilitato non riceve gli eventi del puntatore, quindi il
 * suggerimento che spiega **perche'** non si aprirebbe — cioe' l'unica cosa
 * utile in quei secondi. `aria-disabled` lo dice a chi ascolta, il tono
 * attenuato a chi guarda, e il clic e' una guardia nel provider.
 *
 * **Il titolo e' la prima domanda, troncata.** In 176 px ci stanno ~28
 * caratteri: il suggerimento non spiega niente, mostra cio' che il taglio ha
 * nascosto — la stessa regola del nome del documento nel pannello fonti.
 */
import type { ReactNode } from "react";

import { usaChat } from "../app/chat";
import { titoloDi, vuota } from "../app/cronologia";
import type { Conversazione } from "../app/cronologia";
import { usaLingua } from "../app/i18n";
import { Etichetta } from "./Etichetta";
import { Piu } from "./Icona";
import { Suggerimento } from "./Suggerimento";

export function Cronologia() {
  const { t } = usaLingua();
  const { conversazioni, corrente, occupato, nuova } = usaChat();

  const aperta = conversazioni.find((c) => c.id === corrente) ?? null;
  // Comprende quella aperta, se ha almeno una domanda: la voce attiva e' una
  // voce, non una riga a parte.
  const voci = conversazioni.filter((c) => !vuota(c));

  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <div className="mb-[7px] px-1">
        <Etichetta>{t("history.title")}</Etichetta>
      </div>

      <Voce
        testo={t("history.new")}
        icona={<Piu size={11} />}
        // Attiva quando la conversazione aperta non ha ancora domande: e'
        // letteralmente quella conversazione, e non una scorciatoia per crearne
        // un'altra.
        attiva={aperta === null || vuota(aperta)}
        bloccata={occupato}
        suggerimento={occupato ? t("history.busy") : null}
        onClick={nuova}
      />

      {voci.length > 0 && (
        <>
          {/* Scorre l'elenco, non la corsia: la tendina del dataset sta sopra e
              fuori da qui, quindi nessun contenitore di scorrimento la puo'
              ritagliare. La prima voce resta ferma perche' e' un comando, e un
              comando che scorre via e' un comando da cercare. */}
          <nav
            aria-label={t("history.title")}
            className="mt-px flex min-h-0 flex-1 flex-col gap-px overflow-y-auto"
          >
            {voci.map((c) => (
              <VoceDi key={c.id} conversazione={c} attiva={c.id === corrente} />
            ))}
          </nav>

          <Suggerimento
            testo={t("history.local.hint")}
            className="mt-2 block px-1 text-[9.5px] leading-[1.4] text-muted"
          >
            {t("history.local")}
          </Suggerimento>
        </>
      )}
    </section>
  );
}

function VoceDi({ conversazione, attiva }: { conversazione: Conversazione; attiva: boolean }) {
  const { t } = usaLingua();
  const { occupato, apri } = usaChat();
  const titolo = titoloDi(conversazione) ?? t("history.new");

  return (
    <Voce
      testo={titolo}
      attiva={attiva}
      bloccata={occupato}
      suggerimento={occupato ? t("history.busy") : titolo}
      onClick={() => apri(conversazione.id)}
    />
  );
}

/** Le misure sono quelle del mockup: 11,5 px, la voce attiva su `surface-2`
 *  con l'inchiostro pieno, le altre attenuate. */
function Voce({
  testo,
  attiva,
  bloccata,
  suggerimento,
  icona,
  onClick,
}: {
  testo: string;
  attiva: boolean;
  bloccata: boolean;
  suggerimento: string | null;
  icona?: ReactNode;
  onClick: () => void;
}) {
  const bottone = (
    <button
      type="button"
      aria-current={attiva ? "true" : undefined}
      aria-disabled={bloccata ? true : undefined}
      onClick={() => {
        if (!bloccata) onClick();
      }}
      className={`flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left text-[11.5px] transition-colors ${
        attiva ? "bg-surface-2 font-medium text-ink" : "text-ink-2"
      } ${bloccata ? "cursor-not-allowed opacity-50" : attiva ? "" : "hover:bg-surface-2"}`}
    >
      {icona}
      <span className="truncate">{testo}</span>
    </button>
  );

  if (suggerimento === null) return bottone;
  return (
    <Suggerimento testo={suggerimento} fuoco={false} className="block">
      {bottone}
    </Suggerimento>
  );
}
