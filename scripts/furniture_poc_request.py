"""Send the same Furniture JPEG to both Day 1 PoC endpoints and save responses."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import httpx


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--image", type=Path, default=ROOT / "samples/furniture_v2_sofa.jpg")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    started = datetime.now(timezone.utc)
    output_dir = args.output_dir or (
        ROOT / "results/furniture_day1" / started.strftime("poc_%Y%m%dT%H%M%S%fZ")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    record_path = output_dir / "poc_responses.json"
    if record_path.exists():
        raise SystemExit(f"Run record already exists: {record_path}")
    image_path = args.image.resolve()
    image_bytes = image_path.read_bytes()
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    yolo_record = ROOT / "results/furniture_day1/inference.json"
    previous = json.loads(yolo_record.read_text(encoding="utf-8")) if yolo_record.is_file() else None
    base_url = args.url.rstrip("/")

    def health():
        response = httpx.get(base_url + "/api/health", timeout=10.0, trust_env=False)
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "ok":
            raise RuntimeError("PoC health is not OK")
        return payload

    record = {
        "status": "running", "started_at_utc": started.isoformat(),
        "url": base_url, "image": image_path.as_posix(),
        "image_sha256": image_hash, "image_bytes": len(image_bytes),
        "same_image_as_previous_yolo": previous["image_sha256"] == image_hash if previous else None,
        "request_content_type": "image/jpeg",
        "mode": "one YOLO request and one VLM request submitted concurrently",
        "health_before": health(), "responses": {},
        "timing_note": (
            "Server elapsed_ms includes thread-pool wait, first model loading and inference. "
            "Client timings include HTTP and decoding overhead. This is not a serial/parallel benchmark."
        ),
    }

    def save_record():
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def post(endpoint, required_text):
        start = time.perf_counter()
        response = httpx.post(
            base_url + endpoint, content=image_bytes,
            headers={"Content-Type": "image/jpeg"}, timeout=args.timeout, trust_env=False,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.raise_for_status()
        payload = response.json()
        if response.status_code != 200:
            raise RuntimeError(f"Unexpected status: {response.status_code}")
        if not isinstance(payload.get(required_text), str) or not payload[required_text].strip():
            raise RuntimeError(f"Missing/non-text response field: {required_text}")
        if not isinstance(payload.get("elapsed_ms"), (int, float)) or payload["elapsed_ms"] < 0:
            raise RuntimeError("Invalid elapsed_ms")
        return {
            "endpoint": endpoint, "http_status": response.status_code,
            "request_image_sha256": image_hash, "client_elapsed_ms": elapsed_ms,
            "body": payload,
        }

    save_record()
    print("Healthy PoC server; sending identical JPEG bytes to YOLO and VLM...", flush=True)
    start = time.perf_counter()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {
                pool.submit(post, "/api/yolo-detect", "summary"): "yolo",
                pool.submit(post, "/api/vlm-describe", "description"): "vlm",
            }
            for future in as_completed(futures):
                name = futures[future]
                result = future.result()
                record["responses"][name] = result
                save_record()
                print(json.dumps({"received": name, **result}, ensure_ascii=True), flush=True)
        record["total_client_elapsed_ms"] = (time.perf_counter() - start) * 1000
        record["health_after"] = health()
        if not all(record["health_after"].get(key) for key in ("yolo_loaded", "vlm_loaded")):
            raise RuntimeError("One of the server models is not marked loaded")
        record["status"] = "complete"
        record["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        save_record()
        print(f"Both responses verified and saved: {record_path}", flush=True)
    except Exception as error:
        record.update(status="failed", error_type=type(error).__name__, error=str(error))
        save_record()
        raise


if __name__ == "__main__":
    main()
