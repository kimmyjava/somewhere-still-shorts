"""Shared voice contracts: what a voice request and a TTS engine look like."""
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class VoiceSpec:
    profile_id: str
    engine: str = "qwen"
    model_size: str = "1.7B"
    language: str = "en"
    seed: int = 42


@dataclass
class TTSResult:
    path: Path
    duration_s: float
    seconds_taken: float
    engine: str


class TTSEngine(Protocol):
    def health(self) -> bool: ...
    def synthesize(self, text: str, voice: VoiceSpec, out_wav: Path) -> TTSResult: ...
