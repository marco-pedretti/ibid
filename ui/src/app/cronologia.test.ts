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
import type { Conversazione, Deposito } from "./cronologia";

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
  it("niente, spazzatura e versione diversa danno tutti un elenco vuoto", () => {
    expect(deserializza(null)).toEqual([]);
    expect(deserializza("{ non json")).toEqual([]);
    expect(deserializza("42")).toEqual([]);
    expect(deserializza(JSON.stringify({ v: VERSIONE + 1, conversazioni: [conv("a", ["q"])] }))).toEqual([]);
  });

  it("un giro completo conserva fonti e verdetti", () => {
    const dopo = deserializza(serializza([conv("a", ["Qual è l'RMSE?"])]));
    const r = dopo[0].scambi[0].risposta;
    expect(r.fase).toBe("conclusa");
    expect(r.chunks[0].text).toBe(CHUNK.text);
    expect(r.citazioni[0].supported).toBe(true);
    expect(r.tempi.generation_s).toBe(3.01);
  });

  it("non ricorda quale conversazione era aperta: si riparte da una nuova", () => {
    // Il campo `corrente` c'era e non c'e' piu'. Un deposito piu' vecchio lo
    // porta ancora: viene ignorato, non fa scartare niente.
    expect(serializza([conv("a", ["q"])])).not.toContain("corrente");
    const vecchio = JSON.stringify({ v: VERSIONE, corrente: "b", conversazioni: [conv("b", ["q"])] });
    expect(deserializza(vecchio).map((c) => c.id)).toEqual(["b"]);
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
    const cs = [{ id: "a", dataset_id: null, scambi: [scambio("q", meta)] }];

    const r = deserializza(serializza(cs))[0].scambi[0].risposta;
    expect(r.fase).toBe("interrotta");
    expect(r.verificaInCorso).toBe(false);
    expect(r.testo).toBe("Il valore è 0.0");
    expect(r.chunks).toHaveLength(1);
  });

  it("una risposta conclusa non viene sigillata", () => {
    expect(deserializza(serializza([conv("a", ["q"])]))[0].scambi[0].risposta.fase).toBe("conclusa");
  });

  it("un campo che non c'era prende il suo default, uno col tipo sbagliato torna al default", () => {
    // Il primo caso e' quello che succede davvero: `Risposta` cresce a ogni task.
    // Il secondo e' un deposito modificato a mano, e non deve far cadere niente.
    const json = JSON.stringify({
      v: VERSIONE,
      conversazioni: [
        {
          id: "a",
          scambi: [{ id: "s", domanda: "q", risposta: { fase: "conclusa", testo: "x", chunks: "non un array" } }],
        },
      ],
    });

    const r = deserializza(json)[0].scambi[0].risposta;
    expect(r.chunks).toEqual([]);
    expect(r.senzaCitazione).toEqual([]);
    expect(r.tempi).toEqual({});
    expect(r.riparato).toBe(false);
    expect(r.testo).toBe("x");
  });

  it("scarta le conversazioni illeggibili e tiene le altre", () => {
    const json = JSON.stringify({
      v: VERSIONE,
      conversazioni: [{ id: 7 }, { id: "vuota", scambi: [] }, conv("b", ["q"])],
    });
    expect(deserializza(json).map((c) => c.id)).toEqual(["b"]);
  });

  it("la conversazione aperta, se vuota, non finisce nel deposito", () => {
    const dopo = deserializza(serializza([nuovaConversazione(), conv("a", ["q"])]));
    expect(dopo.map((c) => c.id)).toEqual(["a"]);
  });
});

describe("scrivere nel deposito", () => {
  it("scrive e rilegge", () => {
    const d = deposito();
    salvaCronologia([conv("a", ["q"])], d);
    expect(leggiCronologia(d)[0].scambi[0].domanda).toBe("q");
  });

  it("se non ci sta scrive meno conversazioni invece di nessuna", () => {
    const cs = [conv("a", ["q"]), conv("b", ["q"]), conv("c", ["q"])];
    // Un tetto che sta fra il costo di una conversazione e quello di tre.
    const tetto = serializza([conv("a", ["q"])]).length + 10;
    const d = deposito(tetto);
    salvaCronologia(cs, d);

    const letto = leggiCronologia(d);
    expect(letto.length).toBeGreaterThan(0);
    expect(letto.length).toBeLessThan(3);
    expect(letto[0].id).toBe("a");
  });

  it("senza niente da ricordare la chiave si toglie, invece di restare vecchia", () => {
    const d = deposito();
    salvaCronologia([conv("a", ["q"])], d);
    expect(d.dati.has(CHIAVE_CRONOLOGIA)).toBe(true);

    salvaCronologia([nuovaConversazione()], d);
    expect(d.dati.has(CHIAVE_CRONOLOGIA)).toBe(false);
  });

  it("un deposito negato non solleva: la sessione resta valida, solo non si ricorda", () => {
    expect(leggiCronologia(null)).toEqual([]);
    expect(() => salvaCronologia([conv("a", ["q"])], null)).not.toThrow();
  });

  it("un deposito che solleva in lettura da' un elenco vuoto invece di far cadere l'avvio", () => {
    const rotto: Deposito = {
      getItem: () => {
        throw new Error("SecurityError");
      },
      setItem: () => {},
      removeItem: () => {},
    };
    expect(leggiCronologia(rotto)).toEqual([]);
  });
});
