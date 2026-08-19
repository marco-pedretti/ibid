/**
 * Dove mettere una bolla accanto a qualcosa, senza che finisca fuori schermo.
 *
 * Sta fuori da React perche' e' l'unica parte del suggerimento che puo' **dare un
 * risultato sbagliato** invece di essere solo brutta, ed e' aritmetica: si prova
 * in ambiente `node`, senza DOM e senza una libreria di rendering.
 *
 * Il caso che rende questo modulo necessario e' concreto: il pannello fonti e'
 * larga 272 px e sta **incollata al bordo destro**. Una bolla centrata sul suo
 * contenuto sporge dalla finestra di quasi la sua metà, e una bolla che sporge non
 * si legge — sarebbe uno suggerimento che nasconde ciò che spiega.
 */

/** Quanto la bolla sta staccata dal bersaglio. */
export const DISTANZA = 8;
/** Quanto resta di margine fra la bolla e il bordo della finestra. */
export const MARGINE = 8;

export interface Rettangolo {
  x: number;
  y: number;
  larghezza: number;
  altezza: number;
}

export interface Misura {
  larghezza: number;
  altezza: number;
}

export interface Posa {
  x: number;
  y: number;
  /** Da che parte del bersaglio si e' finiti: serve al verso dell'animazione. */
  verso: "sopra" | "sotto";
}

/**
 * `sopra` per difetto, e non e' una preferenza estetica: il puntatore arriva **da
 * sopra** quasi sempre, e una bolla sotto il bersaglio finisce dove la mano sta
 * andando. Si ripiega sotto solo quando sopra non ci sta.
 *
 * In orizzontale non si ripiega, si **stringe al bordo**: perdere il centramento
 * costa la simmetria, uscire dalla finestra costa il testo.
 */
export function colloca(bersaglio: Rettangolo, bolla: Misura, finestra: Misura): Posa {
  const sopra = bersaglio.y - bolla.altezza - DISTANZA;
  const sotto = bersaglio.y + bersaglio.altezza + DISTANZA;

  const staSopra = sopra >= MARGINE;
  const staSotto = sotto + bolla.altezza <= finestra.altezza - MARGINE;
  // Se non ci sta da nessuna parte si sceglie il lato con piu' spazio, invece di
  // insistere su quello preferito e uscire di sicuro.
  const verso: Posa["verso"] = staSopra
    ? "sopra"
    : staSotto
      ? "sotto"
      : bersaglio.y > finestra.altezza - (bersaglio.y + bersaglio.altezza)
        ? "sopra"
        : "sotto";

  const centro = bersaglio.x + bersaglio.larghezza / 2 - bolla.larghezza / 2;
  const massimo = finestra.larghezza - bolla.larghezza - MARGINE;
  // `Math.max` **dopo** `Math.min`: con una bolla piu' larga della finestra il
  // massimo e' minore del margine, e nell'ordine opposto si finirebbe fuori a
  // sinistra invece che dentro.
  const x = Math.max(MARGINE, Math.min(centro, massimo));

  return { x, y: verso === "sopra" ? sopra : sotto, verso };
}
