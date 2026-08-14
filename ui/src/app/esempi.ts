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
 * **Si leggono nella lingua dell'interfaccia, partono in quella del corpus**, e
 * i due testi stanno uno sopra l'altro apposta. Tradurre anche cio' che parte
 * sarebbe comodo e sbagliato: con un corpus inglese, una domanda in italiano
 * produce una risposta italiana le cui citazioni puntano a chunk inglesi, e il
 * verificatore NLI di C-03 dovrebbe giudicare un'implicazione **cross-lingua**
 * che non ha mai misurato in quella condizione. La precisione di citazione e' la
 * prima affermazione del §0: non si baratta con una comodita' di presentazione.
 *
 * La riga in mono sotto la traduzione e' la query vera. Sta in mono perche' nel
 * §12 il mono e' il ruolo dei **dati**, e quella e' letteralmente cio' che
 * finisce sul filo — si vede prima di cliccare, invece di scoprirlo dopo nella
 * propria domanda.
 */
import type { Chiave, Lingua } from "../i18n/strings";

export interface Esempio {
  /** Cio' che finisce nel campo: **lingua del corpus**, sempre. */
  query: string;
  /** Come si legge, per lingua dell'interfaccia. In `en` coincide con `query`. */
  testo: Record<Lingua, string>;
  /** Cosa guardare quando risponde. Chiave di traduzione, non testo. */
  nota: Chiave;
}

export const ESEMPI: Record<string, Esempio[]> = {
  open_ragbench: [
    {
      query: "How does the MLMM approach affect the analysis of Root Mean Squared Error (RMSE)?",
      testo: {
        it: "In che modo l'approccio MLMM cambia l'analisi del Root Mean Squared Error (RMSE)?",
        en: "How does the MLMM approach affect the analysis of Root Mean Squared Error (RMSE)?",
      },
      nota: "example.note.numbers",
    },
    {
      query: "What is the concept of location-class independence in object detection?",
      testo: {
        it: "Che cos'è l'indipendenza fra posizione e classe nel rilevamento di oggetti?",
        en: "What is the concept of location-class independence in object detection?",
      },
      nota: "example.note.paper",
    },
    {
      query: "Which university funded the 2019 replication study?",
      testo: {
        it: "Quale università ha finanziato lo studio di replica del 2019?",
        en: "Which university funded the 2019 replication study?",
      },
      nota: "example.note.absent",
    },
  ],
  ledger: [
    {
      query: "What was the capital expenditure of The Sherwin-Williams in 2017?",
      testo: {
        it: "Qual è stata la spesa in conto capitale di Sherwin-Williams nel 2017?",
        en: "What was the capital expenditure of The Sherwin-Williams in 2017?",
      },
      nota: "example.note.table",
    },
    {
      query: "What is the accounts receivable for Company The Sherwin-Williams in 2017?",
      testo: {
        it: "A quanto ammontavano i crediti verso clienti di Sherwin-Williams nel 2017?",
        en: "What is the accounts receivable for Company The Sherwin-Williams in 2017?",
      },
      nota: "example.note.numbers",
    },
    {
      query: "What was the operating margin of The Sherwin-Williams in 2024?",
      testo: {
        it: "Qual è stato il margine operativo di Sherwin-Williams nel 2024?",
        en: "What was the operating margin of The Sherwin-Williams in 2024?",
      },
      nota: "example.note.absent",
    },
  ],
};

/** Nessun esempio per un dataset che non ne ha: meglio uno stato vuoto sobrio
 *  che tre domande che non c'entrano col corpus scelto. */
export function esempiDi(dataset_id: string | null): Esempio[] {
  return dataset_id === null ? [] : (ESEMPI[dataset_id] ?? []);
}
