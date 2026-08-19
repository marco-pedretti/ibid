/**
 * Il catalogo dei modelli, letto come **due scelte** invece che come un elenco.
 *
 * Chi guarda sceglie due cose — *chi risponde* e *quanto testo gli entra* —
 * perche' sono due domande diverse. Che sotto la coppia sia un nome solo nel
 * catalogo del motore e' un dettaglio dell'implementazione, e non deve affiorare
 * in una tendina che elenca `gemma4-8k` accanto a `gemma4:e2b`: quello e' un
 * catalogo, non una scelta.
 *
 * **Il raggruppamento non interpreta i nomi.** Ogni voce derivata porta il
 * proprio `parent`, che il motore dichiara (A-08): dedurre `gemma4-8k` →
 * `gemma4` spezzando una stringa sarebbe una convenzione dentro l'interfaccia, e
 * le convenzioni si rompono il giorno in cui qualcuno chiama un modello
 * diversamente. E' la lezione di Q-06, applicata a un dato che il server ha gia'.
 *
 * **`context` e `context_max` non sono la stessa cosa**, e confonderle e' il
 * modo piu' facile di sbagliare qui: il primo dice con quanto una voce e'
 * configurata, il secondo cosa l'architettura regge. Una taglia si offre se sta
 * dentro il secondo; quella che gira e' il primo.
 */
import type { ModelView } from "../api/types";

/** Un modello come lo vede chi sceglie: un nome, e le finestre che ha. */
export interface Modello {
  /** Il nome del modello base, quello che si legge nel primo selettore. */
  nome: string;
  family: string;
  /** Le finestre disponibili, dalla piu' piccola. Sempre almeno una. */
  finestre: Finestra[];
}

export interface Finestra {
  /** Quanti token. `null` = la voce non fissa niente e decide il motore. */
  token: number | null;
  /** Il nome da mandare come `model` per ottenere questa finestra. */
  modello: string;
}

/**
 * Le voci del catalogo raggruppate sotto il modello da cui derivano.
 *
 * Una voce senza `parent` e' un modello base e apre un gruppo; una con `parent`
 * e' una taglia di quel gruppo. Una taglia il cui genitore **non e' nel
 * catalogo** resta un modello a se': e' sparito o non e' mai stato elencato, e
 * appenderla a un gruppo che non esiste la farebbe sparire dal menu.
 */
export function modelli(catalogo: readonly ModelView[]): Modello[] {
  const basi = catalogo.filter((m) => m.parent === "" || !nomi(catalogo).has(m.parent));

  return basi.map((base) => {
    const derivate = catalogo.filter((m) => m.parent === base.name);
    const finestre = [
      { token: base.context, modello: base.name },
      ...derivate.map((d) => ({ token: d.context, modello: d.name })),
    ];
    return {
      nome: base.name,
      family: base.family,
      finestre: ordina(finestre.filter((f) => sostenuta(f.token, base.context_max))),
    };
  });
}

function nomi(catalogo: readonly ModelView[]): Set<string> {
  return new Set(catalogo.map((m) => m.name));
}

/**
 * Una finestra si offre solo se il modello la regge.
 *
 * Il massimo **non e' uno solo** — misurato: `gemma4:latest` 131.072,
 * `gemma4:12b` 262.144 — quindi non esiste una lista di taglie valida per tutti.
 * Una taglia che compare e poi fallisce e' peggio di una che non compare: fa
 * scoprire il limite dopo l'attesa, e per giunta come un errore invece che come
 * un vincolo.
 *
 * Senza un massimo noto si offre tutto: il motore non l'ha detto, e nascondere
 * per un limite che non si conosce e' inventare un vincolo.
 */
function sostenuta(token: number | null, massimo: number | null): boolean {
  return token === null || massimo === null || token <= massimo;
}

/** Dalla piu' piccola, e «decide il motore» per prima: e' il punto di partenza,
 *  non una taglia fra le altre. */
function ordina(finestre: readonly Finestra[]): Finestra[] {
  return [...finestre].sort((a, b) => (a.token ?? -1) - (b.token ?? -1));
}

/** Il modello base di cui `nome` e' una voce, o `null` se non e' nel catalogo. */
export function modelloDi(elenco: readonly Modello[], nome: string): Modello | null {
  return elenco.find((m) => m.finestre.some((f) => f.modello === nome)) ?? null;
}

/** La finestra con cui `nome` gira, o `null`. */
export function finestraDi(elenco: readonly Modello[], nome: string): Finestra | null {
  for (const m of elenco) {
    const f = m.finestre.find((x) => x.modello === nome);
    if (f !== undefined) return f;
  }
  return null;
}

/**
 * Il nome da mandare cambiando **una** delle due scelte.
 *
 * Cambiando modello si tiene la finestra piu' vicina a quella che si aveva,
 * invece di ripartire dal default: chi sta confrontando due modelli sulla stessa
 * domanda sta cambiando **una** cosa, e cambiargliene due sotto le mani e' il
 * §15 rotto dentro un menu.
 */
export function conModello(elenco: readonly Modello[], nome: string, attuale: string): string {
  const m = elenco.find((x) => x.nome === nome);
  if (m === undefined || m.finestre.length === 0) return nome;
  const voluta = finestraDi(elenco, attuale)?.token ?? null;
  return piuVicina(m.finestre, voluta).modello;
}

function piuVicina(finestre: readonly Finestra[], token: number | null): Finestra {
  if (token === null) return finestre[0];
  let scelta = finestre[0];
  for (const f of finestre) {
    const d = Math.abs((f.token ?? 0) - token);
    if (d < Math.abs((scelta.token ?? 0) - token)) scelta = f;
  }
  return scelta;
}
