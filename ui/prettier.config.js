/**
 * Il formattatore, e perche' c'e'.
 *
 * Non «perche' e' lo standard». La ragione e' un'asimmetria: il lato Python ha
 * `ruff` in `pyproject.toml`, con tanto di regole argomentate; il lato
 * TypeScript non aveva niente. In un progetto la cui tesi e' che le cose si
 * misurano e si verificano, una meta' senza attrezzi e' la prima cosa che si
 * nota aprendo l'altra.
 *
 * E c'e' una ragione piu' concreta, imparata sbagliando: **senza questo file
 * `npx prettier` non e' innocuo.** Preso dai suoi default riformatta a 80
 * colonne, cioe' riscrive l'intero albero — e' successo, ed e' stato annullato.
 * Un comando che chiunque proverebbe deve essere sicuro.
 *
 * `printWidth: 100` non e' una preferenza, e' una **misura**: a 100 il
 * riformattaggio dell'albero esistente costa 25 file e ~54 righe nette, a 90 ne
 * costa 36 e ~335. Cioe' 100 e' la larghezza a cui questo codice e' gia'
 * scritto, e adottare il formattatore non diventa un rifacimento travestito da
 * igiene. Le righe piu' lunghe restano quelle che prettier non spezza comunque:
 * le stringhe dell'i18n e le classi Tailwind.
 *
 * Quello che questo file **non** fa: prettier formatta, non trova niente. Il
 * buco che conta ancora e' un linter con `react-hooks/exhaustive-deps` — in
 * questo repo le liste di dipendenze degli `useCallback` sono scritte a mano.
 * E' una decisione separata, con un costo diverso.
 *
 * @type {import("prettier").Config}
 */
export default {
  printWidth: 100,
  // **Non una preferenza: `core.autocrlf=true`.** Su Windows git riscrive i fine
  // riga in CRLF al checkout, e prettier con il suo default (`"lf"`) segnala
  // ogni file cosi' toccato — style issues che non sono di stile. Il controllo
  // diventava rosso su quattro file per un motivo che il diff non mostra.
  // `"auto"` prende come giusto il fine riga che il file gia' ha, che e' l'unica
  // regola compatibile con un repo condiviso fra Windows e Linux senza
  // `.gitattributes`.
  endOfLine: "auto",
};
