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
 * La cronologia e il pulsante «Esplora il corpus» del mockup non ci sono
 * ancora: arriveranno con le schermate che aprono. Un comando che non porta da
 * nessuna parte e' lo stesso difetto del toggle che gira a vuoto — la bozza lo
 * dice della sua stessa didascalia.
 */
import type { ReactNode } from "react";

import { usaLingua } from "../app/i18n";
import { usaTema } from "../app/theme";
import type { SceltaTema } from "../app/theme";
import { LINGUE } from "../i18n/strings";
import { Etichetta } from "./Etichetta";
import { Marchio } from "./Marchio";
import { SelettoreDataset } from "./SelettoreDataset";
import { SelettoreNativo } from "./SelettoreNativo";

export function Telaio({ children, fianco }: { children: ReactNode; fianco?: ReactNode }) {
  const { t } = usaLingua();

  return (
    // `h-dvh` e non `min-h-dvh`: da qui in poi le colonne scorrono per conto
    // loro, e con un'altezza minima scorrerebbe la pagina intera portandosi via
    // la corsia e il campo di scrittura.
    <div
      className={`grid h-dvh overflow-hidden bg-paper text-ink ${
        fianco ? "grid-cols-[200px_1fr_272px]" : "grid-cols-[200px_1fr]"
      }`}
    >
      <aside className="flex flex-col gap-4 overflow-y-auto border-r border-line bg-surface px-3 py-3.5">
        <Marchio className="px-1 text-[19px]" />

        <div>
          <div className="mb-[7px] px-1">
            <Etichetta>{t("datasets.title")}</Etichetta>
          </div>
          <SelettoreDataset />
        </div>

        <div className="mt-auto flex gap-1.5 px-1">
          <PastigliaLingua />
          <PastigliaTema />
        </div>
      </aside>

      <main className="min-h-0 min-w-0">{children}</main>
      {fianco}
    </div>
  );
}

/** La pastiglia in fondo alla corsia: 10 px, bordo sottile, testo attenuato. */
const PASTIGLIA = "rounded-[5px] border border-line-2 px-[7px] py-1 text-[10px] text-muted";

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
 */
function PastigliaLingua() {
  const { t, lingua, imposta } = usaLingua();
  const altra = LINGUE[(LINGUE.indexOf(lingua) + 1) % LINGUE.length];

  return (
    <button
      type="button"
      onClick={() => imposta(altra)}
      aria-label={`${t("lang.label")}: ${lingua.toUpperCase()}`}
      className={`${PASTIGLIA} flex items-center gap-0.5 transition-colors hover:border-line`}
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
  );
}

const TEMI: SceltaTema[] = ["light", "dark", "system"];
const GLIFO: Record<SceltaTema, string> = { light: "☀", dark: "☾", system: "◐" };

/**
 * Il tema e' **una tendina**, non un bottone che cicla.
 *
 * Con tre stati un bottone che gira nasconde le opzioni: non si vede quante
 * sono, non si sa dove si finisce, e per tornare indietro di uno si fa il giro.
 * Chi non ha ancora capito che «sistema» esiste non ha modo di scoprirlo se non
 * cliccando finche' non ricompare — cioe' l'interfaccia si impara per tentativi.
 * La tendina mostra le tre voci insieme e ne fa scegliere una.
 *
 * Il caret `▾` lo mette `SelettoreNativo`, uguale su ogni tendina: nel mockup e'
 * il segno che distingue una pastiglia che apre un menu (`.tg.menu`) da una che
 * commuta e basta, ed e' il modo in cui questa e la lingua si dichiarano
 * diverse.
 *
 * Il **nome** dello stato sta accanto al glifo perche' «sistema» non e'
 * deducibile da un simbolo, ed e' proprio quello che va capito: e' l'unico che
 * continua a cambiare da solo.
 */
function PastigliaTema() {
  const { t } = usaLingua();
  const { scelta, imposta } = usaTema();

  const voci = TEMI.map((s) => ({ valore: s, testo: `${GLIFO[s]}  ${t(`theme.${s}`)}` }));

  return (
    <SelettoreNativo
      etichetta={t("theme.label")}
      valore={scelta}
      voci={voci}
      onCambia={imposta}
      className={`${PASTIGLIA} flex items-center gap-1`}
    >
      <span>{GLIFO[scelta]}</span>
      <span className="lowercase">{t(`theme.${scelta}`)}</span>
    </SelettoreNativo>
  );
}
