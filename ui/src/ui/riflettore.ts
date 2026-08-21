/**
 * Dove sta l'alone attorno a una zona dell'interfaccia, e dove la scheda che la
 * spiega (U-20).
 *
 * Sta fuori da React per la ragione di `collocazione.ts`, che e' il modulo
 * gemello: e' l'unica parte dell'avvio guidato che puo' dare un risultato
 * **sbagliato** invece che brutto — una scheda mezza fuori schermo, un alone
 * attorno al vuoto — ed e' aritmetica, quindi si prova in `node` senza un DOM.
 *
 * **Le due costanti vengono da li' e non sono ridichiarate.** La distanza fra
 * una cosa e la sua spiegazione, e il margine oltre il quale si e' fuori
 * finestra, sono le stesse misure che usa il suggerimento: due numeri uguali
 * scritti in due posti sono due numeri che un giorno saranno diversi.
 *
 * **Perche' prima a destra.** I bersagli di questa guida stanno agli estremi —
 * due nella corsia a sinistra, uno nel pannello fonti a destra — e l'ordine
 * `destra, sinistra, sotto, sopra` li porta tutti a spiegarsi **sopra la colonna
 * di mezzo**: quella della corsia col fianco destro libero, quella delle fonti
 * ripiegando a sinistra perche' a destra il posto non c'e'. Non e' una
 * preferenza estetica, e' dove finisce l'occhio: la colonna di mezzo e' quella
 * che si sta guardando.
 *
 * **`dentro` non e' un ripiego, e' il caso della colonna di mezzo.** Un bersaglio
 * che occupa quasi tutta la finestra non ha un «accanto»: insistere sul lato con
 * piu' spazio metterebbe la scheda in una striscia di venti pixel. Li' la scheda
 * va **dentro** l'alone, in basso, dove non copre cio' che l'alone sta
 * indicando.
 */
import { DISTANZA, MARGINE } from "./collocazione";
import type { Misura, Rettangolo } from "./collocazione";

/** Quanto l'alone sta staccato da cio' che circonda. Piu' stretto della
 *  `DISTANZA`: e' un contorno, non una cosa accanto a un'altra. */
export const RESPIRO = 6;

export type Lato = "destra" | "sinistra" | "sotto" | "sopra" | "dentro";

export interface PosaScheda {
  x: number;
  y: number;
  /** Da che parte si e' finiti: serve al verso dell'animazione e alla punta. */
  lato: Lato;
}

/** `Math.max` **dopo** `Math.min`: con qualcosa piu' grande della finestra il
 *  massimo e' minore del minimo, e nell'ordine opposto si finirebbe fuori dal
 *  bordo opposto. E' la stessa nota di `collocazione.ts`, e lo stesso errore. */
function stringi(valore: number, minimo: number, massimo: number): number {
  return Math.max(minimo, Math.min(valore, massimo));
}

/**
 * L'alone attorno a un bersaglio: il suo rettangolo allargato del respiro, e
 * **ritagliato alla finestra**.
 *
 * Il ritaglio serve a un caso vero: una zona che scorre puo' essere mezza fuori
 * dalla finestra, e un contorno disegnato dove lo schermo non c'e' e' un
 * rettangolo che sembra tagliato per sbaglio. Ritagliato, l'alone chiude sul
 * bordo — che e' anche cio' che l'occhio si aspetta.
 */
export function alone(bersaglio: Rettangolo, finestra: Misura): Rettangolo {
  const sinistra = Math.max(0, bersaglio.x - RESPIRO);
  const sopra = Math.max(0, bersaglio.y - RESPIRO);
  const destra = Math.min(finestra.larghezza, bersaglio.x + bersaglio.larghezza + RESPIRO);
  const sotto = Math.min(finestra.altezza, bersaglio.y + bersaglio.altezza + RESPIRO);

  return {
    x: sinistra,
    y: sopra,
    larghezza: Math.max(0, destra - sinistra),
    altezza: Math.max(0, sotto - sopra),
  };
}

/** Quanti vertici ha il ritaglio del velo. Fisso, e la fissita' e' il punto:
 *  vedi `buco`. */
export const VERTICI = 10;

/**
 * Il `clip-path` del velo: la finestra intera **meno** la zona illuminata.
 *
 * Un velo solo, ritagliato, invece di quattro rettangoli attorno alla zona. La
 * differenza si vede quando il velo sfoca: quattro rettangoli che cambiano
 * misura obbligano il browser a rifare quattro sfocature a ogni fotogramma,
 * mentre qui lo strato sfocato non si muove mai — cambia solo la forma con cui
 * lo si ritaglia.
 *
 * **Dieci vertici, sempre.** Una transizione su `clip-path` interpola solo fra
 * poligoni con lo stesso numero di punti: se il ritaglio ne avesse quattro
 * quando la zona tocca un bordo e dieci quando non lo tocca, il velo
 * **salterebbe** proprio nei passaggi in cui la zona attraversa lo schermo. Il
 * perimetro esterno e il buco sono percio' sempre entrambi presenti, anche
 * degeneri, ed e' cio' che rende il movimento continuo.
 *
 * `evenodd` e' la regola che rende il secondo anello un buco invece di una
 * seconda macchia: senza, i due percorsi si sommerebbero e il velo coprirebbe
 * tutto.
 */
export function buco(contorno: Rettangolo, finestra: Misura): string {
  // Prende l'alone gia' calcolato — non il bersaglio — e lo ritaglia ancora, per
  // difesa: un ritaglio che esce dalla finestra non sbaglia il disegno, ma
  // sposta i vertici dove nessuno li vede e rende illeggibile il movimento.
  const c = {
    x: stringi(contorno.x, 0, finestra.larghezza),
    y: stringi(contorno.y, 0, finestra.altezza),
  };
  const x2 = stringi(contorno.x + contorno.larghezza, c.x, finestra.larghezza);
  const y2 = stringi(contorno.y + contorno.altezza, c.y, finestra.altezza);

  const punti = [
    // Il perimetro della finestra, chiuso tornando all'origine.
    [0, 0],
    [finestra.larghezza, 0],
    [finestra.larghezza, finestra.altezza],
    [0, finestra.altezza],
    [0, 0],
    // Il buco, chiuso allo stesso modo.
    [c.x, c.y],
    [c.x, y2],
    [x2, y2],
    [x2, c.y],
    [c.x, c.y],
  ];

  return `polygon(evenodd, ${punti.map(([x, y]) => `${x}px ${y}px`).join(", ")})`;
}

/**
 * Dove va la scheda, dato l'alone che deve spiegare.
 *
 * Il primo lato dell'ordine in cui la scheda **ci sta per intero** vince; se non
 * ci sta da nessuna parte si va `dentro`. Non si sceglie «il lato con piu'
 * spazio» come fa `colloca` per le bolle, e la differenza e' voluta: una bolla
 * di tre parole sta quasi ovunque, una scheda con un titolo e due frasi no, e
 * scegliere il meno stretto fra due lati stretti significa comunque sporgere.
 */
export function collocaScheda(zona: Rettangolo, scheda: Misura, finestra: Misura): PosaScheda {
  const centroX = stringi(
    zona.x + zona.larghezza / 2 - scheda.larghezza / 2,
    MARGINE,
    finestra.larghezza - scheda.larghezza - MARGINE,
  );
  const centroY = stringi(
    zona.y + zona.altezza / 2 - scheda.altezza / 2,
    MARGINE,
    finestra.altezza - scheda.altezza - MARGINE,
  );

  const aDestra = zona.x + zona.larghezza + DISTANZA;
  const aSinistra = zona.x - DISTANZA - scheda.larghezza;
  const aSotto = zona.y + zona.altezza + DISTANZA;
  const aSopra = zona.y - DISTANZA - scheda.altezza;

  if (aDestra + scheda.larghezza + MARGINE <= finestra.larghezza) {
    return { x: aDestra, y: centroY, lato: "destra" };
  }
  if (aSinistra >= MARGINE) {
    return { x: aSinistra, y: centroY, lato: "sinistra" };
  }
  if (aSotto + scheda.altezza + MARGINE <= finestra.altezza) {
    return { x: centroX, y: aSotto, lato: "sotto" };
  }
  if (aSopra >= MARGINE) {
    return { x: centroX, y: aSopra, lato: "sopra" };
  }

  // Dentro, in basso: sopra ci sta cio' che l'alone indica, e coprirlo con la
  // spiegazione sarebbe indicare e nascondere nello stesso gesto.
  return {
    x: centroX,
    y: stringi(
      zona.y + zona.altezza - scheda.altezza - MARGINE,
      MARGINE,
      finestra.altezza - scheda.altezza - MARGINE,
    ),
    lato: "dentro",
  };
}
