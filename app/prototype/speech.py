# -*- coding: utf-8 -*-
"""Speech in and out for the prototype: Whisper (faster-whisper) and Edge TTS voices."""
from importlib import import_module
normalize = import_module('app.rag.text').normalize

# Hotel words that help Whisper spell names and codes, in the caller's own language
HOTEL_WORDS = {
    'ar': 'فندق نايل بيرل، حجز، check-in، check-out، Deluxe، Suite، Twin، Double، رقم الحجز B013193، جنيه',
    'en': 'Nile Pearl Hotel, booking reference B013193, check-in, check-out, Deluxe, Suite, Twin room, EGP',
    'fr': 'Hôtel Nile Pearl, réservation B013193, arrivée, départ, chambre Deluxe, Suite, livres égyptiennes',
    'ru': 'Отель Nile Pearl, номер бронирования B013193, заезд, выезд, номер Делюкс, люкс, египетских фунтов',
}
VOICES = {'Arabic-Egyptian': 'ar-EG-SalmaNeural', 'Arabic': 'ar-EG-SalmaNeural', 'English': 'en-US-JennyNeural',
          'French': 'fr-FR-DeniseNeural', 'Russian': 'ru-RU-SvetlanaNeural'}

class STT:
    def __init__(self, size='large-v3', device='cuda'):
        from faster_whisper import WhisperModel
        self.m = WhisperModel(size, device=device, compute_type='float16' if device == 'cuda' else 'int8')

    def __call__(self, path, language=None, hotel_prompt=True):
        """Text and language code. The language is detected first (only the first 30 s are read),
        then the audio is transcribed with hotel words in that same language."""
        if language is None:
            _, info = self.m.transcribe(path)                  # lazy: detection only, no decoding
            language = info.language
        prompt = HOTEL_WORDS.get(language) if hotel_prompt else None
        segs, info = self.m.transcribe(path, language=language, beam_size=5, initial_prompt=prompt)
        return ' '.join(s.text.strip() for s in segs).strip(), language

async def speak(text, language='Arabic-Egyptian', path='reply.mp3'):
    import edge_tts
    await edge_tts.Communicate(text, VOICES.get(language, VOICES['English'])).save(path)
    return path

def wer(reference, hypothesis):
    """Word error rate after Arabic normalisation (0 = identical)."""
    r, h = normalize(reference).split(), normalize(hypothesis).split()
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev, d[j] = d[j], cur
    return round(d[len(h)] / max(len(r), 1), 3)
