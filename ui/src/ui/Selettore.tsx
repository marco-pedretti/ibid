/**
 * La tendina, disegnata da noi.
 *
 * Sostituisce il `<select>` nativo che era steso trasparente sopra il disegno.
 * Quello dava gratis cinque cose — tastiera, ruolo ARIA, chiusura al clic
 * fuori, voci disabilitate, lista di sistema — e toglierlo significa **doverle
 * scrivere**, non poterle perdere: una tendina piu' bella e meno usabile
 * sarebbe un peggioramento travestito.
 *
 * Quindi qui c'e' il pattern `listbox`: il fuoco resta sul bottone,
 * `aria-activedescendant` dice quale voce e' evidenziata, e frecce, Invio,
 * Escape, Home e Fine fanno cio' che ci si aspetta. La navigazione (saltare le
 * disabilitate, girare in tondo, fermarsi se **tutte** sono disabilitate) sta in
 * `lista.ts`, provata senza DOM.
 *
 * **L'animazione ha due tempi diversi, e non e' un vezzo.** Aprire e' una
 * risposta a un gesto: 150 ms in `ease-out`, che parte veloce e si posa.
 * Chiudere e' cio' che toglie di mezzo: 110 ms in `ease-in`, che non fa
 * aspettare per una cosa gia' decisa. Un pannello che entra ed esce con la
 * stessa curva sembra sempre in ritardo in uscita.
 *
 * Chi ha chiesto meno movimento lo ottiene: le durate sono transizioni CSS, e
 * la regola globale `prefers-reduced-motion` di `index.css` le azzera tutte.
 */
import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";

import { Caret } from "./Icona";
import { allApertura, estremo, indiceDi, scorri } from "./lista";
import type { Voce } from "./lista";

export type { Voce } from "./lista";

/** Quanto dura la chiusura: il pannello resta montato per questo tempo, se no
 *  sparirebbe di scatto e l'animazione d'uscita non si vedrebbe mai. */
const USCITA_MS = 110;

export function Selettore<T extends string>({
  etichetta,
  valore,
  voci,
  onCambia,
  className = "",
  verso = "giu",
  larghezza = "contenuto",
  children,
}: {
  etichetta: string;
  valore: T;
  voci: readonly Voce<T>[];
  onCambia: (valore: T) => void;
  className?: string;
  /** Dove si apre il pannello. In fondo alla corsia `"su"` e' l'unica scelta
   *  possibile: verso il basso finirebbe fuori dalla finestra. */
  verso?: "giu" | "su";
  /** `"bottone"` incolla il pannello alla larghezza del controllo: dentro una
   *  corsia di 200 px e' l'unica misura che non sfonda. `"contenuto"` lo lascia
   *  crescere, e serve a un controllo piccolo (la pastiglia del tema) le cui
   *  voci sono piu' larghe di lui. */
  larghezza?: "bottone" | "contenuto";
  children: ReactNode;
}) {
  const [aperto, setAperto] = useState(false);
  const [montato, setMontato] = useState(false);
  const [attivo, setAttivo] = useState(() => allApertura(voci, valore));

  const id = useId();
  const contenitore = useRef<HTMLDivElement>(null);
  const bottone = useRef<HTMLButtonElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const apri = () => {
    if (timer.current !== null) clearTimeout(timer.current);
    setAttivo(allApertura(voci, valore));
    setMontato(true);
    // Un fotogramma di ritardo: montato con lo stato «chiuso», poi acceso,
    // altrimenti il browser non ha due valori fra cui interpolare e il pannello
    // comparirebbe di scatto.
    requestAnimationFrame(() => setAperto(true));
  };

  const chiudi = (tornaAlBottone = true) => {
    setAperto(false);
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = setTimeout(() => setMontato(false), USCITA_MS);
    // Il fuoco torna da dove e' partito: chiudendo con Escape, senza questo si
    // finirebbe in cima al documento senza sapere dove.
    if (tornaAlBottone) bottone.current?.focus();
  };

  const scegli = (i: number) => {
    const v = voci[i];
    if (!v || v.disabilitata) return;
    onCambia(v.valore);
    chiudi();
  };

  useEffect(() => () => {
    if (timer.current !== null) clearTimeout(timer.current);
  }, []);

  useEffect(() => {
    if (!montato) return;
    const fuori = (e: PointerEvent) => {
      if (!contenitore.current?.contains(e.target as Node)) chiudi(false);
    };
    document.addEventListener("pointerdown", fuori);
    return () => document.removeEventListener("pointerdown", fuori);
  });

  const daTastiera = (e: KeyboardEvent) => {
    if (!aperto) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        apri();
      }
      return;
    }

    switch (e.key) {
      case "ArrowDown":
      case "ArrowUp": {
        e.preventDefault();
        const i = scorri(voci, attivo, e.key === "ArrowDown" ? 1 : -1);
        if (i !== -1) setAttivo(i);
        break;
      }
      case "Home":
      case "End": {
        e.preventDefault();
        const i = estremo(voci, e.key === "Home" ? 1 : -1);
        if (i !== -1) setAttivo(i);
        break;
      }
      case "Enter":
      case " ":
        e.preventDefault();
        scegli(attivo);
        break;
      case "Escape":
        e.preventDefault();
        chiudi();
        break;
      case "Tab":
        // Non si intrappola il fuoco: Tab porta via, e la tendina si toglie di
        // mezzo invece di restare aperta su niente.
        chiudi(false);
        break;
    }
  };

  const scelta = indiceDi(voci, valore);

  return (
    <div ref={contenitore} className="relative">
      <button
        ref={bottone}
        type="button"
        aria-label={etichetta}
        aria-haspopup="listbox"
        aria-expanded={aperto}
        aria-controls={montato ? `${id}-lista` : undefined}
        aria-activedescendant={aperto && attivo !== -1 ? `${id}-${attivo}` : undefined}
        onClick={() => (aperto ? chiudi() : apri())}
        onKeyDown={daTastiera}
        className={`w-full cursor-pointer text-left ${className}`}
      >
        {children}
        <Caret
          size={12}
          className={`ml-auto text-ink-2 transition-transform duration-150 ${
            aperto ? "rotate-180 ease-out" : "rotate-0 ease-in"
          }`}
        />
      </button>

      {montato && (
        <div
          id={`${id}-lista`}
          role="listbox"
          aria-label={etichetta}
          className={[
            "absolute z-20 overflow-hidden rounded-lg border border-line-2 bg-surface p-1 shadow-carta",
            larghezza === "bottone" ? "w-full" : "min-w-full w-max",
            verso === "giu" ? "top-full mt-1.5 origin-top" : "bottom-full mb-1.5 origin-bottom",
            "transition-[opacity,transform]",
            aperto
              ? "translate-y-0 scale-100 opacity-100 duration-150 ease-out"
              : `${verso === "giu" ? "-translate-y-1" : "translate-y-1"} scale-[0.98] opacity-0 duration-100 ease-in`,
          ].join(" ")}
        >
          {voci.map((v, i) => (
            <div
              key={v.valore}
              id={`${id}-${i}`}
              role="option"
              aria-selected={i === scelta}
              aria-disabled={v.disabilitata}
              onPointerDown={(e) => e.preventDefault()} // il fuoco resta al bottone
              onClick={() => scegli(i)}
              onPointerEnter={() => !v.disabilitata && setAttivo(i)}
              className={[
                "flex items-center gap-2 rounded-md px-2 py-1.5 text-[11.5px]",
                v.disabilitata
                  ? "cursor-not-allowed text-muted"
                  : "cursor-pointer text-ink-2 transition-colors duration-100",
                !v.disabilitata && i === attivo ? "bg-surface-2 text-ink" : "",
                i === scelta && !v.disabilitata ? "font-medium text-accent" : "",
              ].join(" ")}
            >
              {v.icona}
              <span className="truncate">{v.testo}</span>
              {v.dettaglio !== undefined && (
                <span className="ml-auto shrink-0 font-mono text-[10px] text-muted tabular-nums">
                  {v.dettaglio}
                </span>
              )}
              {i === scelta && (
                <span
                  aria-hidden="true"
                  className={`shrink-0 font-mono text-[10px] text-accent ${
                    v.dettaglio === undefined ? "ml-auto" : ""
                  }`}
                >
                  •
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
