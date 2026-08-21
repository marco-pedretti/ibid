/**
 * La misura di lettura: quanto e' larga una colonna di testo, al massimo.
 *
 * **Le percentuali non sono una misura.** Un messaggio del modello era
 * `max-w-[92%]` e uno dell'utente `max-w-[78%]`: numeri giusti dentro una
 * colonna di ~460 px come quella del mockup, e senza senso dentro una da
 * 2.100 — su uno schermo largo la risposta diventava una riga di quasi duemila
 * pixel, cioe' ~300 caratteri, quattro volte cio' che un occhio segue senza
 * perdere il capo riga. Le percentuali restano, e adesso sono percentuali **di
 * questa**.
 *
 * 560 px sono ~80 caratteri al corpo di una risposta (13 px): il limite alto
 * dell'intervallo leggibile, scelto in cima invece che in mezzo perche' qui
 * dentro non c'e' solo prosa — ci sono le pastigliette dei marcatori, le righe
 * dei verdetti, e ogni tanto una tabella. Sotto i 560 px non cambia niente: e'
 * un tetto, e la colonna del mockup ci sta sotto.
 *
 * **Il campo di scrittura porta la stessa misura**, altrimenti si scriverebbe
 * in una riga larga il doppio di quella in cui si legge la risposta — e le due
 * cose sono la stessa colonna.
 *
 * **Sta in un file suo perche' non e' della chat.** Nasce li' (U-18), ma e'
 * una proprieta' dell'occhio, non di una schermata: la pagina «Che cos'e'» e'
 * prosa lunga nella stessa colonna, e due tetti diversi nella stessa
 * applicazione sarebbero due misure di lettura per lo stesso lettore.
 */
export const MISURA = "mx-auto w-full max-w-[560px]";
