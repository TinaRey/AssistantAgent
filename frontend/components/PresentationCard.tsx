export function PresentationCard({ data }: { data: Record<string, any> }) {
  const content = data.content;
  return (
    <section className="card">
      <h3>Présentation : {content.title}</h3>
      <ol>
        {content.slides.map((s: any, i: number) => (
          <li key={i}>
            <strong>{s.title}</strong>
            <ul>{s.bullets.map((b: string, j: number) => <li key={j}>{b}</li>)}</ul>
          </li>
        ))}
      </ol>
      <div className="actions">
        <a className="button" href={data.download_url} download>Télécharger le PowerPoint</a>
      </div>
    </section>
  );
}
