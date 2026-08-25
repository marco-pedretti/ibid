import { FORMA, MOSSA, RIPOSO } from "./pastiglia";

/**
 * Il bottoncino che sceglie fra due viste della stessa cosa.
 *
 * Lo premono in due: la colonna di mezzo dell'esploratore per passare dalla
 * mappa al testo indicizzato, e `Contenuto` per passare dal chunk leggibile al
 * chunk grezzo. Sta in un file suo per questo — e non dentro `Leggibile.tsx`,
 * che sarebbe una casa scelta per caso fra i due.
 *
 * **`aria-pressed` e non un `role="tab"`.** Non e' un gruppo di schede: sono due
 * bottoni che dicono se sono premuti, e chi legge con la voce sente «premuto»
 * su quello attivo senza che serva descrivere un pannello che non c'e'.
 *
 * **E' la pastiglia di `pastiglia.ts`, e adesso lo e' davvero** (D-22). Era la
 * stessa pillola ridisegnata a mano a 10 px, senza fondo e con un grigio piu'
 * chiaro; lo stato acceso, pero', era gia' identico carattere per carattere —
 * il segno che era nata copiando l'altra e poi era stata ritoccata. Le quattro
 * sullo schermo erano le uniche della famiglia a non venire dal modulo.
 *
 * Prende `FORMA` e non `PASTIGLIA` perche' quella porta `pl-[7px] pr-2.5`,
 * asimmetrici apposta per chi ha un glifo davanti, e qui non ce n'e' uno. I
 * margini interni sono quelli del selettore del prompt (`Confronto.tsx`), che
 * e' l'altra pillola senza glifo: dopo questo cambio la forma senza glifo e'
 * **una sola** in tutta l'interfaccia.
 */
export function Modo({
  attivo,
  onClick,
  children,
}: {
  attivo: boolean;
  onClick: () => void;
  children: string;
}) {
  return (
    <button
      type="button"
      aria-pressed={attivo}
      onClick={onClick}
      className={`${FORMA} px-2.5 py-1 ${attivo ? MOSSA : RIPOSO}`}
    >
      {children}
    </button>
  );
}
