/**
 * Come un documento e' stato riconosciuto, e come e' stato tagliato.
 *
 * Sono le due meta' della decisione di routing (R-06): il profilatore assegna un
 * **genere** guardando il documento, e il genere sceglie la **pipeline** che lo
 * spezza. U-05 chiede di renderla visibile, e visibile vuol dire tutte e due —
 * una pipeline da sola non dice in base a cosa e' stata scelta.
 *
 * **I due vocabolari non sono lo stesso vocabolario**, anche se due parole
 * coincidono. `table_heavy` come genere vuol dire «questo documento e' fatto di
 * tabelle»; `table_heavy` come pipeline vuol dire «e' stato spezzato tenendo le
 * tabelle intere». Che il routing mandi il primo sulla seconda e' la decisione,
 * non un'identita': su `open_ragbench` un documento `table_heavy` finisce su
 * `continuous_text`, perche' li' le tabelle sono Markdown e non HTML. Due mappe
 * separate, quindi, e non una condivisa.
 *
 * **`generic` non e' un dato mancante.** E' il termine di paragone di R-07: si
 * prende l'unita' che il documento offre gia' — una pagina, una sezione — e non
 * si applica nessuna pipeline. Fino a U-05 il campo diceva il nome di una
 * pipeline che non aveva girato; ora dice la verita', ed e' l'unica ragione per
 * cui questa targhetta puo' esistere.
 *
 * Un valore che non conosciamo si mostra **com'e'**, senza spiegazione: e' la
 * stessa regola dei modelli fuori catalogo in U-16. Inventare una traduzione per
 * un genere aggiunto domani direbbe una cosa che nessuno ha verificato.
 */
import type { Chiave } from "../i18n/strings";

/** Il genere assegnato dal profilatore → come si legge. */
const GENERI: Record<string, Chiave> = {
  academic_pdf: "source.genre.paper",
  table_heavy: "source.genre.tables",
  continuous_text: "source.genre.prose",
};

/** La pipeline che ha spezzato il documento → come si legge. */
const TAGLI: Record<string, Chiave> = {
  generic: "source.cut.generic",
  structured_hierarchical: "source.cut.sections",
  table_heavy: "source.cut.tables",
  continuous_text: "source.cut.paragraphs",
};

export function nomeGenere(genere: string): Chiave | null {
  return GENERI[genere] ?? null;
}

export function nomeTaglio(pipeline: string): Chiave | null {
  return TAGLI[pipeline] ?? null;
}

/**
 * Il taglio e' stato **scelto in base al genere**?
 *
 * E' la domanda che la targhetta esiste per rispondere, ed e' un si'/no e non un
 * nome: col routing spento ogni documento riceve lo stesso taglio, quindi cio'
 * che si vede non e' *quale* pipeline ma *se* ne ha girata una.
 *
 * Stringa vuota compresa fra i no: un chunk indicizzato prima che il campo
 * esistesse non porta niente, e «non lo so» non e' «e' stata scelta».
 */
export function taglioPerGenere(pipeline: string): boolean {
  return pipeline !== "" && pipeline !== "generic";
}
