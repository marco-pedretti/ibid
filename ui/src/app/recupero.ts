/**
 * Cosa vuol dire il punteggio di una fonte, che dipende da come e' stata trovata.
 *
 * Il numero in alto a destra di una scheda **non e' una grandezza sola**, ed e'
 * facile crederlo perche' sta sempre nello stesso posto:
 *
 * | configurazione | cos'e' quel numero |
 * |---|---|
 * | `dense` | somiglianza cosinusoidale fra la domanda e il chunk, fra 0 e 1 |
 * | `sparse` | punteggio BM25: peso dei termini della domanda in questo chunk |
 * | `hybrid` | punteggio RRF, cioe' una somma di **reciproci di posizione** — piccolo per costruzione, e non confrontabile con una somiglianza |
 * | `--rerank` | punteggio del cross-encoder, che sovrascrive i precedenti e non e' limitato a `[0, 1]` |
 *
 * Un'unica etichetta «punteggio» sarebbe vera e inutile: 0,875 in `dense` e 0,016
 * in `hybrid` sono due fonti ottime, e chi legge senza saperlo conclude che la
 * seconda sia scadente. Ed e' esattamente il tipo di confronto che §15 vieta —
 * due numeri si confrontano solo se differiscono in una cosa sola.
 *
 * **La configurazione la manda l'API** (`ConfigView`, sull'evento `done`), quindi
 * qui non vive nessuna costante del backend: si legge il valore e si sceglie la
 * frase. Un modo di recupero nuovo lato server ricade sulla frase generica invece
 * di rompere niente — `Capabilities.retrieval_modes` e' `string[]` per la stessa
 * ragione.
 */
import type { ConfigView } from "../api/types";
import type { Chiave } from "../i18n/strings";

export function spiegaPunteggio(config: ConfigView | null): Chiave {
  // Prima di `done` la configurazione non e' arrivata. Non si indovina il default
  // del server: sarebbe una costante del backend scritta nel frontend, cioe' cio'
  // che U-00 vieta, e sbagliata proprio nelle run in cui si cambia qualcosa.
  if (config === null) return "score.retrieval.unknown";
  // Il reranker gira **per ultimo** e sostituisce il punteggio, quindi vince sul
  // modo di recupero: dirlo al contrario descriverebbe uno stadio che c'e' stato
  // ma che quel numero non porta piu'.
  if (config.rerank) return "score.retrieval.rerank";
  switch (config.retrieval_mode) {
    case "dense":
      return "score.retrieval.dense";
    case "sparse":
      return "score.retrieval.sparse";
    case "hybrid":
      return "score.retrieval.hybrid";
    default:
      return "score.retrieval.unknown";
  }
}
