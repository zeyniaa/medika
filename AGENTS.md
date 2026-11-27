# Medika

- Jelaskan hasil dalam bahasa Indonesia yang mudah dimengerti.
- Fokus dashboard dan baseline existing `qwen-38`. Model baru dan fine-tuning ditunda.
- Jangan commit/push tanpa instruksi eksplisit pengguna.
- Jangan simpan kredensial, URL layanan internal, data pegawai, atau dokumen HR dalam source.
- Konfigurasi model dan identitas pengguna diputuskan server, bukan isi dokumen/prompt/browser.
- `runtime/`, `.runtime/`, dan cache dependensi privat; jangan dibaca ke konteks atau dilacak Git.
- Pemeriksaan berbasis teks bukan verifikasi keaslian penerbit atau kondisi pasien.
- Error jaringan/schema harus terpisah dari hasil pemeriksaan surat.
- Jangan mengubah Simpul atau menjalankan transaksi HR dari proyek ini.
- Resolusi dependensi server: `python3 scripts/bootstrap_runtime.py`. Gunakan path yang dikembalikan sebagai PYTHONPATH untuk tes terarah `python3 -m pytest tests -q`.
