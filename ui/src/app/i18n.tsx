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
import { CHIAVI, ricorda, ricordato } from "./deposito";

/** Quella ricordata se e' una lingua che esiste, altrimenti quella del browser.
 *  Un valore storto nel deposito ricade sul secondo caso, che e' il predefinito
 *  di chi non ha mai scelto: non c'e' niente da perdere. */
function leggiLingua(): Lingua {
  const salvata = ricordato(CHIAVI.lingua);
  if (salvata !== null && (LINGUE as readonly string[]).includes(salvata)) return salvata as Lingua;
  return navigator.language.toLowerCase().startsWith("it") ? "it" : "en";
}

/** I valori da mettere al posto dei `{nome}` di una frase. */
export type Valori = Record<string, string | number>;

/** La funzione di traduzione da sola, per chi la riceve invece di prenderla dal
 *  contesto: una funzione pura che compone testo non deve essere un componente
 *  solo per poter chiamare `usaLingua`. */
export type Traduci = (chiave: Chiave, valori?: Valori) => string;

interface Traduzione {
  lingua: Lingua;
  /**
   * `t("verdict.mixed", { quante: 1, su: 3 })`.
   *
   * L'interpolazione esiste perche' l'alternativa e' comporre la frase a pezzi
   * nel componente — `t("a") + n + t("b")` — e una frase composta a pezzi non si
   * traduce: l'ordine delle parti e' quello dell'italiano, e in un'altra lingua
   * il numero puo' andare altrove. Tenendo il segnaposto **dentro** la stringa,
   * chi traduce vede la frase intera e la puo' rigirare.
   */
  t: Traduci;
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

  const t = useCallback(
    (chiave: Chiave, valori?: Valori) => {
      const frase = DIZIONARI[lingua][chiave];
      if (valori === undefined) return frase;
      // Un segnaposto senza valore resta scritto com'e': una frase con `{su}`
      // dentro si vede, mentre un buco al suo posto passa inosservato.
      return frase.replace(/\{(\w+)\}/g, (intero, nome: string) =>
        nome in valori ? String(valori[nome]) : intero,
      );
    },
    [lingua],
  );

  const imposta = useCallback((l: Lingua) => {
    setLingua(l);
    ricorda(CHIAVI.lingua, l);
  }, []);

  return <Contesto.Provider value={{ lingua, t, imposta }}>{children}</Contesto.Provider>;
}

export function usaLingua(): Traduzione {
  const l = useContext(Contesto);
  if (!l) throw new Error("usaLingua fuori da <ProvvedeLingua>");
  return l;
}
