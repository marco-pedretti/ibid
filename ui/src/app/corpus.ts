/**
 * L'esploratore del corpus: quali documenti, come sono stati spezzati.
 *
 * **Non e' la dashboard**, ed e' la didascalia del mockup a dirlo: qui non si
 * confrontano configurazioni, si guarda il corpus e come e' stato tagliato —
 * cioe' si rende visibile il routing a chi non sa cosa sia un nDCG.
 *
 * Nasce da U-06, «da una citazione si raggiunge la fonte», e la fonte qui e'
 * **il chunk intero**. La scheda del pannello ne mostra due righe; il chunk che
 * risponde alla domanda sui crediti di Sherwin-Williams e' lungo 6.302
 * caratteri. Per controllare davvero una citazione servono tutti, e il posto in
 * cui leggerli e' anche quello in cui si vede da quale documento vengono e
 * quanti fratelli hanno.
 *
 * **Nessun campo nuovo, di nuovo.** `/chunk/{id}`, `/documents` e
 * `/document/{id}/chunks` esistono dal A-04, A-07 ha creato gli indici payload
 * apposta (misurato allora: 2,07 s → 0,025 s), e `api.ts` li avvolge da U-00 con
 * un commento che dice «(U-06)». Non li aveva mai chiamati nessuno — e' la terza
 * volta dopo `/config` in U-03 e `Risposta.config` in U-15.
 *
 * **Il PDF non c'e', e non e' solo I-06.** Su nessuno dei due corpus esiste un
 * PDF su disco: `open_ragbench` ha il JSON degli articoli, `ledger` il Markdown
 * di Mathpix. Quindi niente pagina renderizzata e niente evidenziazione: si
 * dichiara, non si simula. Cio' che si puo' offrire e' il link esterno dove
 * `source_uri` **e'** un indirizzo, ed e' vero solo per uno dei due.
 */
import type { ChunkView, DocumentView } from "../api/types";

/**
 * I documenti che corrispondono a cio' che si sta cercando.
 *
 * Serve perche' `ledger` ne ha **494**: un elenco cosi' non si scorre, si
 * interroga. Il confronto e' senza maiuscole e su un pezzo qualunque del nome,
 * perche' i nomi sono `NYSE_SHW_2017` e chi cerca scrive `shw` — o `2017`, che
 * sta in fondo.
 *
 * Ricerca vuota vuol dire **tutti**, non nessuno: un campo che si svuota deve
 * riportare all'elenco intero, e non lasciare uno schermo bianco.
 */
export function filtra(documenti: readonly DocumentView[], cerca: string): DocumentView[] {
  const q = cerca.trim().toLowerCase();
  if (q === "") return [...documenti];
  return documenti.filter((d) => d.doc_id.toLowerCase().includes(q));
}

/**
 * Quale chunk e' selezionato aprendo un documento.
 *
 * Arrivando da una citazione e' **quello citato**, che e' il motivo per cui si e'
 * aperto l'esploratore. Arrivando dall'elenco non c'e' un chunk chiesto e si
 * prende il primo, perche' un documento aperto su niente mostrerebbe una mappa
 * senza nessuna tessera scelta e una colonna di destra vuota.
 *
 * Un chunk chiesto che nel documento non c'e' ricade sul primo invece di
 * lasciare la selezione vuota: e' la stessa scelta di `scelta-dataset.ts`, dove
 * un dataset ricordato ma sparito non blocca l'interfaccia.
 */
export function chunkIniziale(chunks: readonly ChunkView[], chiesto: string | null): string | null {
  if (chunks.length === 0) return null;
  if (chiesto !== null && chunks.some((c) => c.chunk_id === chiesto)) return chiesto;
  return chunks[0].chunk_id;
}

/**
 * L'indirizzo da aprire per questa fonte, o `null` se non e' un indirizzo.
 *
 * `source_uri` porta due cose diverse a seconda del corpus: su `open_ragbench`
 * e' `https://arxiv.org/abs/2401.07294`, cioe' un posto dove andare; su `ledger`
 * e' `ledger:NYSE:SHW:2017`, che e' un **identificatore** e non una destinazione.
 * Trasformare il secondo in un link darebbe un comando che non porta da nessuna
 * parte, ed e' lo stesso difetto del controllo che gira a vuoto.
 *
 * Solo `http` e `https`: un `source_uri` non e' scritto da noi — arriva dal
 * payload dell'indice — e uno schema qualunque messo dentro un `href` e' il modo
 * in cui `javascript:` finisce in un clic.
 */
export function indirizzo(sourceUri: string): string | null {
  try {
    const u = new URL(sourceUri);
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}
