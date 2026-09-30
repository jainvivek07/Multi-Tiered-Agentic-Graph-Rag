from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat
from docling.chunking import HierarchicalChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.core.logger import log
from src.models.graph import DocumentChunk

_pipeline_options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
_converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=_pipeline_options)}
)
_hierarchical_chunker = HierarchicalChunker()
_text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)

def parse_document(file_path: str | Path, doc_id: str) -> list[DocumentChunk]:
    """
    Parses a document. Uses RecursiveCharacterTextSplitter for plain text formats,
    and Docling's HierarchicalChunker for rich documents (PDF, HTML).
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    log.info("Parsing document", filename=path.name, suffix=suffix)

    chunks: list[DocumentChunk] = []

    if suffix in ['.txt', '.csv']:
        # Route 1: Plain text chunking
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
        except UnicodeDecodeError:
            with open(path, 'r', encoding='latin-1') as f:
                text = f.read()
                
        raw_chunks = _text_splitter.split_text(text)
        for i, text_chunk in enumerate(raw_chunks):
            t = text_chunk.strip()
            if t:
                chunks.append(
                    DocumentChunk(
                        id=f"{doc_id}_chunk_{i}",
                        text=t,
                        seq_index=i,
                    )
                )
    else:
        # Route 2: Rich document chunking via Docling
        result = _converter.convert(str(path))
        raw_chunks = list(_hierarchical_chunker.chunk(result.document))

        for i, c in enumerate(raw_chunks):
            text = c.text.strip()
            if text:
                chunks.append(
                    DocumentChunk(
                        id=f"{doc_id}_chunk_{i}",
                        text=text,
                        seq_index=i,
                    )
                )

    log.info("Document parsed and chunked", filename=path.name, chunks=len(chunks))
    return chunks
