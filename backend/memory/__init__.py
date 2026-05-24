"""
memory — custom long-term + short-term memory subsystem for JobAgent AI.

No third-party memory frameworks (mem0, LangMem, Zep, etc.).
Built on asyncpg (PostgreSQL/pgvector) + redis-py.
"""

from memory.embedder import MemoryEmbedder
from memory.extractor import MemoryExtractor
from memory.manager import MemoryManager

__all__ = ["MemoryManager", "MemoryEmbedder", "MemoryExtractor"]
