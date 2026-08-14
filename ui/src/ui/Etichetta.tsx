/**
 * L'etichetta di sezione del mockup: mono, maiuscoletto, spaziata.
 *
 * E' mono perche' nel §12 il mono e' il ruolo dei **dati** — `chunk_id`,
 * marcatori, punteggi, etichette — e un titoletto che nomina una colonna di
 * dati appartiene a quel ruolo, non alla prosa.
 */
import type { ReactNode } from "react";

export function Etichetta({ children }: { children: ReactNode }) {
  return (
    <h2 className="font-mono text-[9.5px] font-semibold tracking-[0.12em] text-muted uppercase">
      {children}
    </h2>
  );
}
