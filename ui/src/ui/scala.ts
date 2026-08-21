/**
 * La scala della radice, e i due spazi di coordinate che apre.
 *
 * `index.css` mette uno `zoom` su `:root` per dire quanto e' grande il disegno.
 * Il prezzo e' che da quel momento in poi esistono **due unita' di misura**, e
 * il DOM le mescola senza dirlo. Misurato in Chromium e in Firefox, che
 * concordano su tutto:
 *
 * | cosa si legge | in che unita' |
 * |---|---|
 * | `clientWidth`, `offsetWidth` | px di **disegno** — quelli scritti nel CSS |
 * | `getBoundingClientRect()` | px di **finestra** — gia' moltiplicati per la scala |
 * | `window.innerWidth` / `innerHeight` | px di finestra |
 * | `PointerEvent.clientX` / `clientY` | px di finestra |
 * | una media query | px di finestra, e **non** risente dello zoom |
 * | `left`/`top`/`width` che si **scrivono** | px di disegno |
 *
 * L'ultima riga e' quella che fa i danni: un codice che misura con
 * `getBoundingClientRect()` e poi scrive il risultato in `left` sta convertendo
 * senza saperlo, e sbaglia esattamente di un fattore di scala. Con 1,45 una
 * bolla calcolata a 600 px finisce a 870.
 *
 * La regola qui e' una sola: **si converte al confine.** Tutto cio' che entra
 * dal DOM in px di finestra si divide per la scala una volta, e da li' in poi si
 * ragiona in px di disegno — cioe' negli stessi numeri che stanno nel CSS e nei
 * commenti.
 *
 * Che una media query **non** risenta dello zoom e' la seconda misura, ed e'
 * cio' che rende legittima la scala a scalini di `index.css`: se lo zoom
 * cambiasse la larghezza vista dalle media query, uno scalino cambierebbe lo
 * zoom che cambierebbe lo scalino, e il risultato oscillerebbe.
 */

/**
 * La scala scritta in una dichiarazione `zoom`, o 1 se non ce n'e' una valida.
 *
 * `getComputedStyle().zoom` restituisce `"1.2"` dove lo zoom c'e', e `"normal"`
 * o la stringa vuota dove la proprieta' non e' supportata. Tutto cio' che non e'
 * un numero positivo finito ricade su 1: una scala di zero o negativa non e'
 * «nessuno zoom», e' una divisione che manda le coordinate all'infinito.
 */
export function leggiScala(grezzo: string | null | undefined): number {
  const n = Number.parseFloat(grezzo ?? "");
  return Number.isFinite(n) && n > 0 ? n : 1;
}

/**
 * La scala in vigore adesso.
 *
 * Si legge dal documento invece di importare la costante: la costante sta nel
 * CSS, cambia con la larghezza della finestra (gli scalini di `index.css`), e
 * una copia in TypeScript sarebbe un secondo posto da tenere d'accordo — cioe'
 * il difetto che il progetto evita ovunque tenendo una misura sola.
 */
export function scala(): number {
  try {
    return leggiScala(getComputedStyle(document.documentElement).zoom);
  } catch {
    // Nessun documento (test in ambiente `node`): niente scala, niente
    // conversione.
    return 1;
  }
}
