from __future__ import annotations

import io
import threading
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from .config import Settings


class DocumentError(ValueError):
    pass


@dataclass
class Document:
    mime: str
    extension: str
    pages: int
    width: int
    height: int


def inspect_document(data: bytes, settings: Settings) -> Document:
    if not data or len(data) > settings.max_file_bytes:
        raise DocumentError("Berkas harus terisi dan berukuran maksimal 10 MB.")
    if data.startswith(b"%PDF-"):
        try:
            import pypdfium2 as pdfium
            pdf = pdfium.PdfDocument(data)
            try:
                count = len(pdf)
                if not 1 <= count <= settings.max_pages:
                    raise DocumentError("PDF baseline harus berisi 1–3 halaman. Semua halaman akan diperiksa.")
                page = pdf[0]
                try:
                    width, height = page.get_size()
                    if width <= 0 or height <= 0 or width * height > settings.max_pixels:
                        raise DocumentError("Ukuran halaman PDF tidak didukung.")
                    return Document("application/pdf", ".pdf", count, round(width), round(height))
                finally:
                    page.close()
            finally:
                pdf.close()
        except DocumentError:
            raise
        except Exception:
            raise DocumentError("PDF rusak, terkunci, atau tidak dapat dibaca.") from None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in {"JPEG", "PNG"}:
                    raise DocumentError("Gunakan berkas JPG, PNG, atau PDF.")
                width, height = image.size
                if width * height > settings.max_pixels:
                    raise DocumentError("Gambar terlalu besar. Batasnya 30 megapiksel.")
                if getattr(image, "n_frames", 1) != 1:
                    raise DocumentError("Gunakan gambar satu halaman, bukan gambar animasi.")
                image.verify()
                return Document("image/jpeg" if image.format == "JPEG" else "image/png", ".jpg" if image.format == "JPEG" else ".png", 1, width, height)
    except DocumentError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise DocumentError("Gambar tidak valid atau rusak. Gunakan JPG, PNG, atau PDF yang dapat dibuka.") from None


class DocumentReader:
    def __init__(self):
        self._ocr = None
        self._lock = threading.Lock()

    def _read_image(self, image: Image.Image) -> str:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
        with self._lock:
            if self._ocr is None:
                self._ocr = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((2400, 3200))
            result, _ = self._ocr(np.asarray(image))
        return "\n".join(str(entry[1]) for entry in (result or []) if len(entry) > 1)

    def read(self, data: bytes, document: Document) -> tuple[str, str]:
        if document.mime != "application/pdf":
            with Image.open(io.BytesIO(data)) as image:
                return self._read_image(image), "rapidocr"
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(data)
        chunks, methods = [], set()
        try:
            for index in range(len(pdf)):
                page = pdf[index]
                try:
                    textpage = page.get_textpage()
                    try:
                        text = textpage.get_text_range().strip()
                    finally:
                        textpage.close()
                    if len(text) < 40:
                        width, height = page.get_size()
                        scale = min(2.5, 2400 / max(width, height))
                        bitmap = page.render(scale=scale)
                        try:
                            image = bitmap.to_pil().copy()
                        finally:
                            bitmap.close()
                        try:
                            text = self._read_image(image)
                        finally:
                            image.close()
                        methods.add("rapidocr")
                    else:
                        methods.add("pdf_text")
                    chunks.append(f"[Halaman {index + 1}]\n{text}")
                finally:
                    page.close()
        finally:
            pdf.close()
        return "\n\n".join(chunks), "+".join(sorted(methods))

