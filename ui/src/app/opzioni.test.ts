import { describe, expect, it } from "vitest";

import {
  COME_CONFIGURATO,
  PREDEFINITE,
  SFORZO,
  campiRichiesta,
  ragionamentoDisponibile,
} from "./opzioni";

const SFORZI = ["none", "low", "medium", "high", "max"];

describe("le opzioni della barra", () => {
  it("si parte col RAG acceso, il ragionamento spento e nessun modello scelto", () => {
    // Il secondo non e' pessimismo: C-07 ha misurato che acceso non conviene, e
    // un predefinito diverso consegnerebbe quella misura al contrario.
    expect(PREDEFINITE).toEqual({ rag: true, ragionamento: false, modello: COME_CONFIGURATO });
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
