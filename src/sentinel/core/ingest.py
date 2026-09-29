from typing import Any

from haystack import Document
from haystack.components.writers import DocumentWriter
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.document_stores.types import DocumentStore, DuplicatePolicy


def _require_documents(documents: list[Document]) -> None:
    if not isinstance(documents, list) or any(
        not isinstance(doc, Document) for doc in documents
    ):
        raise TypeError("Expected a list of haystack Document objects")


class Ingest:
    document_store_cls = InMemoryDocumentStore
    writer_cls = DocumentWriter
    policy = DuplicatePolicy.SKIP

    def __init__(
        self,
        document_store: DocumentStore | None = None,
        *,
        policy: DuplicatePolicy | None = None,
        writer: Any | None = None,
    ) -> None:
        if writer is not None and document_store is not None:
            raise TypeError("Pass either a writer or a document_store, not both")
        if policy is not None:
            self.policy = policy
        if writer is not None:
            self._writer = writer
            store = getattr(writer, "document_store", None)
            self.document_store = (
                store if store is not None else self.document_store_cls()
            )
            return
        self.document_store = document_store or self.document_store_cls()
        self._writer = self.writer_cls(
            document_store=self.document_store, policy=self.policy
        )

    def ingest(self, documents: list[Document]) -> int:
        _require_documents(documents)
        if not documents:
            return 0
        written = self._writer.run(documents=documents)["documents_written"]
        if not isinstance(written, int):
            raise TypeError(
                f"{type(self._writer).__name__} did not return documents_written"
            )
        return written


def ingest_documents(
    documents: list[Document],
    document_store: DocumentStore | None = None,
    **kwargs: Any,
) -> int:
    return Ingest(document_store, **kwargs).ingest(documents)
