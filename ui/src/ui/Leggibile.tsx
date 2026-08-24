/**
 * Il testo del corpus, disegnato: un chunk, o un documento intero.
 *
 * **Stava in `Corpus.tsx`**, dov'e' nato, insieme alle tre colonne
 * dell'esploratore. Quel file era il doppio del secondo del progetto, ma il
 * motivo per spostare questa parte non e' la lunghezza: e' che non parla
 * dell'esploratore. Le colonne sanno di selezione, larghezze trascinabili e
 * documenti; questo sa come si mostra del testo che viene dall'indice, e lo
 * saprebbe uguale se a chiederglielo fosse il pannello delle fonti.
 *
 * Quel che **non** si e' spostato sono i mattoni che sembrano generici e non lo
 * sono — `Targa`, `Voce`, `Attesa`: li usa solo l'esploratore, e un modulo
 * condiviso con un consumatore solo e' un'astrazione in cerca di un secondo.
 *
 * `TabellaHtml` resta privata qui dentro: fuori serve solo cio' che disegna del
 * testo, cioe' `Leggibile` e `Contenuto`.
 */
import { useMemo, useState } from "react";

import { usaLingua } from "../app/i18n";
import { Modo } from "./Modo";
import { pezzi } from "./tabellaHtml";
import type { Cella } from "./tabellaHtml";
import { Prosa } from "./Testo";

/**
 * Il chunk, in due modi: come lo si legge e com'e' nell'indice.
 *
 * **Tutti e due servono, e per ragioni diverse.** Leggibile e' il modo di
 * controllare cosa dice una fonte: `## Table of Contents` e' un titolo, e
 * `<table><tr><td>` e' una tabella con dentro dei numeri incolonnati. Grezzo e'
 * cio' che sta davvero nell'indice — la stessa stringa che il modello ha ricevuto
 * in contesto e che il verificatore ha giudicato. In un progetto la cui tesi e'
 * che si controlla cio' che il sistema fa, il secondo non e' una modalita' di
 * ripiego: e' il dato.
 *
 * Si parte da **leggibile** perche' la domanda frequente e' «cosa dice questa
 * fonte», e un muro di `</td><td>` non risponde. Il grezzo resta a un clic, e la
 * pastiglia dice quale dei due si sta guardando invece di chiederlo.
 */
export function Contenuto({ testo }: { testo: string }) {
  const { t } = usaLingua();
  const [grezzo, setGrezzo] = useState(false);

  return (
    <div className="flex min-w-0 flex-col gap-1.5">
      <div className="flex items-center gap-1">
        <Modo attivo={!grezzo} onClick={() => setGrezzo(false)}>
          {t("corpus.readable")}
        </Modo>
        <Modo attivo={grezzo} onClick={() => setGrezzo(true)}>
          {t("corpus.raw")}
        </Modo>
      </div>

      {grezzo ? (
        <p className="min-w-0 rounded-[7px] border border-line-2 bg-surface px-2.5 py-2 font-mono text-[10.5px] leading-[1.55] break-words whitespace-pre-wrap text-ink-2">
          {testo}
        </p>
      ) : (
        <div className="min-w-0 rounded-[7px] border border-line-2 bg-surface px-2.5 py-2">
          <Leggibile testo={testo} />
        </div>
      )}
    </div>
  );
}

/**
 * Del testo del corpus, disegnato: prosa e tabelle.
 *
 * Sta in un componente perche' lo usano in due — il chunk singolo nella colonna
 * di destra e il documento intero in quella di mezzo (U-17) — e sono la stessa
 * cosa a due scale. Il costo e' misurato: preparare i 261 chunk di
 * `NASDAQ_LOOP_2017` (457.565 caratteri) costa **29 ms** fra `pezzi`, `analizza`
 * e `segmenta`, quindi il documento intero non ha bisogno di una finestra sui
 * pezzi visibili.
 */
export function Leggibile({ testo }: { testo: string }) {
  const parti = useMemo(() => pezzi(testo), [testo]);
  return (
    <div className="flex min-w-0 flex-col gap-2 text-[12px] leading-[1.55] text-ink-2">
      {parti.map((p) =>
        p.tipo === "tabella" ? (
          <TabellaHtml key={p.da} righe={p.righe} />
        ) : (
          <Prosa key={p.da} testo={testo.slice(p.da, p.a)} />
        ),
      )}
    </div>
  );
}

/**
 * Una tabella dei bilanci, costruita da noi con del testo.
 *
 * `colSpan`/`rowSpan` passano al browser invece di essere espansi: e' la
 * differenza dichiarata con `parse_html_table` in Python, che le espande perche'
 * serve a cercare. Qui serve a mostrare, e a mostrare ci pensa il browser.
 *
 * **Nessuna riga e' promossa a intestazione per posizione.** L'OCR di `ledger`
 * non produce `<th>` — misurato su 2.758 tabelle — e la prima riga di una
 * tabella di bilancio spesso e' un'etichetta di periodo che copre due colonne,
 * non un'intestazione. Indovinarla la farebbe sembrare un dato del documento.
 */
function TabellaHtml({ righe }: { righe: Cella[][] }) {
  return (
    // Scorre per conto suo: una tabella larga non deve far scorrere la colonna,
    // che porterebbe via anche il resto del chunk.
    <div className="-mx-1 overflow-x-auto px-1">
      <table className="w-full border-collapse font-mono text-[10.5px] tabular-nums">
        <tbody>
          {righe.map((riga, i) => (
            <tr key={i}>
              {riga.map((c, j) => (
                <td
                  key={j}
                  colSpan={c.colspan}
                  rowSpan={c.rowspan}
                  className={`border border-line px-1.5 py-[3px] align-top ${
                    c.intestazione ? "font-semibold text-ink" : "text-ink-2"
                  }`}
                >
                  {c.testo}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
