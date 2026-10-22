"""Verify run evidence and package local submission artifacts, preserving the dataset."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_furniture_structure import source_fingerprint

BASE = ROOT / "results/spec_workflow_20261022"
OUTPUT = ROOT / "output/submission"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    before = read(BASE / "spec1/before_coco_metrics.json")
    after = read(BASE / "spec1/after_finetune_metrics.json")
    browser = read(BASE / "spec3/browser_validation.json")
    gesture = read(BASE / "spec2/gesture_validation.json")
    rules = read(BASE / "spec3/rule_regressions.json")
    raw = source_fingerprint(ROOT / "datasets/roboflow/furniture/v2")
    expected_raw = read(ROOT / "results/furniture_day1/data_audit/raw_fingerprint_before.json")
    if raw != expected_raw:
        raise RuntimeError("Original dataset changed")
    api_log = (BASE / "spec3/api_validation_final.log").read_text(encoding="utf-8")
    if "전체 64/64 PASS" not in api_log or rules["passed"] != rules["total"]:
        raise RuntimeError("Final API or regression checks failed")
    if {c["stage"] for c in browser["cases"]} != {"spec1", "spec2", "spec3"}:
        raise RuntimeError("Missing browser workflow")
    events = []
    video_metadata = []
    qa = ROOT / ".backup/video_qa"
    qa.mkdir(parents=True, exist_ok=True)
    for case in browser["cases"]:
        if case["errors"]:
            raise RuntimeError("Browser error")
        yolo = [e for e in case["exchanges"] if e["endpoint"] == "/api/yolo-detect"]
        vlm = [e for e in case["exchanges"] if e["endpoint"] == "/api/vlm-describe"]
        if len(yolo) != len(vlm) or len(yolo) != len(case["turns"]):
            raise RuntimeError("Perception/frame count mismatch")
        for i, (y, v, turn) in enumerate(zip(yolo, vlm, case["turns"])):
            if not y["input_sha256"] or y["input_sha256"] != v["input_sha256"]:
                raise RuntimeError("Perception inputs differ")
            if sha(Path(y["captured_input"])) != y["input_sha256"]:
                raise RuntimeError("Captured JPEG hash mismatch")
            events.append({"event_id": f"20261022-{case['stage']}-{i+1}",
                "client_date_kst": "2026-10-22", "input_sha256": y["input_sha256"],
                "input_path": Path(y["captured_input"]).relative_to(ROOT).as_posix(),
                "dataset_version": "Furniture v2_curated_v2", "yolo_model": "yolo11n.pt (COCO)",
                "vlm_model": "Qwen2.5-VL-3B Q4_K_M", "llm_model": "Qwen3-4B Q4_K_M",
                "prompt": turn["prompt"], "yolo": y["response"], "vlm": v["response"],
                "gesture": turn["gesture_display"], "decision": turn["response"],
                "observed_elapsed_seconds": turn["seconds"],
                "simulation": case.get("simulator")})
        video = BASE / case["stage"] / "demo.webm"
        cap = cv2.VideoCapture(str(video))
        fps, frames = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or frames <= 0:
            raise RuntimeError("Unplayable browser video")
        for label, frame in (("middle", frames//2), ("last", max(0, frames-5))):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
            ok, image = cap.read()
            if not ok or np.std(image) < 5:
                raise RuntimeError("Video frame is blank or unreadable")
            cv2.imwrite(str(qa / f"{case['stage']}_{label}.png"), image)
        cap.release()
        video_metadata.append({"stage": case["stage"], "format": "WebM", "fps": fps,
            "frames": frames, "seconds": frames/fps, "bytes": video.stat().st_size, "sha256": sha(video)})
    (BASE / "workflow_events.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n", encoding="utf-8")
    save(BASE / "video_metadata.json", video_metadata)
    mandatory = {
        "F101": "model selection notes, conf comparison, measurement.csv",
        "F102": "VLM prompt comparison, time/RSS and regulated repeated outputs",
        "F103": "original PoC endpoints and measured sequential/parallel requests",
        "F104": "frozen curated dataset, pretrained transfer learning10epochs, same-valid aligned-class comparison",
        "F201": "YOLO summary and Korean <=40 character VLM contract with obstacle suffix preserved",
        "F202": "real GestureRecognizer,21landmarks/handedness, direction and mirror tests",
        "F203": "local dashboard, shared-frame YOLO/VLM APIs, independent errors/thread pools",
        "F204": "real Qwen3-4B answer with sourced text and defensive JSON parser",
        "F301": "API design and final64/64 live server checks",
        "F302": "LLM tool selection and guarded arguments",
        "F303": "grounded move/ask, direction-word boundaries, remembered follow-up steps",
        "F304": "real browser describe/ask/move and independently checked wall/boundary simulator result",
    }
    completion = {"date_kst": "2026-10-22", "submitter": {"region": "광주", "class": "5반", "name": "임나경"},
        "mandatory": {key: {"status": "verified_with_static_image_adaptation", "evidence": value} for key, value in mandatory.items()},
        "optional": {
            "F105": {"status": "deferred", "reason": "Live camera capture/custom comprehensive room annotations unavailable"},
            "F106": {"status": "partial", "reason": "448px/token limits and bottleneck measured; controlled original/output-limit/input-resize three-setting study not performed"},
            "F205": {"status": "partial", "reason": "rotation/mirror/finger counts16/16; three personally captured images and live camera not verified"},
            "F206": {"status": "not_implemented", "reason": "YOLO/VLM source-block rules exist; deterministic count-conflict detector and quote enforcement are not implemented"},
            "F305": {"status": "implemented_unverified_live", "reason": "Existing gesture sequence code retained; no live webcam sequence recording"},
            "F306": {"status": "verified_static_and_API", "reason": "Real pointing image selects up, prompt/history/gesture direction priority verified; live mirrored camera remains unverified"}},
        "checks": {"api": "64/64", "rule_regressions": f"{rules['passed']}/{rules['total']}",
            "gesture_directions": f"{gesture['directions_passed']}/{gesture['total']}",
            "gesture_fingers": f"{gesture['finger_counts_passed']}/{gesture['total']}",
            "actual_browser_workflows": len(browser["cases"]), "captured_frame_hashes_verified": True,
            "original_dataset_unchanged": True, "test_split_used_for_training_or_metrics": False},
        "metrics": {"before": before, "after": after},
        "adaptations": ["User-selected Furniture3classes replaces the document's obstacle/marker toy dataset",
            "Supplied/local images replace webcam input by prior user instruction", "Grid simulator replaces physical actuation"],
        "limits": ["Small curated mainly-single-object validation set is not a real-room benchmark",
            "COCO dining table and Furniture Table have different semantic breadth",
            "VLM output formatting is verified; factual accuracy or safety of obstacle statements is not guaranteed",
            "Ballie and SmartThings are reference concepts; no physical robot or SmartThings device is connected"],
        "script_sha256": {p.name: sha(p) for p in [ROOT / "main.py", ROOT / "index.html", ROOT / "API_검증.py"]}}
    save(BASE / "completion.json", completion)
    models = {"detection_candidates": [
        {"name": "YOLOv8n", "params_m": 3.2, "official_coco_map50_95": 37.3, "official_cpu_onnx_ms": 80.4},
        {"name": "YOLO11n", "params_m": 2.6, "official_coco_map50_95": 39.5, "official_cpu_onnx_ms": 56.1},
        {"name": "YOLO11s", "params_m": 9.4, "official_coco_map50_95": 47.0, "official_cpu_onnx_ms": 90.0}],
        "detector_license_reference": "AGPL-3.0 or Enterprise; see publisher terms",
        "selection": "YOLO11n: compact parameter count, CPU budget, existing pipeline and transfer-learning support. Parameter count is only a memory proxy for unmeasured alternatives.",
        "vlm_candidates": [{"name": "Qwen2.5-VL-3B", "selected": True, "license_reference": "GGUF model card Apache-2.0", "local_evidence": "vlm_measurement.csv"},
            {"name": "Qwen2.5-VL-7B", "selected": False, "local_evidence": "not measured"}],
        "sources": ["https://docs.ultralytics.com/models/yolo11/", "https://docs.ultralytics.com/models/yolov8/", "https://www.ultralytics.com/license",
            "https://huggingface.co/ggml-org/Qwen2.5-VL-3B-Instruct-GGUF", "https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct"],
        "note": "Official640px COCO/ONNX references are not measurements on this PC. Local latency, FPS and RSS are separately recorded."}
    save(BASE / "spec1/model_selection.json", models)
    deck = OUTPUT / "AI 코어_2회차_집사형로봇_광주_5반_임나경_최종.pptx"
    if not deck.is_file():
        raise RuntimeError("Final presentation missing")
    source_paths = [ROOT / p for p in ("main.py", "index.html", "API_검증.py", "API_설계.md", "requirements.txt", "README.md")]
    source_paths += sorted((ROOT / "scripts").glob("spec*.py"))
    source_paths += [ROOT / "scripts/spec3_browser_validate.mjs", ROOT / "scripts/build_spec_presentation.mjs"]
    archives = []
    for n in range(1, 4):
        stage = f"spec{n}"
        name = f"AI 코어_2회차_PJT0{n}_동작시연영상_광주_5반_임나경.zip"
        destination = OUTPUT / name
        if destination.exists():
            raise RuntimeError("Do not overwrite an existing submission archive")
        selected = [p for p in (BASE / stage).rglob("*") if p.is_file() and "raw_video" not in p.parts]
        selected += [BASE / "environment.json", BASE / "completion.json", BASE / "workflow_events.jsonl", BASE / "video_metadata.json"]
        selected += list((BASE / "captured_inputs").glob("*.jpg"))
        if n == 1:
            selected += [ROOT / "source/2회차_day1/runs/furniture_spec1_20261022" / p for p in ("weights/best.pt", "args.yaml", "results.csv")]
            selected += [p for p in (ROOT / "datasets/roboflow/furniture/v2_curated_v2").iterdir() if p.is_file() and p.suffix != ".cache"]
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
            zipped.write(deck, "발표자료/" + deck.name)
            for p in selected:
                zipped.write(p, p.relative_to(ROOT).as_posix())
            for p in source_paths:
                zipped.write(p, "updated_source/" + p.relative_to(ROOT).as_posix())
            zipped.writestr("시연_안내.txt", (
                f"광주 5반 임나경 / 명세서 {n}\n"
                f"실제 Edge 브라우저 시연 영상: results/spec_workflow_20261022/{stage}/demo.webm\n"
                "정지 이미지 입력을 사용한 실제 로컬 모델 추론이며 API 응답을 모킹하지 않았습니다.\n"
                "Chrome/Edge/VLC 등에서 WebM을 재생할 수 있습니다.\n"
                "발표자료는 명세서 1,2,3을 순서대로 정리한 공통 PPTX입니다.\n"
                "updated_source에는 이번 변경 코드가 있으며 기존 프로젝트 루트에 적용합니다.\n"
                "대용량 VLM/LLM 가중치와 Python 환경은 제외했습니다. README의 설치·다운로드 방법을 따르세요.\n"
                "실제 카메라·실물 로봇·SmartThings 제어는 검증 범위에 포함하지 않았습니다.\n"
            ).encode("utf-8-sig"))
        with zipfile.ZipFile(destination) as zipped:
            if zipped.testzip() is not None:
                raise RuntimeError("Submission ZIP CRC failed")
            names = zipped.namelist()
            if len(names) != len(set(names)):
                raise RuntimeError("Duplicate archive member")
            if hashlib.sha256(zipped.read("발표자료/" + deck.name)).hexdigest() != sha(deck):
                raise RuntimeError("Packaged deck differs")
            video_name = f"results/spec_workflow_20261022/{stage}/demo.webm"
            if hashlib.sha256(zipped.read(video_name)).hexdigest() != sha(BASE / stage / "demo.webm"):
                raise RuntimeError("Packaged video differs")
        archives.append({"name": name, "bytes": destination.stat().st_size, "sha256": sha(destination)})
    save(OUTPUT / "submission_manifest.json", {"submitter": completion["submitter"],
        "deck": {"name": deck.name, "bytes": deck.stat().st_size, "sha256": sha(deck)}, "archives": archives,
        "video_format": "WebM, real browser screen recording", "original_dataset_tree_sha256": raw["tree_sha256"]})
    print(json.dumps({"mandatory_verified": len(mandatory), "api": "64/64", "archives": archives}, ensure_ascii=True))


if __name__ == "__main__":
    main()
