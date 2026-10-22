"""Regressions for grounded follow-up moves, parser defenses and VLM output format."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main


def run():
    results = []
    def expect(name, actual, expected):
        results.append({"name": name, "passed": actual == expected, "actual": actual, "expected": expected})
    history = [{"role": "user", "content": "[사용자 질문] 저쪽으로 3칸 가"},
               {"role": "assistant", "content": json.dumps({"tool": "ask", "args": {"steps": 3}, "message": "어느 쪽?"})}]
    for tool in ("describe", "ask", "move"):
        call = {"tool": tool, "args": {"direction": "down", "steps": 1} if tool == "move" else {}, "message": "model output"}
        actual = main.apply_rules(call, "왼쪽", history, "up")
        expect(f"R5 direction reply with LLM {tool}", actual["args"], {"direction": "left", "steps": 3})
    actual = main.apply_rules({"tool": "describe", "args": {}, "message": "scene answer"},
                              "왼쪽에 무엇이 보여?", history, "up")
    expect("New scene question must not complete a pending move", actual["tool"], "describe")
    for word in ("위치", "위험", "가위"):
        expect("Direction word boundary: " + word, main.said_direction(word), None)
    expect("Direction word up", main.said_direction("위 2칸 가"), "up")
    expect("Infinite model step value", main.to_steps(float("inf")), 1)
    expect("Clamp large step value", main.to_steps(99), 10)
    expect("Malformed JSON", main.parse_tool_call("{broken")["tool"], "describe")
    expect("Unknown tool", main.parse_tool_call('{"tool":"fly","args":{}}')["tool"], "describe")
    for suffix in ("장애물 있음", "장애물 없음"):
        text = "거실에 베이지색 무늬가 있는 큰 소파와 작은 나무 의자가 놓여 있습니다, " + suffix + "."
        compact = main.compact_vlm_text(main.normalize(text))
        expect("VLM compact preserves " + suffix, all(ok for _, ok in main.check(compact)), True)
        expect("VLM ends with " + suffix, compact.endswith(suffix + "."), True)
    expect("Do not invent missing obstacle evidence", main.compact_vlm_text("소파가 있습니다."), "소파가 있습니다.")
    report = {"passed": sum(r["passed"] for r in results), "total": len(results), "cases": results}
    out = ROOT / "results/spec_workflow_20261022/spec3/rule_regressions.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Rule regressions: {report['passed']}/{report['total']}")
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    run()
