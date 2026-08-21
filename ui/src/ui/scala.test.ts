import { describe, expect, it } from "vitest";

import { leggiScala } from "./scala";

describe("la scala della radice", () => {
  it("legge il numero che il browser restituisce", () => {
    expect(leggiScala("1.2")).toBe(1.2);
    expect(leggiScala("1")).toBe(1);
    expect(leggiScala("1.45")).toBe(1.45);
  });

  it("senza zoom, o dove non e' supportato, vale 1", () => {
    // `"normal"` e la stringa vuota sono le due risposte dei browser che non
    // hanno la proprieta': nessuna delle due e' una scala.
    for (const g of ["normal", "", "auto", null, undefined]) {
      expect(leggiScala(g)).toBe(1);
    }
  });

  it("uno zero o un negativo non sono «nessuno zoom»: sono una divisione rotta", () => {
    // E' il caso che conta: `scala()` finisce a denominatore, e uno zero
    // manderebbe ogni coordinata all'infinito invece di lasciarla dov'era.
    for (const g of ["0", "-1", "-0.5", "NaN"]) {
      expect(leggiScala(g)).toBe(1);
    }
  });
});
