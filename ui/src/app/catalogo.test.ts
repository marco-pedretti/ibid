import { describe, expect, it } from "vitest";

import type { ModelView } from "../api/types";
import {
  PREFERITA,
  comeTaglia,
  conModello,
  daNomi,
  finestraDi,
  modelli,
  modelloDi,
  risolvi,
} from "./catalogo";

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
    expect(e[0].finestre.map((f) => f.token)).toEqual([8192, 32768]);
  });

  it("il modello base non e' una finestra fra le altre", () => {
    // Non fissa `num_ctx`, quindi la sceglie il servizio e il numero non lo
    // sappiamo: in un menu di misure sarebbe l'unica voce che non e' una misura.
    expect(modelli([BASE, OTTO])[0].finestre.map((f) => f.modello)).toEqual(["gemma4-8k"]);
  });

  it("ma resta l'unica finestra quando non ce ne sono altre", () => {
    // Togliere anche lui lascerebbe un modello irraggiungibile, e li' non c'e'
    // comunque niente da scegliere.
    expect(modelli([BASE])[0].finestre).toEqual([{ token: null, modello: "gemma4:e2b" }]);
  });

  it("il raggruppamento non interpreta i nomi", () => {
    // `parent` lo dice il motore. Dedurlo spezzando una stringa sarebbe una
    // convenzione, e si romperebbe con un nome scelto diversamente.
    const strano = voce({ name: "taglia-corta", parent: "gemma4:e2b", context: 4096 });
    expect(modelli([BASE, strano])[0].finestre.map((f) => f.modello)).toEqual(["taglia-corta"]);
  });

  it("due modelli restano due voci, anche della stessa famiglia", () => {
    // `gemma4:e2b` e `gemma4:12b` hanno la stessa `family`: raggruppare per
    // famiglia li avrebbe fusi in uno.
    const dodici = voce({ name: "gemma4:12b", context_max: 262144 });
    expect(modelli([BASE, dodici]).map((m) => m.nome)).toEqual(["gemma4:e2b", "gemma4:12b"]);
  });

  it("dal nome del modello base si risolve la finestra di partenza", () => {
    // `/config` restituisce il modello base, che non e' una finestra: senza
    // risolverlo la barra si aprirebbe su un modello di cui nessuna taglia
    // risulta selezionata. Si parte da 32k, la finestra con cui si misura.
    const e = modelli([BASE, OTTO, TRENTADUE]);
    expect(risolvi(e, "gemma4:e2b")).toBe("gemma4-32k");
    expect(PREFERITA).toBe(32768);
  });

  it("senza 32k si prende la piu' vicina, non la piu' grande", () => {
    // La piu' grande sarebbe la piu' lenta, e chi apre la demo non ha chiesto
    // di aspettare.
    const sedici = voce({ name: "g-16k", parent: "gemma4:e2b", context: 16384 });
    const cento = voce({ name: "g-128k", parent: "gemma4:e2b", context: 131072 });
    expect(risolvi(modelli([BASE, sedici, cento]), "gemma4:e2b")).toBe("g-16k");
  });

  it("una taglia gia' scelta non viene risolta di nuovo", () => {
    expect(risolvi(modelli([BASE, OTTO, TRENTADUE]), "gemma4-8k")).toBe("gemma4-8k");
  });

  it("un nome che il catalogo non ha si lascia com'e'", () => {
    expect(risolvi(modelli([BASE, OTTO]), "mai-visto")).toBe("mai-visto");
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
    expect(modelli([BASE, OTTO, enorme])[0].finestre.map((f) => f.token)).toEqual([8192]);
  });

  it("senza un massimo noto si offre tutto", () => {
    // Nascondere per un limite che il motore non ha dichiarato sarebbe
    // inventare un vincolo.
    const ignoto = voce({ name: "mistral", context_max: null, family: "" });
    const grande = voce({ name: "mistral-256k", parent: "mistral", context: 262144 });
    expect(modelli([ignoto, grande])[0].finestre.map((f) => f.token)).toEqual([262144]);
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
    // `gemma4:12b` ha solo 32k: da 8k si finisce li', e non sul modello base --
    // che da U-16 non e' piu' una finestra scegliibile.
    expect(conModello(elenco, "gemma4:12b", "gemma4-8k")).toBe("g12-32k");
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

describe("senza catalogo si sceglie ancora il modello", () => {
  it("un nome diventa un modello con una finestra sola", () => {
    // `model_catalog` e' vuoto su un motore che non pubblica i dettagli e su un
    // server piu' vecchio di A-08: li' sparisce la scelta della finestra, non
    // quella del modello.
    const e = daNomi(["gemma4:e2b", "mistral"]);
    expect(e.map((m) => m.nome)).toEqual(["gemma4:e2b", "mistral"]);
    expect(e.every((m) => m.finestre.length === 1)).toBe(true);
    expect(e[0].finestre[0]).toEqual({ token: null, modello: "gemma4:e2b" });
  });
});

describe("come si legge una taglia", () => {
  it("in multipli di 1024, perche' e' cosi' che sono tagliate", () => {
    // 131.072 e' `128k`: chiamarlo `131k` sarebbe esatto e irriconoscibile.
    expect(comeTaglia(8192, "—")).toBe("8k");
    expect(comeTaglia(32768, "—")).toBe("32k");
    expect(comeTaglia(131072, "—")).toBe("128k");
    expect(comeTaglia(262144, "—")).toBe("256k");
  });

  it("sotto il migliaio si scrive il numero, e senza numero si ripiega", () => {
    // Il ripiego serve solo dove non c'e' una taglia da scrivere -- cioe' un
    // modello senza finestre derivate, dove non c'e' comunque niente da
    // scegliere: da U-16 il modello base non e' piu' una voce del menu.
    expect(comeTaglia(512, "—")).toBe("512");
    expect(comeTaglia(null, "Contesto")).toBe("Contesto");
  });

  it("una taglia non tonda non diventa un intero sbagliato", () => {
    expect(comeTaglia(6144, "—")).toBe("6k");
    expect(comeTaglia(10000, "—")).toBe("9.8k");
  });
});
