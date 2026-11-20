import type { Artifact } from "@/lib/types";
import { EmailPreview } from "./EmailPreview";
import { LinkedInPreview } from "./LinkedInPreview";
import { PresentationCard } from "./PresentationCard";
import { ResearchCard } from "./ResearchCard";

export function ArtifactView({ artifact }: { artifact: Artifact }) {
  switch (artifact.tool) {
    case "generate_email": return <EmailPreview data={artifact.data} />;
    case "generate_linkedin_post": return <LinkedInPreview data={artifact.data} />;
    case "generate_presentation": return <PresentationCard data={artifact.data} />;
    case "search_company": return <ResearchCard data={artifact.data} />;
    case "retrieve_knowledge": return <KnowledgeCard data={artifact.data} />;
    default: return null;
  }
}

function KnowledgeCard({ data }: { data: Record<string, any> }) {
  if (!data.passages?.length) return null;
  return (
    <section className="card">
      <h3>Sources Pantalelle consultées</h3>
      <ul>{data.passages.map((p: any, i: number) => <li key={i}>{p.source}</li>)}</ul>
    </section>
  );
}
