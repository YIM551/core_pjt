// Node.js 20+, npm install --no-save --package-lock=false playwright@1.62.1
// 운영자가 별도 Pi 터미널에서 camera-stream.service를 중단·복구한다.
const { createConnection, isIPv4 } = require('node:net');
const { setTimeout: sleep } = require('node:timers/promises');
const { parseArgs, isDeepStrictEqual } = require('node:util');

const { values } = parseArgs({ options: {
  device: { type: 'string' }, url: { type: 'string', default: 'http://127.0.0.1:8000' },
  channel: { type: 'string', default: 'msedge' }, help: { type: 'boolean', short: 'h' },
} });
const usage = 'node 실기기_브라우저_장애_검증.cjs --device <Pi IPv4> [--url http://127.0.0.1:8000] [--channel msedge|chromium]';
if (values.help || !isIPv4(values.device || '')) {
  console.log(usage);
  console.log('대시보드와 Pi 서버를 먼저 켜고, 서비스 제어에 쓸 Pi 터미널을 열어 두세요.');
  process.exit(values.help ? 0 : 2);
}
const { chromium } = require('playwright');
const recovery = 'Pi 터미널에서 sudo systemctl start camera-stream.service 를 실행하세요.';
let needsRecovery = false;
let phase = '브라우저 시작';
process.once('SIGINT', () => { if (needsRecovery) console.error(recovery); process.exit(130); });

function check(ok, detail) {
  if (!ok) throw new Error(detail);
}
async function until(condition, timeout, detail) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (await condition()) return;
    await sleep(450);
  }
  throw new Error(detail);
}
function portOpen() {
  return new Promise(resolve => {
    const socket = createConnection({ host: values.device, port: 8080 });
    function finish(open) { socket.destroy(); resolve(open); }
    socket.once('connect', () => finish(true));
    socket.once('error', () => finish(false));
    socket.setTimeout(1500, () => finish(false));
  });
}
async function run(page) {
  // A9의 실제 성공/오류를 유지하고, 이전에 담긴 음성 문장이 화면에서 자동 전송되는 것을 막는다.
  await page.addInitScript(() => {
    const fetchOriginal = window.fetch.bind(window);
    window.fetch = async (input, init) => {
      const url = new URL(input instanceof Request ? input.url : input, location.href);
      const response = await fetchOriginal(input, init);
      if (url.origin === location.origin && url.pathname === '/api/voice-poll' && response.ok) {
        await response.body?.cancel().catch(() => {});
        return Response.json({ seq: 0, text: '' });
      }
      return response;
    };
  });
  const signals = new Map();
  const outputs = ['/api/oled-display', '/api/robot-signal'];
  page.on('request', req => {
    const endpoint = new URL(req.url()).pathname;
    if (req.method() === 'POST' && outputs.includes(endpoint)) {
      const { direction, ip } = req.postDataJSON();
      signals.set(req, { endpoint, direction, ip, ok: false });
    }
  });
  page.on('response', async resp => {
    const signal = signals.get(resp.request());
    if (signal) signal.ok = resp.status() === 200 && await resp.json().then(r => r.ok === true).catch(() => false);
  });
  phase = 'Pi 등록 및 실제 프레임 수신';
  check(await portOpen(), 'Pi 8080 연결 실패');
  await page.goto(values.url, { waitUntil: 'domcontentloaded' });
  const block = page.locator('[data-block-id="1"]');
  await block.locator('[data-role=block-head]').click();
  await block.locator('[data-role=ip-input]').fill(values.device);
  await block.locator('[data-role=confirm-btn]').click();
  await page.locator('[data-tab=tab-dashboard]').click();
  const deviceTab = page.locator('[data-subtab=subtab-device-1]');
  const localTab = page.locator('[data-subtab=subtab-local-pc]');
  const panel = page.locator('#subtab-device-1');
  const status = (kind, text) => panel.locator(`[data-status="${kind}"]`).filter({ hasText: text }).waitFor();
  async function camera() {
    await page.waitForFunction(() => {
      const img = document.querySelector('#subtab-device-1 .cam-img');
      return img?.style.display === 'block' && img.naturalWidth > 0 && img.naturalHeight > 0;
    }, undefined, { timeout: 45000 });
    await Promise.all([status('video', '연결됨'), status('voice', '연결됨')]);
  }
  async function typed(prompt, local = false) {
    const target = local ? page.locator('#subtab-local-pc') : panel;
    await target.locator('textarea').fill(prompt);
    const [resp] = await Promise.all([
      page.waitForResponse(r => {
        const req = r.request();
        if (new URL(r.url()).pathname !== '/api/llm-answer' || req.method() !== 'POST') return false;
        const body = req.postDataJSON();
        return body.prompt === prompt && body.source === (local ? 'text' : 'device') && (local || body.ip === values.device);
      }, { timeout: 190000 }),
      target.locator('[data-role=prompt-send-btn]').click(),
    ]);
    await target.locator('[data-role=prompt-send-btn]:enabled').waitFor();
    return { http: resp.status(), data: await resp.json(), history: resp.request().postDataJSON().history };
  }
  await deviceTab.click();
  await camera();
  phase = '기기 되묻기';
  const first = await typed('저쪽으로 2칸 가');
  check(first.http === 200 && first.data.tool === 'ask' && first.data.args.steps === 2, '2칸 되묻기 실패');
  check(signals.size === 0, '되묻기 중 출력 요청 발생');
  phase = '서비스 중단 및 502 확인';
  needsRecovery = true;
  console.log('지금 Pi 터미널에서 sudo systemctl stop camera-stream.service 를 실행하세요. 2분간 기다립니다.');
  await until(async () => !(await portOpen()), 120000, '8080 중단 대기 시간 초과');
  const failed = await typed('왼쪽');
  check(failed.http === 502 && failed.data.error === 'device_llm_unreachable', '기기 오류 응답 불일치');
  await Promise.all([status('video', '끊김'), status('voice', '끊김'), status('llm', '응답 없음')]);
  check(failed.history.length === 2 && JSON.parse(failed.history[1].content).args.steps === 2, '되묻기 기록 불일치');
  phase = '중단 중 로컬 탭 확인';
  await localTab.click();
  const local = await typed('오른쪽으로 1칸 가', true);
  check(local.http === 200 && local.data.tool === 'move' && local.data.args.direction === 'right'
    && local.data.args.steps === 1 && local.history.length === 0, '로컬 탭 이동 실패');
  check(signals.size === 0 && !(await portOpen()), '장애 중 출력 또는 조기 서비스 복구');
  console.log('PASS · 기기 탭 502, 로컬 탭 200, OLED·LED 요청 0건');
  phase = '서비스 및 영상 복구';
  await deviceTab.click();
  console.log(recovery, '2분간 기다립니다.');
  await until(portOpen, 120000, '8080 복구 대기 시간 초과');
  await camera();
  needsRecovery = false;
  phase = '복구 후 대화 및 출력 확인';
  const retry = await typed('왼쪽');
  check(isDeepStrictEqual(retry.history, failed.history), '재시도한 대화 기록 불일치');
  check(retry.http === 200 && retry.data.tool === 'move'
    && isDeepStrictEqual(retry.data.args, { direction: 'left', steps: 2 }), '재시도 이동 실패');
  await status('llm', '정상');
  await until(() => signals.size >= 2 && [...signals.values()].every(s => s.ok), 20000, 'OLED·LED 응답 대기 시간 초과');
  const received = [...signals.values()];
  check(received.length === 2 && outputs.every(p => received.some(s => s.endpoint === p))
    && received.every(s => s.ip === values.device && s.direction === 'left'), '복구 후 출력 요청 불일치');
  const fresh = await typed('앞에 뭐가 있어?');
  check(fresh.http === 200 && fresh.data.tool === 'describe' && fresh.history.length === 0 && signals.size === 2,
    '새 질문에서 대화 기록 또는 출력 요청 불일치');
  console.log('PASS · 실제 영상 복구, 같은 대화에서 왼쪽 2칸, OLED·LED 각 200, 새 질문의 기록 0건');
}

(async () => {
  const browser = await chromium.launch({ channel: values.channel, headless: true });
  try {
    const page = await browser.newPage({ permissions: [] });
    page.setDefaultTimeout(30000);
    await run(page);
  } finally {
    if (needsRecovery) console.error(recovery);
    await browser.close();
  }
})().catch(error => {
  // 화면 문구, 인식 결과, 요청 본문 등 실기기 정보를 출력하지 않는다.
  console.error('FAIL ·', phase, '·', error.name);
  process.exitCode = 1;
});
