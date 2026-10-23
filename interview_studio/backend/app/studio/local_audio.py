"""Offline acoustic adapters. Model loading never downloads user data or weights.

CTC alignment is an acoustic diagnostic, not a calibrated pronunciation grade.
Speaker separation uses a local TorchScript waveform separator (B,T -> B,T,S).
"""
from pathlib import Path
import io
import math
import re


def unavailable(code):
    return {'status': 'unavailable', 'reason_code': code}


def decode_audio(content):
    import av
    import numpy as np
    chunks = []
    with av.open(io.BytesIO(content)) as container:
        resampler = av.AudioResampler(format='flt', layout='mono', rate=16000)
        for frame in container.decode(audio=0):
            chunks.extend(f.to_ndarray().reshape(-1) for f in resampler.resample(frame))
        chunks.extend(f.to_ndarray().reshape(-1) for f in resampler.resample(None))
    audio = np.concatenate(chunks) if chunks else np.empty(0, dtype='float32')
    if not len(audio) or len(audio) > 16000 * 3600 or not np.isfinite(audio).all():
        raise ValueError('invalid audio')
    return audio


def ctc_alignment(log_probs, tokens, blank=0):
    """Viterbi CTC alignment including repeated-token blank transitions."""
    import numpy as np
    probs = np.asarray(log_probs)
    labels = [blank]
    for token in tokens:
        labels.extend((int(token), blank))
    if not tokens or len(tokens) > 2000 or probs.shape[0] * len(labels) > 20_000_000:
        raise ValueError('alignment bounds')
    previous = np.full(len(labels), -np.inf)
    previous[0] = 0
    back = np.zeros((len(probs), len(labels)), dtype='int8')
    for t, frame in enumerate(probs):
        current = np.full(len(labels), -np.inf)
        for s, label in enumerate(labels):
            options = [(previous[s], 0)]
            if s: options.append((previous[s-1], 1))
            if s > 1 and label != blank and label != labels[s-2]: options.append((previous[s-2], 2))
            value, step = max(options)
            current[s] = value + frame[label]
            back[t, s] = step
        previous = current
    state = len(labels)-1 if previous[-1] >= previous[-2] else len(labels)-2
    if not math.isfinite(previous[state]): raise ValueError('unalignable')
    frames = [[] for _ in tokens]
    for t in range(len(probs)-1, -1, -1):
        if state % 2: frames[state//2].append(t)
        state -= int(back[t, state])
    if any(not f for f in frames): raise ValueError('unalignable')
    return [sorted(f) for f in frames]


def assess_pronunciation(content, reference_text, model_path):
    if not model_path or not Path(model_path).is_dir(): return unavailable('pronunciation_model_missing')
    if not reference_text or len(reference_text) > 10000: return unavailable('reference_required')
    try:
        import torch
        from transformers import AutoProcessor, AutoModelForCTC
        processor = AutoProcessor.from_pretrained(str(model_path), local_files_only=True, trust_remote_code=False)
        model = AutoModelForCTC.from_pretrained(str(model_path), local_files_only=True, trust_remote_code=False).eval()
        audio = decode_audio(content)
        normalized = re.sub(r'[^가-힣a-zA-Z0-9 ]', ' ', reference_text)
        normalized = ' '.join(normalized.split())
        tokens = processor.tokenizer(normalized, add_special_tokens=False).input_ids
        if processor.tokenizer.unk_token_id in tokens: return unavailable('unsupported_reference_tokens')
        inputs = processor(audio, sampling_rate=16000, return_tensors='pt')
        with torch.inference_mode(): logits = model(**inputs).logits[0].log_softmax(-1).cpu().numpy()
        aligned = ctc_alignment(logits, tokens, model.config.pad_token_id)
        scale = len(audio)/16000/len(logits)
        observations = []
        for token, frames in zip(tokens, aligned):
            observations.append({'token': processor.tokenizer.convert_ids_to_tokens(token),
                'start': frames[0]*scale, 'end': (frames[-1]+1)*scale,
                'acoustic_log_posterior': float(logits[frames, token].mean())})
        return {'status': 'complete', 'method': 'local_ctc_forced_alignment', 'calibrated': False,
            'score': None, 'observations': observations,
            'limitation': '음향 정렬 관찰값이며 검증된 한국어 발음 점수가 아닙니다.'}
    except Exception:
        return unavailable('pronunciation_analysis_failed')


def separate_speakers(content, enrollment_audio, model_path, separation_model_path=None):
    """Separate two waveform sources, identify enrolled speaker, exclude uncertainty.

    Speaker encoder is a local TorchScript module (B,T -> B,D); separator is
    local TorchScript (B,T -> B,T,2). No arbitrary downloaded Python executes.
    """
    if not enrollment_audio: return unavailable('speaker_enrollment_required')
    if not model_path or not Path(model_path).exists(): return unavailable('speaker_model_missing')
    if not separation_model_path or not Path(separation_model_path).exists(): return unavailable('separation_model_missing')
    try:
        import torch
        import numpy as np
        encoder = load_speaker_encoder(model_path) if Path(model_path).is_dir() else torch.jit.load(str(model_path), map_location='cpu').eval()
        separator = load_separator(separation_model_path) if Path(separation_model_path).is_dir() else torch.jit.load(str(separation_model_path), map_location='cpu').eval()
        audio = decode_audio(content); enrollment = decode_audio(enrollment_audio)
        if len(enrollment) < 16000*3: return unavailable('enrollment_too_short')
        with torch.inference_mode():
            # WHAMR outputs 8 kHz bandwidth even after upsampling. Match the
            # enrollment bandwidth before comparing speaker embeddings; otherwise
            # spectral loss looks like a different speaker.
            enrollment_wave = torch.from_numpy(enrollment).unsqueeze(0)
            if Path(separation_model_path).is_dir():
                import torchaudio
                enrollment_wave = torchaudio.functional.resample(
                    torchaudio.functional.resample(enrollment_wave, 16000, 8000), 8000, 16000)
            target = encoder(enrollment_wave).reshape(1,-1)
            intervals=[]; clean = np.zeros_like(audio)
            for start in range(0,len(audio),16000*4):
                chunk = torch.from_numpy(audio[start:start+16000*4]).unsqueeze(0)
                outputs=separator(chunk)
                if outputs.ndim != 3 or outputs.shape[0] != 1 or outputs.shape[1] != chunk.shape[1] or outputs.shape[2] != 2:
                    raise ValueError('separator shape')
                similarities=[]
                for i in range(2):
                    vector=encoder(outputs[:,:,i].contiguous()).reshape(1,-1)
                    similarities.append(float(torch.nn.functional.cosine_similarity(target,vector).item()))
                order=sorted(range(2),key=lambda i:similarities[i],reverse=True)
                # Conservative heuristic gate, exposed as such; requires calibration.
                accepted=similarities[order[0]] >= .65 and similarities[order[0]]-similarities[order[1]] >= .15
                if accepted: clean[start:start+chunk.shape[1]]=outputs[0,:,order[0]].numpy()
                intervals.append({'start':start/16000,'end':(start+chunk.shape[1])/16000,
                    'status':'candidate' if accepted else 'excluded_uncertain',
                    'similarities':similarities})
        return {'status':'complete','method':'local_two_source_separation_enrollment',
            'calibrated':False,'intervals':intervals,'sample_rate':16000,'candidate_audio':clean,
            'enrollment_preprocessing': 'whamr_8khz_bandwidth_match' if Path(separation_model_path).is_dir() else 'native_16khz',
            'limitation':'두 화자 분리 모델의 추정이며 겹침·세 명 이상·잔향에서 실패할 수 있습니다.'}
    except Exception:
        return unavailable('speaker_analysis_failed')


def load_speaker_encoder(path):
    """Architecture from official ECAPA model card; weights-only local loading."""
    import torch
    from speechbrain.lobes.features import Fbank
    from speechbrain.processing.features import InputNormalization
    from speechbrain.lobes.models.ECAPA_TDNN import ECAPA_TDNN
    features=Fbank(n_mels=80)
    normalize=InputNormalization(norm_type='sentence',std_norm=False)
    model=ECAPA_TDNN(input_size=80,channels=[1024,1024,1024,1024,3072],kernel_sizes=[5,3,3,3,1],dilations=[1,2,3,4,1],attention_channels=128,lin_neurons=192).eval()
    model.load_state_dict(torch.load(Path(path)/'embedding_model.ckpt',map_location='cpu',weights_only=True))
    def encode(wave):
        return model(normalize(features(wave),torch.ones(wave.shape[0])))
    return encode


def load_separator(path):
    """Official WHAMR SepFormer 8k architecture, adapting input/output to16k."""
    import torch
    import torchaudio
    from speechbrain.lobes.models.dual_path import Encoder,Decoder,SBTransformerBlock,Dual_Path_Model
    encoder=Encoder(kernel_size=16,out_channels=256)
    decoder=Decoder(in_channels=256,out_channels=1,kernel_size=16,stride=8,bias=False)
    def block():
        return SBTransformerBlock(num_layers=8,d_model=256,nhead=8,d_ffn=1024,dropout=0,use_positional_encoding=True,norm_before=True)
    masker=Dual_Path_Model(num_spks=2,in_channels=256,out_channels=256,num_layers=2,K=250,intra_model=block(),inter_model=block(),norm='ln',linear_layer_after_inter_intra=False,skip_around_intra=True)
    for module,name in [(encoder,'encoder'),(decoder,'decoder'),(masker,'masknet')]:
        module.load_state_dict(torch.load(Path(path)/(name+'.ckpt'),map_location='cpu',weights_only=True));module.eval()
    def separate(wave):
        down=torchaudio.functional.resample(wave,16000,8000)
        encoded=encoder(down);masked=masker(encoded)*encoded.unsqueeze(0)
        out=torch.stack([decoder(masked[i]) for i in range(2)],dim=-1)
        if out.shape[1]<down.shape[1]:out=torch.nn.functional.pad(out,(0,0,0,down.shape[1]-out.shape[1]))
        return torchaudio.functional.resample(out.transpose(1,2),8000,16000).transpose(1,2)[:,:wave.shape[1],:]
    return separate


