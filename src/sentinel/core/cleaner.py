from pathlib import Path
from typing import Any, ClassVar

from haystack import Document
from haystack.components.preprocessors import DocumentCleaner, RecursiveDocumentSplitter


def _require_documents(documents: list[Document]) -> None:
    if not isinstance(documents, list) or any(
        not isinstance(doc, Document) for doc in documents
    ):
        raise TypeError("Expected a list of haystack Document objects")


class CleanContent:
    """Clean Haystack documents, then split them into retrieval chunks."""

    cleaner_cls = DocumentCleaner
    cleaner_kwargs: ClassVar[dict[str, Any]] = {
        "remove_empty_lines": True,
        "remove_extra_whitespaces": True,
        "unicode_normalization": "NFC",
        "strip_whitespaces": True,
    }
    splitter_cls = RecursiveDocumentSplitter
    splitter_kwargs: ClassVar[dict[str, Any]] = {
        "split_length": 120,
        "split_overlap": 24,
        "split_unit": "word",
        "separators": ["\n\n", "\n", " "],
    }
    skip_chunk_suffixes: ClassVar[tuple[str, ...]] = ()

    def __init__(
        self,
        component: Any | None = None,
        splitter: Any | None = None,
        **kwargs: Any,
    ) -> None:
        if component is not None and kwargs:
            raise TypeError("Pass either a cleaner component or kwargs, not both")
        if component is not None:
            self._cleaner = component
        else:
            self._cleaner = self.cleaner_cls(**{**self.cleaner_kwargs, **kwargs})
        self._splitter = splitter or self.splitter_cls(**self.splitter_kwargs)

    def clean(self, documents: list[Document]) -> list[Document]:
        _require_documents(documents)
        if not documents:
            return []
        cleaned = self._cleaner.run(documents=documents)["documents"]
        if not isinstance(cleaned, list):
            raise TypeError(
                f"{type(self._cleaner).__name__} did not return a document list"
            )
        headed = [doc for doc in cleaned if self._skip_chunk(doc)]
        rest = [doc for doc in cleaned if not self._skip_chunk(doc)]
        if not rest:
            return headed
        return headed + self._chunk(rest)

    def _skip_chunk(self, document: Document) -> bool:
        suffix = Path(str(document.meta.get("file_path", ""))).suffix.lower()
        return suffix in self.skip_chunk_suffixes

    def _chunk(self, documents: list[Document]) -> list[Document]:
        if not documents:
            return []
        warm_up = getattr(self._splitter, "warm_up", None)
        if callable(warm_up):
            warm_up()
        chunked = self._splitter.run(documents=documents)["documents"]
        if not isinstance(chunked, list):
            raise TypeError(
                f"{type(self._splitter).__name__} did not return a document list"
            )
        return chunked


def clean_documents(documents: list[Document], **kwargs: Any) -> list[Document]:
    return CleanContent(**kwargs).clean(documents)
