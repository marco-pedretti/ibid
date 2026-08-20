/**
 * Quanto e' larga la corsia, e cosa resta quando si chiude.
 *
 * **La griglia del telaio e' un dato e non una classe.** Con due larghezze e il
 * pannello fonti che va e viene le combinazioni diventano quattro, e scritte
 * come classi condizionali sono quattro stringhe che nessuno puo' provare: che
 * la colonna di lavoro guadagni davvero i pixel della corsia chiusa e' una
 * **somma**, e una somma o si calcola o si spera. E' la stessa ragione per cui
 * le tre colonne dell'esploratore hanno `colonne.ts` invece di uno stile in
 * linea calcolato dentro il componente.
 *
 * **Chiusa e' 48 px**, non zero: una corsia larga zero non e' chiusa, e' sparita,
 * e per riaprirla servirebbe un comando che non si vede piu' — lo stesso difetto
 * che `colonne.ts` evita dando un minimo a ogni colonna anche a quella che non
 * si sta trascinando. 48 px e' quanto serve a un bersaglio da toccare (un
 * quadrato di 40 px piu' il respiro attorno) con il glifo di 14 px al centro.
 *
 * **Aperta resta 200 px.** E' la misura da cui vengono tutte le altre della
 * corsia — i 176 px in cui un titolo di conversazione ci sta troncato a ~28
 * caratteri, la riga in cui «CRONOLOGIA LOCALE» e il cestino stanno insieme —
 * e cambiarla qui le sposterebbe tutte.
 */

/** La corsia aperta: la misura del mockup, e quella da cui dipende il resto. */
export const APERTA = 200;

/** La corsia chiusa: una striscia di icone, non un bordo. */
export const CHIUSA = 48;

/** Il pannello fonti, quando c'e'. Sta qui perche' e' la terza traccia della
 *  stessa griglia, e tenerlo altrove significherebbe due posti da cambiare. */
export const FIANCO = 272;

/**
 * `grid-template-columns` del telaio: la corsia, il lavoro, ed eventualmente le
 * fonti.
 *
 * La colonna di mezzo e' **il resto** (`1fr`) e non una misura: e' cio' che fa
 * si' che i 152 px risparmiati dalla corsia chiusa finiscano nel lavoro invece
 * di lasciare una traccia vuota in mezzo alla griglia. Il criterio di U-18
 * chiede esattamente questo, ed e' l'errore facile — una colonna nascosta con
 * `visibility` o un `width: 0` su un `aside` lasciano la traccia dov'era.
 */
export function griglia(chiusa: boolean, fianco: boolean): string {
  const corsia = chiusa ? CHIUSA : APERTA;
  return fianco ? `${corsia}px 1fr ${FIANCO}px` : `${corsia}px 1fr`;
}

/** Dove si ricorda. Un solo prefisso per tutto cio' che il browser tiene di
 *  questo progetto, come `ibid.theme` e `ibid.corpus.colonne`. */
export const DEPOSITO = "ibid.corsia";

/**
 * La corsia e' chiusa? Solo la parola esatta lo dice; qualunque altra cosa
 * riapre.
 *
 * **Il predefinito e' aperta**, e non e' un caso di ripiego: chi arriva la prima
 * volta non sa che esistono il dataset, la cronologia e l'esploratore, e una
 * striscia di sette glifi non glielo dice. Si chiude perche' lo si e' scelto.
 *
 * Si salva una parola e non un booleano serializzato perche' e' cio' che si
 * legge negli strumenti del browser senza doverlo interpretare, e perche' cosi'
 * qualsiasi cosa di storto nel deposito — un JSON di un'altra versione, un
 * valore scritto a mano — ricade sul caso sicuro invece di sollevare.
 */
export function leggi(grezzo: string | null): boolean {
  return grezzo === "chiusa";
}
