/**
 * Il marchio. Una riga, e tre decisioni dentro.
 *
 * **La `i` centrale e' in accento** perche' il nome viene da *ibidem*, e quella
 * lettera e' il punto in cui la parola intera si lascia intravedere: `ib`·`i`·`d`.
 * Non e' un vezzo tipografico, e' l'unica parte del progetto che spiega il
 * proprio nome senza una nota a pie' di pagina.
 *
 * **E' in serif** mentre tutto il resto dell'interfaccia e' sans. La distinzione
 * e' vera e non decorativa: la grazia appartiene al mondo bibliografico da cui
 * il nome arriva, il sans a cio' che si opera. Un marchio in sans si
 * confonderebbe con i bottoni che gli stanno accanto.
 *
 * Sta in un componente e non in un `<span>` copiato in ogni schermata perche'
 * comparira' in tutte e quattro, e un marchio che diverge fra due pagine e'
 * l'errore piu' visibile che un'interfaccia possa fare.
 */
export function Marchio({ className = "" }: { className?: string }) {
  return (
    <span
      className={`font-serif font-semibold tracking-[-0.01em] select-none ${className}`}
      aria-label="ibid"
    >
      ib<span className="text-accent">i</span>d
    </span>
  );
}
