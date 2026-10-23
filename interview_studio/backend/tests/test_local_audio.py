import numpy as np
import pytest
from app.studio.local_audio import ctc_alignment, assess_pronunciation, separate_speakers


def test_alignment_repeated_tokens_needs_blank():
    p=np.log(np.array([[.01,.99],[.99,.01],[.01,.99]]))
    assert ctc_alignment(p,[1,1]) == [[0],[2]]


def test_impossible_alignment_rejected():
    with pytest.raises(ValueError): ctc_alignment(np.log(np.array([[.1,.9]])),[1,1])


def test_missing_models_never_score(tmp_path):
    result=assess_pronunciation(b'invalid','안녕하세요',tmp_path/'missing')
    assert result['status']=='unavailable'
    assert 'score' not in result


def test_speaker_requires_enrollment():
    assert separate_speakers(b'',None,None)['reason_code']=='speaker_enrollment_required'


def test_remote_model_id_never_loaded():
    assert assess_pronunciation(b'', '안녕', 'organization/model')['reason_code']=='pronunciation_model_missing'


def test_real_local_models_opt_in():
    import os
    if os.environ.get('STUDIO_REAL_AUDIO_TEST') != '1': pytest.skip('explicit local model smoke')
    import io
    import wave
    import torch
    from pathlib import Path
    torch.set_num_threads(4)
    root=Path(__file__).resolve().parents[1]/'models'
    if not (root/'korean-ctc').exists(): pytest.skip('models not provisioned')
    samples=(np.sin(np.arange(64000)*.08)*12000).astype('<i2')
    target=io.BytesIO()
    with wave.open(target,'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(16000);stream.writeframes(samples.tobytes())
    content=target.getvalue()
    result=assess_pronunciation(content,'안녕하세요',root/'korean-ctc')
    assert result['status']=='complete',result
    assert result['score'] is None and result['observations']
    speakers=separate_speakers(content,content,root/'ecapa',root/'sepformer')
    assert speakers['status']=='complete',speakers
    assert len(speakers['candidate_audio'])==64000
    assert speakers['calibrated'] is False

def test_real_published_speaker_retention_and_other_exclusion():
    import os
    if os.environ.get('STUDIO_REAL_AUDIO_TEST') != '1': pytest.skip('explicit local model control')
    from pathlib import Path
    import io,wave,torch
    from app.studio.local_audio import decode_audio
    torch.set_num_threads(4)
    root=Path(__file__).resolve().parents[1]
    fixtures=root/'.test-artifacts'/'speaker-control'
    if not (fixtures/'spk1.wav').exists(): pytest.skip('public SpeechBrain speech fixtures not provisioned')
    def encode(audio):
        stream=io.BytesIO()
        with wave.open(stream,'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(16000)
            out.writeframes((np.clip(audio,-1,1)*30000).astype('<i2').tobytes())
        return stream.getvalue()
    speakers=[]
    for name in ('spk1.wav','spk2.wav'):
        audio=decode_audio((fixtures/name).read_bytes())
        audio=np.tile(audio,int(np.ceil(128000/len(audio))))[:128000]
        speakers.append((audio/max(.01,float(np.max(np.abs(audio))))*.5).astype('float32'))
    enrollment=encode(speakers[0])
    for audio in (speakers[0],(speakers[0]+speakers[1])*.5):
        result=separate_speakers(encode(audio),enrollment,root/'models/ecapa',root/'models/sepformer')
        assert result['status']=='complete'
        assert result['enrollment_preprocessing']=='whamr_8khz_bandwidth_match'
        assert all(v['status']=='candidate' for v in result['intervals'])
        assert np.any(result['candidate_audio'])
    other=separate_speakers(encode(speakers[1]),enrollment,root/'models/ecapa',root/'models/sepformer')
    assert other['status']=='complete'
    assert all(v['status']=='excluded_uncertain' for v in other['intervals'])
    assert not np.any(other['candidate_audio'])
