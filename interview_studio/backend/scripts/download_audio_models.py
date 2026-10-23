"""Provision public models explicitly; never run from request handling."""
from pathlib import Path
from huggingface_hub import snapshot_download

ROOT=Path(__file__).resolve().parents[1]/'models'
if __name__ == '__main__':
    for repo,name,revision,files in [
        ('speechbrain/spkrec-ecapa-voxceleb','ecapa','0f99f2d0ebe89ac095bcc5903c4dd8f72b367286',['embedding_model.ckpt','README.md']),
        ('speechbrain/sepformer-whamr','sepformer','9950fd8055b38679d2af5bef2366b5dba600ec66',['encoder.ckpt','decoder.ckpt','masknet.ckpt','README.md']),
        ('kresnik/wav2vec2-large-xlsr-korean','korean-ctc','629c9a3501c10ba128bf3fa1eebb12af3be03f61',['*.json','*.txt','pytorch_model.bin','README.md'])]:
        snapshot_download(repo,revision=revision,local_dir=ROOT/name,allow_patterns=files)
