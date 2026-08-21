/**
 * L'avvio guidato: una scheda che indica la zona di cui sta parlando (U-20).
 *
 * **Indica sul serio, e non impedisce niente.** Il criterio chiede che la prima
 * domanda si possa fare mentre la guida e' aperta, e un velo che copre lo
 * schermo di solito e' esattamente il modo in cui una guida dice il contrario.
 * Qui il velo c'e' — smorzato, basso, quel tanto che porta l'occhio dentro
 * l'alone — ma **non intercetta il puntatore**: tutto lo strato e'
 * `pointer-events-none` tranne la scheda, che ha due bottoni. Si puo' scrivere
 * nel campo, mandare, cliccare un esempio, cambiare dataset, con la guida
 * aperta. Il velo e' un peso visivo, non una porta chiusa.
 *
 * **Ogni zona si dichiara da se'.** L'alone non nasce da un selettore CSS
 * indovinato da qui: nasce da un `data-guida` che il componente della zona si
 * mette addosso, tipizzato su `Passo["id"]`, quindi una zona scritta storta non
 * compila. Era l'obiezione con cui questa forma era stata scartata la prima
 * volta — una guida che evidenzia regioni dello schermo si disallinea in
 * silenzio il giorno in cui l'impaginazione cambia — e la risposta e' che a
 * dichiarare la zona sia chi la disegna. Se poi il nodo non e' sullo schermo
 * (schermata diversa, pannello assente) **l'alone non si disegna affatto** e la
 * scheda si mette in alto, lontana dal campo: la guida dice una cosa in meno,
 * non una cosa falsa, e continua a non impedire la prima domanda.
 *
 * **La collocazione e' aritmetica, e sta in `riflettore.ts`.** E' l'unica parte
 * che puo' dare un risultato sbagliato invece che brutto, quindi si prova in
 * `node`: e' la stessa divisione di lavoro fra `Suggerimento` e
 * `collocazione.ts`, e le due costanti — distanza e margine — sono le stesse,
 * lette da li'.
 *
 * **Si converte al confine.** `getBoundingClientRect` e `innerWidth` arrivano in
 * px di finestra, `left` e `top` si scrivono in px di disegno: senza dividere
 * per `scala()` l'alone si allontanerebbe dal bersaglio esattamente del fattore
 * di zoom. E' il difetto gia' pagato una volta dalla bolla del suggerimento.
 *
 * **Il portale non e' un vezzo**, ed e' la stessa ragione del suggerimento: le
 * colonne dell'interfaccia sono contenitori che scorrono, e un elemento
 * posizionato dentro uno di quelli viene ritagliato ai suoi bordi. Qui in piu'
 * l'alone deve poter stare **sopra la corsia** mentre la scheda sta sopra la
 * colonna di mezzo: due antenati diversi, nessuno dei due giusto.
 *
 * **Si rimisura di continuo, invece di ascoltare gli eventi giusti.** Le cose
 * che spostano un bersaglio qui sono quattro — la finestra che cambia, una
 * colonna che scorre, il pannello fonti che compare, la corsia che si comprime —
 * e l'ultima **sostituisce il nodo** invece di ridimensionarlo, quindi un
 * `ResizeObserver` su cio' che si e' trovato smette di parlare proprio quando
 * servirebbe. Un giro ogni 100 ms che rilegge la zona e aggiorna solo se e'
 * cambiata costa una misura su un elemento, dura quanto la guida, e non ha casi
 * scoperti.
 */
import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { ReactNode } from "react";

import { DEPOSITO, PASSI, avanti, primoPasso, scrivi } from "../app/avvio";
import type { Passo } from "../app/avvio";
import { leggiCronologia } from "../app/cronologia";
import { usaLingua } from "../app/i18n";
import { LINGUE } from "../i18n/strings";
import type { Misura, Rettangolo } from "./collocazione";
import { Astensione, FrecciaSu, Indice, Informazioni, Sostiene } from "./Icona";
import type { PropsIcona } from "./Icona";
import { alone, buco, collocaScheda } from "./riflettore";
import type { PosaScheda } from "./riflettore";
import { scala } from "./scala";
import { Suggerimento } from "./Suggerimento";

/**
 * Il disegno di ogni passo: il glifo della cosa di cui parla, mai un glifo
 * nuovo — l'ultimo e' quello del bottone «Che cos'e'» che nomina.
 *
 * `barra` prende la **freccia dell'invio**, che e' il glifo del bottone
 * immediatamente sopra quella fila: quei controlli non decidono la risposta che
 * si sta leggendo, decidono come partira' la prossima. Disegnare un glifo nuovo
 * — tre manopole, la forma con cui si dice «impostazioni» dappertutto — sarebbe
 * stato piu' preciso e piu' rischioso: a 13 px una manopola e' un punto con un
 * trattino, e le cinque regole in testa a `Icona.tsx` esistono perche' un simbolo
 * nuovo che non regge alla sua misura si vede solo dopo averlo messo.
 *
 * `Record` esaustivo e non una mappa parziale: un passo aggiunto senza il suo
 * glifo **non compila**, invece di disegnarsi senza.
 */
const GLIFO: Record<Passo["id"], (p: PropsIcona) => ReactNode> = {
  fonti: Indice,
  verdetti: Sostiene,
  barra: FrecciaSu,
  corpus: Astensione,
  resta: Informazioni,
};

/** L'attributo con cui una zona dichiara di essere il bersaglio di un passo.
 *  Una costante e non una stringa scritta in due file: e' un contratto che
 *  nessun tipo puo' controllare da solo. */
export const ATTRIBUTO = "data-guida";

/**
 * Da mettere sulla zona che un passo indica: `<aside {...zona("fonti")}>`.
 *
 * Una funzione e non l'attributo scritto a mano, perche' cosi' l'identificativo
 * passa dal tipo: `zona("fonto")` non compila, mentre `data-guida="fonto"`
 * sarebbe una stringa qualunque che nessuno controlla e un alone che non compare
 * mai. E' la sola parte di questo meccanismo che si puo' sbagliare in silenzio,
 * quindi e' la sola che vale la pena chiudere.
 */
export function zona(id: Passo["id"]): Record<string, string> {
  return { [ATTRIBUTO]: id };
}

/** Quanto spesso si rilegge la zona. Vedi la nota in testa: e' il prezzo di non
 *  avere casi scoperti, ed e' una misura ogni decimo di secondo. */
const RILETTURA_MS = 100;

/** La scheda: larga fissa, perche' e' una colonna di lettura corta e non deve
 *  cambiare forma spostandosi da una zona all'altra. */
const LARGHEZZA = 360;

/**
 * Il movimento da una zona all'altra: alone, velo e scheda, tutti e tre.
 *
 * **Una durata sola per le tre cose**, e non tre valori accordati a occhio: si
 * spostano insieme e sono una cosa sola: se il bordo arrivasse prima del velo si
 * vedrebbe l'alone acceso su un fondo ancora scuro, che e' esattamente
 * l'impressione di un programma che fatica.
 *
 * 360 ms sono lunghi per un'interfaccia — una tendina qui ne prende 150 — ed e'
 * voluto: questo movimento non e' un controllo che risponde a un clic, e' un
 * indicatore che **porta l'occhio** da una parte all'altra dello schermo, e a
 * 150 ms non lo si segue, lo si ritrova gia' arrivato. La curva decelera fino
 * quasi a fermarsi, cosi' l'ultimo terzo del tragitto e' la parte che si vede
 * meglio: e' dove si sta guardando quando finisce.
 *
 * Chi ha chiesto meno movimento lo ottiene comunque dalla regola globale
 * `prefers-reduced-motion` in `index.css`, che azzera ogni durata.
 */
const MOVIMENTO = "360ms cubic-bezier(0.32, 0.72, 0, 1)";

/** La comparsa e la sparizione della scheda: breve, perche' non c'e' niente da
 *  seguire — una cosa che c'e' o non c'e'. */
const COMPARSA = "160ms ease-out";

/** Quello che serve per disegnare la guida, e per sapere che c'e'. */
export interface Guida {
  /** Il passo sullo schermo, o `null` se la guida e' finita o saltata. */
  passo: number | null;
  salta: () => void;
  prosegui: () => void;
}

/**
 * Lo stato della guida, tenuto **da chi disegna la colonna** e non qui dentro.
 *
 * Serve in due posti: la guida, e lo stato vuoto sotto — che finche' la guida
 * c'e' tace la propria riga di spiegazione, perche' e' la versione in una frase
 * di cio' che i primi due passi dicono per esteso. Due copie della stessa cosa
 * sulla primissima schermata sono il difetto che questa guida dovrebbe evitare e
 * non introdurre.
 *
 * Un hook e non un contesto: i due che lo leggono stanno nello stesso
 * componente, e un provider in piu' in `App` direbbe che qualcun altro potrebbe
 * volerlo — mentre lo stato non deve uscire dalla chat.
 */
export function usaAvvio(): Guida {
  const [passo, setPasso] = useState<number | null>(() => {
    try {
      // Una cronologia non vuota e' la prova che la prima volta e' gia' passata:
      // la chiave e' nuova, e senza questa domanda il primo avvio dopo U-20
      // accoglierebbe con un tour chi usa la demo da settimane.
      return primoPasso(localStorage.getItem(DEPOSITO), leggiCronologia().length > 0);
    } catch {
      // Deposito negato (finestra privata, iframe): si mostra la guida, che e'
      // il caso in cui non si perde niente.
      return primoPasso(null, false);
    }
  });

  // Scrive **anche al primo disegno**, e non solo quando si clicca. Senza, chi
  // apre la guida e chiede qualcosa senza toccarla lascia il deposito vuoto e
  // la cronologia piena: tornando dalla pagina «Che cos'e'» la guida sarebbe
  // sparita da sola, a meta' lettura, per la regola qui sopra.
  useEffect(() => {
    try {
      localStorage.setItem(DEPOSITO, scrivi(passo));
    } catch {
      // Vale per questa sessione: non ricordarla e' meno grave che non mostrarla.
    }
  }, [passo]);

  const salta = useCallback(() => setPasso(null), []);
  const prosegui = useCallback(() => setPasso((p) => (p === null ? null : avanti(p))), []);

  return useMemo(() => ({ passo, salta, prosegui }), [passo, salta, prosegui]);
}

/** La zona in px di disegno, o `null` se quel passo non ha un bersaglio sullo
 *  schermo. Fuori da React perche' non dipende da niente di React. */
function leggiZona(id: Passo["id"]): Rettangolo | null {
  const nodo = document.querySelector(`[${ATTRIBUTO}="${id}"]`);
  if (nodo === null) return null;

  const r = nodo.getBoundingClientRect();
  if (r.width === 0 && r.height === 0) return null;

  const z = scala();
  return { x: r.left / z, y: r.top / z, larghezza: r.width / z, altezza: r.height / z };
}

function finestraOra(): Misura {
  const z = scala();
  return { larghezza: window.innerWidth / z, altezza: window.innerHeight / z };
}

/** Uguali abbastanza da non ridisegnare: sotto il mezzo pixel non si vede, e
 *  aggiornare lo stato a ogni frazione sarebbe un ciclo di render continuo. */
function stessaZona(a: Rettangolo | null, b: Rettangolo | null): boolean {
  if (a === null || b === null) return a === b;
  return (
    Math.abs(a.x - b.x) < 0.5 &&
    Math.abs(a.y - b.y) < 0.5 &&
    Math.abs(a.larghezza - b.larghezza) < 0.5 &&
    Math.abs(a.altezza - b.altezza) < 0.5
  );
}

export function Avvio({ guida }: { guida: Guida }) {
  const { passo } = guida;
  const id = passo === null ? null : PASSI[passo].id;

  const [zona, setZona] = useState<Rettangolo | null>(null);
  const [finestra, setFinestra] = useState<Misura | null>(null);

  // Un giro solo finche' la guida e' aperta. La zona si rilegge a intervalli e
  // lo stato cambia solo quando e' cambiata davvero: vedi la nota in testa sul
  // perche' non bastano gli eventi.
  useLayoutEffect(() => {
    if (id === null) return;

    let frame = 0;
    let ultima = 0;

    const giro = (ora: number) => {
      frame = requestAnimationFrame(giro);
      if (ora - ultima < RILETTURA_MS) return;
      ultima = ora;

      const letta = leggiZona(id);
      setZona((prima) => (stessaZona(prima, letta) ? prima : letta));
      setFinestra((prima) => {
        const f = finestraOra();
        return prima !== null && prima.larghezza === f.larghezza && prima.altezza === f.altezza
          ? prima
          : f;
      });
    };

    frame = requestAnimationFrame(giro);
    return () => cancelAnimationFrame(frame);
  }, [id]);

  // **Escape non salta la guida, ed e' una deroga voluta.** In questa
  // interfaccia Escape chiude cio' che si e' aperto sopra il contenuto — la
  // tendina, la bolla — e quelle cose si riaprono. Qui la stessa pressione
  // prenderebbe una decisione **definitiva**, e due dei quattro passi indicano
  // proprio una zona che contiene una tendina: chi la chiude con Escape si
  // ritroverebbe la guida via per sempre senza averlo chiesto. Il comando solo
  // che il criterio chiede e' «Salta», e si vede.

  // **Memorizzato, e non e' ottimizzazione prematura.** Questo componente sta
  // dentro la chat, che ridisegna a ogni token in arrivo: un contorno nuovo a
  // ogni giro rifarebbe la misura della scheda una volta per parola, mentre la
  // risposta scorre. Le due misure da cui dipende cambiano dieci volte al
  // secondo al massimo, e solo quando cambiano davvero.
  //
  // `null` quando il passo non ha un bersaglio su questo schermo, e non una
  // finta zona grande quanto la finestra: e' `collocaScheda` a sapere dove va
  // una scheda che non indica niente, e passargli il caso com'e' invece di
  // camuffarlo e' cio' che gli permette di distinguerlo.
  const contorno = useMemo(
    () => (finestra === null || zona === null ? null : alone(zona, finestra)),
    [zona, finestra],
  );

  if (passo === null || id === null || finestra === null) return null;

  return createPortal(
    <Strato guida={guida} id={id} contorno={contorno} finestra={finestra} />,
    document.body,
  );
}

/**
 * Lo strato sopra tutto: il velo con il suo buco, e la scheda.
 *
 * Un componente a parte perche' la scheda **si misura**: la sua altezza dipende
 * da dove il testo va a capo, e nessuno la sa prima di averla disegnata. Due
 * passate, come la bolla del suggerimento — invisibile per essere misurata, poi
 * collocata, poi accesa. Accenderla prima la farebbe comparire in alto a
 * sinistra per un fotogramma.
 */
const Strato = memo(function Strato({
  guida,
  id,
  contorno,
  finestra,
}: {
  guida: Guida;
  id: Passo["id"];
  contorno: Rettangolo | null;
  finestra: Misura;
}) {
  const { t, lingua } = usaLingua();
  const { passo, salta, prosegui } = guida;
  const scheda = useRef<HTMLDivElement>(null);
  const [posa, setPosa] = useState<PosaScheda | null>(null);
  const [posata, setPosata] = useState(false);

  useLayoutEffect(() => {
    const c = scheda.current?.getBoundingClientRect();
    if (!c) return;
    const z = scala();
    const nuova = collocaScheda(
      contorno,
      { larghezza: c.width / z, altezza: c.height / z },
      finestra,
    );
    setPosa((prima) =>
      prima !== null && prima.x === nuova.x && prima.y === nuova.y && prima.lato === nuova.lato
        ? prima
        : nuova,
    );
    // `lingua` fra le dipendenze e non per scrupolo: cambiandola cambia il
    // testo, quindi l'altezza della scheda, quindi dove va messa. Senza,
    // passando a EN la scheda resterebbe ancorata all'angolo di prima e
    // crescerebbe in basso — nel caso `dentro` uscendo dalla zona che spiega.
  }, [contorno, finestra, id, lingua]);

  // Un fotogramma dopo la prima collocazione, e non insieme: se la transizione
  // fosse gia' accesa quando la posizione passa da (0, 0) a quella vera, il
  // primo disegno sarebbe un volo in diagonale dall'angolo dello schermo.
  useEffect(() => {
    if (posa === null || posata) return;
    const f = requestAnimationFrame(() => setPosata(true));
    return () => cancelAnimationFrame(f);
  }, [posa, posata]);

  if (passo === null) return null;
  const { titolo, testo } = PASSI[passo];
  const Glifo = GLIFO[id];
  const ultimo = passo === PASSI.length - 1;

  return (
    // Tutto lo strato lascia passare il puntatore: e' il criterio, non una
    // rifinitura. Solo la scheda lo riprende, perche' ha due bottoni.
    <div className="pointer-events-none fixed inset-0 z-50">
      {contorno !== null && (
        <>
          {/* Il velo: **uno strato solo**, fermo, ritagliato. Era l'ombra da
              9999 px dell'alone — piu' semplice, e incompatibile con la
              sfocatura: un'ombra scurisce, non sfoca, e per sfocare serve un
              elemento che **stia sopra** cio' che deve sfocare. Quattro
              rettangoli attorno alla zona lo farebbero, al prezzo di quattro
              sfocature rifatte a ogni fotogramma mentre si muovono; cosi'
              invece la sfocatura si calcola su uno strato che non si sposta
              mai, e a muoversi e' solo la forma che lo ritaglia. */}
          <div
            aria-hidden="true"
            style={{ clipPath: buco(contorno, finestra), transition: `clip-path ${MOVIMENTO}` }}
            className="absolute inset-0 bg-velo backdrop-blur-[3px]"
          />
          {/* L'alone **scivola** da una zona all'altra invece di saltarci: e' il
              movimento che rende leggibile il legame fra il passo di prima e
              quello dopo, ed e' il motivo per cui il ritaglio ha sempre lo
              stesso numero di vertici (vedi `buco`). Le quattro proprieta' per
              nome e non `all`: `all` interpolerebbe anche il colore del bordo,
              che non cambia mai. */}
          <div
            aria-hidden="true"
            style={{
              left: contorno.x,
              top: contorno.y,
              width: contorno.larghezza,
              height: contorno.altezza,
              transition: `left ${MOVIMENTO}, top ${MOVIMENTO}, width ${MOVIMENTO}, height ${MOVIMENTO}`,
            }}
            className="absolute rounded-[10px] border-2 border-accent"
          />
        </>
      )}

      <div
        ref={scheda}
        role="region"
        aria-label={t("start.title")}
        style={{
          left: posa?.x ?? 0,
          top: posa?.y ?? 0,
          width: LARGHEZZA,
          maxWidth: finestra.larghezza - 16,
          opacity: posa === null ? 0 : 1,
          // **Scivola solo dopo essere comparsa.** Alla prima collocazione la
          // scheda sta ancora a (0, 0) invisibile: con la transizione gia'
          // accesa la si vedrebbe attraversare lo schermo in diagonale
          // dall'angolo in alto a sinistra, che e' il difetto classico di
          // qualunque cosa che si posiziona dopo essersi misurata.
          transition: posata
            ? `left ${MOVIMENTO}, top ${MOVIMENTO}, opacity ${COMPARSA}`
            : `opacity ${COMPARSA}`,
        }}
        className="pointer-events-auto absolute rounded-lg border border-line-2 bg-surface px-3.5 py-3 shadow-carta"
      >
        {/* `aria-live`: cambiando passo cambia il testo di una regione gia'
            sullo schermo, e senza questo chi ascolta sentirebbe solo il proprio
            clic. */}
        <div aria-live="polite">
          <div className="flex items-baseline gap-2">
            <Glifo size={13} className="translate-y-px text-accent" />
            <h2 className="min-w-0 flex-1 text-[12.5px] font-semibold text-ink">{t(titolo)}</h2>
            {/* Mono e tabellare: e' una posizione in una serie, e cambiando passo
                le cifre non devono spostare il titolo. */}
            <span className="shrink-0 font-mono text-[10px] text-muted tabular-nums">
              {t("start.step", { n: passo + 1, tot: PASSI.length })}
            </span>
          </div>
          {/* Un'altezza minima di **quattro righe**, che e' quanto occupa il
              passo piu' lungo a questa larghezza. Senza, la scheda cambia
              altezza a ogni «Avanti» — e cambiando altezza si ricolloca, quindi
              scivolerebbe anche in verticale per una ragione che non ha niente
              a che vedere con la zona che sta indicando. */}
          <p className="mt-1.5 min-h-[6.4em] text-[12px] leading-[1.6] text-ink-2">{t(testo)}</p>
        </div>

        <p className="mt-2 text-[10.5px] leading-[1.45] text-muted">{t("start.local")}</p>

        {/* La riga dei comandi, e la lingua sta a sinistra insieme a loro invece
            che in cima accanto al contatore: e' una cosa che si fa, non un dato
            che si legge. */}
        <div className="mt-2.5 flex items-center justify-between gap-3">
          <Lingua />
          <div className="flex shrink-0 items-center gap-1.5">
            <Comando onClick={salta}>{t("start.skip")}</Comando>
            <Comando onClick={prosegui}>{ultimo ? t("start.done") : t("start.next")}</Comando>
          </div>
        </div>
      </div>
    </div>
  );
});

/**
 * L'altezza dei controlli nel piede della scheda, **dichiarata**.
 *
 * Tre bottoni in fila che prendono l'altezza dal proprio contenuto vengono fuori
 * di tre altezze diverse — 25, 26 e 24 px qui — e una differenza di un pixel non
 * si legge come una gerarchia, si legge come un errore. E' la lezione che la
 * corsia ha gia' pagato in U-19, dove sette comandi incolonnati avevano sette
 * altezze.
 */
const ALTO = "flex h-[26px] items-center rounded-md border border-line-2 transition-colors";

/** La veste dei due comandi: quella neutra della colonna — bordo sottile, testo
 *  attenuato — ed e' la stessa per tutti e due apposta. L'unico bottone pieno
 *  dell'interfaccia e' «Invia», e una guida non deve chiamare piu' forte del
 *  campo in cui si scrive. */
function Comando({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`${ALTO} px-[9px] text-[11px] whitespace-nowrap text-ink-2 hover:border-accent-2 hover:text-ink`}
    >
      {children}
    </button>
  );
}

/**
 * La lingua, dentro la scheda (chiesto da Marco).
 *
 * **Il selettore della corsia c'e' gia', e non basta.** Il velo lascia passare
 * il puntatore, quindi quella pastiglia in fondo alla corsia e' cliccabile anche
 * adesso — ma e' scurita, sfocata e piccola, cioe' e' esattamente cio' che la
 * guida sta dicendo di non guardare. Chi apre il programma e non legge
 * l'italiano deve poter cambiare lingua **prima** di decidere se questa
 * spiegazione gli interessa, e non dopo averla saltata.
 *
 * **Stessa grammatica della pastiglia in corsia**, non lo stesso componente:
 * quello e' dimensionato sulla griglia della corsia e ha gia' due varianti: una
 * terza lo farebbe servire un posto per cui non e' stato fatto. Cio' che non
 * puo' divergere e' il **modo di dire la stessa cosa** — tutte e due le sigle
 * visibili, quella viva in accento su fondo accento — e sono tre righe.
 *
 * Il suggerimento e' quello di sempre, ed e' l'unico posto in cui va detto:
 * questo cambia la cornice, non la lingua della risposta.
 */
function Lingua() {
  const { t, lingua, imposta } = usaLingua();
  const altra = LINGUE[(LINGUE.indexOf(lingua) + 1) % LINGUE.length];

  return (
    <Suggerimento testo={t("lang.hint")} fuoco={false} className="shrink-0">
      <button
        type="button"
        onClick={() => imposta(altra)}
        // L'`aria-label` porta il valore corrente perche' **sostituisce** il
        // testo dentro il bottone: senza, chi ascolta sentirebbe il nome del
        // comando e mai la lingua in cui si trova.
        aria-label={`${t("lang.label")}: ${lingua.toUpperCase()}`}
        className={`${ALTO} shrink-0 gap-0.5 px-[7px] text-[10px] text-muted hover:border-line`}
      >
        {LINGUE.map((l, i) => (
          <span key={l} className="flex items-center gap-0.5">
            {i > 0 && <span className="text-line-2">/</span>}
            <span
              className={
                l === lingua
                  ? "rounded-[3px] bg-accent-soft px-[3px] py-px font-semibold text-accent"
                  : "px-[3px] py-px"
              }
            >
              {l.toUpperCase()}
            </span>
          </span>
        ))}
      </button>
    </Suggerimento>
  );
}
