/**
 * Le domande d'esempio dello stato vuoto.
 *
 * **Sono query d'oro vere**, prese da `eval/golden/*.jsonl`, non inventate: il
 * primo clic di chi prova il progetto non deve finire in un'astensione. Il terzo
 * esempio di ogni dataset invece e' fuori dal corpus **di proposito** — l'unico
 * modo di mostrare che il sistema si astiene e' fargli una domanda a cui non si
 * puo' rispondere, e nasconderla renderebbe la demo una pubblicita'.
 *
 * Sono per dataset perche' un corpus di paper e uno di bilanci non hanno
 * nessuna domanda in comune, e proporre a `ledger` una domanda su RMSE
 * mostrerebbe un'astensione dove il difetto e' della domanda.
 *
 * > **Vincolo su U-08.** Nel profilo `demo` l'indice contiene solo i chunk
 * > d'oro di ~30 query: se questi esempi non sono fra quelle, il primo clic di
 * > chi prova il progetto finisce in un'astensione. La lista qui e' il vincolo,
 * > non un suggerimento — U-08 deve includerle o cambiarle insieme a questa.
 *
 * Le domande restano in inglese perche' i corpus lo sono, ed e' la stessa
 * ragione per cui il selettore di lingua non tocca il testo del modello: far
 * rispondere in italiano su un corpus inglese significherebbe che le citazioni
 * sostengono un testo tradotto. La **nota** sotto ogni domanda e' cornice, e
 * quella si traduce.
 */
import type { Chiave } from "../i18n/strings";

export interface Esempio {
  /** Il testo della query, come finisce nel campo. */
  query: string;
  /** Cosa guardare quando risponde. Chiave di traduzione, non testo. */
  nota: Chiave;
}

export const ESEMPI: Record<string, Esempio[]> = {
  open_ragbench: [
    {
      query: "How does the MLMM approach affect the analysis of Root Mean Squared Error (RMSE)?",
      nota: "example.note.numbers",
    },
    {
      query: "What is the concept of location-class independence in object detection?",
      nota: "example.note.paper",
    },
    {
      query: "Which university funded the 2019 replication study?",
      nota: "example.note.absent",
    },
  ],
  ledger: [
    {
      query: "What was the capital expenditure of The Sherwin-Williams in 2017?",
      nota: "example.note.table",
    },
    {
      query: "What is the accounts receivable for Company The Sherwin-Williams in 2017?",
      nota: "example.note.numbers",
    },
    {
      query: "What was the operating margin of The Sherwin-Williams in 2024?",
      nota: "example.note.absent",
    },
  ],
};

/** Nessun esempio per un dataset che non ne ha: meglio uno stato vuoto sobrio
 *  che tre domande che non c'entrano col corpus scelto. */
export function esempiDi(dataset_id: string | null): Esempio[] {
  return dataset_id === null ? [] : (ESEMPI[dataset_id] ?? []);
}
