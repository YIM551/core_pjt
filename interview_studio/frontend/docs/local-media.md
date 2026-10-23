# Local interview media UI

## Install / run

Run `npm ci`, then `npm run prepare:vision`, then `npm run dev`.
`prepare:vision` is an explicit internet download step for the two pinned Google MediaPipe task files. It verifies SHA256 and copies WASM files from the installed `@mediapipe/tasks-vision` package. Runtime requests use `/models` and `/mediapipe/wasm` on this app's own origin. Personal frames are processed in browser memory; only derived observations are posted to the local backend. No CDN or browser speech service is used.

## Gaze observation

1. Choose webcam + microphone, connect devices, then open six-point iris calibration.
2. Keep the head still. Look at five viewport targets in order and collect each for 1.5 seconds (30 samples, at least 20 valid).
3. For the sixth point, look at the physical camera lens while collecting.
4. Binocular iris positions are measured in each eye's axes. A personal affine screen mapping is fitted on alternating samples and checked on the held-out samples (RMS screen error <= 0.25). This tests repeatability, not absolute gaze accuracy.
5. FaceLandmarker transformation matrices estimate head rotation. Missing iris, closed eyes, inconsistent binocular observations, head changes over 0.15 radians, degenerate mapping, excessive validation error or viewport resize make affected gaze observations unavailable.

The output estimates calibrated camera direction / screen region. It is not a validated eye tracker and does not infer actual eye contact, attention, emotion, personality or interview suitability. Glasses, reflections, camera location and changes of posture require checking / recalibration. The camera region threshold (0.15 screen units) is a transparent engineering heuristic, not a clinically or psychometrically validated threshold. Camera direction outside this region is not automatically a negative behavior.

## Audio flow

Microphone-only mode avoids asking for camera permission. Device confirmation reports actual browser noise-suppression setting; the optional preflight measures microphone RMS and clipping over approximately one second. These observations do not identify a background speaker.

The optional consent button records eight seconds of solo speech and registers it with the local backend before session start. The READY session is reused only when settings, workspace and selected sources match; changing settings requires enrollment again. No speaker identity is inferred from VAD. Reports show backend candidate / uncertain intervals; uncertain intervals are excluded rather than penalized. Pronunciation panels show the configured local acoustic observations and explicitly state that validated Korean pronunciation grades are unavailable.

## Verification and remaining validation

Run `npm test` and `npm run build`. Tests cover calibration mapping and hold-out repeatability, degenerate inputs, absent iris, head changes, upload consistency and lifecycle cleanup. Unit fixtures cannot establish real-world gaze accuracy or Korean pronunciation accuracy. Those require consented local-device trials under glasses, noise, accent and lighting variation.

v0.3 UI audit: difficulty/type/duration, selected source revisions, transcript correction, timer controls, microphone-only fallback, explicit enrollment and partial measurements are present. This UI does not claim that acoustic alignment is a validated pronunciation score or that an embedding classifier reconstructs separated speaker audio. P1 history comparison / JSON export and richer pose gesture semantics are not completed by this frontend change.

## Review repairs

Capture segments now advance `turn_offset_ms` by sealed recording duration within the same turn; pause time is excluded. New turns and explicit answer retries reset this timeline. Input mode changes release camera/microphone tracks and local vision models, clear device readiness, and require reconnection. Text mode cannot request devices or begin recording; the input-mode selector is disabled while recording.

The report screen can open a requested immutable report revision and fetch authenticated audio blobs for capture references loaded with transcripts. Playback object URLs are revoked when replaced, navigating to another report, or unmounting; expired/deleted captures return an error instead of fabricated media.

Verification after repair: `npm test` 48 passed; `npm run build` passed. Added regression tests for two capture segments excluding a ten-second pause, next-turn reset, AV → TEXT → AUDIO → AV device permission changes, archive retrieval and audio URL cleanup.
