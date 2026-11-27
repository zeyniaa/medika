 'use strict';
const $ = id => document.getElementById(id);
const LABELS = {pass:'Lolos', fail:'Tidak lolos', needs_review:'Perlu ditinjau', failed:'Gagal proses'};
const TYPES = {sick_letter:'Surat sakit', health_letter:'Surat sehat', visit_letter:'Bukti berobat', prescription:'Resep', referral:'Surat rujukan', receipt:'Kuitansi', blank_form:'Formulir kosong', other:'Dokumen lain', unknown:'Belum jelas'};
const state = {file:null, url:null, run:null, busy:false, timer:null, retry:null, pollErrors:0};
let toastTimer;
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined && text !== null) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', '#i-' + name); svg.setAttribute('aria-hidden', 'true'); svg.append(use); return svg;
}
function toast(message) {
  clearTimeout(toastTimer); $('toast').textContent = message; $('toast').hidden = false;
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, 6500);
}
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers:{'X-Medika-Request':'dashboard', ...options.headers}});
  const data = await response.json().catch(() => ({detail:'Respons server belum dapat dibaca.'}));
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Permintaan belum berhasil.');
  return data;
}
function setBusy(busy) {
  state.busy = busy; $('change-file').disabled = busy; $('dropzone').disabled = busy;
  $('result-panel').setAttribute('aria-busy', String(busy));
}
function retry(message, action) {
  $('retry-message').textContent = message; $('retry-box').hidden = false; state.retry = action;
}
function clearResult() {
  $('result-empty').hidden = false; $('result-progress').hidden = true; $('result-content').hidden = true;
  $('result-badge').hidden = true; $('retry-box').hidden = true; $('result-content').replaceChildren(); state.retry = null;
}
function progress(stage) {
  clearResult(); $('result-empty').hidden = true; $('result-progress').hidden = false;
  const messages = {uploading:'Mengunggah file…', queued:'Menyiapkan pemeriksaan…', reading:'Membaca dokumen…', analyzing:'Memeriksa isi surat…', checking:'Menyiapkan hasil…'};
  $('progress-title').textContent = messages[stage] || messages.queued; $('progress-note').textContent = 'Tunggu sebentar.';
}
async function selectFile(file) {
  if (!file || state.busy) return;
  const extension = file.name.split('.').pop().toLowerCase();
  if (!['jpg','jpeg','png','pdf'].includes(extension)) return toast('Gunakan JPG, PNG, atau PDF.');
  if (!file.size || file.size > 10 * 1024 * 1024) return toast('Pilih file berisi dengan ukuran maksimal 10 MB.');
  clearTimeout(state.timer); if (state.url) URL.revokeObjectURL(state.url);
  state.file = file; state.run = null; state.pollErrors = 0; state.url = URL.createObjectURL(file);
  $('file-input').value = ''; $('dropzone').hidden = true; $('file-preview').hidden = false; $('file-name').textContent = file.name;
  $('file-size').textContent = file.size >= 1024 * 1024 ? (file.size / (1024 * 1024)).toFixed(1) + ' MB' : Math.max(1, Math.round(file.size / 1024)) + ' KB';
  const preview = node(extension === 'pdf' ? 'iframe' : 'img');
  if (extension === 'pdf') { preview.title = 'Pratinjau dokumen'; preview.setAttribute('sandbox', 'allow-same-origin'); }
  else preview.alt = 'Dokumen yang dipilih';
  preview.src = state.url; $('preview-media').replaceChildren(preview); await upload();
}
async function upload() {
  if (!state.file || state.busy) return;
  setBusy(true); progress('uploading');
  const body = new FormData(); body.append('file', state.file);
  try { const run = await api('/api/runs', {method:'POST', body}); state.run = run; await poll(run.id); }
  catch (error) { setBusy(false); clearResult(); retry(error.message || 'Koneksi terputus. File mungkin sudah diterima server.', upload); }
}
function schedulePoll(id) { clearTimeout(state.timer); state.timer = setTimeout(() => poll(id), 1200); }
async function poll(id) {
  setBusy(true); $('retry-box').hidden = true;
  try {
    const run = await api('/api/runs/' + encodeURIComponent(id)); state.run = run; state.pollErrors = 0;
    if (['queued','running'].includes(run.state)) { progress(run.stage); schedulePoll(id); }
    else { setBusy(false); renderResult(run); }
  } catch (error) {
    state.pollErrors += 1;
    if (state.pollErrors < 3) return schedulePoll(id);
    setBusy(false); $('progress-title').textContent = 'Koneksi terputus'; $('progress-note').textContent = 'Hasil belum berhasil dimuat.';
    retry('Sambungkan lagi untuk melihat hasil.', () => { state.pollErrors = 0; return poll(id); });
  }
}
function renderResult(run) {
  clearResult(); $('result-empty').hidden = true;
  const content = $('result-content'); content.hidden = false;
  const status = run.state === 'failed' ? 'failed' : run.result?.status;
  $('result-badge').hidden = false; $('result-badge').className = 'result-badge ' + status; $('result-badge').textContent = LABELS[status] || 'Perlu ditinjau';
  const summary = node('div', null, 'result-summary ' + status);
  const titles = {pass:'Lolos pemeriksaan', fail:'Tidak lolos pemeriksaan', needs_review:'Perlu ditinjau', failed:'File belum berhasil diproses'};
  summary.append(node('h3', titles[status] || titles.needs_review));
  const fields = run.result?.fields || {};
  summary.append(node('p', run.state === 'failed' ? run.error : fields.summary || run.result?.reasons?.[0] || 'Periksa informasi yang terbaca di bawah.')); content.append(summary);
  if (run.state === 'failed') retry('Kegagalan proses bukan penilaian terhadap surat.', upload);
  else {
    const details = node('dl', null, 'detail-grid');
    const period = [fields.rest_start, fields.rest_end].filter(Boolean).join(' – ');
    [['Jenis dokumen', TYPES[fields.document_type]], ['Nama pasien', fields.patient_name], ['Fasilitas', fields.facility_name], ['Dokter', fields.doctor_name], ['Tanggal surat', fields.issue_date], ['Istirahat', [fields.rest_days ? fields.rest_days + ' hari' : '', period].filter(Boolean).join(' · ')]].forEach(([label, value]) => {
      const group = node('div'); group.append(node('dt', label), node('dd', value || 'Belum terbaca')); details.append(group);
    }); content.append(details);
    const reasons = node('ul', null, 'reasons');
    (run.result?.reasons || []).slice(0, 3).forEach(text => { const item = node('li'); item.append(icon(status === 'pass' ? 'check' : 'info'), node('span', text)); reasons.append(item); });
    if (reasons.childElementCount) content.append(reasons);
    const more = node('details'); more.append(node('summary', 'Lihat rincian'));
    (run.result?.checks || []).forEach(check => more.append(node('p', check.label + ': ' + check.detail)));
    const otherReasons = (run.result?.reasons || []).slice(3);
    if (otherReasons.length) { const list = node('ul'); otherReasons.forEach(text => list.append(node('li', text))); more.append(list); }
    const text = node('details'); text.append(node('summary', 'Teks yang terbaca'), node('pre', run.ocr_text || 'Tidak ada teks yang terbaca.')); more.append(text);
    const seconds = typeof run.metrics?.total_ms === 'number' ? (run.metrics.total_ms / 1000).toFixed(1) + ' detik' : '';
    more.append(node('p', [run.model, seconds].filter(Boolean).join(' · '))); content.append(more);
  }
  const actions = node('div', null, 'result-actions'); const remove = node('button', 'Hapus hasil', 'text-button'); remove.type = 'button';
  remove.addEventListener('click', async () => {
    if (!window.confirm('Hapus file dan hasil pemeriksaan ini?')) return;
    remove.disabled = true;
    try { await api('/api/runs/' + encodeURIComponent(run.id), {method:'DELETE'}); reset(); }
    catch (error) { toast(error.message); remove.disabled = false; }
  }); actions.append(remove); content.append(actions);
}
function reset() {
  clearTimeout(state.timer); if (state.url) URL.revokeObjectURL(state.url);
  state.url = null; state.file = null; state.run = null; state.pollErrors = 0; setBusy(false);
  $('file-input').value = ''; $('preview-media').replaceChildren(); $('file-preview').hidden = true; $('dropzone').hidden = false; clearResult();
}
async function checkConnection() {
  $('check-connection').disabled = true;
  try {
    const provider = await api('/api/provider/check', {method:'POST'});
    $('connection').className = 'connection ' + (provider.ready ? 'ready' : 'unready'); $('connection-label').textContent = provider.ready ? 'Siap digunakan' : 'Belum terhubung';
    $('connection-notice').hidden = !!provider.ready; $('connection-message').textContent = provider.message || 'Koneksi pemeriksaan belum siap.';
  } catch (error) {
    $('connection').className = 'connection unready'; $('connection-label').textContent = 'Belum terhubung'; $('connection-notice').hidden = false; $('connection-message').textContent = 'Server belum dapat dihubungi.';
  } finally { $('check-connection').disabled = false; }
}
$('dropzone').addEventListener('click', () => $('file-input').click());
$('change-file').addEventListener('click', () => { if (!state.busy) $('file-input').click(); });
$('file-input').addEventListener('change', event => selectFile(event.target.files[0]));
['dragenter','dragover'].forEach(name => $('dropzone').addEventListener(name, event => { event.preventDefault(); if (!state.busy) $('dropzone').classList.add('dragover'); }));
['dragleave','drop'].forEach(name => $('dropzone').addEventListener(name, event => { event.preventDefault(); $('dropzone').classList.remove('dragover'); }));
$('dropzone').addEventListener('drop', event => { if (event.dataTransfer.files.length !== 1) return toast('Tambahkan satu file setiap kali pemeriksaan.'); selectFile(event.dataTransfer.files[0]); });
$('retry-button').addEventListener('click', async () => { const action = state.retry; if (!action) return; $('retry-button').disabled = true; try { await action(); } finally { $('retry-button').disabled = false; } });
$('check-connection').addEventListener('click', checkConnection);
window.addEventListener('beforeunload', () => { if (state.url) URL.revokeObjectURL(state.url); clearTimeout(state.timer); });
checkConnection();
