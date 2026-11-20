// 선택 검사 (Node.js 20+). 프로젝트 루트에서 npm install --no-save --package-lock=false playwright@1.62.1
// node "source/3회차_day3/page56_최종_검증/브라우저_장애_검증.cjs" --url http://127.0.0.1:8000
// 기본 브라우저는 Edge. Chromium 사용 시 npx playwright install chromium 후 --channel chromium 추가.
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { parseArgs } = require('node:util');
const { chromium } = require('playwright');

const { values } = parseArgs({ options: {
  url: { type: 'string', default: 'http://127.0.0.1:8000' },
  channel: { type: 'string', default: 'msedge' },
} });
const fakeIp = '192.0.2.23';

async function run(page) {
  const requests = [];
  const signals = [];
  let deviceDown = false;
  let sendFailure;
  const failureGate = new Promise(resolve => { sendFailure = resolve; });
  const sample = readFileSync(path.join(__dirname, '../../3회차_day1/samples/sample.jpg'));

  // 로컬 탭에는 고정 JPEG를 가상 웹캠으로 제공한다. 모델과 기기 API는 브라우저에서 대체한다.
  await page.addInitScript(imageUrl => {
    navigator.mediaDevices.getUserMedia = async () => {
      const image = new Image();
      image.src = imageUrl;
      await image.decode();
      const canvas = document.createElement('canvas');
      canvas.width = image.width;
      canvas.height = image.height;
      const context = canvas.getContext('2d');
      const stream = canvas.captureStream(5);
      const draw = () => context.drawImage(image, 0, 0);
      draw();
      setInterval(draw, 200);
      return stream;
    };
  }, 'data:image/jpeg;base64,' + sample.toString('base64'));
  await page.route('**/mediapipe/**', route => route.abort());
  await page.route('**/api/**', async route => {
    const endpoint = new URL(route.request().url()).pathname;
    const reply = (json, status = 200) => route.fulfill({ json, status });
    switch (endpoint) {
      case '/api/camera-stream':
        return reply({ error: 'camera_unreachable' }, 502);
      case '/api/voice-poll':
        return deviceDown ? reply({ error: 'device_unreachable' }, 502) : reply({ seq: 0, text: '' });
      case '/api/yolo-detect':
        return reply({ objects: [] });
      case '/api/vlm-describe':
        return reply({ description: '샘플 이미지' });
      case '/api/oled-display':
      case '/api/robot-signal':
        signals.push([endpoint, route.request().postDataJSON()]);
        return reply({ ok: true });
      case '/api/llm-answer': {
        const body = route.request().postDataJSON();
        requests.push(body);
        if (body.ip && deviceDown) {
          await failureGate;
          return reply({ error: 'device_llm_unreachable' }, 502);
        }
        let result = { tool: 'describe', args: {}, message: body.ip ? '새 기기 질문 완료' : '로컬 질문 완료' };
        if (body.prompt === '저쪽으로 2칸 가') {
          result = { tool: 'ask', args: { steps: 2 }, message: '어느 쪽으로 갈까요?' };
        }
        if (body.prompt === '왼쪽') {
          const ask = body.history.find(turn => turn.role === 'assistant');
          const steps = ask && JSON.parse(ask.content).args.steps;
          result = { tool: 'move', args: { direction: 'left', steps }, message: '왼쪽으로 이동합니다.' };
        }
        return reply({ ...result, need_more_info: result.tool === 'ask', user_content: body.prompt });
      }
      default:
        return reply({ error: 'unexpected_test_endpoint' }, 404);
    }
  });

  await page.goto(values.url);
  const block = page.locator('[data-block-id="1"]');
  await block.locator('[data-role=block-head]').click();
  await block.locator('[data-role=ip-input]').fill(fakeIp);
  await block.locator('[data-role=confirm-btn]').click();
  await page.locator('[data-tab=tab-dashboard]').click();
  const deviceTab = page.locator('[data-subtab=subtab-device-1]');
  const device = page.locator('#subtab-device-1');
  const local = page.locator('#subtab-local-pc');
  const llm = device.locator('[data-status=llm]');

  async function submit(panel, prompt) {
    await panel.locator('textarea').fill(prompt);
    await panel.locator('[data-role=prompt-send-btn]').click();
  }
  async function expectReply(panel, text) {
    const answer = panel.locator('[data-role=llm-answer-text]').filter({ hasText: text });
    await answer.waitFor();
    assert.equal(await answer.innerText(), text);
    await panel.locator('[data-role=prompt-send-btn]:enabled').waitFor();
  }

  await deviceTab.click();
  await submit(device, '저쪽으로 2칸 가');
  await expectReply(device, '[추가 정보 요청] 어느 쪽으로 갈까요?');
  deviceDown = true;
  await submit(device, '왼쪽');
  await llm.filter({ hasText: '처리 중' }).waitFor();
  assert.ok(await device.locator('textarea').isDisabled());
  sendFailure();
  await expectReply(device, '라즈베리파이 LLM이 응답하지 않습니다 (기기 꺼짐 또는 시간 초과). 대화는 그대로 이어지니 다시 말해 주세요.');
  await llm.filter({ hasText: '응답 없음' }).waitFor();
  await device.locator('[data-status=video]').filter({ hasText: '끊김' }).waitFor();
  await device.locator('[data-status=voice]').filter({ hasText: '끊김' }).waitFor();
  assert.deepEqual(signals, []);
  console.log('PASS F303 처리 중 입력 잠금, 502 안내, 영상·음성 끊김, 오류 중 출력 요청 0건');

  await page.locator('[data-subtab=subtab-local-pc]').click();
  await page.waitForFunction(() => document.querySelector('#subtab-local-pc video').videoWidth > 0);
  await submit(local, '앞에 뭐가 있어?');
  await expectReply(local, '로컬 질문 완료');
  assert.equal(requests[2].vlm_description, '샘플 이미지');
  console.log('PASS R6 기기 오류 중 로컬 탭에서 샘플 영상으로 독립 질문 완료');

  deviceDown = false;
  await deviceTab.click();
  await submit(device, '왼쪽');
  await expectReply(device, '왼쪽으로 이동합니다.');
  await llm.filter({ hasText: '정상' }).waitFor();
  await submit(device, '앞에 뭐가 있어?');
  await expectReply(device, '새 기기 질문 완료');
  assert.deepEqual(requests.map(r => r.source), ['device', 'device', 'text', 'device', 'device']);
  assert.deepEqual(requests.map(r => r.history.length), [0, 2, 0, 2, 0]);
  assert.deepEqual(requests[3].history, requests[1].history);
  assert.equal(JSON.parse(requests[3].history[1].content).args.steps, 2);
  assert.deepEqual(signals, ['/api/oled-display', '/api/robot-signal'].map(endpoint =>
    [endpoint, { ip: fakeIp, direction: 'left' }]));
  console.log('PASS R6·R7 재시도 history 유지(2칸), 정상 배지, 왼쪽 OLED·LED 요청 각 1건, 다음 질문 history 비움');
}

(async () => {
  const browser = await chromium.launch({ channel: values.channel, headless: true });
  try {
    const page = await browser.newPage();
    page.setDefaultTimeout(12000);
    await run(page);
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error('FAIL', error.message);
  process.exitCode = 1;
});
