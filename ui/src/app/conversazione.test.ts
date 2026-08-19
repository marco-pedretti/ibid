import { describe, expect, it } from "vitest";

import type { ChunkView, ConfigView, SseEvent } from "../api/types";
import { ABSTENTION } from "../api/types";
import { applica, chiSiEAstenuto, guasto, inCorso, inizio, interrompi } from "./conversazione";
import type { Risposta } from "./conversazione";

const CHUNK: ChunkView = {
  marker: 1,
  score: 0.71,
  chunk_id: "open_ragbench:doc-1:0",
  dataset_id: "open_ragbench",
  doc_id: "doc-1",
  doc_genre: "paper",
  pipeline: "structured_hierarchical",
  section_path: "4. Results",
  page: 7,
  bbox: null,
  content_type: "text",
  text: "The standard deviation of RMSE for Ridge Regression is 0.0226.",
  source_uri: "https://example.org/doc-1",
};

const CONFIG = { top_k: 5, retrieval_mode: "hybrid" } as unknown as ConfigView;

function risolvi(eventi: SseEvent[], da: Risposta = inizio()): Risposta {
  return eventi.reduce(applica, da);
}

const chunks: SseEvent = { event: "chunks", data: { chunks: [CHUNK] } };
const token = (text: string): SseEvent => ({ event: "token", data: { text } });
const answer = (
  over: Partial<{
    text: string;
    repaired: boolean;
    abstained: boolean;
    abstention: string;
    truncated: boolean;
    verification_pending: boolean;
  }> = {},
): SseEvent => ({
  event: "answer",
  data: {
    text: "Il valore è 0.0226 [1].",
    raw_text: "Il valore è 0.0226 [1].",
    repaired: false,
    abstained: false,
    abstention: ABSTENTION.nessuna,
    truncated: false,
    verification_pending: true,
    ...over,
  },
});
const done = (over: Partial<{ abstention: string; verified: boolean }> = {}): SseEvent => ({
  event: "done",
  data: {
    abstained: false,
    abstention: ABSTENTION.nessuna,
    verified: true,
    timings: { retrieval: 0.02, generation: 11.4, verification: 0.83 },
    config: CONFIG,
    ...over,
  },
});

describe("l'ordine del §3.5", () => {
  it("le fonti arrivano prima del primo token", () => {
    // E' la proprieta' su cui poggia U-02: il pannello fonti si apre mentre il
    // modello sta ancora scrivendo, non a risposta finita.
    const r = risolvi([chunks]);
    expect(r.fase).toBe("fonti");
    expect(r.chunks).toHaveLength(1);
    expect(r.testo).toBe("");
  });

  it("i token si accumulano", () => {
    const r = risolvi([chunks, token("Il valore "), token("è 0.0226")]);
    expect(r.fase).toBe("scrittura");
    expect(r.testo).toBe("Il valore è 0.0226");
    expect(r.definitivo).toBe(false);
  });

  it("`answer` sostituisce il testo, non lo continua", () => {
    // Durante lo stream si accumula il grezzo; `answer` porta il testo dopo la
    // riparazione dei marcatori, ed e' quello che si deve leggere.
    const r = risolvi([token("Il valore è 0.0226 [1"), answer({ repaired: true })]);
    expect(r.testo).toBe("Il valore è 0.0226 [1].");
    expect(r.definitivo).toBe(true);
    expect(r.riparato).toBe(true);
  });

  it("un token in ritardo dopo `answer` viene ignorato", () => {
    // Si vede solo con una rete lenta: appenderlo scriverebbe in coda a una
    // risposta gia' chiusa.
    const r = risolvi([answer(), token(" spazzatura")]);
    expect(r.testo).toBe("Il valore è 0.0226 [1].");
  });

  it("`done` porta tempi e configurazione", () => {
    const r = risolvi([chunks, token("x"), answer(), done()]);
    expect(r.fase).toBe("conclusa");
    expect(r.tempi.generation).toBe(11.4);
    expect(r.config).toBe(CONFIG);
    expect(inCorso(r)).toBe(false);
  });
});

describe("la verifica", () => {
  it("dopo `answer` il testo c'è e i verdetti no", () => {
    const r = risolvi([answer()]);
    expect(r.verificaInCorso).toBe(true);
    expect(r.citazioni).toEqual([]);
    expect(r.verificate).toBe(false);
  });

  it("`citations` chiude l'attesa e porta anche le frasi non citate", () => {
    const r = risolvi([
      answer(),
      {
        event: "citations",
        data: {
          citations: [
            {
              marker: 1,
              chunk_id: CHUNK.chunk_id,
              claim: "Il valore è 0.0226.",
              supported: true,
              score: 0.94,
              numeric: "ok",
            },
          ],
          uncited_claims: ["Questa frase non cita niente."],
        },
      },
    ]);
    expect(r.verificaInCorso).toBe(false);
    expect(r.citazioni).toHaveLength(1);
    expect(r.senzaCitazione).toEqual(["Questa frase non cita niente."]);
  });

  it("«nessuna citazione» e «verdetti non disponibili» non sono lo stesso stato", () => {
    // Senza `verificate` sarebbero la stessa lista vuota, e U-07 chiede di
    // distinguere una citazione non verificata da una verificata.
    const senzaVerifica = risolvi([
      answer({ verification_pending: false }),
      done({ verified: false }),
    ]);
    expect(senzaVerifica.citazioni).toEqual([]);
    expect(senzaVerifica.verificate).toBe(false);

    const verificata = risolvi([
      answer(),
      { event: "citations", data: { citations: [], uncited_claims: [] } },
      done(),
    ]);
    expect(verificata.citazioni).toEqual([]);
    expect(verificata.verificate).toBe(true);
  });
});

describe("le due astensioni", () => {
  it("il gate si astiene prima di generare, e non c'è nessun token", () => {
    const r = risolvi([
      chunks,
      answer({ abstained: true, abstention: ABSTENTION.gate, verification_pending: false }),
      done({ abstention: ABSTENTION.gate }),
    ]);
    expect(chiSiEAstenuto(r)).toBe("gate");
    expect(r.chunks).toHaveLength(1);
  });

  it("il modello si astiene dopo aver letto le fonti", () => {
    const r = risolvi([
      chunks,
      token("Insufficient"),
      answer({ abstained: true, abstention: ABSTENTION.modello }),
      done({ abstention: ABSTENTION.modello }),
    ]);
    expect(chiSiEAstenuto(r)).toBe("modello");
  });

  it("una risposta normale non è un'astensione", () => {
    expect(chiSiEAstenuto(risolvi([answer(), done()]))).toBeNull();
  });
});

describe("cio' che va storto", () => {
  it("un `error` tiene il parziale", () => {
    const r = risolvi([
      chunks,
      token("Il valore "),
      { event: "error", data: { message: "il modello non risponde", stage: "generation" } },
    ]);
    expect(r.fase).toBe("errore");
    expect(r.testo).toBe("Il valore ");
    expect(r.chunks).toHaveLength(1);
    expect(r.errore?.stage).toBe("generation");
  });

  it("uno stream caduto senza `error` si dichiara tale", () => {
    // Il server non ha detto **cosa** e' andato storto: `stage` non lo inventa.
    const r = guasto(risolvi([chunks, token("Il ")]), "network error");
    expect(r.fase).toBe("errore");
    expect(r.errore).toEqual({ message: "network error", stage: "trasporto" });
    expect(r.testo).toBe("Il ");
  });

  it("«Ferma» non è un guasto", () => {
    const r = interrompi(risolvi([chunks, token("Il valore ")]));
    expect(r.fase).toBe("interrotta");
    expect(r.errore).toBeNull();
    expect(r.testo).toBe("Il valore ");
  });

  it("«Ferma» su una risposta già conclusa non la tocca", () => {
    // Il pulsante sparisce, ma un clic partito un istante prima non deve
    // marcare come interrotta una risposta completa.
    const conclusa = risolvi([answer(), done()]);
    expect(interrompi(conclusa)).toBe(conclusa);
  });

  it("`inCorso` è vero finché non si è in uno stato terminale", () => {
    expect(inCorso(inizio())).toBe(true);
    expect(inCorso(risolvi([chunks]))).toBe(true);
    expect(inCorso(risolvi([answer()]))).toBe(true);
    expect(inCorso(risolvi([answer(), done()]))).toBe(false);
    expect(inCorso(interrompi(inizio()))).toBe(false);
  });
});
