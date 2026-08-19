import { describe, expect, it } from "vitest";

import type { ConfigView } from "../api/types";
import {
  AVANZATE_INTATTE,
  COME_CONFIGURATO,
  PREDEFINITE,
  avanzateToccate,
  SFORZO,
  campiRichiesta,
  ragionamentoDisponibile,
  stessaConfigurazione,
} from "./opzioni";

const SFORZI = ["none", "low", "medium", "high", "max"];

const CONFIG: ConfigView = {
  top_k: 5,
  retrieval_mode: "hybrid",
  rerank: true,
  query_rewrite: false,
  filter_content_type: "",
  search_exact: false,
  hnsw_ef: 128,
  model: "gemma4:e4b",
  temperature: 0,
  max_new_tokens: 2048,
  reasoning_effort: "none",
  rag: true,
  baseline_prompt: "strict",
  verify: true,
};

describe("le opzioni della barra", () => {
  it("si parte col RAG acceso, il ragionamento spento e niente scelto a mano", () => {
    // Il secondo non e' pessimismo: C-07 ha misurato che acceso non conviene, e
    // un predefinito diverso consegnerebbe quella misura al contrario.
    expect(PREDEFINITE).toEqual({
      rag: true,
      ragionamento: false,
      modello: COME_CONFIGURATO,
      avanzate: AVANZATE_INTATTE,
    });
    expect(avanzateToccate(AVANZATE_INTATTE)).toBe(false);
  });

  it("le avanzate mandano solo cio' che si tocca", () => {
    // Riempirle coi default del servizio e' impossibile — non li conosciamo — e
    // riempirle con dei numeri qualsiasi scriverebbe sopra la configurazione del
    // deployment dei valori che nessuno ha deciso.
    expect(campiRichiesta(PREDEFINITE)).not.toHaveProperty("top_k");
    expect(campiRichiesta(PREDEFINITE)).not.toHaveProperty("rerank");

    const toccate = { ...AVANZATE_INTATTE, top_k: 12, rerank: false };
    expect(avanzateToccate(toccate)).toBe(true);
    const campi = campiRichiesta({ ...PREDEFINITE, avanzate: toccate });
    expect(campi.top_k).toBe(12);
    expect(campi.rerank).toBe(false);
    expect(campi).not.toHaveProperty("hnsw_ef");
  });

  it("ogni campo parte sempre, anche quando coincide col default", () => {
    // Una richiesta che tace lascerebbe decidere al server una cosa che sullo
    // schermo appare gia' decisa, e `ConfigView` tornerebbe con un valore che
    // nessun controllo ha scelto.
    expect(campiRichiesta(PREDEFINITE)).toEqual({ rag: true, reasoning_effort: "none" });
    expect(campiRichiesta({ ...PREDEFINITE, rag: false, ragionamento: true })).toEqual({
      rag: false,
      reasoning_effort: "high",
    });
  });

  it("il modello e' l'eccezione: scelto parte, «come configurato» tace", () => {
    // Tacere e' l'unico modo di dire il vero: il frontend non sa quale modello
    // il servizio userebbe, e mandarne uno smentirebbe la parola sullo schermo.
    expect(campiRichiesta(PREDEFINITE)).not.toHaveProperty("model");
    expect(campiRichiesta({ ...PREDEFINITE, modello: "gemma4:e4b" }).model).toBe("gemma4:e4b");
  });

  it("i due capi dell'asse sono quelli che C-07 ha misurato", () => {
    expect([SFORZO.spento, SFORZO.acceso]).toEqual(["none", "high"]);
  });

  it("senza tutti e due i capi il controllo sparisce invece di mandare un 422", () => {
    expect(ragionamentoDisponibile(SFORZI)).toBe(true);
    expect(ragionamentoDisponibile(["none", "low"])).toBe(false);
    expect(ragionamentoDisponibile([])).toBe(false);
  });
});

describe("il confronto riparte da cio' che ha girato", () => {
  it("copia ogni campo della configurazione, e il test lo conta", () => {
    // E' la rete: un campo aggiunto a `ConfigView` e non aggiunto li' uscirebbe
    // dal confronto **in silenzio**, cioe' diventerebbe la seconda variabile che
    // `stessaConfigurazione` esiste per impedire (§15).
    expect(Object.keys(stessaConfigurazione(CONFIG)).sort()).toEqual(Object.keys(CONFIG).sort());
    expect(stessaConfigurazione(CONFIG)).toEqual(CONFIG);
  });

  it("invertire il RAG cambia una cosa sola", () => {
    const rilancio = { ...stessaConfigurazione(CONFIG), rag: !CONFIG.rag };
    const diversi = Object.keys(CONFIG).filter(
      (k) => rilancio[k as keyof ConfigView] !== CONFIG[k as keyof ConfigView],
    );
    expect(diversi).toEqual(["rag"]);
  });
});
