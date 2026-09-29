from typing import Any, ClassVar

from haystack import Document
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.document_stores.types import DocumentStore


def _require_query(query: str) -> None:
    if not isinstance(query, str):
        raise TypeError("Expected a query string")
    if not query:
        raise ValueError("Query must not be empty")


class Retriever:
    retriever_cls = InMemoryBM25Retriever
    retriever_kwargs: ClassVar[dict[str, Any]] = {}

    def __init__(
        self,
        document_store: DocumentStore | None = None,
        *,
        retriever: Any | None = None,
        **kwargs: Any,
    ) -> None:
        if retriever is not None and (document_store is not None or kwargs):
            raise TypeError("Pass either a retriever or a document_store, not both")
        if retriever is not None:
            self._retriever = retriever
            store = getattr(retriever, "document_store", None)
            if store is None:
                raise TypeError("retriever has no document_store")
            self.document_store = store
            return
        if document_store is None:
            raise TypeError("A document_store or retriever is required")
        self.document_store = document_store
        self._retriever = self.retriever_cls(
            document_store=self.document_store,
            **{**self.retriever_kwargs, **kwargs},
        )

    def retrieve(
        self,
        query: str,
        *,
        filters: dict[str, Any] | None = None,
        top_k: int | None = None,
    ) -> list[Document]:
        _require_query(query)
        run_kwargs: dict[str, Any] = {"query": query}
        if filters is not None:
            run_kwargs["filters"] = filters
        if top_k is not None:
            run_kwargs["top_k"] = top_k
        retrieved = self._retriever.run(**run_kwargs)["documents"]
        if not isinstance(retrieved, list):
            raise TypeError(
                f"{type(self._retriever).__name__} did not return a document list"
            )
        return retrieved


def retrieve_documents(
    query: str,
    document_store: DocumentStore | None = None,
    *,
    retriever: Any | None = None,
    filters: dict[str, Any] | None = None,
    top_k: int | None = None,
    **kwargs: Any,
) -> list[Document]:
    return Retriever(document_store, retriever=retriever, **kwargs).retrieve(
        query, filters=filters, top_k=top_k
    )
