"""Save measured YOLO/VLM timings, prompt outputs and PoC sequential/parallel results."""
import argparse
import base64
from collections import Counter
import concurrent.futures
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import time

import httpx
from PIL import Image
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def csv_rows(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def yolo(args):
    from ultralytics import YOLO
    process = psutil.Process()
    rows, detections = [], []
    with Image.open(args.image) as opened:
        image = opened.convert("RGB")
    for weight in (ROOT / "yolo11n.pt", ROOT / "source/2회차_day1/runs/furniture_spec1_20261022/weights/best.pt"):
        before = process.memory_info().rss / 2**20
        start = time.perf_counter()
        model = YOLO(str(weight))
        load = time.perf_counter() - start
        start = time.perf_counter()
        model.predict(image, imgsz=320, conf=.25, verbose=False)
        cold = time.perf_counter() - start
        for threshold in (.10, .25, .60):
            times = []
            for _ in range(10):
                start = time.perf_counter()
                result = model.predict(image, imgsz=320, conf=threshold, device="cpu", verbose=False)[0]
                times.append((time.perf_counter()-start)*1000)
            boxes = [{"label": model.names[int(b.cls)], "confidence": float(b.conf),
                      "xyxy": b.xyxy[0].tolist()} for b in result.boxes]
            average = sum(times)/len(times)
            rows.append({"model": weight.name if weight.name != "best.pt" else "furniture_best.pt", "conf": threshold,
                         "imgsz": 320, "runs": 10, "load_seconds": load, "first_inference_seconds": cold,
                         "infer_ms_avg": average, "infer_ms_min": min(times), "infer_ms_max": max(times),
                         "fps": 1000/average, "detected": len(boxes),
                         "summary": ", ".join(f"{k} {v}개" for k, v in Counter(b['label'] for b in boxes).most_common()),
                         "rss_mb": process.memory_info().rss/2**20,
                         "rss_delta_since_model_load_mb": process.memory_info().rss/2**20-before})
            detections.append({"weights": str(weight), "conf": threshold, "boxes": boxes})
            if threshold == .25:
                stem = "before" if weight.name != "best.pt" else "after"
                Image.fromarray(result.plot()[:, :, ::-1]).save(args.output / f"sofa_{stem}.jpg")
        del model
    csv_rows(args.output / "measurement.csv", rows)
    save(args.output / "conf_comparison.json", {"image": str(args.image), "image_sha256": hashlib.sha256(args.image.read_bytes()).hexdigest(),
        "memory_note": "Process RSS snapshots, not GPU memory or peak memory. Delta is relative to before each model load; allocations can be reused by later models.", "results": detections})
    print("Saved YOLO measurements", flush=True)


def vlm(args):
    import main
    process = psutil.Process()
    before = process.memory_info().rss/2**20
    start = time.perf_counter()
    model = main._load_vlm()
    load = time.perf_counter()-start
    main._models["vlm"] = model
    image = Image.open(args.image).convert("RGB")
    image.thumbnail((448, 448))
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    url = "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()
    prompts = [("free", "이 이미지를 설명해줘."), ("concise_ko", "이 이미지에 무엇이 보이는지 한국어로 간결하게 설명해줘."),
               ("count", "보이는 물체를 개수와 함께 한국어로 나열해줘."), ("obstacle", "장애물이 있는지만 한국어로 짧게 답해줘.")]
    report = {"image": str(args.image), "input_size": list(image.size), "temperature": 0.0,
              "max_tokens": 96, "model_load_seconds": load, "rss_before_load_mb": before,
              "runs": [], "regulated_runs": []}
    rows = []
    for label, prompt in prompts:
        start = time.perf_counter()
        response = model.create_chat_completion(messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": url}}, {"type": "text", "text": prompt}]}],
            temperature=0.0, max_tokens=96)
        elapsed = time.perf_counter()-start
        choice = response["choices"][0]
        row = {"prompt_id": label, "prompt": prompt, "output": choice["message"]["content"],
               "finish_reason": choice["finish_reason"], "seconds": elapsed,
               "rss_mb": process.memory_info().rss/2**20, "rss_delta_mb": process.memory_info().rss/2**20-before}
        report["runs"].append(row)
        rows.append(row)
        save(args.output / "vlm_prompt_comparison.json", report)
        csv_rows(args.output / "vlm_measurement.csv", rows)
        print(f"VLM {label}: {elapsed:.2f}s {row['output']}", flush=True)
    for repeat in range(2):
        start = time.perf_counter()
        text = main.describe_scene(image)
        report["regulated_runs"].append({"repeat": repeat+1, "output": text,
            "seconds": time.perf_counter()-start, "checks": dict(main.check(text))})
        save(args.output / "vlm_prompt_comparison.json", report)
    report["regulated_reproducible"] = len({r["output"] for r in report["regulated_runs"]}) == 1
    save(args.output / "vlm_prompt_comparison.json", report)
    print("Saved VLM prompt/format/repeatability measurements", flush=True)


def poc(args):
    raw = args.image.read_bytes()
    def request(endpoint):
        start = time.perf_counter()
        response = httpx.post(args.poc_url+endpoint, content=raw,
                              headers={"Content-Type": "image/jpeg"}, timeout=360)
        response.raise_for_status()
        return {"endpoint": endpoint, "seconds": time.perf_counter()-start, "status": response.status_code, "body": response.json()}
    endpoints = ["/api/yolo-detect", "/api/vlm-describe"]
    warm = [request(e) for e in endpoints]
    rows, details = [], [{"mode": "warmup_excluded", "responses": warm}]
    for mode in ("sequential", "parallel"):
        start = time.perf_counter()
        if mode == "parallel":
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                responses = list(executor.map(request, endpoints))
        else:
            responses = [request(e) for e in endpoints]
        elapsed = time.perf_counter()-start
        rows.append({"mode": mode, "total_seconds": elapsed, "yolo_seconds": responses[0]["seconds"],
                     "vlm_seconds": responses[1]["seconds"], "input_sha256": hashlib.sha256(raw).hexdigest()})
        details.append({"mode": mode, "responses": responses})
        csv_rows(args.output / "poc_timing.csv", rows)
        save(args.output / "poc_responses.json", details)
        print(f"PoC {mode}: {elapsed:.2f}s", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["yolo", "vlm", "poc"])
    parser.add_argument("--image", type=Path, default=ROOT / "samples/furniture_v2_sofa.jpg")
    parser.add_argument("--output", type=Path, default=ROOT / "results/spec_workflow_20261022/spec1")
    parser.add_argument("--poc-url", default="http://127.0.0.1:8001")
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=True)
    globals()[arguments.mode](arguments)
