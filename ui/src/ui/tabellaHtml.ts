/**
 * Le tabelle HTML dei documenti di `ledger`, lette da noi.
 *
 * **Perche' non `innerHTML`.** Il testo di un chunk non lo scriviamo noi: arriva
 * dal payload dell'indice, che arriva dall'OCR di un documento che arriva da
 * fuori. Darlo in pasto al browser come markup significherebbe fidarsi di quella
 * catena intera per sempre — e «il corpus e' nostro» e' precisamente il tipo di
 * premessa che invecchia male, perche' basta un dataset in piu' per renderla
 * falsa senza che nessuno se ne accorga. Qui si legge, si estrae del **testo**, e
 * la tabella la costruisce React con quel testo dentro: nessun percorso in cui
 * un tag del corpus diventi un tag della pagina.
 *
 * E' la stessa regola che `prompt.py` applica al modello — *«the UI does not
 * render markup it did not parse itself»* — dall'altro lato del filo.
 *
 * **Il sottoinsieme e' misurato, non indovinato.** Su 2.758 tabelle prese da 40
 * documenti di `ledger`, i tag che compaiono dentro una `<table>` sono **tre** —
 * `table`, `tr`, `td` — e gli attributi **due**: `colspan` (2.556 volte) e
 * `rowspan` (1.657). Nessun `<th>`, nessun `<br>`, niente di annidato. Il parser
 * copre quello e nient'altro; `<th>` e' accettato perche' costa una lettera
 * nell'espressione e perche' un OCR aggiornato potrebbe cominciare a produrlo.
 *
 * Tutto il resto **non viene parsato** e resta testo: una tabella mezza
 * riconosciuta e' peggio di una non riconosciuta, perche' nasconde le celle che
 * non ha capito.
 *
 * **Le celle unite restano unite**, e qui sta la differenza voluta con
 * `parse_html_table` in `src/ingestion/ocr_tables.py`. Quella le **espande**,
 * ripetendo il valore in ogni posizione occupata, perche' serve a *cercare*: una
 * intestazione che copre due colonne etichetta davvero entrambe. Questa le lascia
 * come sono e passa `colSpan`/`rowSpan` a React, perche' serve a *mostrare*, e a
 * mostrare ci pensa il browser. Due scopi, due semantiche — dichiarate, non
 * divergenti per caso.
 */

/** Una cella, col suo testo gia' ripulito dalle entita'. */
export interface Cella {
  testo: string;
  colspan: number;
  rowspan: number;
  /** `<th>`: intestazione dichiarata dal documento, non dedotta dalla posizione. */
  intestazione: boolean;
}

export type Pezzo =
  | { tipo: "testo"; da: number; a: number }
  | { tipo: "tabella"; da: number; a: number; righe: Cella[][] };

/** Le entita' che l'OCR produce davvero. Un elenco corto e chiuso: una tabella
 *  di duecento voci sarebbe la promessa di essere un parser HTML, che non siamo. */
const ENTITA: Record<string, string> = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  nbsp: " ",
};

/** `&amp;` → `&`, e i numerici. Quello che non si riconosce resta scritto:
 *  meglio un `&xyz;` a vista di un carattere inventato. */
export function testoSemplice(grezzo: string): string {
  return grezzo.replace(/&(#x?[0-9a-fA-F]+|[a-zA-Z]+);/g, (intero, corpo: string) => {
    if (corpo.startsWith("#")) {
      const n =
        corpo[1] === "x" || corpo[1] === "X"
          ? Number.parseInt(corpo.slice(2), 16)
          : Number.parseInt(corpo.slice(1), 10);
      return Number.isFinite(n) && n > 0 && n <= 0x10ffff ? String.fromCodePoint(n) : intero;
    }
    return ENTITA[corpo.toLowerCase()] ?? intero;
  });
}

const APRE_TABELLA = /<table[^>]*>/i;
const CHIUDE_TABELLA = "</table>";
/** Una cella: il tag d'apertura con i suoi attributi, poi il contenuto. */
const CELLA = /<(td|th)([^>]*)>([\s\S]*?)<\/\1\s*>/gi;
const RIGA = /<tr[^>]*>([\s\S]*?)<\/tr\s*>/gi;
const SPAN = /\b(colspan|rowspan)\s*=\s*"?'?(\d{1,3})/gi;
/** Qualunque tag: dentro una cella puo' esserci `<br>` o del grassetto, e li'
 *  si butta il tag e si tiene il testo. */
const TAG = /<[^>]*>/g;

function attributi(grezzo: string): { colspan: number; rowspan: number } {
  const fuori = { colspan: 1, rowspan: 1 };
  for (const m of grezzo.matchAll(SPAN)) {
    const n = Number.parseInt(m[2], 10);
    // Uno span di zero o negativo non esiste; uno enorme e' un OCR sbagliato e
    // farebbe una tabella larga mille colonne. Si riporta dentro un limite
    // invece di scartare la cella, che sparirebbe senza dirlo.
    if (Number.isFinite(n) && n >= 1) {
      fuori[m[1].toLowerCase() as "colspan" | "rowspan"] = Math.min(n, 64);
    }
  }
  return fuori;
}

/** Le righe di una tabella, o `null` se dentro non c'e' niente di riconoscibile. */
function righeDi(html: string): Cella[][] | null {
  const righe: Cella[][] = [];
  for (const r of html.matchAll(RIGA)) {
    const celle: Cella[] = [];
    for (const c of r[1].matchAll(CELLA)) {
      celle.push({
        testo: testoSemplice(c[3].replace(TAG, " ")).replace(/\s+/g, " ").trim(),
        intestazione: c[1].toLowerCase() === "th",
        ...attributi(c[2]),
      });
    }
    if (celle.length > 0) righe.push(celle);
  }
  return righe.length > 0 ? righe : null;
}

/**
 * Il testo diviso in pezzi: prosa e tabelle, con gli offset del grezzo.
 *
 * Gli offset ci sono per la stessa ragione di `matematica.ts`: chi disegna la
 * prosa la passa a `analizza`, che lavora in coordinate del testo di partenza, e
 * senza `da` quel conto andrebbe rifatto sommando lunghezze.
 *
 * Una `<table>` senza chiusura resta **testo**, e non e' una rinuncia: un chunk
 * puo' finire a meta' di una tabella, perche' e' cosi' che e' stato spezzato.
 * Chiuderla noi vorrebbe dire disegnare una griglia che nel documento non
 * finisce li'.
 */
export function pezzi(testo: string): Pezzo[] {
  const fuori: Pezzo[] = [];
  const minuscolo = testo.toLowerCase();
  /** Da dove comincia il tratto di prosa non ancora emesso. */
  let daProsa = 0;
  let i = 0;

  while (i < testo.length) {
    const m = APRE_TABELLA.exec(testo.slice(i));
    if (m === null) break;

    const inizio = i + m.index;
    const chiusura = minuscolo.indexOf(CHIUDE_TABELLA, inizio);
    if (chiusura === -1) break;
    const fine = chiusura + CHIUDE_TABELLA.length;

    const righe = righeDi(testo.slice(inizio + m[0].length, chiusura));
    if (righe === null) {
      // `<table>` senza celle riconoscibili: resta prosa, e si riprende **dopo**
      // la sua chiusura. Fermarsi qui lascerebbe fuori le tabelle vere che
      // vengono dopo.
      i = fine;
      continue;
    }

    if (inizio > daProsa) fuori.push({ tipo: "testo", da: daProsa, a: inizio });
    fuori.push({ tipo: "tabella", da: inizio, a: fine, righe });
    daProsa = fine;
    i = fine;
  }

  if (daProsa < testo.length) fuori.push({ tipo: "testo", da: daProsa, a: testo.length });
  return fuori;
}
