#!/usr/bin/env node
/**
 * 개인 Claude Code statusline HUD
 *
 * 설계 원칙
 *  - 의존성 0 (Node 내장 모듈만)
 *  - 외부 프로세스 spawn 0 (git 호출 대신 .git/HEAD 직접 읽기)
 *  - 자격증명 접근 0 (rate limit / 비용은 stdin 이 그대로 준다)
 *  - 어떤 필드가 없어도 그 항목만 빠지고 나머지는 그린다
 *  - 예외가 나면 아무것도 출력하지 않는다 (깨진 statusline 보다 없는 편이 낫다)
 *
 * stdin 페이로드는 Claude Code 가 렌더마다 새로 준다. `docs/payload-example.json` 참고.
 */

import { readFileSync, statSync } from "node:fs";
import { join, dirname } from "node:path";

// ── 표시 설정 ──────────────────────────────────────────────
const CONFIG = {
  // 컨텍스트 사용률 임계값 (%)
  ctxWarn: 70,
  ctxCrit: 85,
  // rate limit 임계값 (%)
  rateWarn: 60,
  rateCrit: 85,
  // 비용 임계값 (USD, 세션 누적)
  costWarn: 20,
  costCrit: 50,
};

// ── 색상 ──────────────────────────────────────────────────
// NO_COLOR 규약을 따르고, 파이프로 넘어갈 때도 색을 유지한다
// (statusline 은 TTY 가 아니지만 Claude Code 가 ANSI 를 해석해 준다)
const useColor = !process.env.NO_COLOR;
const wrap = (code) => (s) => (useColor ? `\x1b[${code}m${s}\x1b[0m` : String(s));

const dim = wrap(2);
const bold = wrap(1);
const red = wrap(31);
const green = wrap(32);
const yellow = wrap(33);
const cyan = wrap(36);

/** 값이 임계값을 넘는 정도에 따라 색을 고른다 */
function byThreshold(value, warn, crit) {
  if (value >= crit) return red;
  if (value >= warn) return yellow;
  return green;
}

// ── 포맷 헬퍼 ─────────────────────────────────────────────

/** 밀리초 → "3h32m" / "71m" / "45s" */
function humanDuration(ms) {
  if (!Number.isFinite(ms) || ms < 0) return null;
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m`;
  const hr = Math.floor(min / 60);
  const remMin = min % 60;
  if (hr < 24) return remMin ? `${hr}h${remMin}m` : `${hr}h`;
  const day = Math.floor(hr / 24);
  const remHr = hr % 24;
  return remHr ? `${day}d${remHr}h` : `${day}d`;
}

/** epoch(초) → 지금부터 남은 시간 "3h32m". 이미 지났으면 null */
function untilReset(epochSec) {
  if (!Number.isFinite(epochSec)) return null;
  const ms = epochSec * 1000 - Date.now();
  return ms > 0 ? humanDuration(ms) : null;
}

/**
 * 백분율 → "7%".
 * Claude Code 가 7.000000000000001 같은 부동소수점 잔여값을 보내올 때가 있어
 * 표시 직전에 정수로 반올림한다. (임계값 비교는 원본 값으로 한다)
 */
function formatPercent(value) {
  return `${Math.round(value)}%`;
}

/** 비용 → "$8.25". 1달러 미만은 센트 단위까지 */
function formatCost(usd) {
  if (!Number.isFinite(usd)) return null;
  return usd < 1 ? `$${usd.toFixed(3)}` : `$${usd.toFixed(2)}`;
}

// ── git 브랜치 ────────────────────────────────────────────

/**
 * .git 을 찾아 올라가며 현재 브랜치를 읽는다.
 * git 프로세스를 띄우지 않는다 — 렌더마다 spawn 하면 누적 비용이 크다.
 *
 * 처리하는 경우:
 *   - 일반 레포        .git/ 디렉토리
 *   - worktree/submodule  .git 이 "gitdir: <경로>" 파일
 *   - detached HEAD    SHA 앞 7자리를 반환
 */
function gitBranch(startDir) {
  try {
    let dir = startDir;
    for (let depth = 0; depth < 40; depth++) {
      const dotGit = join(dir, ".git");
      let gitDir = null;

      try {
        const st = statSync(dotGit);
        if (st.isDirectory()) {
          gitDir = dotGit;
        } else if (st.isFile()) {
          // worktree / submodule: "gitdir: /절대/또는/상대/경로"
          const m = readFileSync(dotGit, "utf-8").match(/^gitdir:\s*(.+)$/m);
          if (m) {
            const p = m[1].trim();
            gitDir = p.startsWith("/") ? p : join(dir, p);
          }
        }
      } catch {
        // 이 단계에 .git 이 없다 — 위로 올라간다
      }

      if (gitDir) {
        const head = readFileSync(join(gitDir, "HEAD"), "utf-8").trim();
        const ref = head.match(/^ref:\s*refs\/heads\/(.+)$/);
        if (ref) return ref[1];
        // detached HEAD — SHA 가 그대로 들어 있다
        if (/^[0-9a-f]{7,40}$/i.test(head)) return head.slice(0, 7);
        return null;
      }

      const parent = dirname(dir);
      if (parent === dir) break; // 루트 도달
      dir = parent;
    }
  } catch {
    // 무시 — 브랜치 항목만 빠진다
  }
  return null;
}

// ── 렌더 ──────────────────────────────────────────────────

function render(d) {
  const lines = [];

  // 1행: 레포 / 브랜치
  const top = [];
  const repoName = d?.workspace?.repo?.name;
  if (repoName) top.push(dim("repo:") + cyan(repoName));

  const cwd = d?.workspace?.current_dir || d?.cwd;
  if (cwd) {
    const branch = gitBranch(cwd);
    if (branch) top.push(dim("branch:") + cyan(branch));
  }
  if (top.length) lines.push(top.join("  "));

  // 2행: 지표
  const main = [];

  // 모델
  const model = d?.model?.display_name;
  if (model) main.push(bold(model));

  // 컨텍스트 사용률
  const ctx = d?.context_window?.used_percentage;
  if (Number.isFinite(ctx)) {
    main.push(dim("ctx:") + byThreshold(ctx, CONFIG.ctxWarn, CONFIG.ctxCrit)(formatPercent(ctx)));
  }

  // rate limit (5시간 / 7일)
  const rl = d?.rate_limits;
  const rateParts = [];
  for (const [key, label] of [["five_hour", "5h"], ["seven_day", "wk"]]) {
    const w = rl?.[key];
    if (!w || !Number.isFinite(w.used_percentage)) continue;
    const pct = byThreshold(w.used_percentage, CONFIG.rateWarn, CONFIG.rateCrit)(formatPercent(w.used_percentage));
    const left = untilReset(w.resets_at);
    rateParts.push(dim(`${label}:`) + pct + (left ? dim(`(${left})`) : ""));
  }
  if (rateParts.length) main.push(rateParts.join(" "));

  // 세션 비용
  const cost = formatCost(d?.cost?.total_cost_usd);
  if (cost) {
    main.push(byThreshold(d.cost.total_cost_usd, CONFIG.costWarn, CONFIG.costCrit)(cost));
  }

  // 세션 경과 시간
  const dur = humanDuration(d?.cost?.total_duration_ms);
  if (dur) main.push(dim(dur));

  // 변경 줄 수 (둘 다 0이면 표시하지 않는다)
  const added = d?.cost?.total_lines_added ?? 0;
  const removed = d?.cost?.total_lines_removed ?? 0;
  if (added || removed) {
    main.push(green(`+${added}`) + dim("/") + red(`-${removed}`));
  }

  if (main.length) lines.push(main.join(dim(" | ")));
  return lines.join("\n");
}

// ── 진입점 ────────────────────────────────────────────────

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf-8");
}

async function main() {
  try {
    const raw = await readStdin();
    if (!raw.trim()) return;
    const out = render(JSON.parse(raw));
    if (out) process.stdout.write(out + "\n");
  } catch {
    // 조용히 종료 — statusline 이 깨지는 것보다 안 보이는 편이 낫다
  }
}

main();
