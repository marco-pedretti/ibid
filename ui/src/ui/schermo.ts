/**
 * Quando il telaio smette di essere fatto di colonne (U-21).
 *
 * **Il problema e' una somma, non un'impressione.** Le due colonne laterali
 * hanno una misura fissa — 200 px la corsia, 272 il pannello fonti — e quello
 * che resta va alla colonna di lavoro. Sotto una certa larghezza quella somma
 * lascia al lavoro meno di quanto ne ha un telefono, e a quel punto affiancare
 * non e' piu' impaginare: e' spartire.
 *
 * **La soglia si deriva, non si sceglie.** E' la larghezza sotto la quale la
 * colonna di lavoro riceverebbe meno di `TELEFONO`, cioe' meno di quanto ne
 * riceve sull'unico schermo su cui il criterio di U-21 si misura. Un numero
 * tondo preso a occhio — 768, 1024 — sarebbe la misura di un dispositivo di
 * qualcun altro; questa e' la misura delle colonne che questo progetto ha.
 *
 * **Due forme e non tre.** Un gradino in mezzo — corsia affiancata, fonti no —
 * si puo' immaginare, e costa un terzo posto in cui mettere il comando che apre
 * le fonti e un terzo insieme di stati da tenere giusti. Le larghezze che
 * riceverebbe sono proprio quelle in cui la colonna di lavoro e' gia' stretta,
 * ed e' li' che darle tutto lo schermo conviene di piu'. Chi vuole piu' spazio
 * da `larga` in giu' ha gia' la corsia che si comprime (U-18).
 *
 * **Non dipende dalla corsia chiusa**, che pure varrebbe 152 px. La forma del
 * telaio e' una proprieta' dello schermo, non di una preferenza: legarla alla
 * corsia vorrebbe dire che comprimendola compare una colonna di fonti — cioe'
 * che un comando ne fa due cose diverse a seconda della finestra.
 *
 * **Non dipende nemmeno dalla schermata.** La soglia conta il pannello fonti
 * anche dove non c'e' (l'esploratore, «Che cos'e'»): altrimenti la corsia si
 * ritirerebbe in un cassetto aprendo una schermata e tornerebbe chiudendola, e
 * il telaio e' l'unica cosa che in questa interfaccia non deve muoversi.
 */
import { APERTA, FIANCO, griglia } from "./corsia";

/**
 * La larghezza su cui il criterio si misura: 390 px, il telefono del §8.
 *
 * Sta qui come **misura minima della colonna di lavoro**, e non solo come
 * bersaglio della prova: sotto una certa larghezza il lavoro riceve meno di
 * quanto riceve su un telefono, e allora tanto vale dargli lo schermo intero.
 */
export const TELEFONO = 390;

/**
 * Sotto questa, niente colonne.
 *
 * E' anche, di fatto, il punto in cui le due unita' di misura di `scala.ts`
 * coincidono: il primo scalino dello `zoom` sta a 1.400 px e questa soglia gli
 * resta sotto, quindi confrontarla con una larghezza di finestra o con una di
 * disegno da' la stessa risposta. La conversione si fa lo stesso — la regola e'
 * «si converte al confine» — ma non c'e' un caso in cui dimenticarla cambi la
 * forma, e questo lo prova un test.
 */
export const SOGLIA = APERTA + TELEFONO + FIANCO;

/** Colonne affiancate, oppure una colonna sola con le altre due a un gesto. */
export type Forma = "larga" | "stretta";

export function forma(larghezza: number): Forma {
  return larghezza >= SOGLIA ? "larga" : "stretta";
}

/**
 * `grid-template-columns` del telaio, nella forma che ha adesso.
 *
 * A `stretta` la traccia e' una sola e non ha misura: le colonne laterali non
 * sono nascoste, **non ci sono** — la corsia e' un cassetto e le fonti un
 * foglio, tutti e due sopra il lavoro e non accanto. Una traccia lasciata li' a
 * larghezza zero sarebbe lo stesso difetto che `corsia.ts` evita chiudendo la
 * corsia a 48 px invece che a 0.
 *
 * `minmax(0,1fr)` e non `1fr`: la forma corta vale `minmax(auto, 1fr)`, e un
 * `auto` come minimo lascia che un contenuto largo — una tabella, una riga di
 * codice — spinga la traccia oltre lo schermo. E' lo stesso difetto delle righe
 * della griglia gia' pagato due volte qui dentro, sull'asse che U-21 misura.
 */
export function colonne(f: Forma, chiusa: boolean, fianco: boolean): string {
  return f === "stretta" ? "minmax(0,1fr)" : griglia(chiusa, fianco);
}
