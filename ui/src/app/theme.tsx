/**
 * Chiaro, scuro, o quello che dice il sistema.
 *
 * Tre stati e non due: «sistema» non e' un valore di partenza, e' una scelta che
 * resta viva — chi lo lascia cosi' vuole che la pagina cambi quando il sistema
 * cambia, anche a finestra aperta. Per questo il listener sulla media query
 * resta attivo, invece di leggerla una volta all'avvio.
 *
 * Il valore **risolto** finisce sempre in `data-theme` su `<html>`, mai lasciato
 * a `prefers-color-scheme`: con l'attributo sempre presente, la variante CSS e'
 * una condizione sola, e il toggle puo' vincere sul sistema in entrambi i versi.
 * La prima stampa la fa uno script in `index.html`, prima della prima pittura.
 */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { CHIAVI, ricorda, ricordato } from "./deposito";

export type SceltaTema = "light" | "dark" | "system";
export type TemaEffettivo = "light" | "dark";

const SCURO = "(prefers-color-scheme: dark)";

/** Solo «dark» e «light» sono una scelta; tutto il resto — chiave assente,
 *  deposito negato, valore scritto a mano — e' «segui il sistema». */
function leggiScelta(): SceltaTema {
  const v = ricordato(CHIAVI.tema);
  return v === "dark" || v === "light" ? v : "system";
}

function risolvi(scelta: SceltaTema): TemaEffettivo {
  if (scelta !== "system") return scelta;
  return window.matchMedia(SCURO).matches ? "dark" : "light";
}

interface Tema {
  scelta: SceltaTema;
  effettivo: TemaEffettivo;
  imposta: (s: SceltaTema) => void;
}

const Contesto = createContext<Tema | null>(null);

export function ProvvedeTema({ children }: { children: ReactNode }) {
  const [scelta, setScelta] = useState<SceltaTema>(leggiScelta);
  const [effettivo, setEffettivo] = useState<TemaEffettivo>(() => risolvi(leggiScelta()));

  useEffect(() => {
    const applica = () => {
      const risolto = risolvi(scelta);
      document.documentElement.dataset.theme = risolto;
      setEffettivo(risolto);
    };
    applica();
    if (scelta !== "system") return;

    const mq = window.matchMedia(SCURO);
    mq.addEventListener("change", applica);
    return () => mq.removeEventListener("change", applica);
  }, [scelta]);

  const imposta = useCallback((s: SceltaTema) => {
    setScelta(s);
    // «Segui il sistema» non e' un tema salvato: si toglie la chiave, altrimenti
    // si seguirebbe per sempre il sistema com'era nel momento della scelta.
    ricorda(CHIAVI.tema, s === "system" ? null : s);
  }, []);

  return <Contesto.Provider value={{ scelta, effettivo, imposta }}>{children}</Contesto.Provider>;
}

export function usaTema(): Tema {
  const t = useContext(Contesto);
  if (!t) throw new Error("usaTema fuori da <ProvvedeTema>");
  return t;
}
