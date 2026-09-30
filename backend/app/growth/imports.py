"""Local, conservative import extraction. No LLM and no repository code execution."""

import base64
import hashlib
import io
import re
import zipfile

import httpx
from docx import Document
from fastapi import HTTPException
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.growth.models import ImportProposal
from app.profile.models import Profile
from app.taxonomy import SignalCategory, load_taxonomy

MAX_BYTES = 5 * 1024 * 1024
MAX_TEXT = 100_000


def document_text(filename: str, content: bytes) -> str:
    if len(content) > MAX_BYTES:
        raise HTTPException(413, "Soubor je příliš velký (maximum 5 MB).")
    try:
        if filename.lower().endswith(".pdf"):
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted or len(reader.pages) > 100:
                raise ValueError("encrypted or too many pages")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif filename.lower().endswith(".docx"):
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if sum(i.file_size for i in archive.infolist()) > 20 * MAX_BYTES:
                    raise ValueError("expanded document too large")
            doc = Document(io.BytesIO(content))
            text = "\n".join(
                [p.text for p in doc.paragraphs]
                + [c.text for t in doc.tables for r in t.rows for c in r.cells]
            )
        else:
            raise HTTPException(415, "Podporujeme textové PDF a DOCX; nebo vlož text CV.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, "Soubor nelze přečíst. Vlož prosím text CV.") from exc
    if not text.strip():
        raise HTTPException(422, "PDF neobsahuje čitelný text. Skeny zatím neumíme; vlož text CV.")
    if len(text) > MAX_TEXT:
        raise HTTPException(413, "Dokument obsahuje příliš mnoho textu.")
    return text


def detected_skills(text: str) -> list[str]:
    return [
        s.id
        for s in load_taxonomy().signals
        if s.category == SignalCategory.SKILL
        and any(
            re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text, re.I)
            for alias in [s.id.replace("_", " "), s.label, *s.aliases]
        )
    ]


def propose(
    session: Session,
    profile: Profile,
    source: str,
    reference: str,
    text: str,
    title: str | None = None,
) -> list[ImportProposal]:
    # One proposal per nonempty source line, capped to keep review manageable.
    lines = [text] if title else [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise HTTPException(422, "Vlož text, který lze zpracovat.")
    if len(lines) > 100:
        raise HTTPException(413, "Dokument má přes 100 řádků. Importuj jej po částech.")
    result = []
    for line in lines:
        source_key = reference if source == "github" else "cv"
        fingerprint = hashlib.sha256(
            f"{profile.id}:{source}:{source_key}:{' '.join(line.split()).casefold()}".encode()
        ).hexdigest()
        row = session.scalar(
            select(ImportProposal).where(ImportProposal.fingerprint == fingerprint)
        )
        if row is None:
            row = ImportProposal(
                profile_id=profile.id,
                fingerprint=fingerprint,
                source=source,
                reference=reference,
                excerpt=line[:10000],
                proposed={
                    "kind": "project" if title else "achievement",
                    "title": (title or line)[:300],
                    "description": line[:10000],
                    "result": None,
                    "url": reference if source == "github" else None,
                    "signals": detected_skills(line[:10000]),
                    "strength": 0,
                    "achieved_on": None,
                },
            )
            session.add(row)
            session.flush()
        result.append(row)
    session.commit()
    return result


def github_text(repository: str, client: httpx.Client) -> tuple[str, str, str]:
    match = re.fullmatch(
        r"(?:https://github.com/)?([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?", repository
    )
    if not match or any(v in {".", ".."} for v in match.groups()):
        raise HTTPException(422, "Zadej veřejný repozitář jako vlastník/název.")
    owner, repo = match.groups()
    base = f"https://api.github.com/repos/{owner}/{repo}"

    def read(path: str, optional: bool = False) -> dict | None:
        try:
            response = client.get(base + path, headers={"Accept": "application/vnd.github+json"})
        except httpx.HTTPError as exc:
            raise HTTPException(502, "GitHub nyní neodpovídá.") from exc
        if optional and response.status_code == 404:
            return None
        if response.status_code in (403, 429):
            raise HTTPException(429, "GitHub omezil požadavky. Zkus import později.")
        if response.status_code == 404:
            raise HTTPException(404, "Repozitář neexistuje nebo není veřejný.")
        if response.status_code != 200:
            raise HTTPException(502, "GitHub import selhal; profil zůstal beze změny.")
        if len(response.content) > 2 * MAX_BYTES:
            raise HTTPException(413, "Odpověď GitHubu je příliš velká.")
        return response.json()

    meta = read("")
    if not meta or meta.get("private", True):
        raise HTTPException(422, "Importujeme pouze veřejné repozitáře.")
    parts = [f"Metadata: {meta.get('description') or ''}; jazyk: {meta.get('language') or ''}"]
    for path in (
        "/readme",
        "/contents/pyproject.toml",
        "/contents/package.json",
        "/contents/requirements.txt",
    ):
        data = read(path, optional=True)
        if (
            data
            and data.get("type") == "file"
            and data.get("encoding") == "base64"
            and data.get("size", 0) <= MAX_TEXT
        ):
            try:
                body = base64.b64decode(data["content"]).decode("utf-8", errors="replace")[
                    :MAX_TEXT
                ]
            except (ValueError, KeyError):
                continue
            parts.append(f"{path}:\n{body}")
    return f"{owner}/{repo}", f"https://github.com/{owner}/{repo}", "\n\n".join(parts)[:MAX_TEXT]


def propose_extracted(
    session: Session,
    profile: Profile,
    source: str,
    key: str,
    reference: str,
    quote: str,
    proposed: dict,
) -> bool:
    """A proposal found by an extraction step (Gmail, ADR 0009); the user still confirms it.

    ``key`` identifies the origin (e.g. the message id); the verified ``quote`` is the excerpt.
    Returns True when a new proposal was created.
    """
    fingerprint = hashlib.sha256(
        f"{profile.id}:{source}:{key}:{' '.join(quote.split()).casefold()}".encode()
    ).hexdigest()
    if session.scalar(select(ImportProposal).where(ImportProposal.fingerprint == fingerprint)):
        return False
    session.add(
        ImportProposal(
            profile_id=profile.id,
            fingerprint=fingerprint,
            source=source,
            reference=reference,
            excerpt=quote,
            proposed={
                "kind": "achievement",
                "url": None,
                "strength": 0,
                "signals": detected_skills(proposed["title"] + "\n" + quote),
                **proposed,
            },
        )
    )
    session.flush()
    return True
