"""
Type schemas and hover-friendly docs for the AI Livestream system.

This file is types-only. It documents the shapes of configuration objects and
runtime payloads passed between modules (core orchestration, generation, data).
Use these types to annotate variables and function parameters for rich IDE hovers.

Design goals:
- Accurate to current code
- Prefer `TypedDict` + aliases so dict configs keep working unchanged.
- Document key objects at every step of the pipeline:
  entry config → collection orchestration → scene generation → playback.
"""

from __future__ import annotations

from typing import (
    Any,
    Awaitable,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
    TypedDict,
    Union,
)
try:
    # Python 3.11+
    from typing import NotRequired
except ImportError:
    # Python 3.10/Colab fallback
    from typing_extensions import NotRequired

# ──────────────────────────────────────────────────────────────────────────────
# Basic aliases (used throughout)
URL = str
"""A fully-qualified URL string (e.g., 'https://example.com/page')."""

FilePath = str
"""Absolute or relative file path (e.g., 'combined_output_scene_1_audio.mp3')."""

LanguageCode = str
"""Language/region code controlling formatting/voice (e.g., 'ph', 'en')."""

SceneName = str
"""Human-friendly scene identifier (e.g., 'first_scene')."""

QueryString = str
"""A single natural-language search string."""

# ──────────────────────────────────────────────────────────────────────────────
# High-level configuration (what the user / entrypoint provides)
SearchQueries = Union[List[QueryString], Dict[str, QueryString]]
"""
Scene-level search queries.

Permissive by design:
- either a list[str]
- or a dict[str, str] of query-name → query
"""

Websites = Union[
    List[URL],
    Dict[str, Union[URL, List[URL]]],  # e.g. {"primary_website": URL, "sources": [URL, ...]}
]
"""
Scene-level website sources.

Permissive by design:
- a flat list of URLs
- or a dict with keys like 'primary_website' and 'sources'
"""

class SceneConfig(TypedDict, total=False):
    """
    Configuration for **one scene** within a collection.

    Keys:
        name:              Scene identifier (display/logging).
        search_queries:    Queries used to collect context (scrape/db build).
        websites:          Sources to scrape and/or trust for the scene.
        system_instructions:
                           Prompt template for the LLM to generate script/keys.
        language:          Language/region code (influences TTS voice/format).
    """
    name: SceneName
    search_queries: SearchQueries
    websites: Websites
    system_instructions: str
    language: LanguageCode


class CollectionConfig(TypedDict):
    """
    Configuration for a **collection** (batch) of scenes to be played in order.

    Keys:
        tt_storm_url:              Tropical Tidbits (or similar) page to scrape images from.
        scenes:                    Ordered list of SceneConfig items to run sequentially.
        total_collection_iterations:
                                   Number of times to play the full collection in a cycle
                                   before generating a new collection.
    """
    tt_storm_url: URL
    scenes: List[SceneConfig]
    total_collection_iterations: int

# ──────────────────────────────────────────────────────────────────────────────
# Data layer: scraping, database construction, and retrieval
ImageURL = URL
"""Image URL scraped from a target site (e.g., Tropical Tidbits)."""

ScrapedImageList = List[ImageURL]
"""All images scraped for the current collection."""

class DocumentLike(TypedDict):
    """
    Minimal representation of a text chunk used for embeddings/FAISS.

    Keys:
        page_content: The text content to embed/index.
        metadata:     Arbitrary metadata, such as {'website': <url>, 'id': <uuid>}.
        id:           Optional stable ID for deduplication/tracing.
    """
    page_content: str
    metadata: Dict[str, Any]
    id: NotRequired[str]


class VectorDBBundle(TypedDict):
    """
    Link a vector database to its metadata (e.g., website/source).

    Keys:
        database:  Opaque handle to a vector store (e.g., FAISS instance).
        metadata:  {'website': <url>, ...} or similar attribution.
    """
    database: Any
    metadata: Dict[str, Any]


class DatabaseRecord(TypedDict, total=False):
    """
    Bundle returned by database creation for a single query.

    Keys:
        query:          The originating search query (string).
        database_list:  List of VectorDBBundle, one per source/website.
    """
    query: str
    database_list: List[VectorDBBundle]


class WebsiteSlot(TypedDict, total=False):
    """A primary website and an optional backup, scraped by the same driver."""
    primary: URL
    backup: Optional[URL]


WebsitesSlots = Dict[str, WebsiteSlot]

SceneDatabaseResults = List[DatabaseRecord]
"""
The list of database bundles associated with one **scene**.
"""

AllScenesDatabaseResults = List[SceneDatabaseResults]
"""
Database results for the entire **collection** (parallel to the SceneConfig list).
"""


# ──────────────────────────────────────────────────────────────────────────────
# Text generation (LLM) and scene item synthesis
class GeneratedItems(TypedDict, total=False):
    """
    The minimal content bundle produced for a scene by the orchestrators.

    Keys:
        script:        The narration/script text (fed into TTS).
        key_messages:  Optional bullet points (used for overlays/recaps).
        topic:         Optional concise topic/title string.
        image_urls:    Optional image URLs selected for this scene.
    """
    script: str
    key_messages: List[str]
    topic: str
    image_urls: List[URL]


SceneItems = GeneratedItems
"""
Alias: the content payload for a single scene (prepares inputs for audio/render).
"""

ScenesItemsList = List[SceneItems]
"""
All generated items for the collection (aligned with SceneConfig order).
"""


# ──────────────────────────────────────────────────────────────────────────────
# File management and outputs
SavedStreamItems = List[FilePath]
"""
List of file paths that should be downloaded/saved for the scene (e.g., images, script).
"""

class AudioInfo(TypedDict):
    """
    Metadata required to schedule/play an audio asset.

    Keys:
        name:              Filename (e.g., 'combined_output_scene_1_audio.mp3').
        duration_seconds:  Length of audio, in seconds.
    """
    name: FilePath
    duration_seconds: float


GenerateSceneReturn = Tuple[SavedStreamItems, AudioInfo]
"""
Return shape from `generate_scene_content(...)`:
    (saved_stream_items, audio_info)
"""


# ──────────────────────────────────────────────────────────────────────────────
# Orchestration: play pipeline, collections, scenes, concurrency
# Task-like alias anything created via asyncio.create_task(...)
TaskLike = Any
"""
Represents an asyncio.Task (or similar awaitable) created by the orchestration.
Kept as `Any` to avoid importing asyncio here; annotate call sites more concretely if desired.
"""

class PlayAudioTaskInfo(TypedDict, total=False):
    """
    Optional wrapper for audio task metadata (if you choose to track it).

    Keys:
        task:     The asyncio task handle that is currently playing audio.
        audio:    The AudioInfo for the asset being played.
        started:  Epoch seconds when playback began.
    """
    task: TaskLike
    audio: AudioInfo
    started: float

# ──────────────────────────────────────────────────────────────────────────────
# Utilities / Config state (used across modules)
# [ none yet ]
