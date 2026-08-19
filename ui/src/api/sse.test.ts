/**
 * Il parser SSE e' l'unico pezzo di trasporto scritto a mano nel progetto.
 *
 * Le prove che contano non sono «legge un evento»: sono i modi in cui la rete
 * consegna i byte. Un riquadro puo' arrivare spezzato a meta' riga, due possono
 * arrivare insieme, un carattere UTF-8 puo' essere tagliato fra due pacchetti.
 * Un parser che regge solo il caso pulito funziona in locale e si rompe appena
 * c'e' latenza vera — cioe' in demo.
 */
import { describe, expect, it, vi } from "vitest";

import { events, frames } from "./sse";

/** Uno stream che consegna i pezzi **esattamente** come sono scritti qui. */
function stream(...pezzi: (string | Uint8Array)[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const p of pezzi) {
        controller.enqueue(typeof p === "string" ? encoder.encode(p) : p);
      }
      controller.close();
    },
  });
}

async function raccogli<T>(gen: AsyncGenerator<T>): Promise<T[]> {
  const out: T[] = [];
  for await (const x of gen) out.push(x);
  return out;
}

describe("frames", () => {
  it("legge il formato che `sse()` produce davvero", async () => {
    // Byte per byte cio' che scrive `src/api/schema.py::sse`:
    // f"event: {nome}\ndata: {json}\n\n"
    const letti = await raccogli(frames(stream('event: token\ndata: {"text": "ciao"}\n\n')));
    expect(letti).toEqual([{ event: "token", data: '{"text": "ciao"}' }]);
  });

  it("ricompone un riquadro spezzato a meta' riga", async () => {
    const letti = await raccogli(frames(stream("event: tok", 'en\ndata: {"te', 'xt": "a"}\n\n')));
    expect(letti).toEqual([{ event: "token", data: '{"text": "a"}' }]);
  });

  it("estrae piu' riquadri arrivati nello stesso pacchetto", async () => {
    const letti = await raccogli(
      frames(stream('event: token\ndata: {"text":"a"}\n\nevent: token\ndata: {"text":"b"}\n\n')),
    );
    expect(letti.map((f) => f.data)).toEqual(['{"text":"a"}', '{"text":"b"}']);
  });

  it("non taglia un carattere UTF-8 a cavallo fra due pacchetti", async () => {
    // "è" in UTF-8 e' 0xC3 0xA8: il primo pacchetto finisce in mezzo.
    const byte = new TextEncoder().encode('event: token\ndata: {"text":"è"}\n\n');
    const rottura = byte.indexOf(0xc3) + 1;
    const letti = await raccogli(frames(stream(byte.slice(0, rottura), byte.slice(rottura))));
    expect(JSON.parse(letti[0].data)).toEqual({ text: "è" });
  });

  it("accetta le terminazioni \\r\\n", async () => {
    const letti = await raccogli(frames(stream("event: done\r\ndata: {}\r\n\r\n")));
    expect(letti).toEqual([{ event: "done", data: "{}" }]);
  });

  it("unisce le righe `data` multiple con un a capo, come la specifica", async () => {
    const letti = await raccogli(frames(stream("event: x\ndata: uno\ndata: due\n\n")));
    expect(letti[0].data).toBe("uno\ndue");
  });

  it("ignora i commenti e lo spazio facoltativo dopo i due punti", async () => {
    const letti = await raccogli(
      frames(stream(": tengo viva la connessione\nevent:token\ndata:{}\n\n")),
    );
    expect(letti).toEqual([{ event: "token", data: "{}" }]);
  });

  it("scarta il riquadro incompleto quando lo stream cade a meta'", async () => {
    // Non e' un riquadro corto: e' un riquadro che non e' arrivato. Emetterlo
    // significherebbe consegnare come completo qualcosa che e' stato interrotto.
    const letti = await raccogli(
      frames(stream('event: token\ndata: {"text":"a"}\n\nevent: token\ndata: {"tex')),
    );
    expect(letti).toHaveLength(1);
  });

  it("non emette niente per uno stream vuoto", async () => {
    expect(await raccogli(frames(stream()))).toEqual([]);
  });
});

describe("events", () => {
  it("consegna la sequenza del §3.5 nell'ordine in cui arriva", async () => {
    const sorgente = stream(
      'event: chunks\ndata: {"chunks": []}\n\n',
      'event: token\ndata: {"text": "Il "}\n\n',
      'event: answer\ndata: {"text": "Il valore [1].", "verification_pending": true}\n\n',
      'event: citations\ndata: {"citations": [], "uncited_claims": []}\n\n',
      'event: done\ndata: {"verified": true, "timings": {}}\n\n',
    );
    const letti = await raccogli(events(sorgente));
    expect(letti.map((e) => e.event)).toEqual(["chunks", "token", "answer", "citations", "done"]);
  });

  it("salta un evento che il contratto non conosce, e lo dice", async () => {
    // Saltare e' giusto: il server non ha segnalato un guasto, e tradurlo in
    // `error` mostrerebbe all'utente un errore che nessuno ha commesso. Ma
    // saltare **in silenzio** e' l'altro modo di sbagliare.
    const visto = vi.fn();
    const letti = await raccogli(
      events(stream('event: sconosciuto\ndata: {}\n\nevent: token\ndata: {"text":"a"}\n\n'), visto),
    );
    expect(letti.map((e) => e.event)).toEqual(["token"]);
    expect(visto).toHaveBeenCalledWith("sconosciuto");
  });

  it("solleva se `data` non e' JSON", async () => {
    // Qui il contratto e' rotto davvero: proseguire significherebbe consegnare
    // eventi buoni pescati fra eventi illeggibili.
    await expect(raccogli(events(stream("event: token\ndata: non-json\n\n")))).rejects.toThrow(
      /non e' JSON/,
    );
  });

  it("porta `verification_pending` fino al client", async () => {
    // Lo stato piu' scomodo del §3.5: il testo c'e', i verdetti no. Senza questo
    // campo la UI dovrebbe indovinare se aspettare i `citations`, e indovinare
    // male significa o un caricamento eterno o una citazione dichiarata
    // verificata che nessuno ha guardato.
    const [evento] = await raccogli(
      events(stream('event: answer\ndata: {"verification_pending": false}\n\n')),
    );
    expect(evento.event).toBe("answer");
    if (evento.event === "answer") {
      expect(evento.data.verification_pending).toBe(false);
    }
  });
});
