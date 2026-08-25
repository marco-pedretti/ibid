/**
 * Le domande d'esempio dello stato vuoto.
 *
 * **Sono query d'oro vere e — da D-17 — verificate.** La versione precedente si
 * fermava alla prima meta': *«sono prese da `eval/golden`, quindi il primo clic
 * di chi prova il progetto non finisce in un'astensione»*. La premessa era vera
 * e la conclusione no. Una query d'oro ha dei **qrels**, non la garanzia che il
 * recupero li trovi: su `ledger` solo il **35%** delle query d'oro porta il
 * proprio chunk nei primi cinque, e infatti uno degli esempi di allora — i
 * crediti verso clienti di Sherwin-Williams — non arrivava **affatto**. La demo
 * si asteneva su una domanda che proponeva lei.
 *
 * Adesso ogni esempio dichiara `atteso`, cioe' **cosa deve succedere**, e
 * `scripts/verify_esempi.py` lo controlla contro l'indice vero:
 *
 * ```
 * python scripts/verify_esempi.py                    # controlla questi
 * python scripts/verify_esempi.py --cerca ledger     # ne propone di nuovi
 * ```
 *
 * **Va rieseguito quando cambia l'indice, l'embedder o il default del
 * recupero** — e OQ-09 ha mostrato che l'indice puo' cambiare *da solo*, sotto
 * un task che non lo toccava.
 *
 * Il terzo esempio di ogni dataset e' fuori dal corpus **di proposito**: l'unico
 * modo di mostrare che il sistema si astiene e' fargli una domanda a cui non si
 * puo' rispondere, e nasconderla renderebbe la demo una pubblicita'.
 *
 * > **E deve chiudere il *gate*, non affidarsi al modello.** Le due astensioni
 * > non sono la stessa cosa: la soglia di C-04 e' una decisione presa in codice
 * > (§15), il rifiuto scritto dal modello e' una gentilezza che non si controlla
 * > — ed e' D-19. I «fuori corpus» di prima **non chiudevano il gate**: 0,8225
 * > contro una soglia di 0,7924 e 0,8417 contro 0,8289. La demo mostrava
 * > un'astensione vera per la ragione sbagliata.
 *
 * > **Su `ledger` non basta cambiare anno.** Misurato: quattro domande della
 * > forma *«stessa azienda, un anno che il corpus non ha»* passano tutte il gate
 * > (0,837–0,846 contro 0,8289). L'embedder non distingue il 2022 dal 2017 in un
 * > corpus di bilanci quasi identici. A chiudere il gate e' l'**azienda**
 * > assente, non l'anno — ed e' una proprieta' della soglia che vale la pena
 * > sapere prima di fidarsene.
 *
 * Sono per dataset perche' un corpus di paper e uno di bilanci non hanno
 * nessuna domanda in comune, e proporre a `ledger` una domanda su RMSE
 * mostrerebbe un'astensione dove il difetto e' della domanda.
 *
 * > **Vincolo su U-08.** Nel profilo `demo` l'indice contiene solo i chunk
 * > d'oro di ~30 query: se questi esempi non sono fra quelle, il primo clic di
 * > chi prova il progetto finisce in un'astensione. La lista qui e' il vincolo,
 * > non un suggerimento — U-08 deve includerle o cambiarle insieme a questa. I
 * > `chunk` dichiarati sotto sono esattamente cio' che quell'indice deve
 * > contenere.
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

/**
 * Cosa deve succedere quando si clicca. **Non lo legge l'interfaccia**: lo legge
 * `scripts/verify_esempi.py`, e sta qui perche' un'aspettativa scritta lontano
 * da cio' che descrive smette di corrispondere senza che nessuno se ne accorga.
 * Il tipo e' un'unione, quindi un esempio nuovo **non si puo' aggiungere** senza
 * dire quale dei due casi e'.
 */
export type Atteso =
  | {
      esito: "risponde";
      /** Il chunk d'oro che il recupero deve restituire. */
      chunk: string;
      /** In che posizione arriva, **uguale** in ricerca approssimata ed esatta. */
      posizione: number;
    }
  | {
      esito: "si astiene";
      /** Di quanto il punteggio sta **sotto** la soglia, nel peggiore dei due
       *  casi. Registrato per vedere il margine assottigliarsi prima che sparisca:
       *  lo script fallisce quando il gate si apre, questo numero avvisa prima. */
      margine: number;
    };

export interface Esempio {
  /** Cio' che finisce nel campo: **lingua del corpus**, sempre. */
  query: string;
  /** Come si legge, per lingua dell'interfaccia. In `en` coincide con `query`. */
  testo: Record<Lingua, string>;
  /** Cosa guardare quando risponde. Chiave di traduzione, non testo. */
  nota: Chiave;
  /** Cosa deve succedere. Verificato il 2026-08-23, `dense`, `top_k` 5. */
  atteso: Atteso;
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
      atteso: { esito: "risponde", chunk: "open_ragbench:2401.07294v4:12", posizione: 1 },
    },
    {
      query: "What is the concept of location-class independence in object detection?",
      testo: {
        it: "Che cos'è l'indipendenza fra posizione e classe nel rilevamento di oggetti?",
        en: "What is the concept of location-class independence in object detection?",
      },
      nota: "example.note.paper",
      atteso: { esito: "risponde", chunk: "open_ragbench:2410.11774v2:6", posizione: 1 },
    },
    {
      // Query d'oro **non rispondibile** di E-02 (`unanswerable_orb_cross_0004`):
      // una domanda di bilancio posta a un corpus di paper. E' quella con il
      // margine piu' largo fra le tredici che chiudono il gate, ed e' il motivo
      // per cui non si e' tenuta una domanda accademica inventata: le sette
      // provate stavano fra −0,025 e +0,007 dalla soglia, cioe' o passavano o
      // ci andavano cosi' vicino da non reggere il prossimo cambio d'indice.
      query:
        "How much of Allison Transmission Holdings's 2022 net income belongs to the parent company?",
      testo: {
        it: "Quanta parte dell'utile netto 2022 di Allison Transmission Holdings spetta alla capogruppo?",
        en: "How much of Allison Transmission Holdings's 2022 net income belongs to the parent company?",
      },
      nota: "example.note.absent",
      atteso: { esito: "si astiene", margine: 0.0227 },
    },
  ],
  ledger: [
    {
      query:
        "In year 2018, what did The Sherwin-Williams Company report for selling, general, and administrative expenses?",
      testo: {
        it: "Nel 2018, quanto ha riportato Sherwin-Williams per le spese generali, amministrative e di vendita?",
        en: "In year 2018, what did The Sherwin-Williams Company report for selling, general, and administrative expenses?",
      },
      nota: "example.note.table",
      atteso: { esito: "risponde", chunk: "ledger:NYSE_SHW_2019:0058", posizione: 1 },
    },
    {
      query: "Give me the dividend amount paid by The Sherwin-Williams in year 2017.",
      testo: {
        it: "Qual è l'importo dei dividendi pagati da Sherwin-Williams nel 2017?",
        en: "Give me the dividend amount paid by The Sherwin-Williams in year 2017.",
      },
      nota: "example.note.numbers",
      atteso: { esito: "risponde", chunk: "ledger:NYSE_SHW_2019:0062", posizione: 1 },
    },
    {
      // Stessa forma delle due sopra, e un'azienda che il corpus non ha: le 111
      // di `ledger` non comprendono Microsoft. **E' l'azienda a chiudere il
      // gate, non l'anno** — vedi la nota in cima.
      query: "What is the total revenue of Microsoft Corporation for fiscal year 2018?",
      testo: {
        it: "Qual è il ricavo totale di Microsoft Corporation per l'esercizio 2018?",
        en: "What is the total revenue of Microsoft Corporation for fiscal year 2018?",
      },
      nota: "example.note.absent",
      atteso: { esito: "si astiene", margine: 0.0078 },
    },
  ],
};

/** Nessun esempio per un dataset che non ne ha: meglio uno stato vuoto sobrio
 *  che tre domande che non c'entrano col corpus scelto. */
export function esempiDi(dataset_id: string | null): Esempio[] {
  return dataset_id === null ? [] : (ESEMPI[dataset_id] ?? []);
}
