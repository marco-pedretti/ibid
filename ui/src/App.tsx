/**
 * Lo scheletro di U-00: prova che la catena regge, e nient'altro.
 *
 * Le quattro schermate sono U-01…U-07. Qui c'e' solo cio' che serve a sapere
 * che il frontend parla con l'API viva: se questa pagina mostra i dataset, il
 * proxy, i tipi e il client funzionano.
 */
export function App() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">ibid</h1>
      <p className="mt-2 text-muted">
        RAG con citazioni verificate a livello di frase.
      </p>
    </main>
  );
}
