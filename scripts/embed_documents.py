from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from google import genai
from google.genai import types


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "third_party" / "nvidia-build-an-agent"
OUTPUT_PATH = ROOT / "data" / "embeddings.json"
DOCUMENT_NAMES = ("hardware-refresh.md", "help-and-support.md")
SOURCE_REPOSITORY = "https://github.com/brevdev/workshop-build-an-agent"
SOURCE_REVISION = "ac389a0ce6452d4b69af73f75806543fdc652b95"
MODEL = "gemini-embedding-2"
DIMENSIONS = 768


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def chunk_document(path: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
    source_text = path.read_text(encoding="utf-8")
    lines = source_text.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ValueError(f"Expected a level-one title in {path}")

    document_title = lines[0][2:].strip()
    section_title = "Introduction"
    section_lines: list[str] = []
    chunks: list[dict[str, str]] = []

    def append_section() -> None:
        body = "\n".join(section_lines).strip()
        if not body:
            return
        chunks.append(
            {
                "id": f"{path.stem}:{slugify(section_title)}",
                "source": path.relative_to(ROOT).as_posix(),
                "document_title": document_title,
                "section": section_title,
                "text": f"# {document_title}\n\n{body}",
            }
        )

    for line in lines[1:]:
        if line.startswith("## "):
            append_section()
            section_title = line[3:].strip()
            section_lines = [line]
        else:
            section_lines.append(line)
    append_section()

    document = {
        "source": path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
    }
    return document, chunks


def main() -> None:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")

    documents: list[dict[str, str]] = []
    chunks: list[dict[str, object]] = []
    for name in DOCUMENT_NAMES:
        document, document_chunks = chunk_document(SOURCE_DIR / name)
        documents.append(document)
        chunks.extend(document_chunks)

    client = genai.Client(
        vertexai=True,
        project=project,
        location=location,
        http_options=types.HttpOptions(api_version="v1"),
    )

    for index, chunk in enumerate(chunks, start=1):
        title = f"{chunk['document_title']} - {chunk['section']}"
        prepared_text = f"title: {title} | text: {chunk['text']}"
        response = client.models.embed_content(
            model=MODEL,
            contents=prepared_text,
            config=types.EmbedContentConfig(
                output_dimensionality=DIMENSIONS,
                auto_truncate=False,
            ),
        )
        if not response.embeddings or response.embeddings[0].values is None:
            raise RuntimeError(f"Vertex AI returned no embedding for {chunk['id']}")
        embedding = [float(value) for value in response.embeddings[0].values]
        if len(embedding) != DIMENSIONS:
            raise RuntimeError(
                f"Expected {DIMENSIONS} values for {chunk['id']}, got {len(embedding)}"
            )
        chunk["embedding"] = embedding
        print(f"Embedded {index}/{len(chunks)}: {chunk['id']}")

    payload = {
        "schema_version": 1,
        "embedding": {
            "provider": "Google Cloud Vertex AI",
            "model": MODEL,
            "location": location,
            "dimensions": DIMENSIONS,
            "normalized": True,
            "document_input": "title: {title} | text: {text}",
            "query_input": "task: search result | query: {query}",
        },
        "source": {
            "repository": SOURCE_REPOSITORY,
            "revision": SOURCE_REVISION,
        },
        "documents": documents,
        "chunks": chunks,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(chunks)} chunks to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
