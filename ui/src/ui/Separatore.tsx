/**
 * Il manico fra due colonne.
 *
 * **Un pixel di linea, undici di presa.** Un bordo si vede bene sottile e si
 * afferra male: cio' che si disegna resta un filo come tutti gli altri bordi
 * dell'interfaccia, e due riquadri invisibili allargano il bersaglio. Chi guarda
 * vede un bordo, chi trascina prende undici pixel — la misura sotto cui un
 * puntatore comincia a mancarlo.
 *
 * **`setPointerCapture` e non un `mousemove` sul documento.** Con la cattura gli
 * eventi continuano ad arrivare a *questo* elemento anche quando il puntatore
 * ne esce, il che rende il trascinamento immune alle due cose che lo rompono
 * sempre: uscire dalla finestra, e passare sopra un iframe o un contenitore che
 * ferma la propagazione. In cambio non serve montare e smontare ascoltatori
 * globali, che e' la parte che si dimentica di pulire.
 *
 * **Si sposta anche da tastiera.** E' un `separator` con `aria-valuenow`, e le
 * frecce lo muovono di dieci pixel per volta. Non e' un extra: senza, la
 * larghezza delle colonne sarebbe l'unica cosa dell'interfaccia raggiungibile
 * solo con un puntatore — e questa e' la stessa scelta che ha portato la tendina
 * di U-00 a essere riscritta con la tastiera dentro invece che sopra.
 */
import { useRef } from "react";

/** Quanto sposta una freccia. Dieci px: abbastanza da vedersi, poco da poter
 *  ripetere senza contare. */
const PASSO = 10;

export function Separatore({
  etichetta,
  valore,
  onSposta,
}: {
  /** Cosa si sta ridimensionando, per chi ascolta. */
  etichetta: string;
  /** La larghezza attuale della colonna, in pixel: la porta `aria-valuenow`. */
  valore: number;
  /** Di quanti pixel si e' spostato il manico. Positivo = verso destra. */
  onSposta: (delta: number) => void;
}) {
  const ultimo = useRef<number | null>(null);

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={etichetta}
      aria-valuenow={Math.round(valore)}
      tabIndex={0}
      onPointerDown={(e) => {
        // Solo il tasto principale: col destro si apre un menu contestuale, e
        // un trascinamento cominciato li' resterebbe attaccato al puntatore.
        if (e.button !== 0) return;
        e.preventDefault();
        ultimo.current = e.clientX;
        e.currentTarget.setPointerCapture(e.pointerId);
      }}
      onPointerMove={(e) => {
        if (ultimo.current === null) return;
        // Il **delta** e non la posizione assoluta: cosi' il manico non salta
        // sotto il dito quando lo si prende da un bordo invece che dal centro.
        const delta = e.clientX - ultimo.current;
        if (delta === 0) return;
        ultimo.current = e.clientX;
        onSposta(delta);
      }}
      onPointerUp={(e) => {
        ultimo.current = null;
        e.currentTarget.releasePointerCapture(e.pointerId);
      }}
      onPointerCancel={() => {
        ultimo.current = null;
      }}
      onKeyDown={(e) => {
        if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
        e.preventDefault();
        onSposta(e.key === "ArrowRight" ? PASSO : -PASSO);
      }}
      className="group relative cursor-col-resize touch-none focus-visible:outline-none"
    >
      {/* **La linea e' un pixel, la presa e' undici.** Un bordo si vede bene
          sottile e si afferra male: la traccia della griglia e' larga cinque px
          e la presa ne aggiunge tre per lato, ma cio' che si disegna resta una
          linea come tutti gli altri bordi dell'interfaccia. Colorare i cinque
          px avrebbe messo una barra grigia dove il mockup ha un filo. */}
      <span
        aria-hidden="true"
        className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-line transition-colors group-hover:bg-accent-2 group-focus-visible:w-[3px] group-focus-visible:bg-accent"
      />
      <span aria-hidden="true" className="absolute -inset-x-1 inset-y-0" />
    </div>
  );
}
