/**
 * Dove finisce la prosa e comincia la matematica.
 *
 * Serve perche' il corpus `open_ragbench` sono paper: su 2000 risposte di
 * riferimento ci sono **452 formule** fra `$…$`, piu' `\(…\)` e comandi LaTeX.
 * Senza questo, chi legge vede `$\frac{\partial \Im[\ln (\zeta(s)(s-1))]}
 * {\partial t}$` come testo — cioe' la risposta piu' interessante del corpus e'
 * anche l'unica illeggibile.
 *
 * **Il `$` e' ambiguo, e la regola e' stata misurata.** La tentazione e'
 * accettare `$…$` solo se contiene un comando LaTeX, cosi' da non scambiare due
 * prezzi per una formula. Misurato: delle 452 coppie, **125 (28%) non hanno
 * nessun segnale** — sono variabili singole, `$o$`, `$n$`, `$p(y, o, u)$`. Quella
 * regola butterebbe via un quarto della matematica vera.
 *
 * Si usa invece la regola «stretta» dei delimitatori, che e' quella con cui la
 * matematica viene scritta davvero:
 *
 * - niente spazio subito dopo l'apertura ne' subito prima della chiusura;
 * - la formula non attraversa una riga vuota;
 * - dopo la chiusura non c'e' una cifra.
 *
 * Le ultime due righe esistono per la valuta: `da $1,2 mln a $3,4 mln` ha uno
 * spazio prima della seconda `$` **e** una cifra subito dopo, quindi non e' una
 * formula. Su `ledger`, che e' il corpus dei bilanci, di coppie `$…$` ce ne sono
 * misurate **zero**: la regola non ha nemmeno occasione di sbagliare li'.
 *
 * `\(…\)` e `\[…\]` non sono ambigui e passano sempre.
 *
 * **Una formula incompleta resta testo**, e questa non e' una rinuncia: mentre i
 * token arrivano, `$\frac{a}` non ha ancora la sua chiusura. Trattarla come TeX
 * significherebbe disegnare un errore rosso per mezzo secondo a ogni formula che
 * si sta scrivendo.
 */

export type Segmento =
  | { tipo: "testo"; valore: string }
  | { tipo: "inline"; tex: string }
  | { tipo: "blocco"; tex: string };

interface Coppia {
  apre: string;
  chiude: string;
  tipo: "inline" | "blocco";
}

//: `$$` prima di `$`: l'ordine e' cio' che impedisce a `$$x$$` di essere letto
//: come una formula vuota seguita da testo.
const COPPIE: Coppia[] = [
  { apre: "$$", chiude: "$$", tipo: "blocco" },
  { apre: "\\[", chiude: "\\]", tipo: "blocco" },
  { apre: "\\(", chiude: "\\)", tipo: "inline" },
];

export function segmenta(testo: string): Segmento[] {
  const fuori: Segmento[] = [];
  let prosa = "";
  let i = 0;

  const chiudiProsa = () => {
    if (prosa !== "") fuori.push({ tipo: "testo", valore: prosa });
    prosa = "";
  };

  while (i < testo.length) {
    const coppia = COPPIE.find((c) => testo.startsWith(c.apre, i));
    if (coppia) {
      const fine = testo.indexOf(coppia.chiude, i + coppia.apre.length);
      if (fine !== -1) {
        chiudiProsa();
        fuori.push({ tipo: coppia.tipo, tex: testo.slice(i + coppia.apre.length, fine) });
        i = fine + coppia.chiude.length;
        continue;
      }
    }

    if (testo[i] === "$") {
      const fine = chiusuraDollaro(testo, i);
      if (fine !== -1) {
        chiudiProsa();
        fuori.push({ tipo: "inline", tex: testo.slice(i + 1, fine) });
        i = fine + 1;
        continue;
      }
    }

    prosa += testo[i];
    i += 1;
  }

  chiudiProsa();
  return fuori;
}

/** L'indice della `$` che chiude, o -1 se quella aperta non e' matematica. */
function chiusuraDollaro(testo: string, apertura: number): number {
  if (/\s/.test(testo[apertura + 1] ?? "")) return -1;

  for (let j = apertura + 1; j < testo.length; j += 1) {
    // Una riga vuota separa i paragrafi: una formula non ci passa attraverso, e
    // fermarsi qui evita che un `$` orfano si mangi meta' risposta.
    if (testo.startsWith("\n\n", j)) return -1;
    if (testo[j] !== "$") continue;

    const contenuto = testo.slice(apertura + 1, j);
    if (contenuto === "" || /\s$/.test(contenuto)) return -1;
    if (/[0-9]/.test(testo[j + 1] ?? "")) return -1; // `$3,4 mln`: valuta, non TeX
    return j;
  }
  return -1;
}
