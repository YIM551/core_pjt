"""PC에서 D5의 출력 설정과 A5의 실제 판정 경로를 검사한다.

추론 결과와 기기 통신 실패를 주입한다. 음성 인식, 실제 토큰 생성 속도와
OLED·LED의 물리 동작은 --device 및 대시보드에서 별도로 확인한다.
"""
import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx


DAY_DIR = Path(__file__).resolve().parent.parent
PC_SERVER = DAY_DIR / "page30_음성경로_통합" / "대시보드_음성통합.py"
PI_SERVER = DAY_DIR / "page25_온디바이스LLM_D5" / "camera_server.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_device_contract(pi, check):
    from llama_cpp.llama_grammar import json_schema_to_gbnf

    candidate = {"tool": "move", "args": {"direction": "right", "steps": 2}, "message": ""}
    model = Mock()
    model.create_chat_completion.return_value = {
        "choices": [{"message": {"content": json.dumps(candidate, ensure_ascii=False)}}]
    }
    history = [{"role": "user", "content": "지난 질문"}]
    with patch.object(pi, "get_llm_model", return_value=model):
        actual = pi.run_tool_inference("저쪽으로 2칸 가", history)
    config = model.create_chat_completion.call_args.kwargs
    response_format = config.get("response_format", {})
    schema = response_format.get("schema", {})
    props = schema.get("properties", {})
    args = props.get("args", {}).get("properties", {})
    grammar = json_schema_to_gbnf(json.dumps(schema))
    check("D5", "실제 D5에 전달한 JSON 스키마로 GBNF 생성",
          response_format.get("type") == "json_object" and "root ::=" in grammar
          and set(schema.get("required", [])) == {"tool", "args", "message"}
          and set(props.get("tool", {}).get("enum", [])) == {"move", "describe", "ask"}
          and set(args.get("direction", {}).get("enum", [])) == {"up", "down", "left", "right"}
          and args.get("steps", {}).get("type") == "integer"
          and props.get("message", {}).get("type") == "string" and props["message"].get("enum") == [""])
    messages = config.get("messages", [])
    check("D5", "마지막 질문에 /no_think, temperature=0, 생성 토큰 상한 300",
          messages[1:] == [*history, {"role": "user", "content": "저쪽으로 2칸 가 /no_think"}]
          and history == [{"role": "user", "content": "지난 질문"}]
          and config.get("temperature") == 0 and config.get("max_tokens") == 300)
    check("D5", "모의 추론 결과를 도구 후보로 반환", actual == candidate, repr(actual))
    truncated = pi._parse_tool_output('{"tool":"move","args":')
    check("D5", "잘린 기기 응답은 원문을 노출하지 않고 장면 설명으로 복구",
          truncated == {"tool": "describe", "args": {}, "message": ""}, repr(truncated))
    with patch.object(pi, "get_oled_device", return_value=None):
        outcome = pi.show_oled_text("RIGHT")
    check("D3", "사용할 수 없는 OLED가 출력 실패 상태를 반환", outcome == "unavailable", repr(outcome))


async def check_dashboard(pc, check):
    broken = pc.parse_tool_call('{"tool":')
    unknown = pc.parse_tool_call('{"tool":"jump","args":{}}')
    missing = pc.parse_tool_call('{"tool":"move","args":{"steps":2}}')
    clipped = pc.parse_tool_call('{"tool":"move","args":{"direction":"right","steps":99}}')
    check("R1", "잘린 JSON과 미등록 도구 → describe",
          broken["tool"] == unknown["tool"] == "describe", f"{broken['tool']}, {unknown['tool']}")
    check("R2", "방향 없는 move → ask, 99칸 → 10칸",
          missing["tool"] == "ask" and clipped["args"] == {"direction": "right", "steps": 10},
          f"{missing['tool']}, {clipped['args']}")

    body = {"ip": "192.0.2.1", "source": "voice", "prompt": "저쪽으로 2칸 가", "history": []}
    candidate = json.dumps({"tool": "move", "args": {"direction": "right", "steps": 2}, "message": ""})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=pc.app), base_url="http://test") as client:
        invented = json.dumps({"tool": "describe", "args": {}, "message": "강아지가 의자에 앉아 있습니다."})
        observed = "감지된 물체: person 3개, bus 1개. 파란 버스 옆에 사람이 서 있습니다."
        with patch.object(pc, "ask_device_llm", new=AsyncMock(return_value=invented)):
            scene = (await client.post("/api/llm-answer", json={
                **body, "prompt": "앞에 뭐가 있어?", "yolo_summary": "person 3개, bus 1개",
                "vlm_description": "파란 버스 옆에 사람이 서 있습니다."})).json()
        check("F301", "D5가 강아지·의자를 지어내도 A5는 입력의 사람·버스만 설명",
              scene.get("tool") == "describe" and scene.get("message") == observed, repr(scene.get("message")))
        # 실기기에서 D5가 이동 명령 세 가지를 모두 describe로 분류했다.
        movement = [
            ("버스 있는 쪽으로 가", "none", "ask", {"steps": 1}),
            ("위 2칸 가", "left", "move", {"direction": "up", "steps": 2}),
            ("버스 위치로 가", "unknown", "ask", {"steps": 1}),
            ("버스 있는 쪽으로 가", "down", "move", {"direction": "down", "steps": 1}),
        ]
        with patch.object(pc, "ask_device_llm", new=AsyncMock(return_value=invented)):
            for prompt, gesture, tool, args in movement:
                response = await client.post("/api/llm-answer", json={
                    **body, "source": "device", "prompt": prompt, "gesture_direction": gesture,
                    "vlm_description": "오른쪽에 버스가 있습니다."})
                answer = response.json()
                check("R9", f"D5 describe, {prompt!r}, 손 {gesture} → {tool} {args}",
                      response.status_code == 200 and answer.get("tool") == tool and answer.get("args") == args,
                      repr(answer))
        with patch.object(pc, "ask_device_llm", new=AsyncMock(return_value=candidate)):
            for prompt in ("왼쪽에 뭐가 있어?", "버스 어디로 가?", "왼쪽으로 가지 마"):
                response = await client.post("/api/llm-answer", json={
                    **body, "source": "device", "prompt": prompt, "gesture_direction": "right"})
                answer = response.json()
                check("R9", f"D5 move, {prompt!r} → 이동 없이 종료",
                      response.status_code == 200 and answer.get("tool") == "describe"
                      and answer.get("args") == {} and answer.get("need_more_info") is False, repr(answer))
        with patch.object(pc, "ask_device_llm", new=AsyncMock(return_value=candidate)):
            first = (await client.post("/api/llm-answer", json=body)).json()
        expected = {"steps": 2, "guess": "right"}
        check("R3", "유효한 JSON이 방향을 추측하면 ask에 제안만 저장",
              first.get("tool") == "ask" and first.get("args") == expected
              and first.get("need_more_info") is True, repr(first.get("args")))
        with patch.object(pc, "ask_device_llm", new=AsyncMock(return_value=candidate)):
            chain = (await client.post("/api/llm-answer", json={
                **body, "prompt": "왼쪽으로 3칸 아래로 2칸"})).json()
        check("R8", "연결어 없는 두 이동 → left 3, down 2",
              chain.get("tool") == "move" and chain.get("args") == {"direction": "left", "steps": 3}
              and chain.get("then") == [{"direction": "down", "steps": 2}],
              f"{chain.get('args')}, {chain.get('then')}")

        history = [
            {"role": "user", "content": first.get("user_content", "")},
            {"role": "assistant", "content": json.dumps(
                {k: first.get(k) for k in ("tool", "args", "message")}, ensure_ascii=False)},
        ]
        followup = {**body, "source": "device", "prompt": "응", "history": history}
        # Pi가 방향 하나를 장면 질문으로 분류했던 실기기 사례를 재현한다.
        replies = [
            ("voice", "왼쪽", "move", {"direction": "left", "steps": 2}),
            ("device", "위", "move", {"direction": "up", "steps": 2}),
            ("device", "왼쪽에 뭐가 있어?", "describe", {}),
        ]
        with patch.object(pc, "ask_device_llm", new=AsyncMock(return_value=invented)):
            for source, prompt, tool, args in replies:
                response = await client.post("/api/llm-answer", json={
                    **followup, "source": source, "prompt": prompt})
                answer = response.json()
                check("R5", f"되묻기 뒤 {source} {prompt!r} → {tool} {args}",
                      response.status_code == 200 and answer.get("tool") == tool and answer.get("args") == args)
            unconfirmed = [{"role": "assistant", "content": '{"tool":"ask","args":{"steps":2}}'}]
            answer = (await client.post("/api/llm-answer", json={**followup, "history": unconfirmed})).json()
            check("R5", "방향 제안 없이 ‘응’이라고 답하면 2칸을 기억하고 다시 묻는다",
                  answer.get("tool") == "ask" and answer.get("args") == {"steps": 2})
        for wrong_tool in ("ask", "move"):
            mistaken = json.dumps({"tool": wrong_tool, "args": {"direction": "left", "steps": 2}})
            with patch.object(pc, "ask_device_llm", new=AsyncMock(return_value=mistaken)):
                changed = (await client.post("/api/llm-answer", json={
                    **followup, "prompt": "왼쪽에 뭐가 있어?"})).json()
            check("R5", f"장면 질문으로 바꾸면 기기가 {wrong_tool}을 제안해도 describe",
                  changed.get("tool") == "describe" and changed.get("need_more_info") is False)
        with patch.object(pc, "ask_device_llm", new=AsyncMock(side_effect=pc.DeviceError("ReadTimeout"))):
            timeout = await client.post("/api/llm-answer", json=followup)
        check("R6", "D5 시간 초과를 주입하면 해당 A5 요청 → 502 device_llm_unreachable",
              timeout.status_code == 502 and timeout.json().get("error") == "device_llm_unreachable",
              f"HTTP {timeout.status_code}, {timeout.text}")
        with patch.object(pc, "ask_device_llm", new=AsyncMock(return_value=candidate)):
            resumed = (await client.post("/api/llm-answer", json=followup)).json()
        check("R5", "기기 복구 후 같은 history로 ‘응’ → move(right, 2)",
              resumed.get("tool") == "move" and resumed.get("args") == {"direction": "right", "steps": 2}
              and resumed.get("need_more_info") is False, repr(resumed.get("args")))
        check("R10", "기기 탭은 방향 문구를 반환", resumed.get("message") == "오른쪽으로 이동합니다.",
              repr(resumed.get("message")))


def run_offline(check):
    print("[오프라인] 모델 출력·통신 실패를 주입해 실제 D5 설정과 PC API를 확인합니다.")
    pc = load_module("day3_pc_server", PC_SERVER)
    # 센서 SDK를 가져오는 부분만 대체한다. Pi의 D5와 D3 함수는 제출용 서버 코드를 실행한다.
    hardware = {name: Mock() for name in ("gpiozero", "picamera2", "picamera2.encoders", "picamera2.outputs")}
    with patch.dict(sys.modules, hardware):
        pi = load_module("day3_pi_server", PI_SERVER)
    check_device_contract(pi, check)
    asyncio.run(check_dashboard(pc, check))
