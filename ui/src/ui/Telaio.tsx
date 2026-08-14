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

export function Telaio({ children }: { children: ReactNode }) {
  const { t } = usaLingua();

  return (
    <div className="grid min-h-dvh grid-cols-[200px_1fr] bg-paper text-ink">
      <aside className="flex flex-col gap-4 border-r border-line bg-surface px-3 py-3.5">
        <Marchio className="px-1 text-[19px]" />

        <div>
          <div className="mb-[7px] px-1">
            <Etichetta>{t("datasets.title")}</Etichetta>
          </div>
          <SelettoreDataset />
        </div>

        <div className="mt-auto flex gap-1.5 px-1">
          <ChipLingua />
          <ChipTema />
        </div>
      </aside>

      <main className="min-w-0">{children}</main>
    </div>
  );
}

/** La pastiglia in fondo alla corsia: 10 px, bordo sottile, testo attenuato. */
function Chip({
  onClick,
  etichetta,
  children,
}: {
  onClick: () => void;
  etichetta: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={etichetta}
      className="rounded-[5px] border border-line-2 px-[7px] py-1 text-[10px] text-muted transition-colors hover:text-ink"
    >
      {children}
    </button>
  );
}

/** `IT / EN` come nel mockup: si vedono entrambe, e si vede quale e' viva. */
function ChipLingua() {
  const { t, lingua, imposta } = usaLingua();
  const altra = LINGUE[(LINGUE.indexOf(lingua) + 1) % LINGUE.length];

  return (
    <Chip onClick={() => imposta(altra)} etichetta={t("lang.label")}>
      {LINGUE.map((l, i) => (
        <span key={l}>
          {i > 0 && <span className="text-line-2"> / </span>}
          <span className={l === lingua ? "font-medium text-ink" : undefined}>
            {l.toUpperCase()}
          </span>
        </span>
      ))}
    </Chip>
  );
}

const GIRO: SceltaTema[] = ["light", "dark", "system"];
const GLIFO: Record<SceltaTema, string> = { light: "☀", dark: "☾", system: "◐" };

/**
 * Un solo bottone per tre stati, e il nome dello stato scritto accanto al
 * glifo: «sistema» non e' deducibile da un simbolo, ed e' proprio lo stato che
 * va capito — e' quello che continua a cambiare da solo.
 */
function ChipTema() {
  const { t } = usaLingua();
  const { scelta, imposta } = usaTema();
  const prossima = GIRO[(GIRO.indexOf(scelta) + 1) % GIRO.length];

  return (
    <Chip onClick={() => imposta(prossima)} etichetta={t("theme.label")}>
      <span aria-hidden="true">{GLIFO[scelta]}</span>{" "}
      <span className="lowercase">{t(`theme.${scelta}`)}</span>
    </Chip>
  );
}
