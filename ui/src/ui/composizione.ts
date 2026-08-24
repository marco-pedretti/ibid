/**
 * Da un testo con tutto cio' che gli sta sopra a **una lista di pezzi**, e
 * nessun nodo React in mezzo.
 *
 * E' la meta' di U-14 che non si poteva provare (D-8). Le tre parti che
 * compongono una risposta hanno ognuna i propri test — `markdown.ts` gli
 * intervalli di enfasi e sintassi, `matematica.ts` il taglio fra prosa e TeX,
 * `verdetti.ts` quale verdetto tocca a quale occorrenza — ma il **loro
 * incrocio** viveva dentro `Testo.tsx`, cioe' in funzioni che restituiscono
 * JSX, e `ui/` non ha jsdom per scelta di U-00. Il risultato era che le tre
 * decisioni piu' delicate del modulo si verificavano guardando lo schermo.
 *
 * Qui non si disegna niente: si dice **quali pezzi**, in che ordine, con che
 * veste. E' la stessa mossa di `dettagli.ts`, che dice quali campi e in che
 * gruppi senza sapere che aspetto avranno — e per la stessa ragione: e' la
 * parte che si puo' sbagliare **senza che si veda**.
 *
 * Le tre decisioni, che ora sono provabili:
 *
 * 1. **La matematica ha la precedenza.** `segmenta` taglia per primo, e le
 *    annotazioni entrano dentro i suoi pezzi di prosa. Al contrario, un
 *    `$x[3]$` — un indice fra quadre dentro una formula, che in un corpus di
 *    paper esiste — verrebbe spezzato a meta' e la formula non si comporrebbe
 *    piu'. Un errore di matematica rompe il disegno; un marcatore mancato resta
 *    leggibile.
 * 2. **Gli intervalli si ritagliano, non si scartano.** Una frase scoperta che
 *    contiene una formula sta a cavallo di due segmenti: scartarla la
 *    lascerebbe senza sottolineatura proprio nella meta' che si legge.
 * 3. **I caratteri di sintassi spariscono qui**, all'ultimo passo, e non in
 *    `analizza`: toglierli prima sposterebbe gli offset di ogni altro
 *    intervallo, ed e' la ragione d'essere di `markdown.ts`.
 *
 * Ogni pezzo porta il proprio `da`, cioe' dov'era nel testo grezzo. Serve a chi
 * disegna come chiave stabile, e serve a un test per dire *dove* invece che
 * soltanto *cosa*.
 */
import type { Risposta } from "../app/conversazione";
import { marcatoriDelTesto, spanSenzaCitazione } from "../app/verdetti";
import type { Marcato, Span } from "../app/verdetti";
import { stiliIn, visibili } from "./markdown";
import type { Blocco, Nascosto, Stile } from "./markdown";
import { segmenta } from "./matematica";

/** Un tratto di testo che va disegnato diversamente. `marcato: null` = una
 *  frase che non cita niente. */
export interface Annotazione extends Span {
  marcato: Marcato | null;
}

/** Cio' che sta sopra al testo grezzo: i quattro elenchi di intervalli. */
export interface Contesto {
  testo: string;
  annotazioni: readonly Annotazione[];
  stili: readonly Stile[];
  nascosti: readonly Nascosto[];
}

/** La veste di un pezzo di prosa: `null` quando non ne ha nessuna. */
export type Veste = Stile["tipo"] | null;

/**
 * Un pezzo disegnabile.
 *
 * **Piatto e non annidato**, benche' il disegno annidi: un pezzo di prosa in
 * grassetto e sottolineato porta le due cose insieme invece di stare dentro due
 * involucri. Un albero renderebbe i test una descrizione della struttura HTML —
 * cioe' della cosa che il refactor di Q-07 ha il diritto di cambiare — mentre
 * questa lista descrive **cosa si legge e come**, che e' quello che non deve
 * cambiare.
 */
export type Pezzo =
  | { tipo: "testo"; testo: string; da: number; veste: Veste; scoperto: boolean }
  | { tipo: "marcatore"; marcato: Marcato; da: number; veste: Veste }
  | { tipo: "formula"; tex: string; da: number; blocco: boolean };

/**
 * Cosa va annotato sopra una risposta: i marcatori col loro verdetto, e le
 * frasi che non citano niente.
 *
 * **Senza fonti recuperate non c'e' niente da sottolineare.** «Questa frase non
 * cita nessuna fonte» e' un rilievo quando le fonti c'erano e la frase non le
 * ha usate; col RAG spento — e in un'astensione del gate — non ce n'era
 * nessuna, quindi la frase e' vera di ogni riga e non dice niente di nessuna.
 * Sottolineare tutta la colonna la fa anche sembrare *analizzata*, che e'
 * l'opposto di cio' che quella meta' del confronto merita: li' non c'e' un
 * verdetto piu' severo, non c'e' proprio niente da verificare, e a dirlo basta
 * l'avviso — una volta.
 *
 * Le due specie non si annidano mai: una frase «senza citazione» e' per
 * definizione una frase senza marcatori. Quindi una lista piatta, ordinata,
 * basta — e non serve un albero di intervalli.
 */
export function annotazioni(risposta: Risposta): Annotazione[] {
  const marcati = marcatoriDelTesto(risposta);
  const scoperte = risposta.chunks.length === 0 ? [] : spanSenzaCitazione(risposta);
  return [
    ...marcati.map((m): Annotazione => ({
      da: m.indice,
      a: m.indice + m.lunghezza,
      marcato: m,
    })),
    ...scoperte.map((s): Annotazione => ({ ...s, marcato: null })),
  ].sort((x, y) => x.da - y.da);
}

export type Gruppo = { tipo: "elenco" | "solo"; blocchi: Blocco[] };

/**
 * I blocchi raggruppati per il disegno.
 *
 * Serve solo a `<ul>`/`<ol>`: voci consecutive stanno in un elenco, e senza il
 * raggruppamento sarebbero N elenchi da una voce — che i lettori di schermo
 * annunciano uno per uno.
 */
export function raggruppa(blocchi: readonly Blocco[]): Gruppo[] {
  const fuori: Gruppo[] = [];
  for (const b of blocchi) {
    const ultimo = fuori[fuori.length - 1];
    if (b.tipo === "voce" && ultimo?.tipo === "elenco") ultimo.blocchi.push(b);
    else fuori.push({ tipo: b.tipo === "voce" ? "elenco" : "solo", blocchi: [b] });
  }
  return fuori;
}

/**
 * I pezzi di `[da, a)`: un blocco, una voce d'elenco, una cella di tabella.
 *
 * Chi chiama passa un intervallo del testo **grezzo** e riceve indietro cio'
 * che ci si legge dentro. Il resto del modulo e' questa funzione vista da
 * vicino.
 */
export function componi(da: number, a: number, contesto: Contesto): Pezzo[] {
  const grezzo = contesto.testo.slice(da, a);
  const fuori: Pezzo[] = [];

  // `segmenta` lavora sulla stringa che riceve, quindi i suoi `da` sono
  // relativi: si riportano sul grezzo sommando `da`. Meglio che aggiungere un
  // parametro a una funzione che ha gia' i suoi test e che qui non deve
  // cambiare.
  for (const s of segmenta(grezzo)) {
    if (s.tipo === "testo") fuori.push(...conVeste(s.valore, da + s.da, contesto));
    else fuori.push({ tipo: "formula", tex: s.tex, da: da + s.da, blocco: s.tipo === "blocco" });
  }
  return fuori;
}

/**
 * La prosa di un segmento: prima si tolgono i caratteri di sintassi, poi si
 * spezza per enfasi, e dentro ogni pezzo vanno marcatori e sottolineature.
 */
function conVeste(prosa: string, da: number, contesto: Contesto): Pezzo[] {
  const fine = da + prosa.length;
  const stili = stiliIn(contesto.stili, da, fine);

  // I confini che contano: inizio, fine, e ogni estremo di stile. Fra due
  // confini consecutivi lo stile e' uno solo, perche' `analizza` prende ogni
  // carattere una volta sola — quindi gli stili non si annidano e un taglio
  // secco basta. Con l'annidamento servirebbe un albero, e non e' il caso.
  const confini = [...new Set([da, fine, ...stili.flatMap((s) => [s.da, s.a])])].sort(
    (x, y) => x - y,
  );

  const fuori: Pezzo[] = [];
  for (let k = 0; k + 1 < confini.length; k += 1) {
    const [inizio, termine] = [confini[k], confini[k + 1]];
    const dentro = visibili(inizio, termine, contesto.nascosti).flatMap((v) =>
      annota(contesto.testo.slice(v.da, v.a), v.da, contesto.annotazioni),
    );
    if (dentro.length === 0) continue;

    const stile = stili.find((s) => s.da <= inizio && s.a >= termine);
    fuori.push(...(stile === undefined ? dentro : dentro.map((p) => vestito(p, stile.tipo))));
  }
  return fuori;
}

function vestito(p: Pezzo, veste: Veste): Pezzo {
  return p.tipo === "formula" ? p : { ...p, veste };
}

/**
 * La prosa visibile di un tratto, coi marcatori e le sottolineature al loro
 * posto.
 *
 * Gli intervalli si **ritagliano** sul tratto invece di essere scartati: una
 * frase scoperta che contiene una formula sta a cavallo di due segmenti, e
 * scartarla la lascerebbe senza sottolineatura proprio nella meta' che si
 * legge.
 */
function annota(prosa: string, da: number, elenco: readonly Annotazione[]): Pezzo[] {
  const fine = da + prosa.length;
  const pezzi: Pezzo[] = [];
  let i = da;

  for (const ann of elenco) {
    if (ann.a <= i || ann.da >= fine) continue;
    const inizio = Math.max(ann.da, i);
    const termine = Math.min(ann.a, fine);
    if (inizio > i) pezzi.push(nudo(prosa.slice(i - da, inizio - da), i));

    if (ann.marcato !== null) {
      pezzi.push({ tipo: "marcatore", marcato: ann.marcato, da: ann.da, veste: null });
    } else {
      pezzi.push({
        tipo: "testo",
        testo: prosa.slice(inizio - da, termine - da),
        da: inizio,
        veste: null,
        scoperto: true,
      });
    }
    i = termine;
  }

  if (i < fine) pezzi.push(nudo(prosa.slice(i - da), i));
  return pezzi;
}

function nudo(testo: string, da: number): Pezzo {
  return { tipo: "testo", testo, da, veste: null, scoperto: false };
}
