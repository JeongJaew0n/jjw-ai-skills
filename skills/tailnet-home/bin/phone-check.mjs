#!/usr/bin/env node
// Open a home app the way the phone does (390x844, touch, light and dark) in headless Chrome and say what a person would
// trip over: sideways scrolling, errors and failed loads (an absolute path breaks under /apps/<id>/), things too small to
// tap, text too small to read, whether the page follows dark mode. It opens the page and looks, never clicks, and blocks
// every request the page makes that is not GET/HEAD/OPTIONS (a page that saves on load must not write while it is checked).
// It cannot stop an app that changes state on a GET (gisa makes today's quiz set when its home is opened, for one).
//
//   node phone-check.mjs <id | url | --all> [--out <folder>] [--wait <ms>] [--skip id,id]
//     --all  the home and every app it serves that is switched on, one after another, then a summary
//     <id>   an app on this Mac's home: http://localhost:8700/apps/<id>/
//     --out  where the two screenshots go (default: a new temporary folder)
//
// Chrome is driven over a pipe, not a debugging port: on this Mac a port on 127.0.0.1 can be reached from the tailnet
// (userspace tailscaled), so a port would open the browser to every device there while the check runs.
// Exit code: 0 nothing that breaks the page, 1 sideways scroll or errors, 2 could not run.
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const args = process.argv.slice(2);
const flag = (name, dflt) => { const i = args.indexOf(name); return i >= 0 ? args.splice(i, 2)[1] : dflt; };
const OUT = flag('--out', null) || fs.mkdtempSync(path.join(os.tmpdir(), 'phone-check-'));
const WAIT = Number(flag('--wait', 1500));
const SKIP = (flag('--skip', '') || '').split(',').filter(Boolean);
const target = args[0];
if (!target || target === '-h' || target === '--help') { console.error('쓰는 법: node phone-check.mjs <앱 id | 주소 | --all> [--out 폴더] [--wait ms] [--skip id,id]'); process.exit(target ? 0 : 2); }
const odd = args.find(x => x.startsWith('-') && x !== '--all');
if (odd || args.length > 1) { console.error(odd ? `모르는 옵션: ${odd}` : `주소는 하나만: ${args.join(' ')}`); process.exit(2); }

// --all: the home itself, then every app the home serves that is switched on (skipping link-only apps and --skip ones)
if (target === '--all') {
  const homeDir = process.env.TAILNET_HOME_DIR || path.join(os.homedir(), 'my/Dev/home');
  const read = f => { try { return JSON.parse(fs.readFileSync(path.join(homeDir, f), 'utf8')); } catch { return {}; } };
  const off = new Set(read('state.json').disabled || []);
  const ids = ['', ...(read('apps.json').apps || []).filter(a => a.root || a.proxy).map(a => a.id)];
  let worst = 0;
  const lines = [];
  for (const id of ids) {
    if (id && off.has(id)) { lines.push(`  -  ${id}: 홈에서 꺼짐, 건너뜀`); continue; }
    if (id && SKIP.includes(id)) { lines.push(`  -  ${id}: --skip, 건너뜀`); continue; }
    const url = `http://localhost:${process.env.TAILNET_HOME_PORT || 8700}/${id ? `apps/${id}/` : ''}`;
    const r = spawnSync(process.execPath, [process.argv[1], url, '--out', path.join(OUT, id || 'home'), '--wait', String(WAIT)], { encoding: 'utf8' });
    process.stdout.write(r.stdout || ''); process.stderr.write(r.stderr || '');
    const checks = (r.stdout || '').split('\n').filter(l => /^  [✓✗] /.test(l) && !l.includes('어두울 때만'));
    const good = checks.filter(l => l.startsWith('  ✓')).length;
    lines.push(r.status === 2 || !checks.length ? `  ✗  ${id || '홈'}: 검사하지 못함`
      : `  ${good === checks.length && !(r.stdout || '').includes('어두울 때만') ? '✓' : '✗'}  ${id || '홈'}: ${good}/${checks.length}`);
    worst = Math.max(worst, r.status ?? 2);
  }
  console.log('\n요약\n' + lines.join('\n'));
  process.exit(worst);
}
const URL_ = /^https?:\/\//.test(target) ? target : `http://localhost:${process.env.TAILNET_HOME_PORT || 8700}/apps/${target}/`;
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
if (!fs.existsSync(CHROME)) { console.error(`Chrome 이 없습니다: ${CHROME} (CHROME 환경 변수로 바꿀 수 있음)`); process.exit(2); }
fs.mkdirSync(OUT, { recursive: true });

const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'phone-check-chrome-'));
const chrome = spawn(CHROME, ['--headless=new', '--remote-debugging-pipe', `--user-data-dir=${profile}`, '--no-first-run',
  '--no-default-browser-check', '--hide-scrollbars', 'about:blank'], { stdio: ['ignore', 'ignore', 'ignore', 'pipe', 'pipe'] });
const toChrome = chrome.stdio[3], fromChrome = chrome.stdio[4];
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => {
  chrome.kill();
  try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
  process.exit(130);
});
let seq = 0, buf = '', session = null;
const waiting = new Map(), events = [];
let blocked = 0;
fromChrome.on('data', chunk => {
  buf += chunk.toString('utf8');
  let i;
  while ((i = buf.indexOf('\0')) >= 0) {
    const m = JSON.parse(buf.slice(0, i)); buf = buf.slice(i + 1);
    if (m.id && waiting.has(m.id)) { waiting.get(m.id)(m); waiting.delete(m.id); }
    else if (m.method === 'Fetch.requestPaused') {         // writes never leave the browser; reads go on
      const p = m.params, read = ['GET', 'HEAD', 'OPTIONS'].includes(p.request.method);
      if (!read) blocked++;
      send(read ? 'Fetch.continueRequest' : 'Fetch.failRequest', read ? { requestId: p.requestId }
        : { requestId: p.requestId, errorReason: 'BlockedByClient' }, m.sessionId).catch(() => {});
    } else if (m.method) events.push(m);
  }
});
const send = (method, params = {}, sid = session) => new Promise((res, rej) => {
  const id = ++seq;
  const timer = setTimeout(() => { waiting.delete(id); rej(new Error(method + ': 응답 없음')); }, 30000);
  waiting.set(id, m => { clearTimeout(timer); m.error ? rej(new Error(method + ': ' + m.error.message)) : res(m.result); });
  toChrome.write(JSON.stringify(sid ? { id, method, params, sessionId: sid } : { id, method, params }) + '\0');
});
const sleep = ms => new Promise(r => setTimeout(r, ms));
const evaluate = async expr => {
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
  return r.result.value;
};

// What the page shows a thumb: interactive things that cannot be hit across 44 px (links inside a sentence may be small).
// Each small one is scrolled to the middle of the screen first, so things below the first screen are hit-tested too.
const LOOK = `(() => {
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && r.bottom > -5000
      && (!e.checkVisibility || e.checkVisibility({ visibilityProperty: true })); };   // not inside a closed <details>
  // a link inside running text (a sentence of 40+ characters around it) may be small; a breadcrumb like "원본 › v1" may not
  const inSentence = a => a.tagName === 'A' && a.parentElement && /^(P|LI|SPAN|TD|DD)$/.test(a.parentElement.tagName)
    && a.parentElement.textContent.trim().length >= 40 && a.parentElement.textContent.trim().length > a.textContent.trim().length + 20;
  const sel = 'a[href], button, select, summary, input:not([type=hidden]), textarea, [role=button], [role=tab], [onclick]';
  // what a thumb can hit, not what is drawn: a transparent ::before can make a small link 44 px tall. Tap 22 px out from
  // the middle each way (on screen): if those points still land on the element, its reach is 44 px.
  const reach = (e) => {
    const y0 = scrollY, x0 = scrollX;
    e.scrollIntoView({ block: 'center', inline: 'center' });
    const r = e.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const done = v => { scrollTo(x0, y0); return v; };
    if (cy - 22 < 0 || cy + 22 > innerHeight || cx - 22 < 0 || cx + 22 > innerWidth) return done(false);
    const on = (x, y) => { const h = document.elementFromPoint(x, y); return !!h && (h === e || e.contains(h)); };
    return done((r.height >= 44 || (on(cx, cy - 21) && on(cx, cy + 21))) && (r.width >= 44 || (on(cx - 21, cy) && on(cx + 21, cy))));
  };
  const small = [...document.querySelectorAll(sel)].filter(e => vis(e) && !inSentence(e) && !e.disabled).map(e => {
    let r = e.getBoundingClientRect();
    if ((e.type === 'checkbox' || e.type === 'radio') && e.closest('label')) r = e.closest('label').getBoundingClientRect();
    return { r, e };
  }).filter(x => Math.min(x.r.width, x.r.height) < 44 && !reach(x.e))
    .map(x => ({ what: (x.e.tagName.toLowerCase() + ' ' + (x.e.getAttribute('aria-label') || x.e.textContent || x.e.value || x.e.name || '').trim().replace(/\\s+/g, ' ')).slice(0, 40),
                 w: Math.round(x.r.width), h: Math.round(x.r.height) }));
  // furigana (<rt>) is small by design: it sits over text that is read at full size
  const tinyEls = [...document.querySelectorAll('body *')].filter(e => vis(e) && !e.closest('rt, rp') && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())
    && parseFloat(getComputedStyle(e).fontSize) < 12);
  const tiny = tinyEls.length;
  const tinyWhat = tinyEls.slice(0, 5).map(e => (e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\\s+/)[0] : '')
    + ' "' + e.textContent.trim().replace(/\\s+/g, ' ').slice(0, 14) + '" ' + parseFloat(getComputedStyle(e).fontSize) + 'px'));
  // the colour behind the middle of the screen: the first box from there up that paints one (an app often paints #root, not body)
  let el = document.elementFromPoint(innerWidth / 2, innerHeight / 2), bg = '';
  const paint = x => { const c = x && getComputedStyle(x).backgroundColor; return c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent' ? c : ''; };
  for (; el && el !== document.documentElement && !bg; el = el.parentElement) bg = paint(el);
  bg = bg || paint(document.body) || paint(document.documentElement);   // body's colour spreads to the whole canvas
  // things to press that a screen reader cannot name (an icon only, no aria-label or title): told, not counted as ✗
  const nameOf = e => (e.getAttribute('aria-label') || e.getAttribute('title') || e.innerText || e.value || e.getAttribute('alt')
    || e.getAttribute('placeholder')                    // browsers read a placeholder as the name when nothing else names it
    || [...e.querySelectorAll('img[alt], svg title')].map(x => x.getAttribute('alt') || x.textContent).join('')
    || (e.id && [...document.querySelectorAll('label[for]')].find(l => l.htmlFor === e.id)?.innerText)
    || (e.getAttribute('aria-labelledby') && document.getElementById(e.getAttribute('aria-labelledby'))?.innerText) || '').trim();
  const nameless = [...document.querySelectorAll('a[href], button, select, input:not([type=hidden]), textarea, [role=button], [role=tab]')]
    .filter(e => vis(e) && !e.disabled && !e.closest('label') && !nameOf(e))
    .map(e => e.tagName.toLowerCase() + (e.id ? '#' + e.id : e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\\s+/)[0] : ''));
  return { title: document.title, wide: document.documentElement.scrollWidth - 390, scale: window.visualViewport ? visualViewport.scale : 1, noMeta: !document.querySelector('meta[name=viewport]'), small, tiny, tinyWhat, nameless, bg: bg || 'rgb(255, 255, 255)' };
})()`;
const lum = c => { const m = String(c).match(/\d+(\.\d+)?/g); if (!m) return null; const [r, g, b, a = 1] = m.map(Number);
  return Number(a) === 0 ? null : (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255; };

let code = 0;
try {
  await sleep(300);
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' }, null);
  ({ sessionId: session } = await send('Target.attachToTarget', { targetId, flatten: true }, null));
  await send('Page.enable'); await send('Runtime.enable'); await send('Log.enable'); await send('Network.enable');
  await send('Fetch.enable', { patterns: [{ urlPattern: '*', requestStage: 'Request' }] });
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 });
  const runs = {};
  for (const scheme of ['light', 'dark']) {
    events.length = 0;
    await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: scheme }] });
    const nav = await send('Page.navigate', { url: URL_ });
    if (nav.errorText) throw new Error(`${URL_} 를 열지 못했습니다: ${nav.errorText}`);
    await sleep(WAIT);
    const seen = await evaluate(LOOK);
    const status = {}, problems = [];
    for (const m of events) {
      if (m.method === 'Network.responseReceived') status[m.params.requestId] = [m.params.response.status, m.params.response.url];
      if (m.method === 'Network.loadingFailed' && !m.params.canceled && !/BLOCKED_BY_CLIENT/.test(m.params.errorText))
        problems.push(`불러오기 실패 ${m.params.errorText}`);
      if (m.method === 'Runtime.exceptionThrown') problems.push('스크립트 오류 ' + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text).split('\n')[0]);
      if (m.method === 'Log.entryAdded' && m.params.entry.level === 'error' && !/status of 4\d\d|status of 5\d\d|BLOCKED_BY_CLIENT/.test(m.params.entry.text)) problems.push('콘솔 ' + m.params.entry.text.slice(0, 120));
    }
    for (const [st, url] of Object.values(status)) if (st >= 400 && !/favicon\.ico$/.test(url)) problems.push(`${st} ${url.replace(/^https?:\/\/[^/]+/, '')}`);
    const shot = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(OUT, scheme + '.png'), Buffer.from(shot.data, 'base64'));
    runs[scheme] = { ...seen, problems: [...new Set(problems)] };
  }
  const L = runs.light, D = runs.dark;
  const lb = lum(L.bg), db = lum(D.bg);
  console.log(`${URL_}  (${L.title || '제목 없음'})`);
  const line = (bad, text) => console.log((bad ? '  ✗ ' : '  ✓ ') + text);
  // wide is measured against the phone's 390px, not the layout width: a page with no viewport meta is laid out at 980px
  // and shrunk to fit, so it never "scrolls" yet everything on it is drawn at 40%. A wide element under
  // overflow-x:hidden can shrink the page the same way without any scroll width to show for it.
  const shrunk = L.scale < 0.99, pct = Math.round(L.scale * 100), meta = L.noMeta ? ' · viewport meta 없음' : '';
  line(L.wide > 0 || shrunk, L.wide > 0 ? `가로로 ${L.wide}px 넘침 — ${shrunk ? `폰이 ${pct}%로 축소해 보여 줌(글자가 작아짐)` : '옆으로 밀림'}${meta}`
    : shrunk ? `넓은 요소 때문에 폰이 ${pct}%로 축소해 보여 줌(글자가 작아짐)${meta}` : '가로 넘침 없음');
  line(L.problems.length > 0, L.problems.length ? `오류·실패 ${L.problems.length}개: ${L.problems.slice(0, 5).join(' · ')}` : '오류·불러오기 실패 없음');
  line(L.small.length > 0, L.small.length ? `44px 보다 작은 누를 곳 ${L.small.length}개: ` + L.small.slice(0, 8).map(s => `${s.what} ${s.w}×${s.h}`).join(' · ') : '누를 곳 모두 44px 이상');
  line(L.tiny > 0, L.tiny ? `12px 보다 작은 글자 요소 ${L.tiny}개: ${L.tinyWhat.join(' · ')}` : '12px 보다 작은 글자 없음');
  const dark = lb !== null && db !== null && lb - db > 0.3, alwaysDark = lb !== null && db !== null && lb < 0.3 && db < 0.3;
  line(!dark && !alwaysDark, dark ? '다크 모드를 따름' : alwaysDark ? '늘 어두운 화면 (다크 모드에서도 그대로)'
    : `다크 모드를 따르지 않음 (밝게 ${L.bg} / 어둡게 ${D.bg})`);
  if (D.problems.length && D.problems.join() !== L.problems.join()) line(true, `어두울 때만 나는 오류: ${D.problems.slice(0, 3).join(' · ')}`);
  if (L.nameless.length) console.log(`  -  화면 읽기가 이름을 못 읽는 누를 곳 ${L.nameless.length}개: ${[...new Set(L.nameless)].slice(0, 6).join(' · ')} (aria-label 을 달면 됨)`);
  if (blocked) console.log(`  -  쓰기 요청 ${blocked}개는 보내지 않고 막음 (검사는 읽기만)`);
  console.log(`  화면: ${path.join(OUT, 'light.png')} , ${path.join(OUT, 'dark.png')}`);
  code = L.wide > 0 || L.scale < 0.99 || L.problems.length ? 1 : 0;
} catch (e) {
  console.error('검사하지 못했습니다: ' + e.message);
  code = 2;
} finally {
  chrome.kill();
  await new Promise(r => { chrome.once('exit', r); setTimeout(r, 3000); });
  try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
}
process.exit(code);
