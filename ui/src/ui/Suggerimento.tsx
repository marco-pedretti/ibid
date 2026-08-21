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
 * **Un'interazione manda via la bolla, e ne rimanda il ritorno.** Un clic sul
 * bersaglio non e' mai una domanda su di lui: e' il controllo che si sta usando.
 * Chi apre una tendina restando fermo sopra la pastiglia trovava la bolla di
 * nuovo li' nell'istante in cui la richiudeva — l'attesa era gia' scaduta, e il
 * secondo clic la ritrovava smontata e la riapriva «subito». Adesso dopo un clic
 * l'attesa **ricomincia**, e lo stesso vale per il fuoco che arriva da un clic
 * invece che da un Tab: `:focus-visible` e' la distinzione che il browser fa gia'
 * al posto nostro. Il tocco resta l'eccezione — li' un dito non ha un
 * «passaggio sopra», quindi il clic e' l'unico modo di chiedere — e si riconosce
 * da se': su un tocco `pointerleave` arriva **prima** del `click`, quindi al
 * momento del clic il puntatore c'e' solo se e' un mouse.
 *
 * ## Il tocco, e i suoi due casi
 *
 * **Su un dato il tocco basta gia', e non serviva niente.** Un punteggio, un
 * marcatore, un `chunk_id`: sotto non c'e' nessun comando, quindi il tocco non
 * ha altro da significare e apre la bolla — e' la regola scritta qui sopra, che
 * distingue il clic del mouse dal tocco guardando se al momento del clic il
 * puntatore e' ancora sul bersaglio.
 *
 * **Dove sotto c'e' un comando, no**, ed e' l'altra meta': li' il tocco e' gia'
 * preso — manda la domanda, cambia dataset, apre l'esploratore — e non puo'
 * anche voler dire «spiegami». Con una sola cosa da fare e due da dire, quella
 * che si perde e' sempre la spiegazione, che infatti su un telefono compariva un
 * istante e poi spariva insieme alla schermata che l'aveva aperta.
 *
 * Quindi li' la domanda si fa **tenendo premuto**, che e' il gesto con cui un
 * telefono chiede «cos'e' questo» da sempre. Non e' una modalita' che si accende
 * sotto una certa larghezza: si guarda `pointerType`, cioe' **il gesto**, non lo
 * schermo. Un portatile con lo schermo a tocco non ha un passaggio sopra nemmeno
 * a 1.600 px, e un mouse in una finestra stretta ce l'ha eccome.
 *
 * La distinzione fra i due casi e' `fuoco`, che gia' esiste e gia' dice
 * esattamente questo: `fuoco={false}` significa «dentro c'e' qualcosa che prende
 * il fuoco», cioe' un comando. Non e' un secondo interruttore da tenere
 * d'accordo col primo.
 *
 * **Alzando il dito la bolla resta.** Un `pointerleave` arriva subito dopo il
 * `pointerup`, e chiuderla li' vorrebbe dire non averla mai mostrata: se ne va
 * al tocco successivo, ovunque esso cada, o con Escape. E il clic che chiude la
 * pressione **non arriva al comando** — chi ha tenuto premuto stava chiedendo,
 * non premendo.
 *
 * **Il testo e' leggibile anche senza la bolla.** `aria-describedby` punta a uno
 * `<span>` sempre presente e visivamente nascosto: la bolla e' `aria-hidden` e
 * puramente visiva. Legarla agli assistivi significherebbe che un'informazione
 * esiste solo mentre un puntatore ci passa sopra — e chi non ha un puntatore non
 * l'avrebbe mai.
 */
import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { CSSProperties, ReactNode } from "react";

import { colloca } from "./collocazione";
import { scala } from "./scala";
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

/**
 * Quanto si tiene premuto perche' diventi una domanda.
 *
 * 450 ms e' la soglia che iOS e Android usano per la pressione lunga, e vale la
 * pena prendere la loro invece di sceglierne una: il gesto o e' quello che chi
 * tocca ha gia' in mano, o non e' niente — non c'e' modo di insegnarlo.
 *
 * Piu' corta si scontrerebbe con un tocco fermo (un dito si posa e si alza in
 * ~150 ms, ma non tutti); piu' lunga arriverebbe dopo che il browser ha gia'
 * cominciato la propria selezione.
 */
const PRESSIONE_MS = 450;

/** Rete di sicurezza per lo smontaggio: se la transizione non parte affatto
 *  (scheda in secondo piano) `transitionend` non arriva mai. Come nella tendina. */
const USCITA_MAX_MS = 300;

export function Suggerimento({
  testo,
  children,
  className = "",
  stile,
  fuoco = true,
  dato = false,
}: {
  testo: string;
  children: ReactNode;
  /** Classi del bersaglio, non della bolla: il bersaglio resta cio' che era. */
  className?: string;
  /**
   * Stile in linea del bersaglio, per cio' che non e' esprimibile in classi.
   *
   * Serve alla mappa dell'esploratore, dove la larghezza di ogni tratto e' un
   * numero calcolato. E serve **qui** e non sul figlio: il bersaglio e' lo
   * `span` che avvolge, quindi e' lui la voce del contenitore flex, e uno stile
   * messo sul bottone dentro non lo raggiunge. E' un difetto gia' pagato una
   * volta — i tratti venivano fuori tutti larghi due pixel.
   */
  stile?: CSSProperties;
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
  /** Il puntatore e' **adesso** sul bersaglio. Vedi `onClick`: e' cio' che
   *  distingue un clic dato col mouse da un tocco su un telefono. */
  const dentro = useRef(false);
  const uscita = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** La pressione in corso, finche' non e' abbastanza lunga da contare. */
  const pressione = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** La bolla e' li' perche' si e' tenuto premuto. Cambia due cose: non si
   *  chiude quando il dito si alza, e il clic che segue non arriva al comando. */
  const daPressione = useRef(false);

  const fermaTimer = () => {
    if (attesa.current !== null) clearTimeout(attesa.current);
    if (uscita.current !== null) clearTimeout(uscita.current);
    attesa.current = null;
    uscita.current = null;
  };

  const fermaPressione = () => {
    if (pressione.current !== null) clearTimeout(pressione.current);
    pressione.current = null;
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
    daPressione.current = false;
    fermaTimer();
    fermaPressione();
    setAperto(false);
    uscita.current = setTimeout(() => setMontato(false), USCITA_MAX_MS);
  };

  useEffect(
    () => () => {
      fermaTimer();
      fermaPressione();
    },
    [],
  );

  // Due passate, e servono entrambe: la bolla si monta invisibile per **essere
  // misurata** — la sua altezza dipende da dove il testo va a capo, che nessuno
  // sa prima — poi si colloca, e solo dopo si accende. Accenderla prima la
  // farebbe comparire a (0, 0) per un fotogramma, cioe' in alto a sinistra.
  useLayoutEffect(() => {
    if (!montato || posa !== null) return;
    const b = bersaglio.current?.getBoundingClientRect();
    const c = bolla.current?.getBoundingClientRect();
    if (!b || !c) return;
    // **Si converte al confine**, e il confine e' qui: i rettangoli e la finestra
    // arrivano in px di **finestra**, mentre `left` e `top` qui sotto si scrivono
    // in px di **disegno**. Senza la divisione la bolla si allontanerebbe
    // dall'origine esattamente del fattore di scala — a 1,45, una calcolata a
    // 600 px finirebbe a 870. Vedi `scala.ts`, dove i due spazi sono in tabella.
    const z = scala();
    setPosa(
      colloca(
        { x: b.left / z, y: b.top / z, larghezza: b.width / z, altezza: b.height / z },
        { larghezza: c.width / z, altezza: c.height / z },
        { larghezza: window.innerWidth / z, altezza: window.innerHeight / z },
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

  // Una bolla aperta tenendo premuto non ha un «via di qui»: il dito si e' gia'
  // alzato, e il bersaglio non prende il fuoco (e' un comando ad averlo). Se ne
  // va al tocco seguente, dovunque cada — anche sul bersaglio stesso, dove
  // ricomincia una pressione nuova.
  useEffect(() => {
    if (!montato) return;
    const altrove = (e: PointerEvent) => {
      if (!daPressione.current) return;
      if (bersaglio.current?.contains(e.target as Node)) return;
      chiudi();
    };
    document.addEventListener("pointerdown", altrove, true);
    return () => document.removeEventListener("pointerdown", altrove, true);
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
        style={stile}
        // Raggiungibile da tastiera, altrimenti la spiegazione esiste solo per chi
        // ha un puntatore. Nel pannello fonti non c'erano tappe di tabulazione:
        // queste sono le prime, e non rubano il posto a nessuna.
        tabIndex={fuoco ? 0 : undefined}
        aria-describedby={fuoco ? `${id}-testo` : undefined}
        onPointerEnter={() => {
          dentro.current = true;
          apri();
        }}
        onPointerLeave={() => {
          dentro.current = false;
          fermaPressione();
          // Alzando il dito arriva un `pointerleave` subito dopo il `pointerup`:
          // chiudere qui vorrebbe dire non aver mai mostrato la bolla che si e'
          // appena chiesta tenendo premuto.
          if (daPressione.current) return;
          chiudi();
        }}
        // **Tenere premuto e' la domanda, dove il tocco e' gia' preso.** Solo
        // col dito (`pointerType`) e solo dove dentro c'e' un comando
        // (`fuoco === false`): su un dato il tocco basta gia' da se', e chiedere
        // di tenere premuto sarebbe una regola in piu' per la stessa cosa.
        onPointerDown={(e) => {
          if (fuoco || e.pointerType !== "touch") return;
          daPressione.current = false;
          fermaPressione();
          pressione.current = setTimeout(() => {
            daPressione.current = true;
            apri(true);
          }, PRESSIONE_MS);
        }}
        onPointerUp={fermaPressione}
        // Il browser si e' preso il gesto per scorrere: non era una pressione.
        onPointerCancel={fermaPressione}
        // In cattura, cioe' **prima** del comando che sta dentro: chi ha tenuto
        // premuto stava chiedendo, non premendo, e il clic che chiude la
        // pressione non deve mandare una domanda o cambiare schermata.
        onClickCapture={(e) => {
          if (!daPressione.current) return;
          e.preventDefault();
          e.stopPropagation();
        }}
        // **Un clic col puntatore non e' una domanda: e' un'interazione col
        // controllo, e l'attesa ricomincia.** Il tocco non ha un «passaggio
        // sopra», quindi li' il clic e' l'unico modo di chiedere e apre subito —
        // e i due casi si distinguono da soli, perche' su un tocco il browser
        // manda `pointerleave` *prima* del `click`: al momento del clic il
        // puntatore c'e' solo se e' un mouse.
        //
        // Senza questo, chiudere una tendina che si e' aperta stando fermi sopra
        // la pastiglia faceva ricomparire la bolla nello stesso istante: il
        // secondo clic la trovava smontata e la riapriva «subito».
        onClick={() => (montato ? chiudi() : apri(!dentro.current))}
        // Il fuoco che arriva **da un clic** non e' una domanda: e' il bersaglio
        // che si prende il fuoco perche' e' stato premuto. `:focus-visible` e' la
        // distinzione che il browser fa gia' fra la tastiera e il puntatore, e
        // farla qui evita di dover indovinare da dove viene il fuoco.
        onFocus={(e) => {
          if (e.target.matches(":focus-visible")) apri(true);
        }}
        onBlur={chiudi}
        // `cursor-help` e' tutto il segnale che serve, ed e' voluto che sia poco:
        // una sottolineatura al passaggio comparirebbe solo quando ci sei gia'
        // sopra — cioe' quando la bolla sta arrivando comunque — e sotto la
        // pastiglia del marcatore, che ha gia' un bordo, sarebbe una riga in piu'
        // che si somma a quella. Il tratteggio in questa interfaccia ha inoltre
        // gia' un significato preso: la frase che non cita nessuna fonte.
        // Da tastiera il segnale c'e' e non e' questo: e' l'anello di fuoco
        // globale di `index.css`.
        // `select-none` solo dove dentro c'e' un comando: e' li' che si tiene
        // premuto, ed e' li' che senza questo il telefono risponderebbe alla
        // pressione lunga con le maniglie di selezione sull'etichetta di un
        // bottone — cioe' con la sua risposta invece della nostra.
        className={`${fuoco ? "cursor-help" : "select-none"} ${className}`}
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
