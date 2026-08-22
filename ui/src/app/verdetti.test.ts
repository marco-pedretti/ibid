import { describe, expect, it } from "vitest";

import type { CitationView } from "../api/types";
import { inizio } from "./conversazione";
import type { Risposta } from "./conversazione";
import {
  esitoDellaScheda,
  esitoNumericoDellaScheda,
  localizza,
  marcatoriDelTesto,
  riepilogo,
  spanSenzaCitazione,
  statoVerifica,
} from "./verdetti";

/** Una citazione come la manda l'API: `claim` e' la frase **senza** marcatori. */
function cit(
  marker: number,
  claim: string,
  supported: boolean,
  score = 0.5,
  numeric = "not_applicable",
  threshold = 0.5,
): CitationView {
  return { marker, chunk_id: `d:${marker}`, claim, supported, score, threshold, numeric };
}

/** Una risposta a testo definitivo e verifica conclusa: il caso di U-07. */
function verificata(
  testo: string,
  citazioni: CitationView[],
  senzaCitazione: string[] = [],
): Risposta {
  return {
    ...inizio(),
    fase: "conclusa",
    testo,
    definitivo: true,
    citazioni,
    senzaCitazione,
    verificate: true,
  };
}

describe("statoVerifica: quattro stati, e nessuno e' l'assenza di un altro", () => {
  it("prima di `answer` e' inerte, qualunque cosa scorra", () => {
    const r: Risposta = { ...inizio(), fase: "scrittura", testo: "il valore e' 400ms [2]" };
    expect(statoVerifica(r)).toBe("inerte");
  });

  it("con `verification_pending` e' attesa", () => {
    const r: Risposta = { ...inizio(), fase: "risposta", definitivo: true, verificaInCorso: true };
    expect(statoVerifica(r)).toBe("attesa");
  });

  it("fra `citations` e `done` i verdetti sono la prova che la verifica ha girato", () => {
    // `verificate` arriva con `done`: leggerlo qui direbbe «non verificata» di una
    // risposta i cui verdetti sono appena arrivati.
    const r = {
      ...verificata("x [1].", [cit(1, "x.", true)]),
      fase: "citazioni" as const,
      verificate: false,
    };
    expect(statoVerifica(r)).toBe("fatta");
  });

  it("con `verify` spento e' assente, non «fatta senza verdetti»", () => {
    const r: Risposta = { ...inizio(), fase: "conclusa", testo: "x [1].", definitivo: true };
    expect(statoVerifica(r)).toBe("assente");
  });

  it("verifica fatta e niente da giudicare resta «fatta»", () => {
    const r: Risposta = { ...inizio(), fase: "conclusa", definitivo: true, verificate: true };
    expect(statoVerifica(r)).toBe("fatta");
  });
});

describe("localizza: le frasi si ritrovano, non si ritagliano", () => {
  it("trova una frase a cui i marcatori sono stati tolti", () => {
    const testo = "Il valore massimo e' 400ms [2][3]. Il minimo e' 12ms [1].";
    expect(localizza(testo, ["Il valore massimo e' 400ms."])).toEqual([{ da: 0, a: 34 }]);
  });

  it("lo span copre i marcatori che stanno dentro la frase", () => {
    const testo = "Il valore massimo e' 400ms [2][3].";
    const [s] = localizza(testo, ["Il valore massimo e' 400ms."]);
    // I due marcatori stanno a 27 e 30: dentro `[da, a)`, altrimenti nessun
    // verdetto li raggiungerebbe.
    expect(s).toEqual({ da: 0, a: 34 });
  });

  it("prende anche i marcatori in coda a una frase senza punto finale", () => {
    // L'ultima frase di una risposta troncata. Nel testo nudo la frase termina su
    // `s`, e senza la coda il `[2]` cadrebbe fuori dalla propria frase.
    const testo = "Il valore massimo e' 400ms [2]";
    expect(localizza(testo, ["Il valore massimo e' 400ms"])).toEqual([{ da: 0, a: 30 }]);
  });

  it("due frasi identiche non collassano sulla prima", () => {
    const testo = "Non lo riporta [1]. Il resto e' altro. Non lo riporta [2].";
    const spans = localizza(testo, ["Non lo riporta.", "Non lo riporta."]);
    expect(spans[0]?.da).toBe(0);
    expect(spans[1]?.da).toBe(39);
  });

  it("una frase che non si ritrova resta `null` invece di prendere un posto", () => {
    expect(localizza("qualcosa d'altro", ["frase mai scritta."])).toEqual([null]);
  });

  it("una frase vuota non si localizza", () => {
    expect(localizza("qualcosa", [""])).toEqual([null]);
  });
});

describe("marcatoriDelTesto: l'unita' e' la coppia, non il marcatore", () => {
  it("lo stesso marcatore in due frasi porta due verdetti diversi", () => {
    // E' la ragione per cui questo modulo esiste. Aggregare per marcatore
    // cancellerebbe la granularita' di frase, che e' l'affermazione 1 del §0.
    const testo = "Il massimo e' 400ms [3]. Il minimo e' 12ms [3].";
    const r = verificata(testo, [
      cit(3, "Il massimo e' 400ms.", true, 0.81),
      cit(3, "Il minimo e' 12ms.", false, 0.19),
    ]);
    expect(marcatoriDelTesto(r).map((m) => m.esito)).toEqual(["sostenuta", "nonSostiene"]);
  });

  it("un marcatore dopo il punto appartiene alla frase seguente", () => {
    // Il backend spezza sul bianco **dopo** il terminatore, quindi `[2]` scritto
    // li' apre la frase successiva invece di chiudere la precedente.
    const testo = "La prima frase non cita niente. [2] La seconda lo fa.";
    const r = verificata(testo, [cit(2, "La seconda lo fa.", false, 0.2)]);
    const [m] = marcatoriDelTesto(r);
    expect(m.esito).toBe("nonSostiene");
  });

  it("una frase troppo corta per C-03 lascia il marcatore non verificato", () => {
    // Sotto `MIN_CLAIM_CHARS` il backend non produce coppie: «il chunk sostiene
    // questo?» non ha una risposta per un frammento. Non e' un verdetto e non va
    // disegnato come tale.
    const testo = "Si [1]. Il valore massimo misurato e' 400ms [2].";
    const r = verificata(testo, [cit(2, "Il valore massimo misurato e' 400ms.", true, 0.7)]);
    expect(marcatoriDelTesto(r).map((m) => m.esito)).toEqual(["nonVerificata", "sostenuta"]);
  });

  it("un marcatore in una frase verificata ma su un altro chunk non e' verificato", () => {
    const testo = "Il valore massimo misurato e' 400ms [2][4].";
    const r = verificata(testo, [cit(2, "Il valore massimo misurato e' 400ms.", true, 0.7)]);
    expect(marcatoriDelTesto(r).map((m) => [m.marker, m.esito])).toEqual([
      [2, "sostenuta"],
      [4, "nonVerificata"],
    ]);
  });

  it("prima di `answer` sono tutti inerti, e nessuno porta una citazione", () => {
    const r: Risposta = { ...inizio(), fase: "scrittura", testo: "il valore [2] e' alto [3]" };
    const marcati = marcatoriDelTesto(r);
    expect(marcati.map((m) => m.esito)).toEqual(["inerte", "inerte"]);
    expect(marcati.every((m) => m.citazione === null)).toBe(true);
  });

  it("in attesa dei verdetti non sono ne' sostenuti ne' non verificati", () => {
    const r: Risposta = {
      ...inizio(),
      fase: "risposta",
      testo: "il valore [2]",
      definitivo: true,
      verificaInCorso: true,
    };
    expect(marcatoriDelTesto(r).map((m) => m.esito)).toEqual(["attesa"]);
  });

  it("con `verify` spento sono non verificati, non sostenuti per difetto", () => {
    const r: Risposta = { ...inizio(), fase: "conclusa", testo: "il valore [2]", definitivo: true };
    expect(marcatoriDelTesto(r).map((m) => m.esito)).toEqual(["nonVerificata"]);
  });

  it("l'indice e' la chiave: due `[3]` sono due citazioni distinte", () => {
    const testo = "Il massimo e' 400ms [3]. Il minimo e' 12ms [3].";
    const indici = marcatoriDelTesto(verificata(testo, [])).map((m) => m.indice);
    expect(indici).toEqual([20, 43]);
    expect(new Set(indici).size).toBe(2);
  });
});

describe("esitoDellaScheda", () => {
  const testo = "Il valore massimo e' 400ms [1]. Il minimo e' 12ms [1][2].";

  it("un chunk che la risposta non ha usato non e' «non sostenuto»", () => {
    // Dire «non sostiene» di qualcosa che nessuno ha affermato sarebbe inventare
    // un giudizio. La scheda resta nel pannello (U-02), senza verdetto.
    const r = verificata(testo, [cit(1, "Il valore massimo e' 400ms.", true)]);
    expect(esitoDellaScheda(r, 5)).toEqual({ tipo: "nonCitata" });
  });

  it("una sola citazione mostra il proprio punteggio", () => {
    const r = verificata(testo, [cit(2, "Il minimo e' 12ms.", false, 0.212)]);
    expect(esitoDellaScheda(r, 2)).toEqual({
      tipo: "nonSostiene",
      punteggio: 0.212,
      soglia: 0.5,
      su: 1,
    });
  });

  it("la soglia arriva dalla citazione, non da una costante di qui", () => {
    // D-7: e' il backend a decidere dove passa la linea. Un frontend che se la
    // scrivesse resterebbe giusto finche' qualcuno non cambia quella vera --
    // ed e' il divieto di U-00, non una preferenza di stile. Il test usa una
    // soglia diversa da 0,5 proprio per distinguere le due cose.
    const r = verificata(testo, [cit(2, "Il minimo e' 12ms.", true, 0.9, "not_applicable", 0.75)]);
    expect(esitoDellaScheda(r, 2)).toEqual({
      tipo: "sostiene",
      punteggio: 0.9,
      soglia: 0.75,
      su: 1,
    });
  });

  it("una citazione salvata prima di D-7 non porta la soglia, e non fa cadere niente", () => {
    // La cronologia salva le risposte **intere** e le rilegge come
    // `{ ...inizio(), ...salvata }`: una conversazione registrata prima che il
    // contratto avesse `threshold` non ce l'ha, e il tipo non la raggiunge.
    // Prima di questa correzione l'interfaccia spariva -- `undefined.toLocaleString()`
    // durante la fase di verifica, e React smontava l'albero.
    //
    // La soglia resta `undefined` invece di diventare 0: una scala inventata e'
    // peggio di nessuna scala, e chi la mostra ha una frase per il caso.
    const vecchia = {
      marker: 2,
      chunk_id: "d:2",
      claim: "Il minimo e' 12ms.",
      supported: true,
      score: 0.9,
      numeric: "not_applicable",
    } as CitationView;
    const r = verificata(testo, [vecchia]);
    const esito = esitoDellaScheda(r, 2);
    expect(esito).toEqual({ tipo: "sostiene", punteggio: 0.9, soglia: undefined, su: 1 });
  });

  it("fra due sostenute mostra la piu' vicina alla linea", () => {
    const r = verificata(testo, [
      cit(1, "Il valore massimo e' 400ms.", true, 0.91),
      cit(1, "Il minimo e' 12ms.", true, 0.62),
    ]);
    expect(esitoDellaScheda(r, 1)).toEqual({
      tipo: "sostiene",
      punteggio: 0.62,
      soglia: 0.5,
      su: 2,
    });
  });

  it("fra due contrarie mostra quella che quasi ce la faceva", () => {
    const r = verificata(testo, [
      cit(1, "Il valore massimo e' 400ms.", false, 0.11),
      cit(1, "Il minimo e' 12ms.", false, 0.34),
    ]);
    expect(esitoDellaScheda(r, 1)).toEqual({
      tipo: "nonSostiene",
      punteggio: 0.34,
      soglia: 0.5,
      su: 2,
    });
  });

  it("verdetti in disaccordo sono «misto», non una media", () => {
    const r = verificata(testo, [
      cit(1, "Il valore massimo e' 400ms.", true, 0.9),
      cit(1, "Il minimo e' 12ms.", false, 0.2),
    ]);
    expect(esitoDellaScheda(r, 1)).toEqual({ tipo: "misto", nonSostengono: 1, su: 2 });
  });

  it("citata ma senza verdetti e' «non verificata», non «non citata»", () => {
    const r: Risposta = { ...inizio(), fase: "conclusa", testo, definitivo: true };
    expect(esitoDellaScheda(r, 1)).toEqual({ tipo: "nonVerificata" });
  });

  it("mentre la verifica gira, una scheda citata e' in attesa", () => {
    const r: Risposta = {
      ...inizio(),
      fase: "risposta",
      testo,
      definitivo: true,
      verificaInCorso: true,
    };
    expect(esitoDellaScheda(r, 1)).toEqual({ tipo: "attesa" });
    expect(esitoDellaScheda(r, 9)).toEqual({ tipo: "nonCitata" });
  });
});

describe("spanSenzaCitazione", () => {
  it("trova la frase che non cita niente", () => {
    const testo = "Il massimo e' 400ms [1]. Entrambi sul campione trattenuto.";
    const r = verificata(
      testo,
      [cit(1, "Il massimo e' 400ms.", true)],
      ["Entrambi sul campione trattenuto."],
    );
    expect(spanSenzaCitazione(r)).toEqual([{ da: 25, a: 58 }]);
  });

  it("senza frasi scoperte non produce niente", () => {
    expect(spanSenzaCitazione(verificata("x [1].", [cit(1, "x.", true)]))).toEqual([]);
  });
});

describe("riepilogo: la parola, che e' il terzo terzo della regola del §12", () => {
  it("tace quando tutto regge", () => {
    // Un avviso che compare sempre smette di essere letto.
    const r = verificata("Il valore massimo e' 400ms [1].", [
      cit(1, "Il valore massimo e' 400ms.", true, 0.8),
    ]);
    expect(riepilogo(r)).toBeNull();
  });

  it("nomina i marcatori che non reggono, una volta ciascuno", () => {
    const testo = "Il massimo e' 400ms [3]. Il minimo e' 12ms [3][4].";
    const r = verificata(testo, [
      cit(3, "Il massimo e' 400ms.", false, 0.2),
      cit(3, "Il minimo e' 12ms.", false, 0.1),
      cit(4, "Il minimo e' 12ms.", true, 0.9),
    ]);
    expect(riepilogo(r)).toEqual({
      nonSostengono: [3],
      nonSostenute: 2,
      discordanti: 0,
      senzaCitazione: 0,
      nonVerificate: 0,
    });
  });

  it("conta le frasi scoperte anche quando ogni citazione regge", () => {
    const r = verificata(
      "Il massimo e' 400ms [1]. Entrambi sul campione trattenuto.",
      [cit(1, "Il massimo e' 400ms.", true, 0.8)],
      ["Entrambi sul campione trattenuto."],
    );
    expect(riepilogo(r)).toEqual({
      nonSostengono: [],
      nonSostenute: 0,
      discordanti: 0,
      senzaCitazione: 1,
      nonVerificate: 0,
    });
  });

  it("non dice niente finche' i verdetti non ci sono", () => {
    const r: Risposta = {
      ...inizio(),
      fase: "risposta",
      testo: "il valore [2]",
      definitivo: true,
      verificaInCorso: true,
    };
    expect(riepilogo(r)).toBeNull();
  });
});
describe("il verificatore numerico di C-09, accanto e non al posto dell'altro", () => {
  // Il caso vero, misurato il 17 agosto sul capex di Sherwin-Williams: l'NLI dice
  // «non sostiene» a 0,208, il verificatore numerico trova la cifra **dentro la
  // tabella citata**. Mostrare solo il primo darebbe per verdetto cio' che il
  // progetto stesso documenta come debole sulle tabelle.
  const testo = "Le spese in conto capitale nel 2017 sono state 222,8 milioni [5].";
  const claim = "Le spese in conto capitale nel 2017 sono state 222,8 milioni.";

  it("dice «la tabella conferma» dove l'NLI dice «non sostiene»", () => {
    const r = verificata(testo, [cit(5, claim, false, 0.208, "supported")]);
    expect(esitoDellaScheda(r, 5)).toEqual({
      tipo: "nonSostiene",
      punteggio: 0.208,
      soglia: 0.5,
      su: 1,
    });
    expect(esitoNumericoDellaScheda(r, 5)).toEqual({ tipo: "sostiene", su: 1 });
  });

  it("`not_applicable` non e' un verdetto e non produce una pastiglia", () => {
    // E' il caso normale su un corpus di paper: un'etichetta che compare quasi
    // sempre non informa.
    const r = verificata(testo, [cit(5, claim, true, 0.9, "not_applicable")]);
    expect(esitoNumericoDellaScheda(r, 5)).toBeNull();
  });

  it("non porta un punteggio, perche' non ne produce uno", () => {
    // E' un confronto fra numeri, non una probabilita': mostrare uno 0 direbbe
    // il falso.
    const r = verificata(testo, [cit(5, claim, false, 0.2, "unsupported")]);
    expect(esitoNumericoDellaScheda(r, 5)).toEqual({ tipo: "nonSostiene", su: 1 });
  });

  it("finche' i verdetti non ci sono, non c'e' nemmeno quello numerico", () => {
    const r: Risposta = {
      ...inizio(),
      fase: "risposta",
      testo,
      definitivo: true,
      verificaInCorso: true,
    };
    expect(esitoNumericoDellaScheda(r, 5)).toBeNull();
  });

  it("il riepilogo conta le discordanti, che decidono come si intitola", () => {
    // Se tutte le non sostenute sono confermate dal numerico, «non tutte le
    // citazioni reggono» e' la frase sbagliata: non e' la citazione a non
    // reggere, sono i due verificatori a non concordare.
    const r = verificata(testo, [cit(5, claim, false, 0.208, "supported")]);
    expect(riepilogo(r)).toEqual({
      nonSostengono: [5],
      nonSostenute: 1,
      discordanti: 1,
      senzaCitazione: 0,
      nonVerificate: 0,
    });
  });

  it("una non sostenuta che il numerico nemmeno conferma non e' discordante", () => {
    const r = verificata(testo, [cit(5, claim, false, 0.208, "unsupported")]);
    expect(riepilogo(r)?.discordanti).toBe(0);
  });
});
