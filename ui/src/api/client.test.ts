/**
 * Il client e' sottile, e la parte che vale la pena provare e' come **fallisce**.
 *
 * Un 422 di FastAPI porta il nome del campo rifiutato: e' esattamente
 * l'informazione per cui A-07 ha messo la validazione all'orlo invece di
 * lasciar rimbalzare un 400 del modello come 500. Appiattirla in «422
 * Unprocessable Entity» butterebbe via il motivo per cui esiste.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "./client";

function rispondi(status: number, corpo: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(corpo), { status })),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("errori", () => {
  it("mostra quale campo il server ha rifiutato", async () => {
    rispondi(422, {
      detail: [
        {
          loc: ["body", "reasoning_effort"],
          msg: "Value error, reasoning_effort sconosciuto: 'altissimo'",
        },
      ],
    });
    await expect(api.query({ query: "x" })).rejects.toThrow(/reasoning_effort: .*altissimo/);
  });

  it("porta lo stato accanto al messaggio", async () => {
    // 404 e 500 non si mostrano uguali: il primo e' un documento che non c'e',
    // il secondo un guasto del backend, e non c'e' ragione di riprovare da soli.
    rispondi(404, { detail: "documento non trovato: 'boh'" });
    const errore = await api.documentChunks("boh", "ledger").catch((e) => e);
    expect(errore).toBeInstanceOf(ApiError);
    expect(errore.status).toBe(404);
    expect(errore.detail).toContain("boh");
  });

  it("non finge un JSON quando il corpo non ne e' uno", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("<html>502</html>", { status: 502 })),
    );
    await expect(api.capabilities()).rejects.toBeInstanceOf(ApiError);
  });
});

describe("URL", () => {
  function spia(status = 200, corpo: unknown = {}) {
    const f = vi.fn(
      async (_url: string, _init?: RequestInit) => new Response(JSON.stringify(corpo), { status }),
    );
    vi.stubGlobal("fetch", f);
    return f;
  }

  it("omette i parametri che nessuno ha deciso", async () => {
    // `collection` assente significa «quella del dataset», che e' una decisione
    // del server. Mandare `collection=undefined` gliela toglierebbe di mano.
    const f = spia(200, { collection: "ledger", documents: [] });
    await api.documents("ledger");
    expect(f.mock.calls[0][0]).toBe("/api/documents?dataset_id=ledger");
  });

  it("passa `collection` quando c'e'", async () => {
    const f = spia(200, { collection: "ledger_routed", documents: [] });
    await api.documents("ledger", "ledger_routed");
    expect(f.mock.calls[0][0]).toContain("collection=ledger_routed");
  });

  it("non spezza un doc_id che contiene una barra", async () => {
    const f = spia(200, { collection: "c", doc_id: "a/b", chunks: [] });
    await api.documentChunks("a/b", "ledger");
    expect(f.mock.calls[0][0]).toContain("/document/a%2Fb/chunks");
  });
});
