import { describe, expect, it } from "vitest";

import type { ModelView } from "../api/types";
import { conModello, finestraDi, modelli, modelloDi } from "./catalogo";

function voce(p: Partial<ModelView> & { name: string }): ModelView {
  return {
    family: "gemma4",
    context_max: 131072,
    context: null,
    parent: "",
    quantization: "Q4_K_M",
    parameter_size: "",
    ...p,
  };
}

const BASE = voce({ name: "gemma4:e2b" });
const OTTO = voce({ name: "gemma4-8k", parent: "gemma4:e2b", context: 8192 });
const TRENTADUE = voce({ name: "gemma4-32k", parent: "gemma4:e2b", context: 32768 });

describe("il catalogo diventa due scelte", () => {
  it("le taglie stanno sotto il modello da cui derivano", () => {
    const e = modelli([BASE, TRENTADUE, OTTO]);
    expect(e).toHaveLength(1);
    expect(e[0].nome).toBe("gemma4:e2b");
    expect(e[0].finestre.map((f) => f.token)).toEqual([null, 8192, 32768]);
  });

  it("il raggruppamento non interpreta i nomi", () => {
    // `parent` lo dice il motore. Dedurlo spezzando una stringa sarebbe una
    // convenzione, e si romperebbe con un nome scelto diversamente.
    const strano = voce({ name: "taglia-corta", parent: "gemma4:e2b", context: 4096 });
    expect(modelli([BASE, strano])[0].finestre.map((f) => f.modello)).toEqual([
      "gemma4:e2b",
      "taglia-corta",
    ]);
  });

  it("«decide il motore» viene per prima: e' il punto di partenza", () => {
    expect(modelli([OTTO, BASE])[0].finestre[0]).toEqual({ token: null, modello: "gemma4:e2b" });
  });

  it("due modelli restano due voci, anche della stessa famiglia", () => {
    // `gemma4:e2b` e `gemma4:12b` hanno la stessa `family`: raggruppare per
    // famiglia li avrebbe fusi in uno.
    const dodici = voce({ name: "gemma4:12b", context_max: 262144 });
    expect(modelli([BASE, dodici]).map((m) => m.nome)).toEqual(["gemma4:e2b", "gemma4:12b"]);
  });

  it("una taglia orfana resta un modello a se'", () => {
    // Il genitore non e' nel catalogo: appenderla a un gruppo che non esiste la
    // farebbe sparire dal menu.
    const orfana = voce({ name: "roba-vecchia", parent: "sparito", context: 8192 });
    expect(modelli([orfana]).map((m) => m.nome)).toEqual(["roba-vecchia"]);
  });
});

describe("una taglia si offre solo se il modello la regge", () => {
  it("oltre il massimo dell'architettura non compare", () => {
    // Il massimo non e' uno solo -- misurato, 131.072 contro 262.144 -- quindi
    // non esiste una lista di taglie valida per tutti. Una taglia che compare e
    // poi fallisce fa scoprire il limite dopo l'attesa, e come un errore.
    const enorme = voce({ name: "gemma4-256k", parent: "gemma4:e2b", context: 262144 });
    expect(modelli([BASE, OTTO, enorme])[0].finestre.map((f) => f.token)).toEqual([null, 8192]);
  });

  it("senza un massimo noto si offre tutto", () => {
    // Nascondere per un limite che il motore non ha dichiarato sarebbe
    // inventare un vincolo.
    const ignoto = voce({ name: "mistral", context_max: null, family: "" });
    const grande = voce({ name: "mistral-256k", parent: "mistral", context: 262144 });
    expect(modelli([ignoto, grande])[0].finestre).toHaveLength(2);
  });
});

describe("cambiare una scelta sola", () => {
  const DODICI = voce({ name: "gemma4:12b", context_max: 262144 });
  const DODICI_32 = voce({ name: "g12-32k", parent: "gemma4:12b", context: 32768 });
  const elenco = modelli([BASE, OTTO, TRENTADUE, DODICI, DODICI_32]);

  it("cambiando modello si tiene la finestra piu' vicina", () => {
    // Chi confronta due modelli sulla stessa domanda sta cambiando **una** cosa:
    // cambiargliene due sotto le mani e' il §15 rotto dentro un menu.
    expect(conModello(elenco, "gemma4:12b", "gemma4-32k")).toBe("g12-32k");
  });

  it("se la finestra di prima non c'e', si prende la piu' vicina che c'e'", () => {
    expect(conModello(elenco, "gemma4:12b", "gemma4-8k")).toBe("gemma4:12b");
  });

  it("un modello che non e' nel catalogo si manda com'e'", () => {
    expect(conModello(elenco, "mai-visto", "gemma4-8k")).toBe("mai-visto");
  });

  it("da un nome si risale al modello e alla sua finestra", () => {
    expect(modelloDi(elenco, "gemma4-32k")?.nome).toBe("gemma4:e2b");
    expect(finestraDi(elenco, "gemma4-32k")?.token).toBe(32768);
    expect(modelloDi(elenco, "mai-visto")).toBeNull();
  });
});
