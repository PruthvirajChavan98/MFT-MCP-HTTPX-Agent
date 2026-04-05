"""Knowledge base sub-package: repo, service, vector store, FAQ ingestion."""

from .faq_classifier import classify_faqs
from .milvus_store import kb_milvus_store
from .repo import KnowledgeBaseRepo
from .service import KnowledgeBaseService, knowledge_base_service

__all__ = [
    "KnowledgeBaseRepo",
    "KnowledgeBaseService",
    "classify_faqs",
    "kb_milvus_store",
    "knowledge_base_service",
]
