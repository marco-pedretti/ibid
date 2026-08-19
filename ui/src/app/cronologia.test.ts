import { describe, expect, it } from "vitest";

import type { ChunkView } from "../api/types";
import { inizio } from "./conversazione";
import type { Risposta, Scambio } from "./conversazione";
import {
  CHIAVE_CRONOLOGIA,
  MASSIME,
  VERSIONE,
  conConversazione,
  daRicordare,
  deserializza,
  leggiCronologia,
  nuovaConversazione,
  salvaCronologia,
  serializza,
  titoloDi,
  trova,
  vuota,
} from "./cronologia";
import type { Conversazione, Deposito, Stato } from "./cronologia";

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

function conclusa(testo = "Il valore è 0.0226 [1]."): Risposta {
  return {
    ...inizio(),
    fase: "conclusa",
    chunks: [CHUNK],
    testo,
    definitivo: true,
    verificate: true,
    citazioni: [
      { marker: 1, chunk_id: CHUNK.chunk_id, claim: testo, supported: true, score: 0.9, numeric: "not_applicable" },
    ],
    tempi: { retrieval_s: 0.27, generation_s: 3.01 },
  };
}

function scambio(domanda: string, risposta: Risposta): Scambio {
  return { id: `s-${domanda}`, domanda, risposta };
}

function conv(id: string, domande: string[], dataset_id: string | null = "open_ragbench"): Conversazione {
  return { id, dataset_id, scambi: domande.map((d) => scambio(d, conclusa())) };
}

/** Un deposito in memoria che rifiuta oltre `tetto` caratteri, come fa
 *  `localStorage` quando l'origine e' piena. */
function deposito(tetto = Infinity): Deposito & { dati: Map<string, string> } {
  const dati = new Map<string, string>();
  return {
    dati,
    getItem: (k) => dati.get(k) ?? null,
    setItem: (k, v) => {
      if (v.length > tetto) throw new DOMException("quota", "QuotaExceededError");
      dati.set(k, v);
    },
    removeItem: (k) => void dati.delete(k),
  };
}

describe("cosa si ricorda", () => {
  it("una conversazione senza domande non si ricorda", () => {
    expect(vuota(nuovaConversazione())).toBe(true);
    expect(daRicordare([nuovaConversazione(), conv("a", ["q"])])).toHaveLength(1);
  });

  it("il titolo e' la prima domanda, e non e' salvato da nessuna parte", () => {
    expect(titoloDi(conv("a", ["prima", "seconda"]))).toBe("prima");
    expect(titoloDi(nuovaConversazione())).toBeNull();
  });

  it("oltre il tetto si tengono le piu' recenti, che stanno in testa", () => {
    const molte = Array.from({ length: MASSIME + 3 }, (_, i) => conv(`c${i}`, [`q${i}`]));
    const tenute = daRicordare(molte);
    expect(tenute).toHaveLength(MASSIME);
    expect(tenute[0].id).toBe("c0");
    expect(tenute.at(-1)?.id).toBe(`c${MASSIME - 1}`);
  });

  it("conConversazione tocca solo quella con l'id giusto", () => {
    const cs = [conv("a", ["q"]), conv("b", ["q"])];
    const dopo = conConversazione(cs, "b", (c) => ({ ...c, dataset_id: "ledger" }));
    expect(dopo[0]).toBe(cs[0]);
    expect(dopo[1].dataset_id).toBe("ledger");
    expect(trova(dopo, "b")?.dataset_id).toBe("ledger");
    expect(trova(dopo, "z")).toBeNull();
  });
});

describe("rileggere il deposito", () => {
  it("niente, spazzatura e versione diversa danno tutti `null`", () => {
    expect(deserializza(null)).toBeNull();
    expect(deserializza("{ non json")).toBeNull();
    expect(deserializza("42")).toBeNull();
    expect(deserializza(JSON.stringify({ v: VERSIONE + 1, conversazioni: [conv("a", ["q"])] }))).toBeNull();
  });

  it("un giro completo conserva fonti e verdetti", () => {
    const stato: Stato = { conversazioni: [conv("a", ["Qual è l'RMSE?"])], corrente: "a" };
    const dopo = deserializza(serializza(stato));
    expect(dopo?.corrente).toBe("a");
    const r = dopo?.conversazioni[0].scambi[0].risposta;
    expect(r?.fase).toBe("conclusa");
    expect(r?.chunks[0].text).toBe(CHUNK.text);
    expect(r?.citazioni[0].supported).toBe(true);
    expect(r?.tempi.generation_s).toBe(3.01);
  });

  it("una risposta rimasta a meta' torna sigillata, col parziale intatto", () => {
    // La scheda e' stata chiusa durante gli ~11 s: senza questo, al
    // ricaricamento il pallino pulserebbe per sempre.
    const meta: Risposta = {
      ...inizio(),
      fase: "scrittura",
      chunks: [CHUNK],
      testo: "Il valore è 0.0",
      verificaInCorso: true,
    };
    const stato: Stato = {
      conversazioni: [{ id: "a", dataset_id: null, scambi: [scambio("q", meta)] }],
      corrente: "a",
    };

    const r = deserializza(serializza(stato))?.conversazioni[0].scambi[0].risposta;
    expect(r?.fase).toBe("interrotta");
    expect(r?.verificaInCorso).toBe(false);
    expect(r?.testo).toBe("Il valore è 0.0");
    expect(r?.chunks).toHaveLength(1);
  });

  it("una risposta conclusa non viene sigillata", () => {
    const stato: Stato = { conversazioni: [conv("a", ["q"])], corrente: "a" };
    expect(deserializza(serializza(stato))?.conversazioni[0].scambi[0].risposta.fase).toBe("conclusa");
  });

  it("un campo che non c'era prende il suo default, uno col tipo sbagliato torna al default", () => {
    // Il primo caso e' quello che succede davvero: `Risposta` cresce a ogni task.
    // Il secondo e' un deposito modificato a mano, e non deve far cadere niente.
    const json = JSON.stringify({
      v: VERSIONE,
      corrente: "a",
      conversazioni: [
        {
          id: "a",
          scambi: [{ id: "s", domanda: "q", risposta: { fase: "conclusa", testo: "x", chunks: "non un array" } }],
        },
      ],
    });

    const r = deserializza(json)?.conversazioni[0].scambi[0].risposta;
    expect(r?.chunks).toEqual([]);
    expect(r?.senzaCitazione).toEqual([]);
    expect(r?.tempi).toEqual({});
    expect(r?.riparato).toBe(false);
    expect(r?.testo).toBe("x");
  });

  it("scarta le conversazioni illeggibili e tiene le altre", () => {
    const json = JSON.stringify({
      v: VERSIONE,
      corrente: "b",
      conversazioni: [{ id: 7 }, { id: "vuota", scambi: [] }, conv("b", ["q"])],
    });
    const dopo = deserializza(json);
    expect(dopo?.conversazioni.map((c) => c.id)).toEqual(["b"]);
    expect(dopo?.corrente).toBe("b");
  });

  it("se la corrente non c'e' piu' si riapre la piu' recente", () => {
    const stato: Stato = { conversazioni: [conv("a", ["q"]), conv("b", ["q"])], corrente: "sparita" };
    expect(deserializza(serializza(stato))?.corrente).toBe("a");
  });

  it("la corrente vuota non e' salvata, e al ritorno si riapre la prima con qualcosa dentro", () => {
    const nuova = nuovaConversazione();
    const stato: Stato = { conversazioni: [nuova, conv("a", ["q"])], corrente: nuova.id };
    const dopo = deserializza(serializza(stato));
    expect(dopo?.conversazioni.map((c) => c.id)).toEqual(["a"]);
    expect(dopo?.corrente).toBe("a");
  });
});

describe("scrivere nel deposito", () => {
  it("scrive e rilegge", () => {
    const d = deposito();
    const stato: Stato = { conversazioni: [conv("a", ["q"])], corrente: "a" };
    salvaCronologia(stato, d);
    expect(leggiCronologia(d)?.conversazioni[0].scambi[0].domanda).toBe("q");
  });

  it("se non ci sta scrive meno conversazioni invece di nessuna", () => {
    const stato: Stato = {
      conversazioni: [conv("a", ["q"]), conv("b", ["q"]), conv("c", ["q"])],
      corrente: "a",
    };
    // Un tetto che sta fra il costo di una conversazione e quello di tre.
    const tetto = serializza({ conversazioni: [conv("a", ["q"])], corrente: "a" }).length + 10;
    const d = deposito(tetto);
    salvaCronologia(stato, d);

    const letto = leggiCronologia(d);
    expect(letto?.conversazioni.length).toBeGreaterThan(0);
    expect(letto?.conversazioni.length).toBeLessThan(3);
    expect(letto?.conversazioni[0].id).toBe("a");
  });

  it("senza niente da ricordare la chiave si toglie, invece di restare vecchia", () => {
    const d = deposito();
    salvaCronologia({ conversazioni: [conv("a", ["q"])], corrente: "a" }, d);
    expect(d.dati.has(CHIAVE_CRONOLOGIA)).toBe(true);

    const nuova = nuovaConversazione();
    salvaCronologia({ conversazioni: [nuova], corrente: nuova.id }, d);
    expect(d.dati.has(CHIAVE_CRONOLOGIA)).toBe(false);
  });

  it("un deposito negato non solleva: la sessione resta valida, solo non si ricorda", () => {
    expect(leggiCronologia(null)).toBeNull();
    expect(() =>
      salvaCronologia({ conversazioni: [conv("a", ["q"])], corrente: "a" }, null),
    ).not.toThrow();
  });

  it("un deposito che solleva in lettura da' `null` invece di far cadere l'avvio", () => {
    const rotto: Deposito = {
      getItem: () => {
        throw new Error("SecurityError");
      },
      setItem: () => {},
      removeItem: () => {},
    };
    expect(leggiCronologia(rotto)).toBeNull();
  });
});
