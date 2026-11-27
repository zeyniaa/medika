"""Generate clearly fictional, local fixtures. No real names or health records."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "samples"
OUT.mkdir(exist_ok=True)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

def generate(name, heading, lines):
    image = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(image)
    title = ImageFont.truetype(FONT, 34)
    body = ImageFont.truetype(FONT, 27)
    small = ImageFont.truetype(FONT, 21)
    draw.text((110, 100), "KLINIK CONTOH MEDIKA", font=title, fill="#1e293b")
    draw.text((110, 158), "Seluruh identitas pada dokumen ini adalah rekaan.", font=small, fill="#64748b")
    draw.line((110, 215, 1130, 215), fill="#0f766e", width=3)
    draw.text((110, 280), heading, font=title, fill="#1e293b")
    for index, line in enumerate(lines):
        draw.text((110, 395 + index * 65), line, font=body, fill="#1e293b")
    draw.text((110, 1580), "DATA SINTETIS UNTUK UJI PERANGKAT LUNAK", font=small, fill="#0f766e")
    image.save(OUT / (name + ".png"))
    image.save(OUT / (name + ".pdf"), "PDF", resolution=150)

generate("contoh-surat-sakit", "SURAT KETERANGAN SAKIT", [
    "Berdasarkan pemeriksaan, pasien berikut:",
    "Nama: Pasien Contoh", "Dinyatakan sakit dan memerlukan istirahat.",
    "Durasi istirahat: 3 hari", "Mulai: 2026-11-20", "Sampai: 2026-11-22",
    "Tanggal surat: 2026-11-20", "Dokter pemeriksa: dr. Contoh",
])
generate("contoh-bukti-pembayaran", "BUKTI PEMBAYARAN", [
    "Nama: Pasien Contoh", "Layanan: Konsultasi umum", "Total pembayaran: Rp 100.000",
    "Tanggal: 2026-11-20", "Status pembayaran: Lunas", "Petugas: Kasir Contoh",
])
print("Generated two fictional document types in PNG and PDF.")
