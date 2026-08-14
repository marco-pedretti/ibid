/**
 * La lingua della **cornice**. Quella della risposta segue la domanda.
 *
 * Il perche' sta in `src/i18n/strings.ts`, e vale la pena ripeterlo qui dove si
 * potrebbe essere tentati di passarla all'API: non c'e' modo di farlo.
 * `QueryRequest` non ha un campo lingua, quindi la regola e' fatta rispettare
 * dal contratto e non dalla memoria di chi scrive il prossimo componente.
 */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { DIZIONARI, LINGUE } from "../i18n/strings";
import type { Chiave, Lingua } from "../i18n/strings";

const CHIAVE = "ibid.lang";

function leggiLingua(): Lingua {
  try {
    const salvata = localStorage.getItem(CHIAVE);
    if (salvata && (LINGUE as readonly string[]).includes(salvata)) return salvata as Lingua;
  } catch {
    /* localStorage negato: si deduce dal browser */
  }
  return navigator.language.toLowerCase().startsWith("it") ? "it" : "en";
}

interface Traduzione {
  lingua: Lingua;
  t: (chiave: Chiave) => string;
  imposta: (l: Lingua) => void;
}

const Contesto = createContext<Traduzione | null>(null);

export function ProvvedeLingua({ children }: { children: ReactNode }) {
  const [lingua, setLingua] = useState<Lingua>(leggiLingua);

  // `<html lang>` non e' decorazione: da li' un lettore di schermo sceglie la
  // pronuncia, e il browser la sillabazione.
  useEffect(() => {
    document.documentElement.lang = lingua;
  }, [lingua]);

  const t = useCallback((chiave: Chiave) => DIZIONARI[lingua][chiave], [lingua]);

  const imposta = useCallback((l: Lingua) => {
    setLingua(l);
    try {
      localStorage.setItem(CHIAVE, l);
    } catch {
      /* vale per questa sessione */
    }
  }, []);

  return <Contesto.Provider value={{ lingua, t, imposta }}>{children}</Contesto.Provider>;
}

export function usaLingua(): Traduzione {
  const l = useContext(Contesto);
  if (!l) throw new Error("usaLingua fuori da <ProvvedeLingua>");
  return l;
}
