/**
 * L'avvio guidato: cosa dice, dove si e' arrivati, e quando non si mostra piu'.
 *
 * **Ogni passo indica una zona che si vede**, e la indica davvero: l'alone e il
 * velo stanno in `ui/Avvio.tsx`, qui ci sono i passi e la memoria. Non e' un
 * elenco di funzionalita': l'ordine e' quello in cui le cose compaiono guardando
 * una risposta nascere. L'ultimo dice dove sta la spiegazione che **resta** — la
 * pagina «Che cos'e'» di U-19 — ed e' il motivo per cui questa non torna: una
 * guida che si ripresenta a chi l'ha gia' letta e' un difetto, una pagina che si
 * apre quando si vuole no.
 *
 * **Si legge tenendola aperta.** Il criterio chiede che non impedisca di fare la
 * prima domanda, e non e' una concessione: i primi due passi hanno qualcosa da
 * mostrare solo **durante** una risposta — le fonti che arrivano prima del testo,
 * i verdetti che compaiono dopo. Una guida che si chiudesse alla prima domanda si
 * toglierebbe di mezzo nell'unico momento in cui serviva.
 *
 * **Si ricorda il passo, non solo che e' finita.** Costa lo stesso e paga due
 * volte: la guida sopravvive a un ricaricamento senza ricominciare da capo, e
 * soprattutto sopravvive all'andare a vedere «Che cos'e'» o l'esploratore, che
 * smontano la colonna della chat e con lei qualunque stato tenuto in React.
 * Arrivare al passo 3, aprire la pagina che il passo 4 nomina e ritrovarsi al
 * passo 1 sarebbe la guida che punisce chi le da' retta.
 *
 * **Chi questo browser lo ha gia' usato non la vede affatto.** La chiave nel
 * deposito e' nuova, quindi senza questa regola il primo avvio dopo U-20
 * accoglierebbe con un tour chi sta usando la demo da settimane. Una cronologia
 * non vuota e' la prova che la prima volta e' gia' passata: vale come una
 * guida saltata, perche' lo e'.
 */
import type { Chiave } from "../i18n/strings";

/** Un passo: un titolo, una frase, e il glifo di cio' di cui parla — che sta in
 *  `Avvio.tsx`, perche' e' l'unica parte di questo modulo che e' un disegno. */
export interface Passo {
  id: "fonti" | "verdetti" | "barra" | "corpus" | "resta";
  titolo: Chiave;
  testo: Chiave;
}

/**
 * I cinque, nell'ordine in cui le cose compaiono sullo schermo.
 *
 * Prima cio' che si vede mentre una risposta nasce — le fonti, poi i verdetti —
 * e subito dopo **con che cosa e' nata**: la barra sotto il campo, che e' anche
 * il solo posto da cui si cambia qualcosa. Poi il limite dentro cui vale tutto
 * quanto, il corpus. Ultimo il rimando alla pagina che resta.
 *
 * Un passo in piu' costa un clic e vale il posto solo se indica qualcosa che si
 * vede: e' la ragione per cui il confronto affiancato non ne ha uno. Quel
 * comando compare **dentro una risposta**, e al primo avvio di risposte non ce
 * n'e' nessuna: un alone attorno al vuoto, o attorno a una zona che comparira'
 * dopo, sarebbe la guida che indica una cosa che non c'e'.
 */
export const PASSI: readonly Passo[] = [
  { id: "fonti", titolo: "start.sources.title", testo: "start.sources" },
  { id: "verdetti", titolo: "start.verdicts.title", testo: "start.verdicts" },
  { id: "barra", titolo: "start.bar.title", testo: "start.bar" },
  { id: "corpus", titolo: "start.corpus.title", testo: "start.corpus" },
  { id: "resta", titolo: "start.rest.title", testo: "start.rest" },
];

/** Cio' che si scrive quando la guida e' finita: una parola, non un booleano
 *  serializzato, perche' e' cio' che si legge negli strumenti del browser senza
 *  doverlo interpretare. */
const FATTA = "fatto";

/**
 * Il passo da mostrare rileggendo il deposito, o `null` se la guida e' finita.
 *
 * Qualunque cosa di storto — un valore scritto a mano, un indice di una
 * versione con piu' passi, il JSON di un'altra chiave — ricade sul **primo
 * passo** e non su «finita». E' il verso sicuro qui, ed e' l'opposto di quello
 * di `corsia.ts`: li' il caso da proteggere e' non perdere una colonna, qui e'
 * non perdere la spiegazione a chi non l'ha mai vista. Costa un giro di guida
 * gia' letta a chi si e' rovinato il deposito; l'altro verso costa la prima
 * volta a tutti quelli a cui e' andata storta.
 */
export function leggi(grezzo: string | null): number | null {
  if (grezzo === FATTA) return null;

  const n = Number(grezzo);
  if (!Number.isInteger(n) || n < 0 || n >= PASSI.length) return 0;
  return n;
}

/** Cio' che si scrive nel deposito per un passo, o per la fine. L'inverso di
 *  `leggi`, e i due si provano insieme: un giro completo deve tornare uguale. */
export function scrivi(passo: number | null): string {
  return passo === null ? FATTA : String(passo);
}

/**
 * Il passo con cui si parte, la prima volta che l'applicazione si disegna.
 *
 * `usata` e' «in questo browser c'e' gia' una conversazione»: quando il
 * deposito non dice niente e' l'unica prova disponibile che la prima volta e'
 * passata, e vale come una guida saltata. Se invece il deposito dice qualcosa,
 * comanda lui — chi ha ripreso la guida dopo aver chiesto qualcosa non se la
 * vede sparire alla ricarica.
 */
export function primoPasso(grezzo: string | null, usata: boolean): number | null {
  if (grezzo === null) return usata ? null : 0;
  return leggi(grezzo);
}

/** Il passo dopo, o `null` quando non ce n'e' un altro: l'ultimo «Avanti»
 *  chiude la guida come la chiude «Salta», e per lo stesso deposito. */
export function avanti(passo: number): number | null {
  return passo + 1 < PASSI.length ? passo + 1 : null;
}
