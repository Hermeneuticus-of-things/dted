# Modelele de transcriere pentru limba română — măsurători și recomandări

## REZULTAT FINAL (24.10.2026): eek câștigă — model implicit din v0.4.0

| Model | Carte (30 s) | Total | Viteză | Dimensiune |
|---|---|---|---|---|
| **eek whisper-turbo-ro-en (ales)** | **5,4%** | **5,8%** | 1,3 s | 788 MB |
| standard large-v3-turbo | 12,2% | 10,9% | 1,6 s | 1,6 GB |
| TransferRapid turbo_ro | 47,3% | 37,0% | 0,7 s | 1,6 GB |

Accesul la eek (gated) a fost aprobat la 24.10 seara; modelul e instalat în
`%LOCALAPPDATA%\Dictare&Transcriere Română\model\whisper-turbo-ro-en-ct2`
și e **implicit** (config `model_preferat=auto` îl alege primul).

## Măsurătorile inițiale (24.10.2026, placă video NVIDIA RTX PRO 4000)

Mostre: voce românească sintetizată cu [XTTS-v2-romanian-v2](https://huggingface.co/eduardem/xtts-v2-romanian-v2)
(vocile Georgel/Costel, cele mai bune), un pasaj de carte de 30 s + 3 propoziții scurte.
Text cunoscut → WER (rata cuvintelor greșite) calculat cuvânt cu cuvânt.

| Model | WER total | Carte (30 s) | Scurte | Viteză (30 s audio) |
|---|---|---|---|---|
| **Whisper large-v3-turbo (standard)** | **15,0%** | 12,2% | 0–50% | 2,5 s |
| large-v3-turbo_ro (fine-tunat RO, [TransferRapid](https://huggingface.co/TransferRapid/whisper-large-v3-turbo_ro)) | 37,0% | 47,3% | 0–12% | 0,7 s |

Pe fișierul uman curat (18 s, dictare de probă): standard **0%** WER.

## Concluzia (pentru dictare de CARTE)

**Modelul standard (large-v3-turbo) rămâne implicit.** Fine-tunatul
românesc, deși are WER 4,69% pe benchmark-ul Common Voice 20 (clipuri de ~5 s),
**taie textul lung**: oprește generația devreme (antrenat doar pe clipuri scurte)
— inacceptabil pentru dictarea de cărți. E disponibil ca opțiune în
Setări → „Cum transcrie”, pentru clipuri scurte.

Alegerea se face din **Setări → „Cum transcrie” → Modelul de transcriere**;
„Automat” = standardul. Diacriticele cu sedilă (ş/ţ) se repară automat la
afișare (`text_ro.repara_diacritice`).

## Ce am încercat și am reținut

- **[TransferRapid/whisper-large-v3-turbo_ro](https://huggingface.co/TransferRapid/whisper-large-v3-turbo_ro)** — descărcat, convertit CT2 float16, inclus ca opțiune. Licență CC-BY-NC-4.0 (necomercial).
- **[eek/whisper-turbo-ro-en](https://huggingface.co/eek/whisper-turbo-ro-en)** — cel mai bun raportat pe română vorbită (WER 7,9 mediu pe 9 seturi, MIT, conversie CT2 inclusă), dar **cu acces restricționat**: cere „Request access” pe pagina HuggingFace. După aprobare: descarcă folderul `ctranslate2-int8` și copiază-l în `%LOCALAPPDATA%\Dictare&Transcriere Română\model\whisper-turbo-ro-en-ct2` — apare singur ca opțiune (adaugă-l în `MODELE_TRANSCRIBERE`).
- **[Systran/faster-whisper-large-v3](https://huggingface.co/Systran/faster-whisper-large-v3)** — modelul complet large-v3 (nu turbo): potențial mai precis, de ~2–3× mai lent; de testat ca opțiune viitoare.

## Cum îți faci propriul fine-tuning (pentru text lung de carte)

Rețetă (detalii: [ghidul HuggingFace](https://huggingface.co/blog/fine-tune-whisper)):

1. **Date**: [Common Voice română](https://commonvoice.mozilla.org/ro) + texte lungi proprii
   (cel mai important: clipuri **lungi**, ca să nu învețe să taie); sau
   [eduardem/romanian-speech-v2](https://huggingface.co/datasets/eduardem/romanian-speech-v2) (360 h).
2. **Antrenare**: `transformers` + `peft` (LoRA), bază `openai/whisper-large-v3-turbo`,
   2–5 epoci, lr ~1e-5, pe GPU ≥16 GB.
3. **Conversie**: `ct2-transformers-converter --model modelul-ro --output_dir model-ro-ct2 --quantization float16`
   (+ `tokenizer.json`/`preprocessor_config.json` din modelul de bază).
4. **Instalare**: folderul în `%LOCALAPPDATA%\Dictare&Transcriere Română\model\`, apoi apare în Setări.

## Probele de acuratețe (reproductibile)

Mostrele sunt în `D:\OpenCode\probe_ro\` (generate local), iar scriptul de WER
compară oricare două foldere de modele. TTS-ul de generat mostre românești:
`D:\OpenCode\xtts-v2-romanian-v2` (mediu `D:\OpenCode\tts-venv`).
