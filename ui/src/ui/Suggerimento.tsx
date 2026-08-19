/**
 * Il suggerimento, disegnato da noi. Stessa scelta della tendina, stesse ragioni.
 *
 * Il `title` nativo dava gratis quattro cose — comparsa al passaggio, chiusura da
 * sola, nessun rischio di sporgere, lettura dagli assistivi — e toglierlo
 * significa **doverle scrivere**, non poterle perdere. Ma quello che il `title`
 * non da' e' quasi tutto: compare dopo un secondo e mezzo che nessuno controlla,
 * ha i colori del sistema operativo e non quelli del §12, non va a capo dove
 * serve, sparisce da solo dopo pochi secondi mentre lo si sta leggendo, e su un
 * dispositivo a tocco **non esiste affatto**. In un'interfaccia il cui scopo e'
 * spiegare da dove viene un numero, il posto dove i numeri si spiegano non puo'
 * essere l'unico pezzo che sembra di un altro programma.
 *
 * **Il portale non e' un vezzo.** Il pannello fonti e' un contenitore che scorre
 * (`overflow-y-auto`), e un elemento posizionato dentro un contenitore che scorre
 * viene **ritagliato** ai suoi bordi: e' lo stesso difetto che aveva la tendina
 * del dataset nella corsia. Con `createPortal` la bolla vive in fondo al `body` e
 * si colloca in coordinate di finestra, quindi nessun antenato la puo' tagliare.
 * Il prezzo e' che la posizione va calcolata a mano — e sta in `collocazione.ts`,
 * provata a parte, perche' e' la parte che puo' dare un risultato sbagliato.
 *
 * **L'animazione ha i due tempi della tendina**, e per la stessa ragione: 150 ms
 * in uscita dal nulla e 110 ms per togliersi di mezzo. Solo `opacity` e
 * `translate`, mai `scale` — su del testo lo `scale` costringe a ri-rasterizzare i
 * glifi a ogni fotogramma, ed e' la causa vera dello scatto. Chi ha chiesto meno
 * movimento lo ottiene dalla regola globale `prefers-reduced-motion`.
 *
 * **Il testo e' leggibile anche senza la bolla.** `aria-describedby` punta a uno
 * `<span>` sempre presente e visivamente nascosto: la bolla e' `aria-hidden` e
 * puramente visiva. Legarla agli assistivi significherebbe che un'informazione
 * esiste solo mentre un puntatore ci passa sopra — e chi non ha un puntatore non
 * l'avrebbe mai.
 */
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { ReactNode } from "react";

import { colloca } from "./collocazione";
import type { Posa } from "./collocazione";

/**
 * Due attese, perche' ci sono due domande diverse.
 *
 * Su un **dato** — un punteggio, un marcatore, un verdetto, un nome troncato —
 * il puntatore *e' gia' la domanda*: ci si va sopra perche' quel numero non si
 * capisce, e 140 ms sta sotto la soglia in cui l'attesa si nota. E' il caso per
 * cui i suggerimenti esistono in questa interfaccia.
 *
 * Su un **comando** o sul nome di una sezione il puntatore non chiede niente:
 * sta passando per andare altrove. Con la stessa attesa breve ogni movimento del
 * mouse accende una bolla lungo il tragitto, e un'interfaccia che vuole essere
 * minimale si riempie di riquadri che nessuno ha chiesto. Un secondo e mezzo e'
 * il tempo oltre il quale un puntatore fermo non e' piu' spiegabile come
 * transito: chi e' rimasto li' cosi' a lungo sta chiedendo.
 *
 * Che sia **la stessa attesa del `title` nativo** criticato qui sopra non e' una
 * contraddizione: il rimprovero non era la durata, era che nessuno la sceglie e
 * che vale identica per tutto. Qui e' scelta, ed e' una delle due.
 *
 * Il ritardo lungo e' il **predefinito**: un suggerimento aggiunto domani nasce
 * calmo, e per renderlo rapido bisogna dichiarare che spiega un dato.
 */
const ATTESA_DATO_MS = 140;
const ATTESA_COMANDO_MS = 1500;

/** Rete di sicurezza per lo smontaggio: se la transizione non parte affatto
 *  (scheda in secondo piano) `transitionend` non arriva mai. Come nella tendina. */
const USCITA_MAX_MS = 300;

export function Suggerimento({
  testo,
  children,
  className = "",
  fuoco = true,
  dato = false,
}: {
  testo: string;
  children: ReactNode;
  /** Classi del bersaglio, non della bolla: il bersaglio resta cio' che era. */
  className?: string;
  /**
   * `true` quando sotto c'e' **un dato da spiegare** — un punteggio, un
   * marcatore, un verdetto, un nome troncato — e non un comando o il nome di una
   * sezione. Cambia solo la pausa prima di comparire, e la ragione sta su
   * `ATTESA_DATO_MS`: li' il puntatore e' gia' una domanda, altrove sta passando.
   */
  dato?: boolean;
  /**
   * `false` quando dentro c'e' gia' qualcosa che prende il fuoco — un bottone, un
   * link. Senza, si finirebbe con **due** tappe di tabulazione per un comando
   * solo: si tabula sull'involucro, poi sul bottone dentro, e la seconda sembra
   * un salto a vuoto. `focus`/`blur` risalgono dal figlio, quindi la bolla si
   * apre comunque da tastiera.
   */
  fuoco?: boolean;
}) {
  const [aperto, setAperto] = useState(false);
  const [montato, setMontato] = useState(false);
  const [posa, setPosa] = useState<Posa | null>(null);

  const id = useId();
  const bersaglio = useRef<HTMLSpanElement>(null);
  const bolla = useRef<HTMLDivElement>(null);
  const attesa = useRef<ReturnType<typeof setTimeout> | null>(null);
  const uscita = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fermaTimer = () => {
    if (attesa.current !== null) clearTimeout(attesa.current);
    if (uscita.current !== null) clearTimeout(uscita.current);
    attesa.current = null;
    uscita.current = null;
  };

  const apri = (subito = false) => {
    fermaTimer();
    if (montato) {
      setAperto(true);
      return;
    }
    const monta = () => {
      setMontato(true);
      setPosa(null);
    };
    // `subito` e' il tocco e il fuoco da tastiera: li' non c'e' niente da
    // distinguere fra transito e intenzione, perche' un transito non esiste.
    if (subito) monta();
    else attesa.current = setTimeout(monta, dato ? ATTESA_DATO_MS : ATTESA_COMANDO_MS);
  };

  const chiudi = () => {
    fermaTimer();
    setAperto(false);
    uscita.current = setTimeout(() => setMontato(false), USCITA_MAX_MS);
  };

  useEffect(() => fermaTimer, []);

  // Due passate, e servono entrambe: la bolla si monta invisibile per **essere
  // misurata** — la sua altezza dipende da dove il testo va a capo, che nessuno
  // sa prima — poi si colloca, e solo dopo si accende. Accenderla prima la
  // farebbe comparire a (0, 0) per un fotogramma, cioe' in alto a sinistra.
  useLayoutEffect(() => {
    if (!montato || posa !== null) return;
    const b = bersaglio.current?.getBoundingClientRect();
    const c = bolla.current?.getBoundingClientRect();
    if (!b || !c) return;
    setPosa(
      colloca(
        { x: b.left, y: b.top, larghezza: b.width, altezza: b.height },
        { larghezza: c.width, altezza: c.height },
        { larghezza: window.innerWidth, altezza: window.innerHeight },
      ),
    );
  }, [montato, posa]);

  useEffect(() => {
    if (posa === null) return;
    const f = requestAnimationFrame(() => setAperto(true));
    return () => cancelAnimationFrame(f);
  }, [posa]);

  // La bolla e' in coordinate di finestra e il bersaglio sta in una colonna che
  // scorre: senza questo, uno scatto di rotella la lascerebbe indietro attaccata
  // al vuoto. Si ricalcola invece di chiudere, perche' chiudere qualcosa che si
  // sta leggendo per un movimento involontario e' peggio.
  useEffect(() => {
    if (!montato) return;
    const risistema = () => setPosa(null);
    window.addEventListener("scroll", risistema, { capture: true, passive: true });
    window.addEventListener("resize", risistema, { passive: true });
    return () => {
      window.removeEventListener("scroll", risistema, { capture: true });
      window.removeEventListener("resize", risistema);
    };
  }, [montato]);

  useEffect(() => {
    if (!montato) return;
    const daTastiera = (e: KeyboardEvent) => {
      // Escape chiude cio' che si e' aperto sopra il contenuto, sempre, in tutta
      // l'interfaccia: e' la stessa regola della tendina.
      if (e.key === "Escape") chiudi();
    };
    document.addEventListener("keydown", daTastiera);
    return () => document.removeEventListener("keydown", daTastiera);
  }, [montato]);

  return (
    <>
      <span
        ref={bersaglio}
        // Raggiungibile da tastiera, altrimenti la spiegazione esiste solo per chi
        // ha un puntatore. Nel pannello fonti non c'erano tappe di tabulazione:
        // queste sono le prime, e non rubano il posto a nessuna.
        tabIndex={fuoco ? 0 : undefined}
        aria-describedby={fuoco ? `${id}-testo` : undefined}
        onPointerEnter={() => apri()}
        onPointerLeave={chiudi}
        // Il tocco non ha un «passaggio sopra»: senza questo, su un telefono la
        // spiegazione non esisterebbe. Subito, perche' un tocco **e'** intenzione.
        onClick={() => (montato ? chiudi() : apri(true))}
        onFocus={() => apri(true)}
        onBlur={chiudi}
        // `cursor-help` e' tutto il segnale che serve, ed e' voluto che sia poco:
        // una sottolineatura al passaggio comparirebbe solo quando ci sei gia'
        // sopra — cioe' quando la bolla sta arrivando comunque — e sotto la
        // pastiglia del marcatore, che ha gia' un bordo, sarebbe una riga in piu'
        // che si somma a quella. Il tratteggio in questa interfaccia ha inoltre
        // gia' un significato preso: la frase che non cita nessuna fonte.
        // Da tastiera il segnale c'e' e non e' questo: e' l'anello di fuoco
        // globale di `index.css`.
        className={`${fuoco ? "cursor-help" : ""} ${className}`}
      >
        {children}
      </span>

      {/* Sempre nel documento, mai sullo schermo: e' questo che porta la
          spiegazione a chi ascolta invece di legarla a un puntatore. */}
      <span id={`${id}-testo`} className="sr-only">
        {testo}
      </span>

      {montato &&
        createPortal(
          <div
            ref={bolla}
            aria-hidden="true"
            onTransitionEnd={(e) => {
              if (e.propertyName === "opacity" && !aperto) setMontato(false);
            }}
            style={{
              // `-9999` finche' la misura non c'e': fuori campo invece di in alto
              // a sinistra, cosi' il fotogramma di misura non si vede.
              left: posa?.x ?? -9999,
              top: posa?.y ?? -9999,
            }}
            className={[
              "pointer-events-none fixed z-50 max-w-[240px] rounded-lg border border-line-2 bg-surface px-2.5 py-1.5",
              "text-[10.5px] leading-[1.45] text-ink-2 shadow-carta",
              "transition-[opacity,translate] will-change-[opacity,translate]",
              aperto
                ? "translate-y-0 opacity-100 duration-150 ease-[cubic-bezier(0.2,0,0,1)]"
                : [
                    // Entra **da** dove sta il bersaglio e esce verso di lui: il
                    // movimento dice da cosa viene la spiegazione.
                    posa?.verso === "sotto" ? "-translate-y-1" : "translate-y-1",
                    "opacity-0 duration-100 ease-[cubic-bezier(0.4,0,1,1)]",
                  ].join(" "),
            ].join(" ")}
          >
            {testo}
          </div>,
          document.body,
        )}
    </>
  );
}
