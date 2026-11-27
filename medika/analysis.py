from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .provider import PROMPT_VERSION, ProviderError

POLICY_VERSION = "baseline-visual-v1"


class Extracted(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)
    document_type: Literal["sick_letter", "health_letter", "visit_letter", "prescription", "referral", "receipt", "blank_form", "other", "unknown"]
    patient_name: str | None = Field(default=None, max_length=200)
    doctor_name: str | None = Field(default=None, max_length=200)
    facility_name: str | None = Field(default=None, max_length=200)
    issue_date: str | None = Field(default=None, max_length=40)
    rest_start: str | None = Field(default=None, max_length=40)
    rest_end: str | None = Field(default=None, max_length=40)
    rest_days: int | None = Field(default=None, ge=1, le=365)
    sick_statement: str | None = Field(default=None, max_length=500)
    uncertainties: list[str] = Field(default_factory=list, max_length=12)
    summary: str = Field(max_length=1000)


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def supported(value: str, text: str) -> bool:
    # OCR may join words. Normalize only whitespace; do not invent spelling or names.
    return re.sub(r"\s+", "", value).casefold() in re.sub(r"\s+", "", text).casefold()


def decide(raw: dict, text: str) -> dict:
    try:
        fields = Extracted.model_validate(raw)
    except ValidationError:
        raise ProviderError("Informasi dari model tidak sesuai kontrak pemeriksaan. Hasil belum dapat dinilai.") from None
    findings = []
    review = []
    failed = []
    normalized = compact(text)
    checks = []

    def check(code, label, status, detail):
        checks.append({"code": code, "label": label, "status": status, "detail": detail})

    if fields.document_type == "unknown":
        review.append("Jenis dokumen belum dapat dikenali dengan cukup jelas.")
        check("document_type", "Jenis dokumen", "review", review[-1])
    elif fields.document_type != "sick_letter":
        failed.append("Dokumen dikenali sebagai jenis lain, bukan surat keterangan sakit.")
        check("document_type", "Jenis dokumen", "fail", failed[-1])
    else:
        check("document_type", "Jenis dokumen", "pass", "Model mengenali dokumen sebagai surat sakit; bukan verifikasi keaslian.")

    # Evidence and identities must be supported by the locally extracted text.
    for key, label in (("patient_name", "Identitas pasien"), ("doctor_name", "Nama dokter"), ("facility_name", "Nama fasilitas")):
        value = getattr(fields, key)
        if value and supported(value, text):
            check(key, label, "pass", "Teks ditemukan pada hasil pembacaan dokumen.")
        else:
            if value:
                review.append(f"{label} hasil model belum cocok dengan teks yang terbaca.")
                setattr(fields, key, None)
            check(key, label, "review", "Belum tersedia atau belum terbaca dengan jelas.")

    if fields.document_type == "sick_letter":
        if not fields.patient_name:
            review.append("Identitas pasien belum cukup terbaca untuk baseline ini.")
        if not (fields.doctor_name or fields.facility_name):
            review.append("Identitas penerbit belum cukup terbaca untuk baseline ini.")
        evidence = fields.sick_statement
        if evidence and supported(evidence, text):
            check("statement", "Keterangan sakit / istirahat", "pass", evidence)
        else:
            review.append("Kutipan keterangan sakit atau istirahat belum didukung teks yang terbaca.")
            check("statement", "Keterangan sakit / istirahat", "review", review[-1])

    parsed_dates = {}
    for key in ("issue_date", "rest_start", "rest_end"):
        value = getattr(fields, key)
        if value:
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    raise ValueError()
                parsed_dates[key] = date.fromisoformat(value)
            except ValueError:
                review.append("Ada tanggal yang belum dapat diinterpretasikan secara pasti.")
                setattr(fields, key, None)

    start, end = parsed_dates.get("rest_start"), parsed_dates.get("rest_end")
    if start and end:
        days = (end - start).days + 1
        if days < 1:
            failed.append("Tanggal akhir istirahat mendahului tanggal mulai menurut hasil pembacaan model.")
            check("dates", "Konsistensi periode", "fail", failed[-1])
        elif fields.rest_days and days != fields.rest_days:
            failed.append(f"Rentang tanggal berjumlah {days} hari, berbeda dari durasi {fields.rest_days} hari yang terbaca. Penghitungan inklusif.")
            check("dates", "Konsistensi periode", "fail", failed[-1])
        else:
            check("dates", "Konsistensi periode", "pass", f"Rentang {days} hari dengan tanggal awal dan akhir dihitung.")
    else:
        check("dates", "Konsistensi periode", "not_assessed", "Tidak cukup tanggal untuk pencocokan silang. Ini bukan bukti surat palsu.")
    if fields.document_type == "sick_letter" and not (parsed_dates.get("issue_date") or start or end):
        review.append("Belum ada tanggal yang dapat dibaca dengan pasti.")
    review.extend(fields.uncertainties)
    status = "fail" if failed else "needs_review" if review else "pass"
    return {
        "status": status,
        "passed": status == "pass",
        "fields": fields.model_dump(),
        "checks": checks,
        "reasons": list(dict.fromkeys(failed + review)) or ["Lolos kriteria baseline administratif berdasarkan teks yang terbaca."],
        "authenticity": "not_verified",
        "tampering": "not_assessed",
        "policy_version": POLICY_VERSION,
        "prompt_version": PROMPT_VERSION,
    }

