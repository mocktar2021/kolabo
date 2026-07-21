export default function App() {
  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem" }}>
      <h1>Kolabo</h1>
      <p>Bilingual influencer marketing marketplace for Africa — web app scaffold.</p>
      <p>Backend health check: <code>{import.meta.env.VITE_API_URL}/health</code></p>
    </main>
  );
}
