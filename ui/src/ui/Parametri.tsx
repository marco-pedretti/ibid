/**
 * Con quali parametri e' stata data questa risposta, e cosa e' cambiato.
 *
 * **Si vede a malapena, ed e' voluto.** Stesso peso di «Invio per mandare»:
 * mono, 10 px, attenuato. Non e' un messaggio della conversazione — non ha una
 * bolla, non ha un mittente, non prende una riga alta — perche' non l'ha detto
 * nessuno: e' una nota a margine su come e' stata prodotta la riga sotto. Un
 * riquadro di sistema fra due domande spezzerebbe la lettura del filo per dire
 * una cosa che nel 90% dei casi e' «niente e' cambiato».
 *
 * **Compare solo quando ha qualcosa da dire.** Fra due domande con la stessa
 * configurazione non c'e' riga: una nota che c'e' sempre smette di essere letta,
 * ed e' la stessa regola del riepilogo dei verdetti.
 *
 * L'unica che compare **comunque** e' la prima di una conversazione, perche' li'
 * la domanda «con cosa e' partita?» ha sempre una risposta. Il confronto e' con
 * i predefiniti del servizio, quindi una conversazione in cui non si e' toccato
 * niente lo dice in tre parole invece che in quattordici.
 *
 * La configurazione **intera** sta nel suggerimento, che e' il posto dove la si
 * va a cercare: e' un dato, quindi si apre subito (vedi `Suggerimento`).
 */
import { usaLingua } from "../app/i18n";
import type { Traduci } from "../app/i18n";
import { differenze, intera } from "../app/parametri";
import type { Differenza } from "../app/parametri";
import type { ConfigView } from "../api/types";
import { Suggerimento } from "./Suggerimento";

export function Parametri({
  config,
  precedente,
  predefiniti,
}: {
  /** La configurazione che ha girato per questa risposta. */
  config: ConfigView | null;
  /** Quella dell'ultima risposta che ne aveva una, o `null` se e' la prima. */
  precedente: ConfigView | null;
  predefiniti: ConfigView | null;
}) {
  const { t, lingua } = usaLingua();

  // Senza `config` la risposta non e' arrivata a `done`: interrotta, caduta, o
  // ancora in corso. «Non si sa cosa ha girato» non e' «non e' cambiato
  // niente», e tacere e' l'unico dei due che non afferma il falso.
  if (config === null) return null;

  const prima = precedente ?? predefiniti;
  const cambiati = differenze(prima, config);
  const primaRiga = precedente === null;
  if (cambiati.length === 0 && !primaRiga) return null;

  const testo =
    cambiati.length === 0
      ? t("params.default")
      : primaRiga
        ? `${t("params.start")} ${elenca(cambiati, t, lingua)}`
        : elenca(cambiati, t, lingua);

  return (
    <Suggerimento
      dato
      testo={`${t("params.all")} ${elenca(intera(config), t, lingua)}`}
      className="block font-mono text-[10px] leading-[1.5] text-muted"
    >
      {testo}
    </Suggerimento>
  );
}

/** `rag sì → no · top_k 5 → 12`. Il separatore e' quello dei tempi nella riga
 *  di stato, cosi' le due note a margine si leggono con la stessa grammatica. */
function elenca(d: readonly Differenza[], t: Traduci, lingua: string): string {
  return d
    .map((x) =>
      x.prima === undefined
        ? `${x.campo} ${valore(x.dopo, t, lingua)}`
        : `${x.campo} ${valore(x.prima, t, lingua)} → ${valore(x.dopo, t, lingua)}`,
    )
    .join(" · ");
}

/**
 * Un valore come si legge.
 *
 * I booleani prendono le parole gia' in uso sotto «Avanzate» invece di `true` e
 * `false`: sono le stesse che si vedono nei controlli che li hanno cambiati, e
 * due vocabolari per lo stesso interruttore sono un vocabolario di troppo.
 *
 * `null` e' `auto` e non «vuoto»: e' un valore vero — lasciar decidere l'indice
 * — e la stringa vuota e' «nessun filtro», che e' un'altra cosa ancora.
 */
function valore(v: unknown, t: Traduci, lingua: string): string {
  if (typeof v === "boolean") return t(v ? "bar.advanced.on" : "bar.advanced.off");
  if (v === null) return t("bar.advanced.auto");
  if (v === "") return t("params.none");
  if (typeof v === "number") {
    return v.toLocaleString(lingua === "it" ? "it-IT" : "en-US", { maximumFractionDigits: 2 });
  }
  return String(v);
}
