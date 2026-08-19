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

export type SceltaTema = "light" | "dark" | "system";
export type TemaEffettivo = "light" | "dark";

const CHIAVE = "ibid.theme"; // la stessa che legge lo script in index.html
const SCURO = "(prefers-color-scheme: dark)";

function leggiScelta(): SceltaTema {
  try {
    const v = localStorage.getItem(CHIAVE);
    return v === "dark" || v === "light" ? v : "system";
  } catch {
    // localStorage negato (modalita' privata, iframe): si segue il sistema.
    return "system";
  }
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
    try {
      if (s === "system") localStorage.removeItem(CHIAVE);
      else localStorage.setItem(CHIAVE, s);
    } catch {
      // Il tema resta valido per questa sessione: non ricordarlo e' meno grave
      // che rifiutare di cambiarlo.
    }
  }, []);

  return <Contesto.Provider value={{ scelta, effettivo, imposta }}>{children}</Contesto.Provider>;
}

export function usaTema(): Tema {
  const t = useContext(Contesto);
  if (!t) throw new Error("usaTema fuori da <ProvvedeTema>");
  return t;
}
