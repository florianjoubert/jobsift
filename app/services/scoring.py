"""Relevance scoring of job listings via OpenAI (structured output)."""

import logging

from openai import OpenAI

from app.config import settings
from app.schemas.job import Job, ScoredJob
from app.schemas.scoring import ScoreBatch, ScoreItem

logger = logging.getLogger(__name__)

_CLIENT: OpenAI | None = None
BATCH_SIZE = 5

SYSTEM_PROMPT = """\
# Rôle
Tu es un expert du recrutement tech / produit / IA. Tu évalues, avec rigueur et sans
complaisance, l'adéquation entre une offre d'emploi et le profil d'un candidat précis.
Tu raisonnes à partir des FAITS présents dans l'offre, jamais d'hypothèses flatteuses.

# Tâche
Pour chaque offre : un score de pertinence de 0 à 100 (vs le profil et ses contraintes,
fournis dans le message), un résumé de 2-3 phrases en français, et des points forts (pros)
et faibles (cons) CONCRETS, ancrés dans le texte de l'offre. Réutilise EXACTEMENT la
valeur du champ « ID » de chaque offre comme job_id dans ta réponse.

# Barème (calibre-toi dessus, sois strict)
- 90-100 : correspondance idéale (cible principale + plusieurs signaux forts, aucun red flag).
- 75-89  : très pertinent (bon fit, signaux positifs nets, red flags mineurs).
- 55-74  : pertinent avec réserves (fit partiel, imparfait).
- 35-54  : faible (points communs mais s'éloigne de la cible, ou red flag notable).
- 0-34   : hors cible ou disqualifié (voir règles ci-dessous).

# Disqualifiants (plafonnent le score, priment sur tout le reste)
1. REMOTE - le full remote est IMPÉRATIF. Si l'offre n'est clairement PAS full remote
   (présentiel, hybride, remote partiel/occasionnel), plafonne à 35, quelle que soit la
   qualité du poste. Le champ « Remote détecté » est un indice heuristique (faux positifs
   possibles) : recoupe-le avec la description, ton jugement final fait foi. Si le mode de
   travail est vraiment indéterminable, ne plafonne pas mais signale-le en cons.
2. LANGUE - offre ni en français ni en anglais → score ≤ 20.
3. EXCLUSIONS - respecte les exclusions explicites du profil (ex. feature PM sur produit
   mature, ESN / conseil / régie courte, verticaux non-tech, rôle Salesforce pur). Une offre
   qui y tombe → ≤ 35.

# Signaux à valoriser (montent le score)
- Colle à la CIBLE PRINCIPALE du profil (lis-la attentivement).
- Freelance / mission (préféré par le candidat) : bonus ~+15 vs un CDI équivalent.
- Rôle « Product Builder » / build assisté par IA (Claude Code, Cursor, LLM, agents), ou
  poste AI Engineer / Product Engineer : bonus ~+15 (cœur de la reconversion visée).
- Construction 0→1, refonte de plateforme, migration, SaaS B2B tech.

# Méthode & garde-fous
- Juge sur le CONTENU de la description, pas seulement le titre.
- N'invente aucune information absente. Info manquante ou ambiguë → reste prudent, baisse
  le score plutôt que de supposer le meilleur.
- Ignore le bourrage de mots-clés : exige des preuves concrètes.
- Reste calibré : 90+ seulement pour de vraies pépites ; la plupart des offres réelles
  tombent entre 20 et 60.
- pros / cons : 2 à 4 puces chacun, spécifiques (cite ce qui colle ou non), jamais génériques.
"""


def _get_client() -> OpenAI:
    global _CLIENT
    if _CLIENT is None:
        # High max_retries: gpt-5.x occasionally returns 503s under load;
        # we retry with backoff rather than falling back to the neutral score (50).
        _CLIENT = OpenAI(api_key=settings.openai_api_key, max_retries=5, timeout=60.0)
    return _CLIENT


def _norm_id(job_id: str) -> str:
    """The LLM sometimes prefixes the id with "JOB" (template artefact) - we normalise
    on both sides to make the score↔listing merge reliable."""
    return job_id.strip().removeprefix("JOB ").removeprefix("job ").strip()


def _jobs_to_text(jobs: list[Job]) -> str:
    blocks = []
    for j in jobs:
        remote_label = "oui" if j.remote else "non"
        contrat = j.contract_type or "n/a"
        salaire = f"\nSalaire: {j.salary}" if j.salary else ""
        blocks.append(
            f"### OFFRE\nID: {j.job_id}\nTitre: {j.title}\nEntreprise: {j.company}\n"
            f"Lieu: {j.location}\nRemote détecté: {remote_label}\n"
            f"Type de contrat: {contrat}{salaire}\n"
            f"Description:\n{j.description[:3000]}"
        )
    return "\n\n".join(blocks)


def _call_llm(client: OpenAI, jobs: list[Job], profile: str, model: str) -> ScoreBatch:
    # Uses client.responses.parse with text_format= (Responses API, openai v2.41.0).
    # The return value is a ParsedResponse[ScoreBatch]; output_parsed holds the Pydantic instance.
    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"PROFIL:\n{profile}\n\nOFFRES:\n{_jobs_to_text(jobs)}"},
        ],
        text_format=ScoreBatch,
    )
    result = response.output_parsed
    if result is None:
        raise ValueError("output_parsed est None (refus/filtre)")
    return result


def score_jobs(jobs: list[Job], profile: str) -> list[ScoredJob]:
    if not jobs:
        return []
    client = _get_client()
    by_id: dict[str, ScoreItem] = {}

    for i in range(0, len(jobs), BATCH_SIZE):
        batch = jobs[i : i + BATCH_SIZE]
        try:
            result = _call_llm(client, batch, profile, settings.openai_model)
            for item in result.items:
                by_id[_norm_id(item.job_id)] = item
        except Exception as e:
            logger.error(f"Scoring batch failed: {e}")
            for j in batch:  # fallback: neutral score
                by_id[j.job_id] = ScoreItem(
                    job_id=j.job_id, score=50, summary="Scoring indisponible"
                )

    scored: list[ScoredJob] = []
    for j in jobs:
        item = by_id.get(j.job_id) or ScoreItem(
            job_id=j.job_id, score=50, summary="Scoring indisponible"
        )
        scored.append(
            ScoredJob(
                **j.model_dump(),
                relevance_score=item.score,
                ai_summary=item.summary,
                ai_pros=item.pros,
                ai_cons=item.cons,
            )
        )
    return scored
