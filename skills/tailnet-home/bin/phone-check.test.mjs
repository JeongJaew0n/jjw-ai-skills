#!/usr/bin/env node
// phone-check.mjs on pages made to trip each rule, served on a free [::1] port by this file: every past misjudgement
// (a transparent ::before, a breadcrumb, a closed <details>, a short dark page, furigana, a placeholder, a write on
// load, a page that cannot be opened, a too-wide page the phone zooms out on, with or without a viewport meta or overflow-x:hidden) has a page here.
//
//   node phone-check.test.mjs        exit 0 all as expected, 1 not
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const TOOL = path.join(path.dirname(fileURLToPath(import.meta.url)), 'phone-check.mjs');
const head = (style = '') => `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>t</title><style>:root{color-scheme:light dark}body{margin:0;padding:16px;font:16px system-ui;background:#fff;color:#111}
@media (prefers-color-scheme:dark){body{background:#111;color:#eee}}${style}</style><body>`;
const tall = '<div style="height:1200px"></div>';
const PAGES = {
  '/good.html': head() + '<h1>좋은 화면</h1><button style="min-height:48px;min-width:48px">누름</button>',
  '/small.html': head() + '<button style="height:20px;padding:0 4px">작음</button>',
  '/padded.html': head('a.p{position:relative;font-size:14px}a.p::before{content:"";position:absolute;inset:-14px -12px}')
    + '<p style="margin:40px">… <a class="p" href="#">판 덧댄 링크입니다요</a></p>',
  '/crumb.html': head() + '<p><span><a href="#">원본</a> › v1</span></p>',
  '/sentence.html': head() + '<p>이 문장은 충분히 길어서 그 안에 든 <a href="#">링크</a>는 작아도 괜찮다고 보는 것이 맞습니다.</p>',
  '/below.html': head() + tall + '<button style="height:20px">아래 작은 단추</button>',
  '/details.html': head() + '<details><summary style="display:block;min-height:48px">열기</summary><a href="#" style="font-size:10px">닫힌 안</a></details>',
  '/tiny.html': head() + '<p style="font-size:10px">작은 글자</p>',
  '/ruby.html': head() + '<p><ruby>漢<rt>かん</rt></ruby>字</p>',
  '/short-dark.html': head() + '<p>짧은 화면</p>',
  '/light-only.html': '<!doctype html><meta name="viewport" content="width=device-width"><title>l</title><body style="background:#fff"><p>밝기만</p>',
  '/always-dark.html': '<!doctype html><meta name="viewport" content="width=device-width"><title>d</title><body style="background:#123;color:#eee"><p>늘 어두움</p>',
  '/wide.html': head() + '<div style="width:800px">넓음</div>',
  '/wide-scaled.html': head().replace('width=device-width', 'width=device-width,initial-scale=1') + '<div style="width:800px">넓음</div>',
  '/wide-nometa.html': '<!doctype html><meta charset="utf-8"><title>n</title><body style="margin:0"><div style="width:800px">viewport meta 없음</div>',
  '/wide-hidden.html': '<!doctype html><meta charset="utf-8"><title>h</title><style>html,body{overflow-x:hidden}</style><div style="width:800px">넘침을 가림</div>',
  '/write.html': head() + '<p>열 때 저장</p><script>fetch("/api/save",{method:"POST",body:"x"}).catch(()=>{});fetch("/ok.txt")</script>',
  '/abs.html': head() + '<p>절대경로</p><script src="/missing.js"></script>',
  '/nameless.html': head() + '<button style="min-height:48px;min-width:48px"><svg width="20" height="20"></svg></button>',
  '/placeholder.html': head() + '<textarea placeholder="모르는 점을 적어 주세요" style="min-height:48px;width:200px"></textarea>',
};
const seen = [];
const server = http.createServer((req, res) => {
  seen.push(`${req.method} ${req.url}`);
  const body = PAGES[req.url] ?? (req.url === '/ok.txt' ? 'ok' : null);
  if (body === null) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': req.url.endsWith('.txt') ? 'text/plain' : 'text/html; charset=utf-8' });
  res.end(body);
});
await new Promise(r => server.listen(0, '::1', r));
const base = `http://[::1]:${server.address().port}`;
const out = fs.mkdtempSync(path.join(os.tmpdir(), 'phone-check-test-'));

// spawn, not spawnSync: the pages are served by this process, so its event loop must keep running.
function check(page, url = base + page) {
  return new Promise(resolve => {
    const child = spawn(process.execPath, [TOOL, url, '--out', path.join(out, page.replace(/\W/g, '') || 'x'), '--wait', '700']);
    let text = '';
    child.stdout.on('data', d => { text += d; });
    child.stderr.on('data', d => { text += d; });
    child.on('close', code => {
      const line = re => (text.split('\n').find(l => re.test(l)) || '').trim();
      resolve({ code, text, small: line(/누를 곳/), tiny: line(/12px/), dark: line(/다크|어두운/), wide: line(/가로/),
                errors: line(/오류/), nameless: line(/이름을 못/), blocked: line(/막음/) });
    });
  });
}
let failed = 0;
const ok = (cond, what, detail = '') => { console.log((cond ? '  ok   ' : '  FAIL ') + what + (cond ? '' : '  ← ' + detail)); if (!cond) failed++; };
const r = {};
const queue = Object.keys(PAGES);
await Promise.all(Array.from({ length: 4 }, async () => { for (let p; (p = queue.shift());) r[p] = await check(p); }));
ok(r['/good.html'].code === 0 && !/✗/.test(r['/good.html'].text), '좋은 화면은 ✗ 없음', r['/good.html'].text);
ok(/✗/.test(r['/small.html'].small), '20px 단추는 작은 누를 곳', r['/small.html'].small);
ok(/✓/.test(r['/padded.html'].small), '투명한 ::before 로 넓힌 링크는 통과(실제 눌리는 범위)', r['/padded.html'].small);
ok(/✗/.test(r['/crumb.html'].small), '짧은 경로 줄 링크("원본 › v1")는 봐주지 않음', r['/crumb.html'].small);
ok(/✓/.test(r['/sentence.html'].small), '긴 문장 속 링크는 작아도 됨', r['/sentence.html'].small);
ok(/✗/.test(r['/below.html'].small), '첫 화면 아래의 작은 단추도 잡음', r['/below.html'].small);
ok(/✓/.test(r['/details.html'].small) && /✓/.test(r['/details.html'].tiny), '닫힌 <details> 안은 세지 않음', r['/details.html'].small + ' / ' + r['/details.html'].tiny);
ok(/✗/.test(r['/tiny.html'].tiny) && /p "/.test(r['/tiny.html'].tiny), '10px 글자는 예와 함께 짚음', r['/tiny.html'].tiny);
ok(/✓/.test(r['/ruby.html'].tiny), '후리가나(rt)는 작은 글자로 세지 않음', r['/ruby.html'].tiny);
ok(/✓.*따름/.test(r['/short-dark.html'].dark), '짧은 화면도 body 색으로 다크 판정', r['/short-dark.html'].dark);
ok(/✗/.test(r['/light-only.html'].dark), '밝기만 한 화면은 다크 모드 ✗', r['/light-only.html'].dark);
ok(/✓.*늘 어두운/.test(r['/always-dark.html'].dark), '늘 어두운 화면은 통과', r['/always-dark.html'].dark);
ok(/✗/.test(r['/wide.html'].wide) && r['/wide.html'].code === 1, '가로 넘침은 ✗ 와 종료 1 (initial-scale 없어 폰이 축소해 보여도)', r['/wide.html'].wide);
ok(/✗/.test(r['/wide-scaled.html'].wide), '가로 넘침 (initial-scale=1)', r['/wide-scaled.html'].wide);
ok(/✗.*축소.*viewport meta 없음/.test(r['/wide-nometa.html'].wide) && r['/wide-nometa.html'].code === 1, 'viewport meta 없는 넓은 화면(980px 로 그려 축소)도 ✗', r['/wide-nometa.html'].wide);
ok(/✗.*축소/.test(r['/wide-hidden.html'].wide), 'overflow-x:hidden 으로 가려도 meta 가 없어 폰이 축소하면 ✗ (meta 가 있으면 축소 없이 잘림: 이 검사 밖)', r['/wide-hidden.html'].wide);
ok(/✓/.test(r['/write.html'].errors) && /쓰기 요청 2개/.test(r['/write.html'].blocked)
  && !seen.some(s => s.startsWith('POST')) && seen.includes('GET /ok.txt'), '열 때 보내는 POST 는 막고(밝게·어둡게 2번), GET 은 보냄', r['/write.html'].blocked + ' ' + seen.filter(s => !s.startsWith('GET /')).join());
ok(/✗.*404 \/missing\.js/.test(r['/abs.html'].errors) && r['/abs.html'].code === 1, '없는 파일(절대경로 깨짐)은 오류로', r['/abs.html'].errors);
ok(/이름을 못/.test(r['/nameless.html'].nameless) && r['/nameless.html'].code === 0, '아이콘만 있는 단추는 알리되 ✗ 로 세지 않음', r['/nameless.html'].text);
ok(!r['/placeholder.html'].nameless, 'placeholder 는 이름으로 침', r['/placeholder.html'].nameless);
const run = (...a) => new Promise(res => { const c = spawn(process.execPath, [TOOL, ...a]); let t = ''; c.stderr.on('data', d => { t += d; }); c.on('close', code => res({ code, t })); });
const help = await run('--help'), odd = await run('gisa', '--wiat', '300'), two = await run('gisa', 'mascot');
ok(help.code === 0 && /쓰는 법/.test(help.t), '--help 는 쓰는 법과 종료 0', help.code + help.t);
ok(odd.code === 2 && /모르는 옵션: --wiat/.test(odd.t), '뒤쪽의 틀린 옵션도 종료 2', odd.code + odd.t);
ok(two.code === 2 && /하나만/.test(two.t), '주소 둘은 종료 2', two.code + two.t);
const closed = await check('/x', 'http://[::1]:1/');
ok(closed.code === 2 && /열지 못했습니다/.test(closed.text), '열지 못하는 주소는 이유와 종료 2', closed.text);

server.close();
fs.rmSync(out, { recursive: true, force: true });
console.log(failed ? `${failed}개 실패` : `모두 통과 (${Object.keys(PAGES).length + 1}개 화면, 인자 3가지)`);
process.exit(failed ? 1 : 0);
