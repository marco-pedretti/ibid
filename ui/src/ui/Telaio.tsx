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
 *
 * ## Il telefono (U-21)
 *
 * Sotto la soglia di `schermo.ts` il telaio ha **una colonna sola**, e le due
 * laterali non spariscono: escono dalla griglia e diventano due strati che si
 * aprono sopra il lavoro — la corsia da sinistra, le fonti da destra. Il
 * criterio di U-02 dice «raggiungibile in ogni stato, non necessariamente
 * affiancata», ed e' esattamente questa la differenza fra le due parole.
 *
 * **Una testata compare solo qui.** Nelle colonne non serve — il marchio sta in
 * cima alla corsia e le fonti sono gia' sullo schermo — e infatti in tutta la
 * Fase 8 non ce n'e' mai stata una. Stretta serve: e' l'unico posto dove
 * possono stare i due comandi che riaprono cio' che e' uscito dalla griglia, e
 * il marchio ci torna perche' altrimenti il programma non direbbe piu' il
 * proprio nome da nessuna parte.
 *
 * **Il cassetto si chiude su cio' che cambia schermata, e non su cio' che
 * cambia un'impostazione.** Nuova conversazione, una voce di cronologia,
 * l'esploratore, «Che cos'e'»: quei quattro portano da un'altra parte, e
 * lasciare il cassetto aperto sopra la cosa appena aperta sarebbe fare il gesto
 * a meta'. Dataset, lingua e tema no: si cambiano **per** guardare quello che
 * c'e' sotto, e chiudersi addosso costringerebbe a riaprire per cambiare la
 * seconda. Chi naviga si dichiara — `usaChiudiCassetto()` — che e' la stessa
 * forma con cui in U-20 una zona si dichiara bersaglio della guida.
 */
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { usaEsploratore } from "../app/esploratore";
import { usaLingua } from "../app/i18n";
import { usaPresentazione } from "../app/presentazione";
import { usaTema } from "../app/theme";
import type { SceltaTema } from "../app/theme";
import { LINGUE } from "../i18n/strings";
import { zona } from "./Avvio";
import { Chiusura, usaChiudiCassetto } from "./cassetto";
import { APERTA, DEPOSITO, FIANCO, leggi } from "./corsia";
import { Cronologia, CronologiaCompatta, NuovaCompatta } from "./Cronologia";
import { Etichetta } from "./Etichetta";
import { Chiaro, Corpus, Corsia, Indice, Informazioni, Scuro, Sistema } from "./Icona";
import type { PropsIcona } from "./Icona";
import { Marchio } from "./Marchio";
import { usaUltimaRisposta } from "./PannelloFonti";
import { colonne, forma } from "./schermo";
import type { Forma } from "./schermo";
import { scala } from "./scala";
import { SelettoreDataset } from "./SelettoreDataset";
import { Selettore } from "./Selettore";
import { Strato } from "./Strato";
import { Suggerimento } from "./Suggerimento";

/**
 * La forma del telaio, per chi ci sta dentro.
 *
 * Un contesto e non un hook per ciascuno: la larghezza della finestra e' una
 * cosa sola, e tre componenti che la misurano per conto proprio sono tre
 * ascoltatori e — quel che conta di piu' — tre posti in cui la soglia puo'
 * divergere. Il telaio e' anche l'unico che la puo' provvedere senza aggiungere
 * un provider in `App`: avvolge gia' tutte e quattro le schermate.
 */
const Contesto = createContext<Forma>("larga");

export function usaForma(): Forma {
  return useContext(Contesto);
}

/**
 * La forma che la finestra impone, adesso.
 *
 * **Si converte al confine**, come vuole `scala.ts`: `innerWidth` arriva in px
 * di finestra e la soglia e' scritta in px di disegno. Sotto i 1.400 px le due
 * coincidono — lo prova un test in `schermo.test.ts` — ma dividere e' la regola
 * della casa, e una regola che si applica solo dove serve non e' una regola.
 *
 * `resize` e non una media query: la soglia e' un numero derivato dalle colonne
 * (`schermo.ts`), e riscriverlo in CSS lo renderebbe un secondo posto da tenere
 * d'accordo. Ed e' comunque la **struttura** a cambiare, non solo lo stile.
 */
function usaFormaDellaFinestra(): Forma {
  const [f, setF] = useState<Forma>(() => forma(window.innerWidth / scala()));

  useEffect(() => {
    const misura = () => setF(forma(window.innerWidth / scala()));
    misura();
    window.addEventListener("resize", misura, { passive: true });
    return () => window.removeEventListener("resize", misura);
  }, []);

  return f;
}

export function Telaio({ children, fianco }: { children: ReactNode; fianco?: ReactNode }) {
  const { t } = usaLingua();
  const f = usaFormaDellaFinestra();
  const conFonti = fianco !== undefined;
  const [cassetto, setCassetto] = useState(false);
  const [foglio, setFoglio] = useState(false);
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

  // Tornando alle colonne, cio' che era stato tirato fuori rientra: uno strato
  // rimasto aperto starebbe sopra la colonna che disegna la stessa cosa.
  useEffect(() => {
    if (f === "larga") {
      setCassetto(false);
      setFoglio(false);
    }
  }, [f]);

  // Le fonti se ne vanno con la schermata che le ha: aperto il foglio su una
  // risposta e poi l'esploratore, resterebbe un pannello che parla di una
  // risposta che non e' piu' sullo schermo.
  useEffect(() => {
    if (!conFonti) setFoglio(false);
  }, [conFonti]);

  const chiudiCassetto = useCallback(() => setCassetto(false), []);

  // Escape chiude cio' che si e' aperto sopra il contenuto, come dappertutto
  // qui dentro. `defaultPrevented` perche' dentro il cassetto ci sono tendine
  // che Escape chiude per prime: senza, un Escape ne chiuderebbe due.
  useEffect(() => {
    if (!cassetto && !foglio) return;
    const tasto = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented) return;
      setCassetto(false);
      setFoglio(false);
    };
    window.addEventListener("keydown", tasto);
    return () => window.removeEventListener("keydown", tasto);
  }, [cassetto, foglio]);

  return (
    <Contesto.Provider value={f}>
      <Chiusura.Provider value={chiudiCassetto}>
        {/* `h-full` e non `h-dvh`: le due sarebbero equivalenti — `html` e
            `body` sono al 100% in `index.css` — se non fosse per lo `zoom`
            della radice. Misurato in Chromium e in Firefox: un'unita' di
            viewport si risolve nel viewport **non scalato** e poi viene
            moltiplicata per lo zoom, quindi `100dvh` valeva 960 px in una
            finestra da 800 e la barra sotto il campo finiva fuori. Una
            percentuale no: risolve dentro lo spazio gia' scalato e torna
            esatta. Resta un'altezza fissa e non minima — da qui in poi le
            colonne scorrono per conto loro, e con `min-h-` scorrerebbe la
            pagina intera portandosi via la corsia e il campo di scrittura. */}
        <div className="flex h-full flex-col overflow-hidden bg-paper text-ink">
          {f === "stretta" && (
            <Testata
              apriCorsia={() => setCassetto(true)}
              apriFonti={conFonti ? () => setFoglio(true) : null}
            />
          )}

          <div
            // Le colonne sono uno stile in linea e non una classe: sono una
            // misura calcolata, e `schermo.ts` la calcola dove si puo' provarla.
            style={{ gridTemplateColumns: colonne(f, chiusa, conFonti) }}
            // `grid-rows-[minmax(0,1fr)]`: senza una riga dichiarata quella
            // implicita e' `auto`, cioe' alta quanto il contenuto -- e una
            // colonna piu' alta dello schermo la faceva crescere oltre
            // l'altezza piena invece di scorrere dentro di se'. E' lo stesso
            // difetto delle due colonne del confronto, un piano piu' su.
            className="grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)] overflow-hidden"
          >
            {f === "larga" &&
              (chiusa ? (
                <Striscia apri={() => setChiusa(false)} />
              ) : (
                <CorsiaAperta chiudi={() => setChiusa(true)} />
              ))}

            {/* `overflow-hidden` qui e' la rete: se una schermata futura sbaglia
                i propri vincoli, deborda dentro il suo riquadro invece di
                allungare la pagina e portarsi via la corsia. */}
            <main className="h-full min-h-0 min-w-0 overflow-hidden">{children}</main>
            {f === "larga" && fianco}
          </div>
        </div>

        {f === "stretta" && cassetto && (
          <Strato lato="sinistra" larghezza={APERTA} chiudi={chiudiCassetto} nome={t("rail.close")}>
            <CorsiaAperta chiudi={chiudiCassetto} nelCassetto />
          </Strato>
        )}

        {f === "stretta" && foglio && conFonti && (
          <Strato
            lato="destra"
            larghezza={FIANCO}
            chiudi={() => setFoglio(false)}
            nome={t("sources.close")}
          >
            {fianco}
          </Strato>
        )}
      </Chiusura.Provider>
    </Contesto.Provider>
  );
}

/**
 * La testata che compare solo a colonna sola.
 *
 * Tre cose e nient'altro: il comando che riapre la corsia, il marchio, e — dove
 * c'e' una risposta di cui parlano — le fonti. Non e' il posto in cui accumulare
 * i comandi della schermata sotto: quelli stanno dove sono sempre stati, e una
 * testata che cambia contenuto passando da una schermata all'altra sarebbe lo
 * stesso difetto della corsia che cambia larghezza.
 *
 * Il marchio e' **piu' piccolo** che nella corsia (17 contro 19 px), e qui e'
 * giusto: nella striscia di U-18 non rimpiccioliva perche' li' era l'unica cosa
 * rimasta a dire il nome del programma, mentre una testata e' una riga di
 * comandi e un marchio della stessa misura di un titolo direbbe di essere il
 * titolo della pagina.
 */
function Testata({
  apriCorsia,
  apriFonti,
}: {
  apriCorsia: () => void;
  apriFonti: (() => void) | null;
}) {
  return (
    <header className="flex shrink-0 items-center gap-2 border-b border-line bg-surface px-2.5 py-1.5">
      <BottoneCorsia chiusa cambia={apriCorsia} className="h-[34px] w-[34px]" />
      <Marchio className="text-[17px]" />
      {apriFonti !== null && <BottoneFonti apri={apriFonti} />}
    </header>
  );
}

/**
 * Le fonti, da una colonna sola: il comando, e **quante ne sono arrivate**.
 *
 * Il numero non e' un ornamento. Nelle colonne il pannello e' sempre sullo
 * schermo e si riempie mentre la risposta nasce — e' la ragione per cui U-02 lo
 * voleva affiancato; chiuso dentro un foglio, quel riempirsi non si vedrebbe
 * piu' e le fonti tornerebbero a essere una funzione da andare a cercare. Il
 * conteggio e' la parte di quel segnale che sta in una testata.
 *
 * `zona("fonti")` sta qui perche' a colonna sola **questo** e' il posto delle
 * fonti. Il pannello dentro il foglio porta lo stesso attributo, ma e' nel DOM
 * dopo di noi e solo mentre il foglio e' aperto: la guida trova prima questo, e
 * indica il comando invece di una colonna che non c'e'.
 */
function BottoneFonti({ apri }: { apri: () => void }) {
  const { t } = usaLingua();
  const risposta = usaUltimaRisposta();
  const quante = risposta?.chunks.length ?? 0;

  return (
    <Suggerimento testo={t("sources.open.hint")} fuoco={false} className="ml-auto">
      <button
        {...zona("fonti")}
        type="button"
        onClick={apri}
        className="flex h-[34px] items-center gap-1.5 rounded-[7px] border border-line-2 px-2.5 text-[11.5px] text-ink-2 transition-colors hover:border-accent-2 hover:text-ink"
      >
        <Indice size={13} />
        {t("sources.title")}
        {quante > 0 && (
          <span className="rounded bg-accent px-[5px] py-px font-mono text-[10px] font-semibold text-accent-ink tabular-nums">
            {quante}
          </span>
        )}
      </button>
    </Suggerimento>
  );
}

/** La corsia larga: quella di sempre, piu' il comando che la chiude. */
function CorsiaAperta({
  chiudi,
  nelCassetto = false,
}: {
  chiudi: () => void;
  nelCassetto?: boolean;
}) {
  const { t } = usaLingua();

  return (
    // Niente `overflow-y-auto` qui: un contenitore di scorrimento ritaglia
    // cio' che esce dai suoi bordi, e la tendina del dataset -- che e'
    // posizionata in assoluto -- ne veniva tagliata. Lo scorrimento sta dentro
    // la cronologia, sull'elenco, che e' la sola parte che cresce.
    <aside className="flex h-full flex-col gap-4 border-r border-line bg-surface px-3 py-3.5">
      {/* Il comando sta accanto al marchio e non in fondo: e' l'unica cosa qui
          che riguarda la corsia stessa invece di cio' che ci sta dentro, e la
          riga del marchio e' il bordo di questa colonna. */}
      <div className="flex items-center justify-between gap-2 px-1">
        <Marchio className="text-[19px]" />
        <BottoneCorsia
          chiusa={false}
          nelCassetto={nelCassetto}
          cambia={chiudi}
          className="h-[26px] w-[26px]"
        />
      </div>

      <div {...zona("corpus")}>
        <div className="mb-[7px] px-1">
          <Etichetta>{t("datasets.title")}</Etichetta>
        </div>
        <SelettoreDataset />
        <BottoneCorpus />
      </div>

      <Cronologia />

      {/* Due righe e non una: le tre cose affiancate non ci stavano — misurate,
          185 px dentro 175 — e la prima ha comunque un'aria diversa dalle altre
          due. Lingua e tema sono due valori che si commutano; «Che cos'e'» apre
          una schermata, come «Esplora il corpus», e ne porta la stessa forma. */}
      <div className="mt-auto flex flex-col gap-1.5">
        <BottoneInfo />
        {/* Il tema prende quel che resta: cosi' la riga finisce dove finiscono
            i comandi qui sopra, invece di lasciare ventisette pixel di vuoto a
            destra. La lingua no — le sue due sigle hanno una larghezza loro, e
            allargarla le separerebbe senza motivo. */}
        <div className="flex gap-1.5">
          <PastigliaLingua />
          <div className="min-w-0 flex-1">
            <PastigliaTema />
          </div>
        </div>
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
 * Il marchio resta, **e resta della sua misura**. Non e' decorazione: e' l'unica
 * cosa che dice che questa striscia di glifi appartiene ancora al programma di
 * prima, e un marchio che rimpicciolisce insieme alla colonna che lo contiene lo
 * direbbe piu' piano proprio dove ce n'e' piu' bisogno. E' anche la regola che
 * questo componente ha gia': una corsia che cambia di larghezza fra due
 * schermate e' il difetto piu' visibile che un'interfaccia possa avere, e un
 * marchio che cambia di corpo fra due stati e' lo stesso difetto in piccolo.
 */
function Striscia({ apri }: { apri: () => void }) {
  return (
    <aside className="flex flex-col gap-2 border-r border-line bg-surface px-[7px] py-3.5">
      {/* Il marchio non rimpicciolisce con la corsia: e' l'unica cosa che dice
          che questa striscia di glifi appartiene ancora al programma di prima, e
          scritta piu' piccola lo direbbe piu' piano proprio dove serve di piu'.
          I 19 px pero' non stanno nei 34 px che restano fra i due margini —
          «ibid» in Georgia ne misura ~32 — quindi qui il margine si annulla e la
          riga si prende tutti e 48. `whitespace-nowrap` e' la rete per un serif
          piu' largo di quelli previsti: meglio che sporga di un pelo, che
          spezzarsi in due righe. */}
      <Marchio className="-mx-[7px] block text-center text-[19px] whitespace-nowrap" />
      <BottoneCorsia chiusa cambia={apri} className="h-[34px] w-full" />

      {/* Gli stessi due della corsia larga, in un contenitore che ripete il
          suo passo: la zona che la guida indica deve essere una sola cosa in
          tutti e due gli stati, altrimenti l'alone cambia di senso comprimendo
          la corsia. */}
      <div {...zona("corpus")} className="flex flex-col gap-2">
        <SelettoreDataset compatta />
        <BottoneCorpus compatto />
      </div>
      <NuovaCompatta />
      <CronologiaCompatta apri={apri} />

      <div className="mt-auto flex flex-col gap-1.5">
        <BottoneInfo compatto />
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
  nelCassetto = false,
}: {
  chiusa: boolean;
  cambia: () => void;
  className: string;
  nelCassetto?: boolean;
}) {
  const { t } = usaLingua();
  // Dentro il cassetto lo stesso bottone non **comprime**: chiude, e non resta
  // nessuna striscia di comandi. Dirlo lo stesso sarebbe promettere un ripiego
  // che a colonna sola non esiste.
  const nome = nelCassetto ? t("rail.close") : chiusa ? t("rail.expand") : t("rail.collapse");
  const bolla = nelCassetto
    ? t("rail.close.hint")
    : chiusa
      ? t("rail.expand.hint")
      : t("rail.collapse.hint");

  return (
    <Suggerimento testo={bolla} fuoco={false} className="block">
      <button
        type="button"
        onClick={cambia}
        aria-label={nome}
        aria-expanded={!chiusa}
        className={`flex items-center justify-center rounded-[7px] text-muted transition-colors hover:bg-surface-2 hover:text-ink ${className}`}
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
  // Cambia schermata, quindi si porta via il cassetto: vedi `cassetto.ts`.
  const chiudiCassetto = usaChiudiCassetto();
  const vai = () => {
    apri();
    chiudiCassetto();
  };

  if (compatto) {
    return (
      <Suggerimento testo={t("corpus.open.action")} fuoco={false} className="block">
        <button
          type="button"
          onClick={vai}
          aria-label={t("corpus.open.action")}
          className="flex h-[34px] w-full items-center justify-center rounded-[7px] border border-line-2 text-ink-2 transition-colors hover:border-accent-2 hover:text-ink"
        >
          <Corpus size={14} />
        </button>
      </Suggerimento>
    );
  }

  return (
    <button
      type="button"
      onClick={vai}
      className="mt-1.5 flex h-[34px] w-full items-center gap-2 rounded-[7px] border border-line-2 px-2.5 text-[11.5px] text-ink-2 transition-colors hover:border-accent-2 hover:text-ink"
    >
      <Corpus size={13} />
      {t("corpus.open.action")}
    </button>
  );
}

/**
 * La pastiglia in fondo alla corsia: bordo sottile, testo attenuato.
 *
 * **L'altezza e' dichiarata, non dedotta dal contenuto.** Erano 27 px la lingua
 * e 25 il tema nella corsia larga, 42 e 26 nella striscia — perche' una porta
 * due sigle impilate e l'altro un glifo, e la scatola seguiva. Due controlli
 * affiancati che differiscono di due pixel non si leggono come due misure, si
 * leggono come un errore; nella striscia, dove sono uno sopra l'altro in una
 * colonna di celle da 34, quella da 42 rompe il ritmo di tutte.
 *
 * Le due misure restano costanti separate perche' due classi in conflitto nella
 * stessa stringa non si risolvono nell'ordine in cui sono scritte — vince
 * l'ordine del foglio.
 */
const PASTIGLIA = "rounded-[7px] border border-line-2 text-muted";
const PASTIGLIA_LARGA = `${PASTIGLIA} h-[26px] px-[7px] text-[10px]`;
const PASTIGLIA_STRETTA = `${PASTIGLIA} h-[34px] px-1 text-[9px]`;

/**
 * «Che cos'e'»: la pagina che presenta il progetto (U-19).
 *
 * **Sta in fondo, sopra lingua e tema**, e quel gruppo non e' «le impostazioni»:
 * e' cio' che riguarda l'applicazione invece della conversazione o del corpus.
 * Sopra c'e' il dataset, che e' il corpus, e la cronologia, che e' la
 * conversazione; una pagina che dice cosa fa il programma non appartiene a
 * nessuno dei due.
 *
 * **Ha la forma di «Esplora il corpus» e non di una pastiglia**, perche' fa la
 * stessa cosa: apre una schermata. Lingua e tema commutano un valore e restano
 * dove sono — accanto a loro questo bottone sarebbe stato un terzo oggetto della
 * stessa taglia con un comportamento diverso, e per giunta non ci stava: misurati,
 * i tre affiancati chiedono 185 px dove la corsia ne ha 175.
 *
 * **La parola c'e' finche' c'e' posto.** Nella striscia resta il solo glifo, come
 * per gli altri comandi, e il nome passa nell'`aria-label` e nella bolla.
 */
function BottoneInfo({ compatto = false }: { compatto?: boolean }) {
  const { t } = usaLingua();
  const { apri } = usaPresentazione();
  const chiudiCassetto = usaChiudiCassetto();
  const vai = () => {
    apri();
    chiudiCassetto();
  };

  // Il `div` esiste per la guida e non per l'impaginazione: `Suggerimento` non
  // inoltra attributi, e la zona va dichiarata su qualcosa che sta nel DOM.
  // Nella colonna in cui vive e' un blocco fra blocchi, quindi non sposta niente.
  if (compatto) {
    return (
      <div {...zona("resta")}>
        <Suggerimento testo={t("about.hint")} fuoco={false} className="block">
          <button
            type="button"
            onClick={vai}
            aria-label={t("about.action")}
            className="flex h-[34px] w-full items-center justify-center rounded-[7px] border border-line-2 text-ink-2 transition-colors hover:border-accent-2 hover:text-ink"
          >
            <Informazioni size={14} />
          </button>
        </Suggerimento>
      </div>
    );
  }

  return (
    <div {...zona("resta")}>
      <Suggerimento testo={t("about.hint")} fuoco={false} className="block">
        <button
          type="button"
          onClick={vai}
          className="flex h-[34px] w-full items-center gap-2 rounded-[7px] border border-line-2 px-2.5 text-[11.5px] text-ink-2 transition-colors hover:border-accent-2 hover:text-ink"
        >
          <Informazioni size={13} />
          {t("about.action")}
        </button>
      </Suggerimento>
    </div>
  );
}

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
          compatta ? "w-full flex-col items-center justify-center gap-px" : "items-center gap-0.5"
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
        compatta ? "justify-center" : "gap-1.5"
      }`}
    >
      <Segno size={12} />
      {!compatta && <span className="lowercase">{t(`theme.${scelta}`)}</span>}
    </Selettore>
  );
}
