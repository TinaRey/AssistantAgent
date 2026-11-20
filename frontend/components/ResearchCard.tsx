const Src = ({ url }: { url: string }) => (
  <a href={url} target="_blank" rel="noopener noreferrer">source</a>
);

export function ResearchCard({ data }: { data: Record<string, any> }) {
  return (
    <section className="card">
      <h3>Recherche : {data.company_name}</h3>
      {data.warnings?.map((w: string, i: number) => <p key={i} className="warn">⚠ {w}</p>)}
      {data.official_website && (
        <p>Site officiel : <a href={data.official_website} target="_blank" rel="noopener noreferrer">{data.official_website}</a></p>
      )}
      {data.summary && <p>{data.summary}</p>}
      {data.findings?.length > 0 && (
        <>
          <h4>Constats vérifiés</h4>
          <ul>{data.findings.map((f: any, i: number) => <li key={i}>{f.statement} (<Src url={f.source_url} />)</li>)}</ul>
        </>
      )}
      {data.collaboration_ideas?.length > 0 && (
        <>
          <h4>Pistes de collaboration <span className="tag">hypothèses</span></h4>
          <ul>{data.collaboration_ideas.map((c: any, i: number) => <li key={i}><strong>{c.idea}</strong> — {c.rationale}</li>)}</ul>
        </>
      )}
      {data.contacts?.length > 0 && (
        <>
          <h4>Contacts publics trouvés</h4>
          <ul>
            {data.contacts.map((c: any, i: number) => (
              <li key={i}>
                {[c.name, c.role].filter(Boolean).join(", ") || "Contact"}
                {c.email ? ` : ${c.email}` : " : adresse non trouvée"} (<Src url={c.source_url} />)
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
