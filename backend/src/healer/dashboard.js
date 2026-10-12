const $ = (id) => document.getElementById(id);
const token = $('token');
const appId = $('app-id');
const sessionId = $('session-id');
const message = $('message');
const rows = $('rows');
const dialog = $('resolution-dialog');
let activeFinding = null;

const segments = location.pathname.split('/').filter(Boolean);
if (segments.length >= 3 && segments[0] === 'app') {
  appId.value = decodeURIComponent(segments[1]);
  sessionId.value = decodeURIComponent(segments[2]);
}
token.value = sessionStorage.getItem('spectre-token') || '';

function element(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content != null) node.textContent = String(content);
  return node;
}
function cell(row, content, className) {
  const td = element('td', className);
  if (content instanceof Node) td.append(content);
  else td.textContent = content;
  row.append(td);
  return td;
}
function link(url, text) {
  try {
    if (!['https:', 'http:'].includes(new URL(url).protocol)) return element('span', '', text);
  } catch (_) { return element('span', '', text); }
  const a = element('a', 'inline-link', text);
  a.href = url;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  return a;
}
async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { Authorization: `Bearer ${token.value}`, ...(options.headers || {}) },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}
function renderRow(item) {
  const tr = element('tr');
  const finding = item.finding;
  const trace = element('div');
  trace.append(element('span', `severity ${finding.severity}`, finding.severity.toUpperCase()));
  trace.append(element('div', 'mono', finding.trace_id));
  trace.append(element('div', 'small', item.app_id + ' / ' + item.session_id));
  if (finding.trace_url) trace.append(link(finding.trace_url, 'View trace ↗'));
  cell(tr, trace);

  const failure = element('div');
  failure.append(element('div', 'reason', finding.reason));
  failure.append(element('div', 'small mono', `${finding.check} · span ${finding.span_id || 'n/a'}`));
  cell(tr, failure);

  const suggestion = element('div');
  suggestion.append(element('div', '', item.suggestion));
  for (const loc of item.candidate_locations) {
    const ref = `${loc.file}:${loc.line}`;
    const line = element('div', 'small mono');
    line.append(loc.url ? link(loc.url, ref) : element('span', '', ref));
    suggestion.append(line);
  }
  if (!item.candidate_locations.length) suggestion.append(element('div', 'small', 'No matching code symbol'));
  cell(tr, suggestion);

  const repair = element('div');
  repair.append(element('div', 'status', item.resolution?.status || 'Unreviewed'));
  if (item.resolution?.note) repair.append(element('div', 'small', item.resolution.note));
  if (item.resolution_history?.length > 1) {
    const history = element('details', 'small');
    history.append(element('summary', '', `${item.resolution_history.length} updates`));
    for (const event of item.resolution_history) {
      history.append(element('div', 'small', `${event.status} · ${event.note || 'No note'}`));
    }
    repair.append(history);
  }
  const pr = element('div', 'small');
  pr.append(item.resolution?.pr_url ? link(item.resolution.pr_url, 'View PR ↗') : element('span', '', 'No PR recorded'));
  repair.append(pr);
  const update = element('button', 'secondary', 'Update progress');
  update.style.marginTop = '12px';
  update.addEventListener('click', () => {
    activeFinding = finding.id;
    $('dialog-finding').textContent = `${finding.check} · ${finding.trace_id}`;
    $('resolution-status').value = item.resolution?.status || 'investigating';
    $('resolution-note').value = item.resolution?.note || '';
    $('resolution-pr').value = item.resolution?.pr_url || '';
    dialog.showModal();
  });
  repair.append(update);
  cell(tr, repair);

  const copy = element('button', 'secondary', 'Copy to Agent');
  copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(item.copy_to_agent);
      copy.textContent = 'Copied ✓';
      setTimeout(() => { copy.textContent = 'Copy to Agent'; }, 1800);
    } catch (_) { message.textContent = 'Clipboard access was denied by the browser.'; }
  });
  cell(tr, copy);
  return tr;
}
async function load() {
  message.textContent = '';
  if (!token.value) { message.textContent = 'Enter the server token to load diagnostics.'; return; }
  sessionStorage.setItem('spectre-token', token.value);
  const query = new URLSearchParams({ since: $('since').value });
  if (appId.value.trim()) query.set('app_id', appId.value.trim());
  if (sessionId.value.trim()) query.set('session_id', sessionId.value.trim());
  $('refresh').disabled = true;
  try {
    const data = await request(`/v1/doctor?${query}`);
    $('trace-count').textContent = data.trace_count;
    $('finding-count').textContent = data.finding_count;
    $('repository').textContent = data.repository.github_url?.replace('https://github.com/', '') || 'Local only';
    $('commit').textContent = data.repository.commit?.slice(0, 8) || 'Unlinked';
    $('updated').textContent = new Date(data.generated_at).toLocaleString();
    if (data.rows.length) rows.replaceChildren(...data.rows.map(renderRow));
    else {
      const tr = element('tr');
      const td = cell(tr, 'No findings in this window.', 'empty');
      td.colSpan = 5;
      rows.replaceChildren(tr);
    }
  } catch (error) { message.textContent = error.message; }
  finally { $('refresh').disabled = false; }
}
$('refresh').addEventListener('click', load);
$('save-resolution').addEventListener('click', async (event) => {
  event.preventDefault();
  try {
    await request('/v1/resolutions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        finding_id: activeFinding,
        status: $('resolution-status').value,
        note: $('resolution-note').value,
        pr_url: $('resolution-pr').value || null,
      }),
    });
    dialog.close();
    await load();
  } catch (error) { message.textContent = error.message; dialog.close(); }
});
if (token.value) load();
