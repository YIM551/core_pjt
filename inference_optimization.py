"""Bounded exact-input reuse and a deliberately narrow scene-question fast path."""
from collections import OrderedDict
import re
import threading
import time


def bounded_setting(value, name, minimum, maximum):
    try:
        parsed=int(value)
    except (TypeError,ValueError):
        raise ValueError(f'{name} must be an integer') from None
    if not minimum <= parsed <= maximum:
        raise ValueError(f'{name} must be between {minimum} and {maximum}')
    return parsed


def choose_vlm_side(objects, fast_side=420, detail_side=448):
    # The measured chair/sofa cases tolerate 420; tables and uncertainty retain detail.
    reliable = objects and all(o.get('label','').lower() in ('chair','sofa','couch')
                              and o.get('confidence',0) >= 0.8 for o in objects)
    return fast_side if reliable else max(fast_side,detail_side)


class ExactResultCache:
    def __init__(self, capacity=8, ttl=60, clock=time.monotonic):
        self.capacity=capacity
        self.ttl=ttl
        self.clock=clock
        self.lock=threading.Lock()
        self.entries=OrderedDict()

    def get_or_compute(self, key, compute):
        if self.capacity <= 0:
            return compute(), False
        # Single flight: simultaneous identical frames must not generate twice.
        # The VLM itself is already serial; unrelated YOLO/LLM work is unaffected.
        with self.lock:
            now=self.clock()
            for stale in [k for k, (expiry, _) in self.entries.items() if expiry <= now]:
                del self.entries[stale]
            if key in self.entries:
                expiry,value=self.entries.pop(key)
                self.entries[key]=(expiry,value)
                return value, True
            value=compute()  # Failed generations are not cached.
            self.entries[key]=(self.clock()+self.ttl,value)
            while len(self.entries)>self.capacity:
                self.entries.popitem(last=False)
            return value, False


def is_simple_scene_question(prompt):
    # Full match only; movement, ambiguous requests and follow-up directions still use LLM/rules.
    text=re.sub(r'\s+',' ',prompt.strip())
    return bool(re.fullmatch(
        r'(?:어떤 가구가 몇 개 보여\? YOLO 개수와 VLM 장면 설명을 참고해서 한국어로 알려줘\.?'
        r'|(?:거실에 )?어떤 가구가 보여[?.]?|무엇이 보여[?.]?|뭐가 보여[?.]?|가구가 몇 개야[?.]?)',text))
