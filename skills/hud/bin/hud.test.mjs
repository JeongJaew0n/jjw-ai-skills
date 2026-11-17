#!/usr/bin/env node
// hud.mjs on fixture payloads fed through stdin, with HOME pointed at a temp folder (git branches come from fake
// .git folders made there). No network, nothing outside the temp folder is read on purpose. Also runs the `hud`
// launcher with a broken NODE_OPTIONS and with no node on PATH.
//
//   env -u NODE_OPTIONS node hud.test.mjs        exit 0 all as expected, 1 not
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TOOL = path.join(HERE, 'hud.mjs');
const LAUNCHER = path.join(HERE, 'hud');
const tmp = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'hud-test-')));
const HOME = path.join(tmp, 'home');
fs.mkdirSync(HOME);

const baseEnv = () => { const e = { ...process.env, HOME }; delete e.NODE_OPTIONS; return e; };
function hud(payload, { color = false, env = {} } = {}) {
  const e = { ...baseEnv(), ...env };
  if (color) delete e.NO_COLOR; else e.NO_COLOR = '1';
  const input = typeof payload === 'string' ? payload : JSON.stringify(payload);
  const r = spawnSync(process.execPath, [TOOL], { input, env: e, encoding: 'utf8', timeout: 10000 });
  return { code: r.status, out: r.stdout, err: r.stderr, lines: r.stdout.replace(/\n$/, '').split('\n') };
}
function mkdirp(...p) { const d = path.join(...p); fs.mkdirSync(d, { recursive: true }); return d; }
function write(file, body) { fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, body); }

let failed = 0;
const ok = (cond, what, detail = '') => { console.log((cond ? '  ok   ' : '  FAIL ') + what + (cond ? '' : '  ← ' + JSON.stringify(detail))); if (!cond) failed++; };

// ── fake repos ───────────────────────────────────────────
const repo = mkdirp(HOME, 'my', 'Dev', 'some-repo');
write(path.join(repo, '.git', 'HEAD'), 'ref: refs/heads/feat/x\n');
const sub = mkdirp(repo, 'src', 'deep');
const detached = mkdirp(HOME, 'detached');
write(path.join(detached, '.git', 'HEAD'), '0123456789abcdef0123456789abcdef01234567\n');
const wt = mkdirp(HOME, 'wt');
write(path.join(wt, '.git'), 'gitdir: ../wt-gitdir\n');
write(path.join(HOME, 'wt-gitdir', 'HEAD'), 'ref: refs/heads/wt-branch\n');
const odd = mkdirp(HOME, 'odd');
write(path.join(odd, '.git', 'HEAD'), 'garbage\n');
const plain = mkdirp(tmp, 'plain');   // outside HOME, no .git up to tmp (the tmp root itself has none)

const now = Math.floor(Date.now() / 1000);
const full = {
  model: { display_name: 'Opus 5' },
  effort: { level: 'high' },
  workspace: { current_dir: repo, repo: { name: 'some-repo' } },
  context_window: { used_percentage: 42.5 },
  rate_limits: {
    five_hour: { used_percentage: 18, resets_at: now + 3 * 3600 + 32 * 60 + 30 },
    seven_day: { used_percentage: 63.2, resets_at: now + 3 * 86400 },
  },
  cost: { total_cost_usd: 8.2543, total_duration_ms: 12720000, total_lines_added: 231, total_lines_removed: 47 },
};

// ── empty / broken input ─────────────────────────────────
for (const [input, what] of [['', '빈 stdin'], ['   \n', '공백 stdin'], ['{not json', '깨진 JSON'], ['{}', '빈 객체'], ['null', 'null']]) {
  const r = hud(input);
  ok(r.code === 0 && r.out === '', `${what} → 출력 없이 종료 0`, r);
}

// ── full payload ─────────────────────────────────────────
{
  const r = hud(full);
  ok(r.code === 0 && r.lines.length === 2, '전체 페이로드는 두 줄', r.out);
  ok(r.lines[0] === 'branch:feat/x  ~/my/Dev/some-repo', '1행: 레포 이름이 경로 끝과 같으면 repo: 생략, 홈은 ~', r.lines[0]);
  const parts = r.lines[1].split(' | ');
  ok(parts[0] === 'Opus 5 high', '모델 + effort', parts[0]);
  ok(parts[1] === 'ctx:43%', 'ctx 42.5 → 43% (반올림)', parts[1]);
  ok(/^5h:18%\(3h3[12]m\) wk:63%\(\d{1,2}\/\d{1,2}\([일월화수목금토]\) \d\d:\d\d\)$/.test(parts[2]), '5h 는 남은 시간, wk 는 날짜(요일) 시각', parts[2]);
  ok(parts[3] === '$8.25', '비용 $8.25', parts[3]);
  ok(parts[4] === '3h32m', '경과 3h32m', parts[4]);
  ok(parts[5] === '+231/-47', '변경 줄 수', parts[5]);
  ok(!/\x1b\[/.test(r.out), 'NO_COLOR 면 ANSI 없음', r.out);
}

// ── line 1 variants ──────────────────────────────────────
{
  let r = hud({ workspace: { current_dir: sub, repo: { name: 'some-repo' } } });
  ok(r.out === 'repo:some-repo  branch:feat/x  ~/my/Dev/some-repo/src/deep\n', '하위 폴더면 repo: 를 남기고 .git 을 위로 찾아감', r.out);
  r = hud({ cwd: detached });
  ok(r.out === 'branch:0123456  ~/detached\n', 'detached HEAD 는 SHA 7자리, workspace 없으면 cwd', r.out);
  r = hud({ cwd: wt });
  ok(r.out === 'branch:wt-branch  ~/wt\n', 'worktree 의 .git 파일(상대 gitdir)', r.out);
  r = hud({ cwd: odd });
  ok(r.out === '~/odd\n', '알 수 없는 HEAD 면 브랜치만 빠짐', r.out);
  r = hud({ cwd: plain });
  ok(r.out === plain + '\n', '홈 밖 경로는 그대로, .git 없으면 브랜치 없음', r.out);
  r = hud({ cwd: HOME });
  ok(r.out === '~\n', '홈 자체는 ~', r.out);
  r = hud({ cwd: HOME + 'wood/x' });
  ok(r.out === HOME + 'wood/x\n', '홈과 접두어만 같은 경로(홈이 /home/u 일 때 /home/uwood)는 줄이지 않음', r.out);
  r = hud({ cwd: '/definitely/not/here' });
  ok(r.out === '/definitely/not/here\n', '없는 경로도 그대로 그림', r.out);
  r = hud({ cwd: path.join(HOME, 'x') }, { env: { HOME: '' } });
  ok(r.out === path.join(HOME, 'x') + '\n', 'HOME 이 비면 줄이지 않음', r.out);
}

// ── line 2 variants ──────────────────────────────────────
{
  let r = hud({ effort: { level: 'max' } });
  ok(r.out === 'max\n', '모델 없이 effort 만', r.out);
  r = hud({ model: { display_name: 'M' }, context_window: { used_percentage: 7.000000000000001 } });
  ok(r.out === 'M | ctx:7%\n', '부동소수점 잔여값은 정수로', r.out);
  r = hud({ cost: { total_cost_usd: 0.0123 } });
  ok(r.out === '$0.012\n', '1달러 미만은 소수 셋째 자리', r.out);
  r = hud({ cost: { total_lines_added: 0, total_lines_removed: 0, total_duration_ms: 45000 } });
  ok(r.out === '45s\n', '+0/-0 은 숨기고 45s', r.out);
  r = hud({ cost: { total_lines_removed: 3 } });
  ok(r.out === '+0/-3\n', '한쪽만 있어도 표시', r.out);
  r = hud({ cost: { total_duration_ms: 90061000 } });
  ok(r.out === '1d1h\n', '하루 넘으면 1d1h', r.out);
  r = hud({ cost: { total_duration_ms: -5 } });
  ok(r.out === '', '음수 경과는 빠짐', r.out);
  r = hud({ rate_limits: { five_hour: { used_percentage: 50, resets_at: now - 10 }, seven_day: { used_percentage: 'x' } } });
  ok(r.out === '5h:50%\n', '지난 리셋 시각은 괄호 없이, 숫자 아닌 비율은 빠짐', r.out);
  r = hud({ rate_limits: { seven_day: { used_percentage: 1, resets_at: now + 60 } } });
  ok(/^wk:1%\((\d\d:\d\d|\d{1,2}\/\d{1,2}\(.\) \d\d:\d\d)\)\n$/.test(r.out), '곧 리셋되는 wk 는 시각만 (자정 근처면 날짜)', r.out);
}

// ── colours ──────────────────────────────────────────────
{
  const R = '\x1b[31m', Y = '\x1b[33m', G = '\x1b[32m', C = '\x1b[36m';
  const c = (pct) => hud({ context_window: { used_percentage: pct } }, { color: true }).out;
  ok(c(10).includes(G + '10%'), 'ctx 10% 초록', c(10));
  ok(c(70).includes(Y + '70%'), 'ctx 70% 노랑 (경계 포함)', c(70));
  ok(c(85).includes(R + '85%'), 'ctx 85% 빨강 (경계 포함)', c(85));
  const cost = hud({ cost: { total_cost_usd: 60 } }, { color: true }).out;
  ok(cost.includes(R + '$60.00'), '비용 50달러 넘으면 빨강', cost);
  const eff = hud({ effort: { level: 'turbo' } }, { color: true }).out;
  ok(eff.includes(C + 'turbo'), '모르는 effort 는 청록으로 그대로', eff);
  const plainEff = hud({ effort: { level: 'medium' } }, { color: true }).out;
  ok(plainEff === 'medium\n', 'medium 은 색 없음', plainEff);
}

// ── launcher (bin/hud) ───────────────────────────────────
{
  const nodeDir = path.dirname(process.execPath);
  const run = (env) => spawnSync('/bin/sh', [LAUNCHER], { input: JSON.stringify({ cwd: HOME }), encoding: 'utf8', timeout: 10000,
    env: { HOME, NO_COLOR: '1', ...env } });
  let r = run({ PATH: `${nodeDir}:/usr/bin:/bin`, NODE_OPTIONS: `--require ${path.join(tmp, 'gone.cjs')}` });
  ok(r.status === 0 && r.stdout === '~\n', '런처는 깨진 NODE_OPTIONS 를 지우고 그림', r);
  const noNode = fs.existsSync('/usr/bin/node') || fs.existsSync('/bin/node');
  if (noNode) console.log('  skip node 없는 PATH (/usr/bin 에 node 가 있음)');
  else {
    r = run({ PATH: '/usr/bin:/bin' });
    ok(r.status === 0 && r.stdout === '', 'node 가 없으면 조용히 종료 0', r);
  }
}

fs.rmSync(tmp, { recursive: true, force: true });
console.log(failed ? `${failed}개 실패` : '모두 통과');
process.exit(failed ? 1 : 0);
