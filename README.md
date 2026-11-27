# Medika

Ruang uji baseline surat sakit, berdiri di luar Simpul. Dashboard memakai palet
teal `#0F766E`, biru `#2563EB`, mint `#D1FAE5`, putih `#F8FAFC`, garis `#E2E8F0`,
dan teks `#1E293B`.

## Baseline saat ini

- Model: **qwen-38**, model yang tersedia pada layanan existing Simpul.
- Alur: pembacaan PDF/OCR lokal → qwen-38 → pemeriksaan aturan Python.
- Fine-tuning belum digunakan. Qwen3-VL dan model baru ditunda.
- DeepSeek tidak tersedia pada daftar model layanan saat integrasi diperiksa.
  Pemakaian qwen-38 dipilih langsung oleh pengguna.
- Tidak ada pengajuan cuti, perubahan HR, atau penyalinan tabel pegawai.

## Menjalankan

Python 3.10+ diperlukan. Lingkungan proyek dapat memakai virtual environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
./scripts/start.sh
```

Pemasangan pada server JDS menyimpan arsip dependensi terisolasi di `.runtime/`.
Saat mulai, arsip dipulihkan ke cache disk lokal dengan pemeriksaan checksum;
cache dapat dipulihkan lagi setelah pembersihan `/tmp` tanpa mengunduh ulang.
`scripts/start.sh` mendukung arsip server maupun virtual environment. Alamat default adalah
`http://127.0.0.1:8096` pada server. Untuk perangkat lain, gunakan penerusan port
melalui koneksi server yang sudah diautentikasi. Jangan membuka port secara publik.

Proses terpisah dapat dinyalakan dengan `python3 scripts/start_service.py`.
PID dan log berada di `runtime/`. Ini bukan layanan otomatis saat reboot.

Pada pemasangan server, backend dan proxy dikelola oleh
`medika-backend.service` dan `medika-network.service` pada systemd pengguna.
Sesuai permintaan pengguna, dashboard diakses melalui **HTTP tanpa login** pada
antarmuka LAN. Alamatnya tersedia di `runtime/network/akses.txt` dan tidak disalin
ke source. Backend tetap loopback dengan token internal; kredensial model tetap
berada di server. Siapa pun yang dapat menjangkau port LAN tersebut dapat memakai
fitur dan API Medika. Tidak ada pemisahan data per pengguna.
Gunakan `systemctl --user restart medika-backend.service medika-network.service`
untuk memulai ulang pemasangan ini; jangan menjalankan helper proses terpisah
bersamaan dengan layanan systemd. Autostart terhubung ke `default.target`, dengan
linger aktif agar layanan tidak bergantung pada sesi SSH.

Konfigurasi model dibaca **di server** dari `.env` Simpul melalui
`MEDIKA_SIMPUL_ENV`. Hanya pengaturan model yang digunakan. Kunci dan alamat
layanan tidak disalin ke source Medika, respons API, atau browser.
Untuk konfigurasi independen, gunakan variabel `MEDIKA_MODEL_URL`,
`MEDIKA_MODEL_API_KEY`, dan `MEDIKA_MODEL_NAME` pada environment server.
Jangan menyimpan nilai rahasia di berkas yang dilacak Git.

Untuk akses jaringan, proxy meneruskan token server `MEDIKA_ACCESS_TOKEN` ke
backend. Token ini tidak dikirim ke browser. Pemasangan HTTP tanpa autentikasi
LAN merupakan keputusan eksplisit pengguna; mode pengembangan bawaan tetap loopback.

## Menggunakan dashboard

1. Tambahkan satu JPG, PNG, atau PDF. Maksimal 10 MB dan tiga halaman PDF.
2. Pemeriksaan langsung berjalan dan menampilkan hasil beserta informasi surat.
3. Buka **Lihat rincian** untuk alasan lengkap dan teks yang terbaca.
4. Gunakan **Ganti file** untuk memeriksa file lain, atau **Hapus hasil** untuk
   menghapus dokumen dan hasilnya melalui konfirmasi.

Antarmuka difokuskan pada tambah file dan hasil. Riwayat, ekspor, serta label
penilai masih tersedia di API untuk pengembangan; tidak tampil pada halaman utama.

Data disimpan privat di `runtime/`, tidak diunggah ke hosting pihak lain. Metadata
pengujian memakai berkas JSON per pengujian dengan penggantian atomik, sehingga
tidak bergantung pada penguncian SQLite di folder jaringan. Satu proses layanan
Medika harus menjadi pemilik runtime ini. Teks
dikirim ke layanan model existing yang dipilih server. Raw image tidak dikirim
ke model dalam baseline ini. Tidak ada permintaan font, analitik, atau media eksternal.

## Arti hasil

- `pass`: lolos kriteria baseline administratif berdasarkan teks yang terbaca.
- `fail`: jenis dokumen berbeda atau terdapat pertentangan periode hasil ekstraksi.
- `needs_review`: pembacaan/bukti belum cukup atau masih ada ketidakpastian.
- `failed` adalah **kegagalan proses**, bukan label pada surat.

`authenticity=not_verified` dan `tampering=not_assessed` selalu dinyatakan eksplisit.
Tidak ada klaim asli/palsu, diagnosis benar, atau tanda tangan terautentikasi.
Hasil tidak mengeksekusi penolakan izin HR.

Kriteria `baseline-visual-v1` adalah kriteria eksperimen, bukan persyaratan hukum
universal. Dokumen sakit perlu punya bukti pernyataan sakit/istirahat, pasien,
penerbit, dan paling sedikit satu tanggal yang cukup terbaca untuk bisa lolos
otomatis. Informasi tidak cukup memerlukan tinjauan. Periode memakai hitungan
inklusif. Ketiadaan diagnosis, stempel, atau nomor izin bukan alasan otomatis gagal.

Pencocokan identitas dan kutipan menggunakan teks lokal dengan normalisasi spasi.
Tanggal masih merupakan hasil ekstraksi model; salah baca dapat memengaruhi
pemeriksaan hitungan. Pembacaan teks asli PDF belum memverifikasi kesesuaiannya
dengan tampilan visual PDF. Multi-halaman yang memuat dokumen berbeda dan teks
tersembunyi memerlukan pengujian lebih lanjut. Baseline bukan pemeriksa forensik.

## Evaluasi dan pengembangan berikutnya

Label penilai mengukur kesesuaian dengan kriteria yang sama, bukan keaslian surat.
Hasil baseline ini bukan ukuran akurasi final.
Gunakan kumpulan uji terpisah dan pisahkan dokumen asal/template sebelum melatih model.

Untuk membuat dua contoh rekaan lokal:

```sh
PYTHONPATH="$(python3 scripts/bootstrap_runtime.py)" python3 scripts/generate_samples.py
```

Contoh bertanda data sintetis dapat masuk `needs_review`; ini tidak sama dengan
pemalsuan. Contoh tersebut hanya untuk smoke test, bukan benchmark.

```sh
PYTHONPATH="$(python3 scripts/bootstrap_runtime.py)" PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests -q
```

`scripts/live_smoke.py` menghubungi baseline nyata dengan contoh rekaan.
Jalankan hanya pada runtime pengujian kosong karena skrip mencatat dua percobaan.
`scripts/browser_qa.py` memeriksa desktop, tablet, dan ponsel.
`scripts/browser_flow.py` memeriksa unggah otomatis hingga hasil nyata dan menghapus
data rekaannya. Tentukan `MEDIKA_QA_URL` ke alamat layanan untuk kedua skrip.
Playwright/browser pengujian tercantum dalam `requirements-dev.txt`.

MCP belum dibuat dalam tahap ini. Fungsi pembacaan, koneksi model, aturan keputusan,
dan penyimpanan sudah terpisah agar dapat dibungkus oleh tim MCP selanjutnya.
