# Modelele de transcriere pentru limba română

## Ce folosește D&TED (v0.1.2-beta)

Din v0.1.2, programul folosește implicit **modelul îmbunătățit pentru română**:
[`large-v3-turbo-ro-ct2`](https://huggingface.co/TransferRapid/whisper-large-v3-turbo_ro) —
Whisper large-v3-turbo (OpenAI) **fine-tunat pe 47 de ore de română** din Common Voice 20
(41 431 de înregistrări), de TransferRapid.

Rezultatele autorului pe setul de test Common Voice 20 (română):

| Model | WER (cuvinte greșite) | CER (caractere greșite) |
|---|---|---|
| Whisper large-v3-turbo (original) | 20,72% | 6,50% |
| **large-v3-turbo_ro (fine-tunat)** | **4,69%** | **1,22%** |

Conversia în formatul CTranslate2 (float16) a fost făcută local cu
`ct2-transformers-converter`. Licența modelului: **CC-BY-NC-4.0** (utilizare
necomercială — pentru uz personal, ca acest program, este permisă).

Alegerea modelului se schimbă din **Setări → „Cum transcrie” → Modelul de
transcriere**: „Automat” (românescul, dacă există), românescul sau cel standard
multilingv. Diacriticele cu sedilă (ş/ţ) pe care le produce uneori modelul se
repară automat la afișare de către program (`text_ro.repara_diacritice`).

## Alternativa mai bună (dacă obții acces)

[`eek/whisper-turbo-ro-en`](https://huggingface.co/eek/whisper-turbo-ro-en) este,
la data de 2026-10-24, cel mai bun model local pentru româna vorbită curentă:
WER mediu **7,9** pe 9 seturi de test românești (vs 12,1 pentru large-v3),
antrenat pe română conversațională, licență MIT, include o conversie CTranslate2.
Modelul este **cu acces restricționat** (gated): intri pe pagina lui, apeși
„Request access”, iar după aprobarea autorului descarci folderul
`ctranslate2-int8` și îl copiezi în
`%LOCALAPPDATA%\Dictare&Transcriere Română\model\whisper-turbo-ro-en-ct2`
(cu `model.bin` și `tokenizer.json` în el) — apoi apare singur în Setări.

## Cum îți faci propriul fine-tuning pentru română

Rețetă scurtă (detalii: [ghidul oficial HuggingFace](https://huggingface.co/blog/fine-tune-whisper)):

1. **Date**: [Common Voice română](https://commonvoice.mozilla.org/ro) (20+),
   [eduardem/romanian-speech-v2](https://huggingface.co/datasets/eduardem/romanian-speech-v2)
   (360 h) sau propriile înregistrări (fișier CSV: cale audio + text).
2. **Antrenare** (LoRA sau complet, pe o placă video cu ≥16 GB):
   `transformers` + `peft` + `datasets`, model de bază `openai/whisper-large-v3-turbo`,
   2–5 epoci, learning rate ~1e-5.
3. **Conversie în formatul programului**:
   ```bash
   ct2-transformers-converter --model modelul-meu-ro --output_dir large-v3-turbo-ro-ct2 --quantization float16
   ```
   plus `tokenizer.json`/`preprocessor_config.json` copiate din modelul de bază.
4. **Instalare**: copiază folderul rezultat în
   `%LOCALAPPDATA%\Dictare&Transcriere Română\model\` și alege-l din Setări.

## Surse

- [TransferRapid/whisper-large-v3-turbo_ro](https://huggingface.co/TransferRapid/whisper-large-v3-turbo_ro)
- [eek/whisper-turbo-ro-en](https://huggingface.co/eek/whisper-turbo-ro-en)
- [Systran/faster-whisper-large-v3](https://huggingface.co/Systran/faster-whisper-large-v3)
- [Fine-Tune Whisper (HuggingFace)](https://huggingface.co/blog/fine-tune-whisper)
- [faster-whisper (CTranslate2)](https://github.com/SYSTRAN/faster-whisper)
- [Modern Speech Recognition for Romanian Language (MDPI 2026)](https://www.mdpi.com/2076-3417/16/4/1928)
- [gigant/whisper-medium-romanian](https://huggingface.co/gigant/whisper-medium-romanian)
