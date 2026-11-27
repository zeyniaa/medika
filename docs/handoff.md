# Handoff Medika — 27 November 2026

## Keputusan pengguna

- Nama: Medika. Folder terpisah `/home/jds2/Medika` pada server JDS.
- Dashboard terlebih dahulu; model baru dan fine-tuning ditunda.
- Pengguna awalnya menyebut DeepSeek. Pemeriksaan layanan existing menampilkan
  `qwen-35b`, `qwen-35b-vision`, `ocr-lighton`, dan `qwen-38`, tanpa DeepSeek.
  Pengguna kemudian secara eksplisit memilih baseline `qwen-38`.
- Palet warna mengikuti referensi pengguna. Tidak ada publikasi ke Sites/cloud.

## Implementasi

- Frontend HTML/CSS/JS tanpa build step; bahasa Indonesia; desktop, tablet, dan ponsel.
- Antarmuka disederhanakan sesuai permintaan terakhir: tambah file langsung
  menjalankan pemeriksaan, lalu hasil. Sidebar, statistik, evaluasi, konfigurasi,
  dan formulir label dihapus dari UI; API serta data sebelumnya dipertahankan.
  Rincian pemeriksaan dapat dibuka seperlunya dan hasil bisa dihapus dengan konfirmasi.
- FastAPI; antrean satu worker, delapan slot; unggah berbatas JPG/PNG/PDF.
- PDFium untuk validasi/render/teks PDF; RapidOCR lokal untuk gambar/halaman pindai.
- Adapter model OpenAI-compatible menyesuaikan pola koneksi Simpul:
  normalisasi URL, bearer di server, dan opsi DNS absolute mempertahankan Host/SNI.
  Tidak mengimpor backend Simpul, menyalin `.env`, atau memodifikasi layanan Simpul.
- Model/instruksi ditentukan server. Instruksi memperlakukan teks dokumen sebagai data.
- JSON hasil divalidasi Pydantic; bukti nama/kutipan dicocokkan ke teks lokal.
- Pemeriksaan tanggal/durasi menggunakan Python, penghitungan inklusif.
- Penyimpanan lokal hanya berkas/hasil eksperimen Medika, bukan mirror HR.
- Folder proyek server gagal melakukan locking SQLite saat aktivasi awal.
  Penyimpanan diganti menjadi JSON per pengujian, cache dalam proses, serta
  write/flush/fsync/replace atomik. Tidak ada data pengguna sebelum perubahan ini.
  Gunakan satu proses layanan untuk satu runtime; tidak ada kebutuhan database terpisah.
- Browser tidak menerima kredensial, endpoint upstream, atau path konfigurasi privat.
- Loopback default; proteksi Origin/header untuk mutasi, CSP, no-store,
  penolakan berkas rusak/kelebihan ukuran/halaman, dan penghapusan dengan konfirmasi UI.
- Hasil, label penilai, filter riwayat, ekspor, serta matriks kesesuaian dapat digunakan.

## Verifikasi

- 24 tes otomatis lulus, termasuk pemulihan penyimpanan setelah restart. Ada peringatan deprecation TestClient/httpx dari dependency;
  tidak ada tes gagal.
- Tes otomatis mencakup jenis dokumen, ketidakpastian, bukti yang tidak didukung,
  tanggal, schema, kebocoran konfigurasi, unggah/review/ekspor/hapus, CSRF,
  teks tidak terbaca, dan pemisahan kegagalan layanan dari penolakan surat.
- Smoke test **layanan qwen-38 nyata** memakai satu PNG surat sakit rekaan dan satu
  PDF bukti pembayaran rekaan. Klasifikasi keduanya sesuai jenis yang diharapkan.
- Hasil awal PNG `needs_review`, dengan ketidakpastian spasi OCR dan penanda sintetis;
  PDF `fail` karena kuitansi. Ini bukan pengukuran akurasi atau keaslian.
- Waktu proses pada kedua contoh awal sekitar 5–6 detik; bukan jaminan performa.
- Pencocokan spasi OCR diperbaiki dan diberi tes. Penanda sintetis dapat tetap memicu tinjauan.
- Runtime smoke test dan data pengguna dipisahkan. Tidak memakai data pegawai live.
- Browser desktop 1440px dan ponsel 390px: navigasi, konfigurasi, keadaan kosong,
  pencarian/filter, serta tidak ada overflow halaman atau error JavaScript.
- Alur browser penuh memakai qwen-38 nyata: unggah, hasil, label manual, ekspor,
  dan konfirmasi hapus lulus tanpa error JavaScript.
- Dependensi server dibundel pada `.runtime/`, dengan checksum dan pemulihan cache
  disk lokal otomatis. Ini menghindari banyak akses berkas kecil pada folder proyek.

## Batas dan lanjutan

- Akses LAN kini memakai **HTTP tanpa username/password**, sesuai instruksi eksplisit
  pengguna terbaru. HTTPS dan autentikasi Basic pada proxy telah dihapus; sertifikat
  dan berkas password lama juga dihapus. Backend tetap loopback dengan token internal.
  Alamat tersedia di `runtime/network/akses.txt`; jangan salin alamat internal atau
  konfigurasi privat ke source. Semua pemakai yang menjangkau port LAN berbagi akses
  yang sama, termasuk API riwayat dan penghapusan.
- Dua layanan systemd pengguna mengelola backend dan proxy Medika. Autostart memakai
  symlink pada `default.target.wants`, dengan linger aktif pada akun server.
  Pada filesystem server, laporan `is-enabled` tidak konsisten; periksa juga symlink
  persisten dan dependensi `default.target`. Jangan jalankan helper proses terpisah
  bersamaan dengan layanan ini.
- Tidak memeriksa RS/dokter ke registri, QR, tanda tangan digital, atau manipulasi gambar.
- Teks PDF belum dibandingkan dengan tampilan visual; bukan pemeriksa forensik.
- Tanggal hasil ekstraksi model masih dapat salah; label penilai penting untuk evaluasi.
- Dataset pengembangan ini tidak cukup untuk klaim akurasi asli/palsu.
- MCP belum diterapkan; bungkus layanan yang ada setelah kontrak final disepakati.
- Commit/push hanya atas instruksi eksplisit pengguna. Pengguna kini meminta repo
  GitHub baru; source disiapkan tanpa runtime, cache, kredensial, atau data HR.

## Akses dan antarmuka terkini

- HTTP pada antarmuka LAN server melayani dashboard tanpa dialog login atau sertifikat.
- Koneksi qwen-38 lewat proxy berhasil. Token backend tetap tidak dikirim ke browser;
  validasi Origin/header untuk mutasi tetap aktif.
- Dua layanan systemd Medika tetap berjalan dengan autostart; Simpul tidak diubah.
- Teks UI dipangkas menjadi petunjuk tambah file, progres, dan hasil; batas pemeriksaan
  tetap dinyatakan singkat: pemeriksaan isi dokumen, bukan bukti keaslian.
- Verifikasi terbaru: 24 tes backend lulus; browser desktop, tablet, dan ponsel
  tanpa error JavaScript atau overflow. Tambah PNG pembayaran sintetis langsung
  memproses OCR/qwen-38 hingga hasil, rincian bisa dibuka, lalu penghapusan dengan
  konfirmasi berhasil. Data rekaan dibersihkan dan jumlah riwayat semula dipertahankan.

## Pemeriksaan pemasangan akhir

- Layanan dari `/home/jds2/Medika` merespons HTTP 200 dan model `qwen-38` terhubung.
- Arsip dependensi berhasil dipulihkan ke disk lokal dan semua 24 tes lulus dari folder terpasang.
- Satu PNG pembayaran rekaan diproses melalui OCR dan model nyata; label, ekspor, dan penghapusan berhasil pada penyimpanan JSON server.
- Data uji akhir dihapus; riwayat pengguna kosong.
- Browser desktop dan ponsel lulus tanpa error JavaScript atau overflow halaman.
