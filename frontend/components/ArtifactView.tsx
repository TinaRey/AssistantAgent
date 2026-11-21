import type { Artifact } from "@/lib/types";
import { EmailPreview } from "./EmailPreview";
import { LinkedInPreview } from "./LinkedInPreview";
import { PresentationEditor } from "./PresentationEditor";
import { ResearchCard } from "./ResearchCard";

export type DraftProps = {
  busy: boolean;
  onEdit: (callId: string, edits: Record<string, any> | undefined) => void;
  onRevise: (instruction: string, context: string) => void;
};

export function ArtifactView({
  artifact, busy, onEdit, onRevise, startIndex,
}: { artifact: Artifact; startIndex?: number } & DraftProps) {
  const draft = { artifact, busy, onEdit, onRevise };
  switch (artifact.tool) {
    case "generate_email": return <EmailPreview {...draft} />;
    case "generate_linkedin_post": return <LinkedInPreview {...draft} startIndex={startIndex} />;
    case "generate_presentation":
      return artifact.data.presentation_id
        ? <PresentationEditor presentationId={artifact.data.presentation_id} warnings={artifact.data.warnings} template={artifact.data.template} />
        : <section className="card"><p className="muted">Ancienne présentation : relancez la demande pour la modifier.</p></section>;
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
