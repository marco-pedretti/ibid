/**
 * Il bottoncino che sceglie fra due viste della stessa cosa.
 *
 * Lo premono in due, e su due scale diverse: la colonna di mezzo
 * dell'esploratore per passare dalla mappa al testo indicizzato, e `Contenuto`
 * per passare dal chunk leggibile al chunk grezzo. Sta in un file suo per
 * questo — e non dentro `Leggibile.tsx`, che sarebbe una casa scelta per caso
 * fra i due.
 *
 * **`aria-pressed` e non un `role="tab"`.** Non e' un gruppo di schede: sono due
 * bottoni che dicono se sono premuti, e chi legge con la voce sente «premuto»
 * su quello attivo senza che serva descrivere un pannello che non c'e'.
 *
 * **E' la pastiglia di `pastiglia.ts` presa a un'altra misura** — pillola,
 * bordo, accento da acceso — con 10 px invece di 11 e margini interni suoi.
 * Perche' siano due non risulta da nessuna parte: e' registrato come debito, e
 * unificarle qui avrebbe cambiato dei pixel, che e' cio' che il gate di Q-07
 * vieta.
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
      className={`rounded-full border px-2 py-[3px] text-[10px] transition-colors ${
        attivo
          ? "border-accent bg-accent-soft text-accent"
          : "border-line-2 text-muted hover:border-accent-2 hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}
