"""Recognize supplied hand images, rotations and mirror directions without a webcam."""
import importlib.util
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/spec_workflow_20261022/spec2"


def exercise(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    direction = exercise("direction", "source/2회차_day2/page31_제스처_방향판별/제스처_방향판별.py")
    fingers = exercise("fingers", "source/2회차_day2/page36_제스처_인식/제스처_인식_도전2_정답.py")
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    with direction.load_recognizer() as recognizer:
        for name, expected_fingers in (("pointing_up.jpg", 1), ("victory.jpg", 2)):
            base = Image.open(ROOT / "samples" / name).convert("RGB")
            tiles = []
            for angle, expected_direction in zip((0, 90, 180, 270), ("up", "left", "down", "right")):
                image = base.rotate(angle, expand=True)
                result = recognizer.recognize(direction.to_mp_image(image))
                landmarks = result.hand_landmarks[0] if result.hand_landmarks else None
                for mirror in (False, True):
                    found = direction.classify_direction(landmarks, image.width, image.height, mirror) if landmarks else "none"
                    expected = {"left": "right", "right": "left"}.get(expected_direction, expected_direction) if mirror else expected_direction
                    count = fingers.count_fingers(landmarks) if landmarks else None
                    rows.append({"image": name, "angle": angle, "mirror": mirror,
                        "landmark_count": len(landmarks) if landmarks else 0,
                        "handedness": result.handedness[0][0].category_name if landmarks else None,
                        "category": result.gestures[0][0].category_name if result.gestures else None,
                        "direction": found, "expected_direction": expected,
                        "finger_count": count, "expected_finger_count": expected_fingers,
                        "direction_pass": found == expected, "finger_count_pass": count == expected_fingers})
                tiles.append((image, landmarks, f"{angle} deg: {rows[-2]['direction']}, fingers={count}"))
            direction.save_directions(tiles, OUT / (Path(name).stem + "_rotations.png"))
        empty = recognizer.recognize(direction.to_mp_image(Image.open(ROOT / "samples/furniture_v2_sofa.jpg").convert("RGB")))
    report = {"input_source": "Supplied static hand images, not newly captured personal webcam images",
        "cases": rows, "no_hand_sofa_pass": not empty.hand_landmarks,
        "directions_passed": sum(row["direction_pass"] for row in rows),
        "finger_counts_passed": sum(row["finger_count_pass"] for row in rows),
        "total": len(rows), "limitation": "Live webcam variability and optional F205 three personally captured images remain unverified."}
    (OUT / "gesture_validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, ensure_ascii=True))


if __name__ == "__main__":
    main()
