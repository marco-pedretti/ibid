import type { ReactNode } from "react";

/**
 * Uno strato che entra da un bordo, col resto dello schermo velato dietro.
 *
 * **Sta in un file suo perche' lo aprono in due**, e non e' un'astrazione fatta
 * in anticipo: U-21 lo ha scritto per la corsia e le fonti a colonna sola, D-5
 * lo riusa per i dettagli della run -- che pero' e' uno strato **in tutte e due
 * le forme**, perche' non sostituisce nessuna colonna. Il componente non sa
 * quale dei due casi sta servendo, ed e' giusto cosi': sa entrare da un bordo e
 * lasciarsi chiudere.
 *
 * **La larghezza e' quella della colonna che sostituisce** — 200 px la corsia,
 * 272 le fonti — e non una frazione dello schermo. Tutte le misure di quelle due
 * colonne sono state accordate su quei numeri (i titoli di conversazione
 * troncati a ~28 caratteri, il nome del documento in 272 px): darne di diverse
 * qui vorrebbe dire avere due impaginazioni per lo stesso componente, e la prima
 * che si rompe e' quella che non si guarda mai. Il tetto in percentuale e' per
 * gli schermi piu' stretti del telefono del criterio, dove uno strato pieno
 * lascerebbe il velo largo un dito e non si capirebbe piu' che si chiude.
 *
 * **Il velo e' un bottone**, non un `div` con un `onClick`: chiudere toccando
 * fuori e' un comando, e un comando ha un nome che si puo' leggere e un fuoco su
 * cui si puo' arrivare col tasto di tabulazione. Il velo e' lo stesso token
 * dell'avvio guidato (U-20) — e li' non intercettava il puntatore perche' la
 * guida non doveva impedire niente; qui **deve**, perche' cio' che ci sta sotto
 * e' coperto e cliccare alla cieca aprirebbe cose che non si vedono.
 */
export function Strato({
  lato,
  larghezza,
  chiudi,
  nome,
  children,
}: {
  lato: "sinistra" | "destra";
  larghezza: number;
  chiudi: () => void;
  nome: string;
  children: ReactNode;
}) {
  return (
    <div className={`fixed inset-0 z-40 flex ${lato === "destra" ? "flex-row-reverse" : ""}`}>
      <div
        style={{ width: larghezza }}
        className={`h-full max-w-[86%] shrink-0 ${lato === "destra" ? "entra-da-destra" : "entra-da-sinistra"}`}
      >
        {children}
      </div>
      <button
        type="button"
        onClick={chiudi}
        aria-label={nome}
        className="appare h-full flex-1 bg-velo backdrop-blur-[2px]"
      />
    </div>
  );
}
