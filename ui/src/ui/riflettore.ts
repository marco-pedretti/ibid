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
 * Quanto della scheda deve restare **fuori** dalla zona perche' accostarla sia
 * meglio che metterla dentro: la meta'.
 *
 * Sotto quella soglia una scheda accostata copre comunque quasi tutta la zona,
 * e in piu' la copre **in mezzo** — dove sta cio' che si sta indicando — invece
 * che in fondo. Sopra, quel che copre e' un bordo.
 */
export const FUORI = 0.5;

/** I lati, nell'ordine in cui si provano. Vedi la nota in testa al modulo. */
const ORDINE: Lato[] = ["destra", "sinistra", "sotto", "sopra"];

/**
 * Dove va la scheda, dato l'alone che deve spiegare.
 *
 * **La regola vera e' una sola: non coprire cio' che si sta indicando.** Da li'
 * i tre gradini.
 *
 * 1. Il primo lato dell'ordine in cui la scheda **ci sta per intero**. Non «il
 *    lato con piu' spazio» come fa `colloca` per le bolle: una bolla di tre
 *    parole sta quasi ovunque, una scheda con un titolo e due frasi no.
 * 2. Se non ci sta da nessuna parte, **il lato piu' capiente, accostata al
 *    bordo**, purche' ne resti fuori almeno la meta'. Sporge sulla zona di
 *    quello che manca, e copre un bordo invece che il mezzo.
 * 3. Solo se nemmeno quello, `dentro`, in basso.
 *
 * Il gradino 2 e' arrivato dopo, guardando il passo sulla colonna delle
 * risposte: quella zona e' alta quanto la finestra e larga quanto la misura di
 * lettura, quindi sopra e sotto non c'e' niente e ai fianchi ci sono trecento
 * pixel dove la scheda ne vuole trecentosessanta. Senza il gradino si finiva
 * `dentro`, cioe' con la spiegazione appoggiata sopra la cosa spiegata — che e'
 * il difetto che questo modulo esiste per non avere.
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

  /** Lo spazio libero da ogni lato, distanza e margine gia' tolti. */
  const spazio: Record<Lato, number> = {
    destra: finestra.larghezza - (zona.x + zona.larghezza) - DISTANZA - MARGINE,
    sinistra: zona.x - DISTANZA - MARGINE,
    sotto: finestra.altezza - (zona.y + zona.altezza) - DISTANZA - MARGINE,
    sopra: zona.y - DISTANZA - MARGINE,
    dentro: 0,
  };

  /** Quanto ne chiede la scheda su quell'asse. */
  const chiesto: Record<Lato, number> = {
    destra: scheda.larghezza,
    sinistra: scheda.larghezza,
    sotto: scheda.altezza,
    sopra: scheda.altezza,
    dentro: 0,
  };

  const intero = ORDINE.find((l) => spazio[l] >= chiesto[l]);
  const capiente = ORDINE.reduce((a, b) =>
    spazio[b] / chiesto[b] > spazio[a] / chiesto[a] ? b : a,
  );
  const lato =
    intero ?? (spazio[capiente] >= chiesto[capiente] * FUORI ? capiente : ("dentro" as Lato));

  // Ogni posizione e' **stretta alla finestra**: al gradino 1 lo stringimento non
  // fa niente — ci stava — e al gradino 2 e' proprio cio' che accosta la scheda
  // al bordo invece di lasciarla uscire.
  const aBordo = (v: number, misura: number, dentroChe: number) =>
    stringi(v, MARGINE, dentroChe - misura - MARGINE);

  switch (lato) {
    case "destra":
      return {
        x: aBordo(zona.x + zona.larghezza + DISTANZA, scheda.larghezza, finestra.larghezza),
        y: centroY,
        lato,
      };
    case "sinistra":
      return {
        x: aBordo(zona.x - DISTANZA - scheda.larghezza, scheda.larghezza, finestra.larghezza),
        y: centroY,
        lato,
      };
    case "sotto":
      return {
        x: centroX,
        y: aBordo(zona.y + zona.altezza + DISTANZA, scheda.altezza, finestra.altezza),
        lato,
      };
    case "sopra":
      return {
        x: centroX,
        y: aBordo(zona.y - DISTANZA - scheda.altezza, scheda.altezza, finestra.altezza),
        lato,
      };
    default:
      // Dentro, in basso: sopra ci sta cio' che l'alone indica, e coprirlo con
      // la spiegazione sarebbe indicare e nascondere nello stesso gesto.
      return {
        x: centroX,
        y: aBordo(
          zona.y + zona.altezza - scheda.altezza - MARGINE,
          scheda.altezza,
          finestra.altezza,
        ),
        lato: "dentro",
      };
  }
}
