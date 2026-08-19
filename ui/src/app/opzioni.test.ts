import { describe, expect, it } from "vitest";

import { PREDEFINITE, campiRichiesta } from "./opzioni";

describe("le opzioni della barra", () => {
  it("si parte con il RAG acceso: e' il modo in cui il progetto funziona", () => {
    expect(PREDEFINITE.rag).toBe(true);
  });

  it("il RAG parte sempre, anche quando coincide col default", () => {
    // Una richiesta che tace lascerebbe decidere al server una cosa che sullo
    // schermo appare gia' decisa, e `ConfigView` tornerebbe con un valore che
    // nessun controllo ha scelto.
    expect(campiRichiesta(PREDEFINITE)).toEqual({ rag: true });
    expect(campiRichiesta({ ...PREDEFINITE, rag: false })).toEqual({ rag: false });
  });
});
