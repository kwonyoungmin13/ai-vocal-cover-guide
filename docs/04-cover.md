# 4. 새 곡을 변환하고 반주와 믹싱하기

[처음으로](../README.md) · [이전: 학습](03-training.md) · [문제 해결](05-troubleshooting.md)

목소리 모델이 준비되었으면 **새 곡의 보컬을 RVC로 변환하고, 같은 곡의 반주와 합칩니다.** 기존 모델이 있다면 학습 단계는 건너뛸 수 있지만 모델 사용 권한과 대응 인덱스를 확인해야 합니다.

## 4-1. 새 실행 준비

저장소 루트에서 환경을 적용합니다. 같은 출력 폴더를 재사용하지 않습니다. 아래 모델 이름은 학습 문서에서 사용한 예시이며 자신의 모델로 바꾸세요.

```powershell
Get-Location
. .\scripts\workspace.ps1
$ProjectRoot = (Get-Location).Path
$HelperPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$Separator = Join-Path $ProjectRoot '.venv-separation\Scripts\audio-separator.exe'
$Applio = Join-Path $ProjectRoot 'tools\Applio'
$TrainPython = Join-Path $Applio '.venv\Scripts\python.exe'
$ModelName = 'my_voice_v2_40k_001'
$VoiceModel = Join-Path $ProjectRoot "models\$ModelName\$ModelName.pth"
$VoiceIndex = Join-Path $ProjectRoot "models\$ModelName\$ModelName.index"
$CoverRun = Join-Path $ProjectRoot 'outputs\cover-v1'
if (Test-Path -LiteralPath $CoverRun) { throw '새 커버 실행 폴더 이름을 지정하세요.' }
New-Item -ItemType Directory $CoverRun | Out-Null
foreach ($p in @($TrainPython, $VoiceModel, $VoiceIndex)) {
    if (-not (Test-Path -LiteralPath $p)) { throw "없는 파일: $p" }
}
$env:APPLIO_ROOT = $Applio
$env:APPLIO_CODE_ROOT = $Applio
$env:APPLIO_LOGS_DIR = Join-Path $CoverRun 'applio-logs'
$env:APPLIO_CONFIG_FILE = Join-Path $CoverRun 'applio-user-config.json'
$env:PYTHONPATH = $Applio
$env:USE_LIBUV = '0'
[System.IO.File]::WriteAllText($env:APPLIO_CONFIG_FILE, '{}', (New-Object System.Text.UTF8Encoding($false)))
Get-FileHash -LiteralPath $VoiceModel, $VoiceIndex -Algorithm SHA256
```

원곡을 `data\source\cover-song.wav`로 준비하고 출처·해시를 기록합니다. 다운로드 기능은 이 저장소에 포함하지 않습니다. 이미 보컬/반주를 갖고 있다면 분리를 건너뛰고 각각의 시작점과 길이를 확인하세요.

## 4-2. 새 곡의 보컬과 반주 분리

```powershell
& $Separator .\data\source\cover-song.wav --model_filename vocals_mel_band_roformer.ckpt --model_file_dir .\models\separation --output_dir .\data\separated\cover-v1 --output_format WAV --sample_rate 44100 --use_soundfile --use_native_fp16 --mdxc_batch_size 1 --mdxc_overlap 4 --normalization 0.98
if ($LASTEXITCODE -ne 0) { throw '커버 음원 분리 실패' }
Get-ChildItem -LiteralPath .\data\separated\cover-v1
```

출력에서 실제 Vocals·Instrumental 파일을 확인해 작업용 복사본을 각각 `data\separated\cover-vocals.wav`, `data\separated\cover-instrumental.wav`로 만듭니다. 둘 모두 동일한 타임라인을 유지합니다. 보컬의 무음을 잘라서 앞으로 당기면 반주와 어긋납니다.

보컬 잔향이 심하면 [데이터 준비의 A/B 절차](02-dataset.md#2-4-잔향-제거-ab-비교)를 적용하고 더 나은 가이드를 선택합니다. 아래는 분리 보컬을 사용하는 예입니다. Dry를 선택했다면 `$Guide`만 실제 파일로 바꾸세요.

```powershell
$Guide = Join-Path $ProjectRoot 'data\separated\cover-vocals.wav'
$Backing = Join-Path $ProjectRoot 'data\separated\cover-instrumental.wav'
& $HelperPython .\scripts\audio_tools.py inspect --input $Guide --json-output outputs/cover-v1/guide-inspection.json
if ($LASTEXITCODE -ne 0) { throw '가이드 검사 실패' }
& $HelperPython .\scripts\audio_tools.py inspect --input $Backing --json-output outputs/cover-v1/backing-inspection.json
if ($LASTEXITCODE -ne 0) { throw '반주 검사 실패' }
```

## 4-3. 대표 20초부터 변환

저음·고음·자음이 함께 있는 구간을 선택합니다. 예시의 60~80초가 곡 범위를 벗어나면 시간을 바꾸세요.

```powershell
& $HelperPython .\scripts\audio_tools.py preview --input $Guide --start 60 --duration 20 --output outputs/cover-v1/guide-20s.wav
if ($LASTEXITCODE -ne 0) { throw '가이드 미리듣기 생성 실패' }
& $HelperPython .\scripts\audio_tools.py preview --input $Backing --start 60 --duration 20 --output outputs/cover-v1/backing-20s.wav
if ($LASTEXITCODE -ne 0) { throw '반주 미리듣기 생성 실패' }
$SampleInput = Join-Path $CoverRun 'guide-20s.wav'
$SampleOutput = Join-Path $CoverRun 'converted-20s-pitch0.wav'
Push-Location -LiteralPath $Applio
try {
    & $TrainPython core.py infer --input-path $SampleInput --output-path $SampleOutput --pth-path $VoiceModel --index-path $VoiceIndex --pitch 0 --index-rate 0.3 --volume-envelope 1.0 --protect 0.33 --f0-method rmvpe --embedder-model contentvec --export-format WAV
    if ($LASTEXITCODE -ne 0) { throw '대표 구간 변환 실패' }
} finally { Pop-Location }
```

콘솔에 예외·인덱스 읽기 오류가 없는지 확인하고 생성 파일을 듣습니다. 원본 자음, 숨소리, 고음이 자연스러운지, 목표 음색이 유지되는지 확인하세요. `index-rate 0.3`, `protect 0.33`은 사례의 시작값입니다. 한 번에 하나의 값만 바꾸고 새 파일명으로 비교합니다. 학습 때와 같은 contentvec를 사용합니다.

## 4-4. 반음과 옥타브 구분

| Pitch | 의미 | 반주 처리 |
|---|---|---|
| `0` | 원곡 음높이 | 반주도 0 |
| `-1` | 반음 낮춤 | 반주도 -1 |
| `-2` | 온음 낮춤 | 반주도 -2 |
| `-12` | 한 옥타브 낮춤 | 반주를 0으로 유지해도 음의 종류는 일치 |

“한 키”라는 표현은 사람마다 다르게 쓰므로 **반음 수를 숫자로 정해 기록**합니다. 음역 통계만으로 키를 결정하지 않습니다. 0과 -1을 비교하려면 위 대표 변환에서 `--pitch -1`과 새 출력명을 사용하고 반주도 -1로 변환해야 합니다. 목소리 변환과 반주 조옮김을 중복 적용하지 마세요.

FFmpeg의 rubberband 필터가 있는 빌드에서, 속도를 유지한 반주 -1반음의 예시는 다음과 같습니다. 이 명령은 20초 샘플용입니다.

```powershell
ffmpeg -filters | Select-String rubberband
$Ratio = [Math]::Pow(2.0, -1.0 / 12.0).ToString('R', [Globalization.CultureInfo]::InvariantCulture)
ffmpeg -n -i .\outputs\cover-v1\backing-20s.wav -af "rubberband=tempo=1:pitch=$Ratio" -c:a pcm_s24le .\outputs\cover-v1\backing-20s-pitch-1.wav
if ($LASTEXITCODE -ne 0) { throw '반주 조옮김 실패' }
```

필터가 없으면 지원하는 FFmpeg 빌드나 오디오 편집기의 피치 변경 기능을 사용합니다. 단순 샘플레이트 변경은 속도까지 바꾸므로 이 방법의 대체가 아닙니다. 조옮김 뒤에도 시작점·총 길이를 확인합니다.

## 4-5. 샘플레이트와 타임라인 맞추기

RVC 40kHz 출력과 44.1kHz 반주는 그대로 합칠 수 없습니다. 먼저 별도 파일로 44.1kHz 변환합니다.

```powershell
ffmpeg -n -i .\outputs\cover-v1\converted-20s-pitch0.wav -ar 44100 -ac 2 -c:a pcm_s24le .\outputs\cover-v1\converted-20s-pitch0-44100.wav
if ($LASTEXITCODE -ne 0) { throw '샘플레이트 변환 실패' }
& $HelperPython .\scripts\audio_tools.py mix --vocals outputs/cover-v1/converted-20s-pitch0-44100.wav --instrumental outputs/cover-v1/backing-20s.wav --output outputs/cover-v1/mix-20s-pitch0.wav --vocal-gain-db -2 --instrumental-gain-db 0 --peak-dbfs -1
if ($LASTEXITCODE -ne 0) { throw '샘플 믹스 실패: 표본율·채널·길이 확인' }
```

믹스 도구는 기본적으로 표본율·채널·프레임 수가 다르면 중단합니다. 모노 보컬을 스테레오 반주에 넣을 때는 명시적으로 `--mono-vocals-to-stereo`를 쓸 수 있습니다. 길이만 다른 경우 오디오 편집기에서 두 트랙의 시작점과 끝을 확인하고 같은 범위를 내보내는 것이 좋습니다. `--length-policy trim-to-shorter`는 **더 짧은 쪽에 맞춰 끝을 자르는 선택**일 뿐, 타이밍을 정렬하지 않습니다.

정상 변환의 재표본화 반올림 때문에 몇 샘플만 차이 난다면, 시작점과 내용이 일치하는지 확인한 뒤 원 반주의 길이를 기준으로 끝을 패딩/절단할 수 있습니다. 큰 차이가 있다면 원인을 찾으세요. 보컬 시작 지연이나 누락은 이 작업으로 고쳐지지 않습니다.

## 4-6. 전곡 변환과 믹스

선택한 설정이 만족스러우면 전체 가이드를 변환합니다. 이 예시는 원곡키 0이며, -1로 바꿨다면 전곡 반주도 -1로 준비합니다.

```powershell
$FullOutput = Join-Path $CoverRun 'converted-full-pitch0-40k.wav'
Push-Location -LiteralPath $Applio
try {
    & $TrainPython core.py infer --input-path $Guide --output-path $FullOutput --pth-path $VoiceModel --index-path $VoiceIndex --pitch 0 --index-rate 0.3 --volume-envelope 1.0 --protect 0.33 --f0-method rmvpe --embedder-model contentvec --export-format WAV
    if ($LASTEXITCODE -ne 0) { throw '전체 변환 실패' }
} finally { Pop-Location }
```

고정 Applio는 긴 파일에서 내부 구간 처리를 수행합니다. 그래도 메모리·경계 문제가 생기면 짧은 구간으로 진단하고, 분할 결과의 경계 클릭·반복·누락을 들어 봅니다. 길이가 맞는 정상 전곡에서만 아래 정렬 복사본을 만듭니다.

```powershell
$TargetFrames = [int64](& $HelperPython -c "import soundfile as sf; print(sf.info(r'data/separated/cover-instrumental.wav').frames)")
ffmpeg -n -i .\outputs\cover-v1\converted-full-pitch0-40k.wav -af "aresample=44100,apad,atrim=end_sample=$TargetFrames" -ac 2 -c:a pcm_s24le .\outputs\cover-v1\converted-full-pitch0-44100.wav
if ($LASTEXITCODE -ne 0) { throw '전체 정렬 복사본 생성 실패' }
& $HelperPython .\scripts\audio_tools.py mix --vocals outputs/cover-v1/converted-full-pitch0-44100.wav --instrumental $Backing --output outputs/cover-v1/cover-final.wav --vocal-gain-db -2 --instrumental-gain-db 0 --peak-dbfs -1 --json-output outputs/cover-v1/mix-report.json
if ($LASTEXITCODE -ne 0) { throw '전체 믹스 실패' }
ffmpeg -n -i .\outputs\cover-v1\cover-final.wav -c:a libmp3lame -b:a 320k .\outputs\cover-v1\cover-final.mp3
if ($LASTEXITCODE -ne 0) { throw 'MP3 출력 실패' }
```

`--peak-dbfs -1`은 혼합 신호의 최대 샘플이 한계를 넘을 때 전체를 정적으로 감쇠합니다. 컴프레서·리미터·LUFS 또는 true-peak 마스터링을 수행하는 옵션이 아닙니다. 보컬 균형은 샘플을 들으며 조정하세요. 원본 반주에 이미 리버브가 있으면 보컬에 과도한 잔향을 추가하지 않습니다.

## 4-7. 완료 검사

```powershell
& $HelperPython .\scripts\audio_tools.py inspect --input outputs/cover-v1/cover-final.wav --json-output outputs/cover-v1/final-wav-inspection.json
if ($LASTEXITCODE -ne 0) { throw '최종 WAV 검사 실패' }
ffmpeg -v error -i .\outputs\cover-v1\cover-final.mp3 -f null -
if ($LASTEXITCODE -ne 0) { throw '최종 MP3 디코드 실패' }
Get-FileHash -LiteralPath .\outputs\cover-v1\cover-final.wav, .\outputs\cover-v1\cover-final.mp3 -Algorithm SHA256
```

WAV의 44.1kHz·스테레오·PCM24, 전체 길이, 비유한 값, near-full-scale 샘플을 확인합니다. MP3는 손실 압축·인코더 지연과 디코드 peak 변화가 있을 수 있으므로 WAV 검사값을 그대로 적용하지 않습니다. **최종 WAV와 MP3 모두 처음부터 끝까지 듣습니다.** 인트로, 보컬 첫 진입, 고음, 간주 뒤 재진입, 마지막 음과 꼬리를 확인하세요.

출처, 모델/index SHA, 고정 소스 commit, pitch, 반주 pitch, gain, 정렬 값, 도구 버전, 검사 결과, 청취 판단을 함께 기록합니다. [설정 예시](../examples/cover-settings.example.json)는 기록용 템플릿이며 실행 프로그램이 읽는 설정 파일은 아닙니다. 수정본은 `cover-v2`에 만들고 첫 결과를 보존합니다.
