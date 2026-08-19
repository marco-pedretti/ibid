/**
 * L'applicazione: i provider, il telaio, e la colonna che cambia.
 *
 * L'ordine dei provider non e' decorativo — `ProvvedeChat` legge il dataset
 * scelto e i controlli della barra, che a loro volta leggono le capabilities:
 * annidarli al contrario romperebbe in esecuzione con un `usaX fuori da
 * <ProvvedeX>`, che e' il modo in cui questo albero dichiara le proprie
 * dipendenze.
 *
 * Gli stati del backend restano tre e non due: «sto contattando» non e' «e'
 * rotto», e mostrare subito l'errore per poi toglierlo fa lampeggiare un guasto
 * che non c'era.
 */
import { ProvvedeBackend, usaBackend } from "./app/backend";
import { ProvvedeBarra } from "./app/barra";
import { ProvvedeChat, usaChat } from "./app/chat";
import { ProvvedeDataset } from "./app/dataset";
import { ProvvedeLingua, usaLingua } from "./app/i18n";
import { ProvvedeTema } from "./app/theme";
import { Chat } from "./ui/Chat";
import { Confronto } from "./ui/Confronto";
import { PannelloFonti } from "./ui/PannelloFonti";
import { Telaio } from "./ui/Telaio";

export function App() {
  return (
    <ProvvedeLingua>
      <ProvvedeTema>
        <ProvvedeBackend>
          <ProvvedeDataset>
            <ProvvedeBarra>
              <ProvvedeChat>
                <Schermata />
              </ProvvedeChat>
            </ProvvedeBarra>
          </ProvvedeDataset>
        </ProvvedeBackend>
      </ProvvedeTema>
    </ProvvedeLingua>
  );
}

/**
 * Quale schermata sta nel telaio, e se il pannello fonti c'e'.
 *
 * Il pannello e' passato al telaio e non alla chat: il criterio di U-02 dice
 * «visibile in ogni stato», e uno stato in cui la chat non c'e' e' comunque uno
 * stato. Con **una** eccezione, e non e' un'eccezione al criterio: nel confronto
 * le fonti stanno dentro la colonna «con le fonti», perche' averle da una parte
 * e non dall'altra e' l'argomento di quella schermata. Una colonna sola di
 * fianco mostrerebbe le fonti di uno dei due bracci senza dire di quale.
 *
 * Un componente e non `App` perche' `usaChat` va chiamato **sotto**
 * `<ProvvedeChat>`.
 */
function Schermata() {
  const { confronto } = usaChat();

  if (confronto !== null) {
    return (
      <Telaio>
        <Confronto confronto={confronto} />
      </Telaio>
    );
  }

  return (
    <Telaio fianco={<PannelloFonti />}>
      <Colonna />
    </Telaio>
  );
}

function Colonna() {
  const { t } = usaLingua();
  const { backend, ricarica } = usaBackend();

  if (backend.stato === "caricamento") {
    return (
      <div className="px-[22px] py-5">
        <p className="flex items-center gap-2 font-mono text-[11px] tracking-[0.02em] text-muted">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
          {t("backend.loading")}
        </p>
      </div>
    );
  }

  if (backend.stato === "guasto") {
    return (
      <div className="px-[22px] py-5">
        <section className="rounded-lg border border-line-2 border-l-[3px] border-l-warn bg-warn-soft p-4">
          <h2 className="text-sm font-semibold">{t("backend.down")}</h2>
          <p className="mt-1 text-xs text-ink-2">{t("backend.hint")}</p>
          <p className="mt-2 font-mono text-[11px] break-all text-muted">{backend.errore}</p>
          <button
            type="button"
            onClick={ricarica}
            className="mt-3 rounded-md border border-accent bg-accent-soft px-3 py-1.5 text-xs font-medium text-accent"
          >
            {t("backend.retry")}
          </button>
        </section>
      </div>
    );
  }

  return <Chat />;
}
