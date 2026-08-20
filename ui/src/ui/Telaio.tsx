/**
 * La corsia laterale e la colonna di lavoro: il telaio di tutte le schermate.
 *
 * E' il layout del mockup, e le sue misure vengono da li' — 190 px di corsia,
 * bordo a destra, superficie chiara contro la carta della colonna centrale.
 * Sta in un componente perche' le quattro schermate lo condividono: chat,
 * confronto, esploratore e fonte hanno tutte la stessa corsia, e una corsia che
 * cambia di larghezza passando da una schermata all'altra e' il difetto piu'
 * visibile che un'interfaccia possa avere.
 *
 * **Lingua e tema stanno in fondo alla corsia**, come nel mockup, e non piu'
 * in una testata: sono impostazioni dell'applicazione, non della pagina, e
 * quando la colonna centrale diventera' la chat non ci sara' nessuna testata
 * dove metterle.
 *
 * **La cronologia e' la parte che cresce**, quindi e' la sola che scorre: il
 * resto della corsia ha un'altezza che non dipende da quanto si e' lavorato.
 *
 * **«Esplora il corpus» sta sotto il dataset**, e non in fondo accanto a lingua
 * e tema: apre una vista *su quel dataset*, quindi appartiene a lui e non alle
 * impostazioni dell'applicazione. Fino a U-06 non c'era affatto, ed era la
 * regola giusta — un comando che non porta da nessuna parte e' lo stesso difetto
 * del controllo che gira a vuoto.
 *
 * ## La corsia si comprime (U-18)
 *
 * **Nella striscia resta cio' che un simbolo sa dire per intero.** Un comando
 * — nuova conversazione, esplora il corpus — e una scelta fra poche voci che
 * hanno un nome ciascuna — dataset, lingua, tema — stanno in 34 px: il pannello
 * che si apre e' largo quanto le voci, non quanto il bottone che lo apre. La
 * cronologia no, ed e' l'unica: e' un elenco di titoli gia' troncati una volta,
 * e il suo comando **riapre la corsia** dicendo perche'.
 *
 * **La striscia e' 48 px e non zero.** Le ragioni stanno in `corsia.ts`, insieme
 * alla griglia: una colonna a zero non e' chiusa, e' sparita.
 *
 * **Non si anima, ed e' una scelta.** Interpolare la traccia della griglia da
 * 200 a 48 px vuol dire rifare l'impaginazione della conversazione a ogni
 * fotogramma — mandare a capo il testo, ricollocare le pastiglie dei marcatori,
 * ridisegnare i verdetti — cioe' lo stesso costo per cui `Suggerimento` vieta lo
 * `scale` sul testo. Una transizione che scatta e' peggio di nessuna
 * transizione: dice che il programma sta faticando. Qui il cambio e' immediato e
 * il movimento resta dov'e' gratis, sulle bolle e sulle tendine.
 *
 * **La scelta si ricorda**, come le larghezze dell'esploratore (U-17) e per la
 * stessa ragione: e' una preferenza — «lo schermo che ho, lo voglio cosi'» — e
 * vale anche domani.
 */
import { useEffect, useState } from "react";
import type { ReactNode } from "react";

import { usaEsploratore } from "../app/esploratore";
import { usaLingua } from "../app/i18n";
import { usaTema } from "../app/theme";
import type { SceltaTema } from "../app/theme";
import { LINGUE } from "../i18n/strings";
import { DEPOSITO, griglia, leggi } from "./corsia";
import { Cronologia, CronologiaCompatta, NuovaCompatta } from "./Cronologia";
import { Etichetta } from "./Etichetta";
import { Chiaro, Corpus, Corsia, Scuro, Sistema } from "./Icona";
import type { PropsIcona } from "./Icona";
import { Marchio } from "./Marchio";
import { SelettoreDataset } from "./SelettoreDataset";
import { Selettore } from "./Selettore";
import { Suggerimento } from "./Suggerimento";

export function Telaio({ children, fianco }: { children: ReactNode; fianco?: ReactNode }) {
  const [chiusa, setChiusa] = useState(() => {
    try {
      return leggi(localStorage.getItem(DEPOSITO));
    } catch {
      // Deposito negato (finestra privata, iframe): si parte aperta, che e' il
      // caso in cui non si perde niente.
      return leggi(null);
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(DEPOSITO, chiusa ? "chiusa" : "aperta");
    } catch {
      // Vale per questa sessione: non ricordarla e' meno grave che rifiutarsi
      // di cambiarla.
    }
  }, [chiusa]);

  return (
    // `h-dvh` e non `min-h-dvh`: da qui in poi le colonne scorrono per conto
    // loro, e con un'altezza minima scorrerebbe la pagina intera portandosi via
    // la corsia e il campo di scrittura.
    <div
      // Le colonne sono uno stile in linea e non una classe: sono una misura
      // calcolata, e `corsia.ts` la calcola dove si puo' provarla.
      style={{ gridTemplateColumns: griglia(chiusa, fianco !== undefined) }}
      // `grid-rows-[minmax(0,1fr)]`: senza una riga dichiarata quella
      // implicita e' `auto`, cioe' alta quanto il contenuto -- e una colonna
      // piu' alta dello schermo la faceva crescere oltre `h-dvh` invece di
      // scorrere dentro di se'. E' lo stesso difetto delle due colonne del
      // confronto, un piano piu' su.
      className="grid h-dvh grid-rows-[minmax(0,1fr)] overflow-hidden bg-paper text-ink"
    >
      {chiusa ? (
        <Striscia apri={() => setChiusa(false)} />
      ) : (
        <CorsiaAperta chiudi={() => setChiusa(true)} />
      )}

      {/* `overflow-hidden` qui e' la rete: se una schermata futura sbaglia
          i propri vincoli, deborda dentro il suo riquadro invece di
          allungare la pagina e portarsi via la corsia. */}
      <main className="h-full min-h-0 min-w-0 overflow-hidden">{children}</main>
      {fianco}
    </div>
  );
}

/** La corsia larga: quella di sempre, piu' il comando che la chiude. */
function CorsiaAperta({ chiudi }: { chiudi: () => void }) {
  const { t } = usaLingua();

  return (
    // Niente `overflow-y-auto` qui: un contenitore di scorrimento ritaglia
    // cio' che esce dai suoi bordi, e la tendina del dataset -- che e'
    // posizionata in assoluto -- ne veniva tagliata. Lo scorrimento sta dentro
    // la cronologia, sull'elenco, che e' la sola parte che cresce.
    <aside className="flex flex-col gap-4 border-r border-line bg-surface px-3 py-3.5">
      {/* Il comando sta accanto al marchio e non in fondo: e' l'unica cosa qui
          che riguarda la corsia stessa invece di cio' che ci sta dentro, e la
          riga del marchio e' il bordo di questa colonna. */}
      <div className="flex items-center justify-between gap-2 px-1">
        <Marchio className="text-[19px]" />
        <BottoneCorsia chiusa={false} cambia={chiudi} className="h-[26px] w-[26px]" />
      </div>

      <div>
        <div className="mb-[7px] px-1">
          <Etichetta>{t("datasets.title")}</Etichetta>
        </div>
        <SelettoreDataset />
        <BottoneCorpus />
      </div>

      <Cronologia />

      <div className="mt-auto flex gap-1.5 px-1">
        <PastigliaLingua />
        <PastigliaTema />
      </div>
    </aside>
  );
}

/**
 * La corsia chiusa: gli stessi comandi, nello stesso ordine, senza le parole.
 *
 * L'ordine e' quello della corsia larga e non «i piu' usati in cima»: chi la
 * chiude ha appena visto l'altra, e trovare le stesse cose nelle stesse
 * posizioni e' cio' che rende il gesto reversibile invece di disorientante.
 *
 * Il marchio resta, in piccolo. Non e' decorazione: e' l'unica cosa che dice che
 * questa striscia di glifi appartiene ancora al programma di prima.
 */
function Striscia({ apri }: { apri: () => void }) {
  return (
    <aside className="flex flex-col gap-2 border-r border-line bg-surface px-[7px] py-3.5">
      <Marchio className="text-center text-[14px]" />
      <BottoneCorsia chiusa cambia={apri} className="h-[30px] w-full" />

      <SelettoreDataset compatta />
      <BottoneCorpus compatto />
      <NuovaCompatta />
      <CronologiaCompatta apri={apri} />

      <div className="mt-auto flex flex-col gap-1.5">
        <PastigliaLingua compatta />
        <PastigliaTema compatta />
      </div>
    </aside>
  );
}

/**
 * Apre e chiude la corsia. Un bottone solo, con due nomi.
 *
 * `aria-expanded` perche' e' esattamente cio' che dichiara: un controllo che
 * mostra e nasconde una regione. Senza, chi ascolta sentirebbe due comandi
 * diversi in due momenti diversi senza sapere che sono lo stesso.
 */
function BottoneCorsia({
  chiusa,
  cambia,
  className,
}: {
  chiusa: boolean;
  cambia: () => void;
  className: string;
}) {
  const { t } = usaLingua();
  const nome = chiusa ? t("rail.expand") : t("rail.collapse");

  return (
    <Suggerimento
      testo={chiusa ? t("rail.expand.hint") : t("rail.collapse.hint")}
      fuoco={false}
      className="block"
    >
      <button
        type="button"
        onClick={cambia}
        aria-label={nome}
        aria-expanded={!chiusa}
        className={`flex items-center justify-center rounded-md text-muted transition-colors hover:bg-surface-2 hover:text-ink ${className}`}
      >
        <Corsia size={chiusa ? 15 : 14} />
      </button>
    </Suggerimento>
  );
}

/**
 * «Esplora il corpus»: la schermata che guarda l'indice invece della risposta.
 *
 * Non e' disabilitato quando manca un dataset — non capita, perche' senza indice
 * pronto la corsia mostra gia' il proprio stato vuoto e questa colonna non
 * arriva a disegnarsi con una scelta a `null` che si possa cliccare.
 */
function BottoneCorpus({ compatto = false }: { compatto?: boolean }) {
  const { t } = usaLingua();
  const { apri } = usaEsploratore();

  if (compatto) {
    return (
      <Suggerimento testo={t("corpus.open.action")} fuoco={false} className="block">
        <button
          type="button"
          onClick={() => apri()}
          aria-label={t("corpus.open.action")}
          className="flex h-[34px] w-full items-center justify-center rounded-lg border border-line-2 text-ink-2 transition-colors hover:border-accent-2 hover:text-ink"
        >
          <Corpus size={14} />
        </button>
      </Suggerimento>
    );
  }

  return (
    <button
      type="button"
      onClick={() => apri()}
      className="mt-1.5 flex w-full items-center gap-2 rounded-lg border border-line-2 px-2.5 py-[7px] text-[11.5px] text-ink-2 transition-colors hover:border-accent-2 hover:text-ink"
    >
      <Corpus size={13} />
      {t("corpus.open.action")}
    </button>
  );
}

/** La pastiglia in fondo alla corsia: bordo sottile, testo attenuato. Le due
 *  misure sono separate perche' due classi in conflitto nella stessa stringa non
 *  si risolvono nell'ordine in cui sono scritte — vince l'ordine del foglio. */
const PASTIGLIA = "rounded-[5px] border border-line-2 text-muted";
const PASTIGLIA_LARGA = `${PASTIGLIA} px-[7px] py-1 text-[10px]`;
const PASTIGLIA_STRETTA = `${PASTIGLIA} px-1 text-[9px]`;

/**
 * `IT / EN` come nel mockup, e resta un bottone.
 *
 * Con **due** stati il bottone e' la forma giusta: si vedono entrambi, si vede
 * quale e' vivo, e un clic porta all'altro senza aprire niente. Una tendina di
 * due voci farebbe fare due gesti dove ne basta uno, e nasconderebbe meta'
 * dell'informazione dietro il primo.
 *
 * La lingua viva e' **accento su fondo accento**, che nel mockup e' il modo in
 * cui un controllo dice «questo e' acceso» (`.tg.on`). Prima era solo un grigio
 * un po' meno spento di un altro: a 10 px la differenza fra `ink` e `muted`
 * esiste sulla carta e non sullo schermo, e chi guardava doveva indovinare.
 *
 * L'`aria-label` porta il valore corrente perche' **sostituisce** il testo
 * dentro il bottone: senza, chi ascolta sentirebbe il nome del comando e mai la
 * lingua in cui si trova — proprio il dato che l'evidenziazione aggiunge per
 * chi guarda.
 *
 * Nella striscia le due sigle si **impilano** invece di stare in riga. E' il
 * modo di non perdere l'unica cosa che questo controllo fa meglio di una
 * tendina: mostrare tutte e due le lingue e quale delle due e' viva. Tenerle
 * affiancate avrebbe voluto dire mostrarne una sola, cioe' trasformarlo in un
 * bottone che cicla — la forma criticata due funzioni piu' sotto.
 */
function PastigliaLingua({ compatta = false }: { compatta?: boolean }) {
  const { t, lingua, imposta } = usaLingua();
  const altra = LINGUE[(LINGUE.indexOf(lingua) + 1) % LINGUE.length];

  return (
    // Il suggerimento sta **qui** e non sotto gli esempi: la frase ha bisogno che
    // si veda cosa cambia, e cosa cambia e' questo controllo. Con
    // `fuoco={false}` la tappa di tabulazione resta una — quella del bottone — e la
    // bolla si apre comunque da tastiera, perche' `focus` risale dal figlio.
    <Suggerimento testo={t("lang.hint")} fuoco={false} className={compatta ? "block" : ""}>
      <button
        type="button"
        onClick={() => imposta(altra)}
        aria-label={`${t("lang.label")}: ${lingua.toUpperCase()}`}
        className={`${compatta ? PASTIGLIA_STRETTA : PASTIGLIA_LARGA} flex transition-colors hover:border-line ${
          compatta ? "w-full flex-col items-stretch gap-px py-1" : "items-center gap-0.5 py-1"
        }`}
      >
        {LINGUE.map((l, i) => (
          <span
            key={l}
            className={compatta ? "block" : "flex items-center gap-0.5"}
            // Il separatore ha senso in riga; impilate, due sigle una sopra
            // l'altra sono gia' due cose.
          >
            {i > 0 && !compatta && <span className="text-line-2">/</span>}
            <span
              className={`${compatta ? "block text-center" : "px-[3px]"} ${
                l === lingua
                  ? "rounded-[3px] bg-accent-soft py-px font-semibold text-accent"
                  : "py-px"
              }`}
            >
              {l.toUpperCase()}
            </span>
          </span>
        ))}
      </button>
    </Suggerimento>
  );
}

const TEMI: SceltaTema[] = ["light", "dark", "system"];
const SEGNO: Record<SceltaTema, (p: PropsIcona) => ReactNode> = {
  light: Chiaro,
  dark: Scuro,
  system: Sistema,
};

/**
 * Il tema e' **una tendina**, non un bottone che cicla.
 *
 * Con tre stati un bottone che gira nasconde le opzioni: non si vede quante
 * sono, non si sa dove si finisce, e per tornare indietro di uno si fa il giro.
 * Chi non ha ancora capito che «sistema» esiste non ha modo di scoprirlo se non
 * cliccando finche' non ricompare — cioe' l'interfaccia si impara per tentativi.
 * La tendina mostra le tre voci insieme e ne fa scegliere una.
 *
 * Il caret lo mette `Selettore`, uguale su ogni tendina, e ruota di mezzo giro
 * all'apertura: nel mockup e' il segno che distingue una pastiglia che apre un
 * menu (`.tg.menu`) da una che commuta e basta, ed e' il modo in cui questa e
 * la lingua si dichiarano diverse.
 *
 * Il **nome** dello stato sta accanto al glifo perche' «sistema» non e'
 * deducibile da un simbolo, ed e' proprio quello che va capito: e' l'unico che
 * continua a cambiare da solo. Nella striscia non ci sta, e finisce
 * nell'`aria-label` — ma le tre voci col loro nome restano nel pannello, che e'
 * dove il problema di «sistema» si risolve davvero.
 */
function PastigliaTema({ compatta = false }: { compatta?: boolean }) {
  const { t } = usaLingua();
  const { scelta, imposta } = usaTema();
  const Segno = SEGNO[scelta];

  // Le icone tornano nella lista: le voci di un `<option>` nativo potevano
  // essere solo testo, ed era l'unico posto dell'interfaccia in cui il
  // simbolo restava un glifo. Con la lista disegnata da noi, no.
  const voci = TEMI.map((s) => {
    const Segno = SEGNO[s];
    return { valore: s, testo: t(`theme.${s}`), icona: <Segno size={12} /> };
  });

  return (
    <Selettore
      etichetta={compatta ? `${t("theme.label")}: ${t(`theme.${scelta}`)}` : t("theme.label")}
      valore={scelta}
      voci={voci}
      onCambia={imposta}
      verso="su"
      className={`${compatta ? PASTIGLIA_STRETTA : PASTIGLIA_LARGA} flex items-center ${
        compatta ? "justify-center py-1.5" : "gap-1.5"
      }`}
    >
      <Segno size={12} />
      {!compatta && <span className="lowercase">{t(`theme.${scelta}`)}</span>}
    </Selettore>
  );
}
