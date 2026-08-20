import { describe, expect, it } from "vitest";

import { chunkIniziale, filtra, indirizzo } from "./corpus";
import type { ChunkView, DocumentView } from "../api/types";

const doc = (doc_id: string, n_chunks = 10): DocumentView => ({ doc_id, n_chunks });

const chunk = (chunk_id: string): ChunkView => ({
  marker: 0,
  score: 0,
  chunk_id,
  dataset_id: "ledger",
  doc_id: "NYSE_SHW_2017",
  doc_genre: "table_heavy",
  pipeline: "generic",
  section_path: "",
  page: 0,
  bbox: null,
  content_type: "text",
  text: "",
  source_uri: "ledger:NYSE:SHW:2017",
});

describe("trovare un documento fra 494", () => {
  const elenco = [doc("NYSE_SHW_2017"), doc("NYSE_SHW_2019"), doc("NASDAQ_AAPL_2022")];

  it("un pezzo qualunque del nome, senza maiuscole", () => {
    // I nomi sono `NYSE_SHW_2017` e chi cerca scrive `shw`, o `2017`, che sta
    // in fondo: un confronto sull'inizio non troverebbe ne' l'uno ne' l'altro.
    expect(filtra(elenco, "shw").map((d) => d.doc_id)).toEqual(["NYSE_SHW_2017", "NYSE_SHW_2019"]);
    expect(filtra(elenco, "2022").map((d) => d.doc_id)).toEqual(["NASDAQ_AAPL_2022"]);
  });

  it("una ricerca vuota vuol dire tutti, non nessuno", () => {
    // Un campo che si svuota riporta all'elenco intero: il verso opposto
    // lascerebbe uno schermo bianco dopo aver cancellato una lettera.
    expect(filtra(elenco, "")).toHaveLength(3);
    expect(filtra(elenco, "   ")).toHaveLength(3);
  });

  it("nessuna corrispondenza e' un elenco vuoto, non l'elenco intero", () => {
    expect(filtra(elenco, "zzz")).toEqual([]);
  });
});

describe("su quale chunk si apre un documento", () => {
  const chunks = [chunk("a:1"), chunk("a:2"), chunk("a:3")];

  it("su quello citato, se si arriva da una citazione", () => {
    expect(chunkIniziale(chunks, "a:2")).toBe("a:2");
  });

  it("sul primo, se non e' stato chiesto niente", () => {
    // Dall'elenco non c'e' un chunk chiesto: aprirsi su niente mostrerebbe una
    // mappa senza tessera scelta e la colonna di destra vuota.
    expect(chunkIniziale(chunks, null)).toBe("a:1");
  });

  it("sul primo anche se il chunk chiesto in questo documento non c'e'", () => {
    expect(chunkIniziale(chunks, "b:9")).toBe("a:1");
  });

  it("su niente se il documento non ha chunk", () => {
    expect(chunkIniziale([], "a:1")).toBeNull();
  });
});

describe("quando «apri la fonte» ha una destinazione", () => {
  it("su open_ragbench si', ed e' l'articolo", () => {
    expect(indirizzo("https://arxiv.org/abs/2401.07294")).toBe("https://arxiv.org/abs/2401.07294");
  });

  it("su ledger no: e' un identificatore, non un posto", () => {
    // `ledger:NYSE:SHW:2017` e' sintatticamente un URI con schema `ledger:`, e
    // un controllo ingenuo lo accetterebbe dando un comando che non porta da
    // nessuna parte.
    expect(indirizzo("ledger:NYSE:SHW:2017")).toBeNull();
  });

  it("solo http e https", () => {
    // `source_uri` arriva dal payload dell'indice e non lo scriviamo noi: uno
    // schema qualunque dentro un `href` e' il modo in cui `javascript:` finisce
    // sotto un clic.
    expect(indirizzo("javascript:alert(1)")).toBeNull();
    expect(indirizzo("file:///etc/passwd")).toBeNull();
    expect(indirizzo("http://example.org/x")).toBe("http://example.org/x");
  });

  it("una stringa che non e' un URI non fa esplodere niente", () => {
    expect(indirizzo("")).toBeNull();
    expect(indirizzo("non un uri")).toBeNull();
  });
});
