from pathlib import Path
from typing import Any, ClassVar

from haystack import Document
from haystack.components.converters import DOCXToDocument, PyPDFToDocument
from haystack.components.preprocessors import MarkdownHeaderSplitter


class ReadContent:
    suffixes: tuple[str, ...] = ()
    converter_cls = None
    converter_kwargs: ClassVar[dict[str, Any]] = {}

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise FileNotFoundError(f"Not a file: {self.path}")
        if self.suffixes and self.path.suffix.lower() not in self.suffixes:
            raise ValueError(f"{type(self).__name__} cannot read {self.path.suffix}")

    def read(self) -> list[Document]:
        if self.converter_cls is None:
            raise TypeError(f"{type(self).__name__} has no converter")
        converter = self.converter_cls(**self.converter_kwargs)
        return converter.run(sources=[self.path])["documents"]


class Markdown(ReadContent):
    suffixes = (".md", ".markdown")
    splitter_cls = MarkdownHeaderSplitter
    splitter_kwargs: ClassVar[dict[str, Any]] = {
        "keep_headers": True,
        "header_split_levels": [1, 2, 3, 4, 5, 6],
    }

    def read(self) -> list[Document]:
        document = Document(
            content=self.path.read_text(encoding="utf-8"),
            meta={"file_path": self.path.name},
        )
        splitter = self.splitter_cls(**self.splitter_kwargs)
        warm_up = getattr(splitter, "warm_up", None)
        if callable(warm_up):
            warm_up()
        documents = splitter.run(documents=[document])["documents"]
        if not isinstance(documents, list):
            raise TypeError(
                f"{type(splitter).__name__} did not return a document list"
            )
        return documents


class Pdf(ReadContent):
    suffixes = (".pdf",)
    converter_cls = PyPDFToDocument


class Docx(ReadContent):
    suffixes = (".docx",)
    converter_cls = DOCXToDocument


_READERS = {
    ".md": Markdown,
    ".markdown": Markdown,
    ".pdf": Pdf,
    ".docx": Docx,
}


def can_read(path: str | Path) -> bool:
    return Path(path).suffix.lower() in _READERS


def read(path: str | Path) -> list[Document]:
    path = Path(path)
    try:
        cls = _READERS[path.suffix.lower()]
    except KeyError as exc:
        raise ValueError(f"Unsupported file type: {path.suffix}") from exc
    return cls(path).read()
