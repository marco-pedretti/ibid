import { describe, expect, it } from "vitest";

import { PASSI, avanti, leggi, primoPasso, scrivi } from "./avvio";

describe("i passi", () => {
  it("ognuno ha un titolo e una frase, e nessuno ripete l'altro", () => {
    const chiavi = PASSI.flatMap((p) => [p.titolo, p.testo]);
    expect(new Set(chiavi).size).toBe(chiavi.length);
    expect(new Set(PASSI.map((p) => p.id)).size).toBe(PASSI.length);
  });
});

describe("dove si era arrivati", () => {
  it("chi non ha mai visto niente parte dal primo", () => {
    expect(leggi(null)).toBe(0);
  });

  it("la parola della fine e' l'unica che finisce la guida", () => {
    // E' il criterio di U-20: saltata una volta, non torna al ricaricamento.
    expect(leggi("fatto")).toBe(null);
  });

  it("un passo salvato si ritrova dov'era", () => {
    expect(leggi("2")).toBe(2);
  });

  it("qualunque cosa di storto nel deposito riparte dal primo, non dalla fine", () => {
    // Il verso opposto a quello di `corsia.ts`, e la ragione sta nel modulo: qui
    // il caso da proteggere e' chi la guida non l'ha mai vista.
    for (const g of ["", "fine", "-1", "1.5", "{}", "FATTO", String(PASSI.length)]) {
      expect(leggi(g)).toBe(0);
    }
  });

  it("un giro dal deposito torna uguale, per ogni passo e per la fine", () => {
    for (const passo of [...PASSI.map((_, i) => i), null]) {
      expect(leggi(scrivi(passo))).toBe(passo);
    }
  });
});

describe("il primo avvio", () => {
  it("chi arriva la prima volta vede la guida", () => {
    expect(primoPasso(null, false)).toBe(0);
  });

  it("chi in questo browser ha gia' chiesto qualcosa non la vede affatto", () => {
    // La chiave e' nuova: senza questa regola il primo avvio dopo U-20
    // accoglierebbe con un tour chi usa la demo da settimane.
    expect(primoPasso(null, true)).toBe(null);
  });

  it("ma se il deposito dice qualcosa, comanda lui", () => {
    // Chi ha lasciato la guida a meta' per chiedere qualcosa se la ritrova dov'era:
    // la cronologia non vuota non deve chiudergliela alle spalle.
    expect(primoPasso("1", true)).toBe(1);
    expect(primoPasso("fatto", false)).toBe(null);
  });
});

describe("andare avanti", () => {
  it("porta al passo dopo", () => {
    expect(avanti(0)).toBe(1);
  });

  it("dall'ultimo chiude la guida, come «Salta»", () => {
    expect(avanti(PASSI.length - 1)).toBe(null);
  });

  it("arrivare in fondo passa da tutti i passi una volta sola", () => {
    const visti: number[] = [];
    let passo: number | null = 0;
    while (passo !== null) {
      visti.push(passo);
      passo = avanti(passo);
    }
    expect(visti).toEqual(PASSI.map((_, i) => i));
  });
});
