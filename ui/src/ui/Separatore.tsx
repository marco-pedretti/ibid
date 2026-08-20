/**
 * Il manico fra due colonne.
 *
 * **Un pixel di linea, undici di presa.** Un bordo si vede bene sottile e si
 * afferra male: cio' che si disegna resta un filo come tutti gli altri bordi
 * dell'interfaccia, e due riquadri invisibili allargano il bersaglio. Chi guarda
 * vede un bordo, chi trascina prende undici pixel — la misura sotto cui un
 * puntatore comincia a mancarlo.
 *
 * **Si misura dall'origine del trascinamento, non dall'ultimo fotogramma.** E'
 * la differenza fra un manico che si comporta e uno che no. Sommando i delta
 * fotogramma per fotogramma e tagliando ogni volta il risultato, l'eccedenza
 * oltre il limite **si perde**: si trascina duecento pixel oltre il minimo, si
 * inverte di uno, e il manico riparte subito — mentre il puntatore e' ancora
 * lontanissimo. Tenendo la posizione di partenza e la larghezza di partenza, la
 * larghezza e' sempre `iniziale + (x - x0)` tagliata: per rimettere in moto il
 * manico bisogna riportare il puntatore dove il manico e' rimasto, che e' cio'
 * che fa ogni altro ridimensionamento al mondo.
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
  onInizio,
  onSposta,
  onFine,
}: {
  /** Cosa si sta ridimensionando, per chi ascolta. */
  etichetta: string;
  /** La larghezza attuale della colonna, in pixel: la porta `aria-valuenow`. */
  valore: number;
  /** Il trascinamento comincia: chi ascolta fissa la larghezza di partenza. */
  onInizio: () => void;
  /** Di quanti pixel il puntatore si e' spostato **dall'inizio** del
   *  trascinamento. Positivo = verso destra. */
  onSposta: (delta: number) => void;
  /** Il trascinamento e' finito. */
  onFine: () => void;
}) {
  const origine = useRef<number | null>(null);

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
        origine.current = e.clientX;
        onInizio();
        e.currentTarget.setPointerCapture(e.pointerId);
      }}
      onPointerMove={(e) => {
        if (origine.current === null) return;
        // Dall'origine e **non** dall'ultimo fotogramma: vedi la nota in testa.
        // La distanza dal punto in cui si e' cominciato non si perde quando il
        // risultato viene tagliato, quindi oltre il limite il manico resta fermo
        // finche' il puntatore non torna indietro davvero.
        onSposta(e.clientX - origine.current);
      }}
      onPointerUp={(e) => {
        origine.current = null;
        onFine();
        e.currentTarget.releasePointerCapture(e.pointerId);
      }}
      onPointerCancel={() => {
        origine.current = null;
        onFine();
      }}
      onKeyDown={(e) => {
        if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
        e.preventDefault();
        // Ogni pressione e' un gesto per conto suo: si fissa la partenza, si
        // sposta di un passo, si chiude. Cosi' la tastiera usa la stessa strada
        // del puntatore invece di una seconda.
        onInizio();
        onSposta(e.key === "ArrowRight" ? PASSO : -PASSO);
        onFine();
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
