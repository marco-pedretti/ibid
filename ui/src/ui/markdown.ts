/**
 * Il markdown come **intervalli sul testo grezzo**, non come testo riscritto.
 *
 * E' il vincolo che decide tutta la forma di questo file. I verdetti per frase e
 * le frasi scoperte arrivano dal backend come posizioni dentro cio' che il
 * modello ha scritto (`verdetti.ts`), e la matematica e' gia' segmentata sugli
 * stessi offset (`matematica.ts`). Un parser che restituisse una stringa
 * ripulita — senza asterischi, senza cancelletti — sposterebbe ogni indice a
 * valle del primo simbolo tolto, e la sottolineatura di «questa frase non cita
 * niente» finirebbe su un'altra frase. Sarebbe un errore invisibile in revisione
 * e sistematico in esecuzione.
 *
 * Quindi qui non si toglie niente: si dice **dove** c'e' enfasi, **dove** i
 * caratteri di sintassi vanno nascosti, e **come** il testo si divide in
 * blocchi. Chi disegna compone questi intervalli con quelli che ha gia'.
 *
 * **Un sottoinsieme, scelto e non ridotto per pigrizia.** Grassetto, corsivo,
 * codice in linea, titoli, elenchi e tabelle: sono le forme che i due corpora
 * contengono davvero (titoli nel 100% dei chunk di `open_ragbench` e nel 77% di
 * `ledger`, tabelle nel 39% di `ledger`) e quindi quelle che un modello che li
 * ha letti riproduce. Citazioni in blocco, immagini e link non ci sono: le prime
 * due nessuno le ha viste, e un link in una risposta senza fonti verificabili
 * sarebbe un riferimento che nessuno puo' controllare — l'opposto della tesi.
 *
 * **HTML mai**, coerente col prompt: cio' che arriva come tag resta testo. La UI
 * non disegna markup che non ha analizzato lei, e il 39% di `ledger` porta
 * tabelle HTML di Mathpix che il modello potrebbe riecheggiare.
 */

/** Un tratto con un'enfasi. Gli offset sono sul testo **grezzo**. */
export interface Stile {
  da: number;
  a: number;
  tipo: "forte" | "enfasi" | "codice";
}

/** Caratteri di sintassi: ci sono nel testo, non si disegnano. */
export interface Nascosto {
  da: number;
  a: number;
}

export type TipoBlocco = "paragrafo" | "titolo" | "voce" | "tabella";

export interface Blocco {
  tipo: TipoBlocco;
  da: number;
  a: number;
  /** 1–6 per un titolo. */
  livello?: number;
  /** `true` per una voce di elenco numerato. */
  numerata?: boolean;
  /** Per una tabella: le righe, e ogni riga le sue celle. La prima riga e'
   *  l'intestazione. Gli offset restano quelli del testo grezzo. */
  righe?: { da: number; a: number }[][];
}

export interface Analisi {
  blocchi: Blocco[];
  stili: Stile[];
  nascosti: Nascosto[];
}

/** `#` fino a sei, uno spazio, e il titolo. */
const TITOLO = /^(#{1,6})[ \t]+(.*)$/;
/** `-`, `*` o `+` seguiti da spazio; oppure `1.` / `1)`. */
const VOCE = /^[ \t]*(?:([-*+])|(\d{1,3})[.)])[ \t]+/;
/** La riga di separazione di una tabella: `|---|:--:|`. */
const SEPARATORE = /^[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(\|[ \t]*:?-{2,}:?[ \t]*)*\|?[ \t]*$/;

function haPipe(riga: string): boolean {
  return riga.includes("|");
}

/**
 * Divide in blocchi e trova enfasi e sintassi, tutto in coordinate del grezzo.
 *
 * Le righe si scorrono con il loro offset di partenza invece di usare `split`:
 * `split` perde le posizioni, ed e' precisamente cio' che non si puo' perdere.
 */
export function analizza(testo: string): Analisi {
  const blocchi: Blocco[] = [];
  const nascosti: Nascosto[] = [];

  const righe: { testo: string; da: number }[] = [];
  let i = 0;
  for (const r of testo.split("\n")) {
    righe.push({ testo: r, da: i });
    i += r.length + 1;
  }

  let n = 0;
  while (n < righe.length) {
    const riga = righe[n];

    if (riga.testo.trim() === "") {
      n += 1;
      continue;
    }

    const titolo = TITOLO.exec(riga.testo);
    if (titolo) {
      // I cancelletti e il loro spazio spariscono; il testo resta dov'e'.
      const salto = titolo[0].length - titolo[2].length;
      nascosti.push({ da: riga.da, a: riga.da + salto });
      blocchi.push({
        tipo: "titolo",
        livello: titolo[1].length,
        da: riga.da + salto,
        a: riga.da + riga.testo.length,
      });
      n += 1;
      continue;
    }

    const voce = VOCE.exec(riga.testo);
    if (voce) {
      nascosti.push({ da: riga.da, a: riga.da + voce[0].length });
      blocchi.push({
        tipo: "voce",
        numerata: voce[2] !== undefined,
        da: riga.da + voce[0].length,
        a: riga.da + riga.testo.length,
      });
      n += 1;
      continue;
    }

    // Una tabella e' **almeno** intestazione piu' separatore: senza la riga di
    // trattini due frasi che contengono un `|` diventerebbero una griglia.
    if (haPipe(riga.testo) && n + 1 < righe.length && SEPARATORE.test(righe[n + 1].testo)) {
      const righeTab: { da: number; a: number }[][] = [celle(riga)];
      nascosti.push({ da: righe[n + 1].da, a: righe[n + 1].da + righe[n + 1].testo.length });
      let m = n + 2;
      while (m < righe.length && haPipe(righe[m].testo) && righe[m].testo.trim() !== "") {
        righeTab.push(celle(righe[m]));
        m += 1;
      }
      blocchi.push({
        tipo: "tabella",
        da: riga.da,
        a: righe[m - 1].da + righe[m - 1].testo.length,
        righe: righeTab,
      });
      n = m;
      continue;
    }

    // Un paragrafo prende le righe fino alla prima vuota o al primo blocco di
    // altra specie: senza, un elenco attaccato a una frase sparirebbe dentro
    // il paragrafo che lo precede.
    let m = n;
    while (
      m < righe.length &&
      righe[m].testo.trim() !== "" &&
      !TITOLO.test(righe[m].testo) &&
      !(m > n && VOCE.test(righe[m].testo))
    ) {
      m += 1;
    }
    blocchi.push({
      tipo: "paragrafo",
      da: riga.da,
      a: righe[m - 1].da + righe[m - 1].testo.length,
    });
    n = m;
  }

  // `enfasi` aggiunge i propri caratteri di sintassi a `nascosti`, quindi si
  // chiama prima di unire: unire una lista che qualcuno sta ancora riempiendo e'
  // il genere di ordine implicito che si rompe alla prima riga aggiunta qui.
  const stili = enfasi(testo, nascosti);
  return { blocchi, stili, nascosti: unisci(nascosti) };
}

/** Le celle di una riga di tabella, senza le pipe. */
function celle(riga: { testo: string; da: number }): { da: number; a: number }[] {
  const fuori: { da: number; a: number }[] = [];
  let inizio = riga.da;
  const testo = riga.testo;

  for (let k = 0; k <= testo.length; k += 1) {
    if (k === testo.length || testo[k] === "|") {
      const cella = { da: inizio, a: riga.da + k };
      // Le pipe di bordo lasciano una cella vuota per lato: si scartano, ma solo
      // agli estremi — una cella vuota **in mezzo** e' un dato mancante, ed e'
      // un'informazione.
      const dentro = testo.slice(cella.da - riga.da, cella.a - riga.da);
      const bordo = (cella.da === riga.da || cella.a === riga.da + testo.length) && dentro.trim() === "";
      if (!bordo) fuori.push(ritaglia(testo, riga.da, cella));
      inizio = riga.da + k + 1;
    }
  }
  return fuori;
}

/** Toglie gli spazi ai bordi **spostando gli estremi**, non tagliando il testo. */
function ritaglia(
  testo: string,
  base: number,
  s: { da: number; a: number },
): { da: number; a: number } {
  let { da, a } = s;
  while (da < a && /\s/.test(testo[da - base])) da += 1;
  while (a > da && /\s/.test(testo[a - 1 - base])) a -= 1;
  return { da, a };
}

/**
 * Grassetto, corsivo e codice in linea.
 *
 * Il codice si cerca **per primo** e ciò che copre e' intoccabile: dentro
 * `` `a*b*c` `` gli asterischi sono codice, non corsivo, ed e' la sola regola di
 * precedenza che serve qui.
 *
 * `**` prima di `*` per la ragione ovvia, e l'underscore vale solo fra confini
 * di parola: `snake_case_name` non e' un corsivo, e in un corpus di paper e
 * bilanci gli identificatori con underscore ci sono davvero.
 */
function enfasi(testo: string, nascosti: Nascosto[]): Stile[] {
  const stili: Stile[] = [];
  const preso = new Array<boolean>(testo.length).fill(false);

  const libero = (da: number, a: number) => {
    for (let k = da; k < a; k += 1) if (preso[k]) return false;
    return true;
  };
  const prendi = (da: number, a: number) => {
    for (let k = da; k < a; k += 1) preso[k] = true;
  };

  const cerca = (re: RegExp, tipo: Stile["tipo"], apri: number) => {
    for (const m of testo.matchAll(re)) {
      const da = m.index;
      const a = da + m[0].length;
      if (!libero(da, a)) continue;
      prendi(da, a);
      stili.push({ da: da + apri, a: a - apri, tipo });
      nascosti.push({ da, a: da + apri }, { da: a - apri, a });
    }
  };

  cerca(/`([^`\n]+)`/g, "codice", 1);
  cerca(/\*\*([^\s*][^*]*?)\*\*/g, "forte", 2);
  cerca(/(?<![\w*])\*([^\s*][^*]*?)\*(?![\w*])/g, "enfasi", 1);
  cerca(/(?<![\w_])__([^\s_][^_]*?)__(?![\w_])/g, "forte", 2);
  cerca(/(?<![\w_])_([^\s_][^_]*?)_(?![\w_])/g, "enfasi", 1);

  return stili.sort((x, y) => x.da - y.da);
}

/** Gli intervalli nascosti, uniti e ordinati: chi disegna li salta e basta. */
export function unisci(n: readonly Nascosto[]): Nascosto[] {
  const ordinati = [...n].sort((x, y) => x.da - y.da);
  const fuori: Nascosto[] = [];
  for (const s of ordinati) {
    const ultimo = fuori[fuori.length - 1];
    if (ultimo !== undefined && s.da <= ultimo.a) ultimo.a = Math.max(ultimo.a, s.a);
    else fuori.push({ ...s });
  }
  return fuori;
}

/** Gli stili che toccano `[da, a)`, ritagliati su di lui. */
export function stiliIn(stili: readonly Stile[], da: number, a: number): Stile[] {
  return stili
    .filter((s) => s.a > da && s.da < a)
    .map((s) => ({ ...s, da: Math.max(s.da, da), a: Math.min(s.a, a) }))
    .sort((x, y) => x.da - y.da);
}
