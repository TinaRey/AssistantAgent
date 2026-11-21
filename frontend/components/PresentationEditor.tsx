"use client";
import { useEffect, useRef, useState } from "react";
import {
  ApiError, generateSlideImage, getPresentation, savePresentation,
  type PresentationData, type PresentationSlide, type ThemeColors,
} from "@/lib/api";

type EditSlide = {
  key: string; title: string; bulletsText: string; numbered: boolean;
  image_id: string | null; image_prompt: string | null; speaker_notes: string | null; suggested_visual: string | null;
};

const toEdit = (s: PresentationSlide): EditSlide => ({
  key: crypto.randomUUID(), title: s.title, bulletsText: s.bullets.join("\n"), numbered: s.numbered,
  image_id: s.image_id ?? null, image_prompt: s.image_prompt ?? null,
  speaker_notes: s.speaker_notes ?? null, suggested_visual: s.suggested_visual ?? null,
});
const bulletsOf = (s: EditSlide) => s.bulletsText.split("\n").map((b) => b.trim()).filter(Boolean);
const money = (usd: number) => `≈ ${usd.toFixed(2).replace(".", ",")} $`;
const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : "Impossible de joindre le serveur.");

export function PresentationEditor({
  presentationId, warnings, template,
}: { presentationId: string; warnings?: string[]; template?: string | null }) {
  const [data, setData] = useState<PresentationData | null>(null);
  const [title, setTitle] = useState("");
  const [slides, setSlides] = useState<EditSlide[]>([]);
  const [colors, setColors] = useState<ThemeColors | null>(null); // null = the brand's own colors
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);
  const descriptions = useRef<Record<string, string>>({});

  function load(d: PresentationData) {
    setData(d); setTitle(d.content.title); setSlides(d.content.slides.map(toEdit)); setDirty(false);
    setColors(d.theme);
  }
  useEffect(() => {
    getPresentation(presentationId).then(load).catch((e) => (e instanceof ApiError && e.status === 404 ? setMissing(true) : setError(errMsg(e))));
  }, [presentationId]);

  const payload = () => ({
    theme: colors,
    title: title.trim() || "Présentation",
    slides: slides.map((s) => ({
      title: s.title.trim() || "Sans titre", bullets: bulletsOf(s), numbered: s.numbered, image_id: s.image_id,
      image_prompt: s.image_prompt, speaker_notes: s.speaker_notes, suggested_visual: s.suggested_visual,
    })),
  });

  async function save(): Promise<boolean> {
    if (!dirty) return true;
    setBusy("Enregistrement…"); setError(null);
    try { load(await savePresentation(presentationId, payload())); return true; }
    catch (e) { setError(errMsg(e)); return false; }
    finally { setBusy(null); }
  }

  async function download(url: string) {
    if (await save()) window.location.href = url; // attachment: the page stays where it is
  }

  async function illustrate(index: number, key: string) {
    const replacing = !!slides[index].image_id;
    const cost = data ? money(data.image_cost_usd) : "";
    if (!confirm(`${replacing ? "Régénérer" : "Générer"} une illustration pour cette diapositive ? Coût indicatif : ${cost} (facturé sur la clé OpenAI).`)) return;
    if (!(await save())) return;
    setBusy("Génération de l'illustration… (10 à 30 s)"); setError(null);
    try { load(await generateSlideImage(presentationId, index, descriptions.current[key])); }
    catch (e) { setError(errMsg(e)); }
    finally { setBusy(null); }
  }

  const edit = (key: string, patch: Partial<EditSlide>) => {
    setSlides((all) => all.map((s) => (s.key === key ? { ...s, ...patch } : s))); setDirty(true);
  };
  const move = (i: number, d: -1 | 1) => {
    setSlides((all) => { const next = [...all]; [next[i], next[i + d]] = [next[i + d], next[i]]; return next; }); setDirty(true);
  };

  if (missing) return <section className="card"><p className="muted">Cette présentation n'est plus disponible (le serveur a redémarré). Relancez la demande dans le chat.</p></section>;
  if (!data) return <section className="card"><p className="muted">{error ?? "Chargement de la présentation…"}</p></section>;

  return (
    <section className="card">
      <h3>Présentation pour {data.company ?? "…"} {data.visual_style && <span className="tag">{data.visual_style}</span>} {template && <span className="tag">d'après : {template}</span>} {dirty && <span className="tag edited">modifications non enregistrées</span>}</h3>
      <p className="muted">La page de garde et la page de fin sont ajoutées automatiquement. Les textes sont modifiables ci-dessous.</p>
      {warnings?.map((w, i) => <p key={i} className="warn">⚠ {w}</p>)}
      {error && <p role="alert" className="error">{error}</p>}
      <label>Titre de la présentation<input value={title} onChange={(e) => { setTitle(e.target.value); setDirty(true); }} /></label>

      <div className="theme-row">
        <strong>Couleurs</strong>
        {(() => {
          const shown = colors ?? data.default_theme;
          const pick = (k: keyof ThemeColors) => (e: React.ChangeEvent<HTMLInputElement>) => {
            setColors({ ...shown, [k]: e.target.value.replace("#", "").toUpperCase() }); setDirty(true);
          };
          return (
            <>
              <label className="swatch">Principale (titres, mots-clés)<input type="color" value={`#${shown.primary}`} onChange={pick("primary")} /></label>
              <label className="swatch">Fond clair (bandeaux)<input type="color" value={`#${shown.tint}`} onChange={pick("tint")} /></label>
            </>
          );
        })()}
        {colors && <button className="link" onClick={() => { setColors(null); setDirty(true); }}>Couleurs de la marque</button>}
        <span className="muted">Une couleur trop claire est assombrie à l'enregistrement pour rester lisible. Le logo garde ses couleurs.</span>
      </div>

      {slides.map((s, i) => (
        <div key={s.key} className="slide-edit">
          <div className="slide-head">
            <strong>Diapositive {i + 1}</strong>
            <span className="actions">
              <button className="icon" disabled={i === 0} onClick={() => move(i, -1)} aria-label="Monter" title="Monter">↑</button>
              <button className="icon" disabled={i === slides.length - 1} onClick={() => move(i, 1)} aria-label="Descendre" title="Descendre">↓</button>
              <button className="icon" onClick={() => confirm("Supprimer cette diapositive ?") && (setSlides((a) => a.filter((x) => x.key !== s.key)), setDirty(true))} aria-label="Supprimer la diapositive" title="Supprimer">×</button>
            </span>
          </div>
          <input value={s.title} onChange={(e) => edit(s.key, { title: e.target.value })} aria-label={`Titre de la diapositive ${i + 1}`} maxLength={200} />
          <textarea rows={5} value={s.bulletsText} onChange={(e) => edit(s.key, { bulletsText: e.target.value })} aria-label={`Contenu de la diapositive ${i + 1}`} />
          <p className="muted">Une ligne par puce (6 maximum). Entourez un mot de **astérisques** pour le mettre en rouge.{bulletsOf(s).length > 6 && <span className="error"> Trop de puces : {bulletsOf(s).length}.</span>}</p>
          <label className="check"><input type="checkbox" checked={s.numbered} onChange={(e) => edit(s.key, { numbered: e.target.checked })} /> Liste numérotée</label>

          <div className="slide-image">
            {s.image_id && /* eslint-disable-next-line @next/next/no-img-element */ <img src={`/api/presentations/${presentationId}/images/${s.image_id}`} alt={`Illustration de la diapositive ${i + 1}`} />}
            <div>
              <input placeholder="Sujet de l'illustration (facultatif, ex. randonneuse dans une vallée verte)" onChange={(e) => (descriptions.current[s.key] = e.target.value)} defaultValue="" maxLength={300} />
              <button disabled={!!busy || (!s.image_id && data.image_count >= data.max_images)} onClick={() => illustrate(i, s.key)}>
                {s.image_id ? "Régénérer l'illustration" : "Générer une illustration"} ({money(data.image_cost_usd)})
              </button>
            </div>
          </div>
          <details>
            <summary>Notes de l'orateur</summary>
            <textarea rows={3} value={s.speaker_notes ?? ""} onChange={(e) => edit(s.key, { speaker_notes: e.target.value || null })} />
          </details>
        </div>
      ))}

      <div className="actions">
        <button disabled={slides.length >= 30} onClick={() => { setSlides((a) => [...a, toEdit({ title: "Nouvelle diapositive", bullets: [], numbered: false })]); setDirty(true); }}>+ Ajouter une diapositive</button>
        <button className="primary" disabled={!dirty || !!busy} onClick={save}>Enregistrer</button>
      </div>
      {busy && <p className="muted typing">{busy}</p>}
      <div className="actions">
        <button className="primary" disabled={!!busy} onClick={() => download(data.pdf_url)}>Télécharger le PDF</button>
        <button disabled={!!busy} onClick={() => download(data.pptx_url)}>Télécharger le PowerPoint (modifiable)</button>
        <span className="muted">{data.image_count}/{data.max_images} illustrations · coût indicatif par image {money(data.image_cost_usd)}</span>
      </div>
    </section>
  );
}
