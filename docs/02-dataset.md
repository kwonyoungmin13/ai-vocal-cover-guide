# 2. 보컬 분리부터 학습 데이터 확정까지

[처음으로](../README.md) · [이전: 환경](01-setup.md) · [다음: 학습](03-training.md)

**학습용 목소리 녹음과 커버할 곡은 서로 다른 입력입니다.** 여기서는 목소리 모델을 만들 녹음을 준비합니다. 한 화자의 목소리로 시작하세요. 이미 깨끗한 단독 보컬이 있다면 분리 과정을 건너뛰고 구간 검토로 이동할 수 있습니다.

## 2-1. 원음과 출처 보존

사용할 수 있는 녹음을 `data\source\train-001.wav`처럼 번호를 붙여 둡니다. 원음은 가공 출력으로 덮어쓰지 않습니다. 학습에 사용할 권한을 확인하고 출처·화자·허용 범위·파일 해시를 따로 기록합니다.

```powershell
. .\scripts\workspace.ps1
$ProjectRoot = (Get-Location).Path
$SepPython = Join-Path $ProjectRoot '.venv-separation\Scripts\python.exe'
$Separator = Join-Path $ProjectRoot '.venv-separation\Scripts\audio-separator.exe'
$HelperPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
Get-FileHash -LiteralPath .\data\source\train-001.wav -Algorithm SHA256
```

다음과 같이 무손실 WAV로 변환할 수 있습니다. 변환은 원래 압축 음원의 손실을 복구하지 않습니다. `-n`은 기존 출력 덮어쓰기를 막습니다.

```powershell
ffmpeg -n -i .\data\source\recording.flac -ar 44100 -ac 2 -c:a pcm_s24le .\data\source\train-001.wav
if ($LASTEXITCODE -ne 0) { throw 'WAV 변환 실패' }
```

## 2-2. 짧은 구간으로 분리 시험

FFmpeg로 원음의 30~50초를 시험 파일로 만듭니다. 곡 길이에 맞게 시간을 바꾸세요.

```powershell
ffmpeg -n -ss 30 -i .\data\source\train-001.wav -t 20 -c:a pcm_s24le .\data\source\train-001-test.wav
if ($LASTEXITCODE -ne 0) { throw '시험 구간 생성 실패' }
& $Separator .\data\source\train-001-test.wav --model_filename vocals_mel_band_roformer.ckpt --model_file_dir .\models\separation --output_dir .\data\separated\train-001-test --output_format WAV --sample_rate 44100 --use_soundfile --use_native_fp16 --mdxc_batch_size 1 --mdxc_overlap 4 --normalization 0.98
if ($LASTEXITCODE -ne 0) { throw '시험 분리 실패' }
Get-ChildItem -LiteralPath .\data\separated\train-001-test
```

`Kim`은 모델 별칭입니다. CLI에는 공백 없는 **`vocals_mel_band_roformer.ckpt`**를 넣습니다. 첫 실행은 모델을 다운로드하므로 시간이 더 걸립니다. `--model_file_dir`를 생략하면 캐시가 의도하지 않은 위치에 생길 수 있습니다.

`Vocals` 파일을 듣고 자음, 긴 모음, 고음, 작은 소리, 악기 잔여를 확인합니다. 반주가 없는 목소리일수록 학습용 선별이 수월합니다. fp16에 문제가 있으면 시험 실행에서 `--use_native_fp16`을 빼고 비교합니다.

## 2-3. 전곡 분리

시험이 만족스러우면 전곡을 새 폴더로 처리합니다. 같은 출력 폴더로 재실행하지 않습니다.

```powershell
& $Separator .\data\source\train-001.wav --model_filename vocals_mel_band_roformer.ckpt --model_file_dir .\models\separation --output_dir .\data\separated\train-001-v1 --output_format WAV --sample_rate 44100 --use_soundfile --use_native_fp16 --mdxc_batch_size 1 --mdxc_overlap 4 --normalization 0.98
if ($LASTEXITCODE -ne 0) { throw '전곡 분리 실패' }
Get-ChildItem -LiteralPath .\data\separated\train-001-v1
```

도구가 생성한 파일명에는 모델과 stem이 붙습니다. 실제 `Vocals` 파일을 확인해 별도 작업용 `data\separated\train-001-vocals.wav`로 복사하고, 원래 분리 결과를 남깁니다. 자동 생성 이름을 추측해 다음 명령에 넣지 마세요.

## 2-4. 잔향 제거 A/B 비교

이 사례의 잔향 모델은 다음과 같습니다. 분리한 **보컬**을 입력하고 `Dry` stem을 선택합니다.

```powershell
& $Separator .\data\separated\train-001-vocals.wav --model_filename dereverb-echo_mel_band_roformer_sdr_13.4843_v2.ckpt --model_file_dir .\models\separation --output_dir .\data\dereverb\train-001-v1 --output_format WAV --single_stem Dry --sample_rate 44100 --use_soundfile --use_native_fp16 --mdxc_batch_size 1 --mdxc_overlap 4 --normalization 1.0
if ($LASTEXITCODE -ne 0) { throw '잔향 제거 실패' }
Get-ChildItem -LiteralPath .\data\dereverb\train-001-v1
```

먼저 15~20초 대표 구간에서 시험하는 것을 권합니다. 같은 시간 구간을 원 보컬과 Dry에서 꺼내, 더 큰 쪽을 감쇠해 비슷한 음량으로 듣습니다. 더 큰 소리를 더 좋은 음질로 오해하기 쉽습니다. RMS 음량 맞춤은 근사 비교이며 지각 음량을 완전히 같게 만들지는 않습니다.

잔향이 줄어도 발음이 잘리거나 금속성 잡음이 생기면 원 보컬을 선택하거나 해당 구간을 제외합니다. 잔향 제거는 모든 녹음에 필수인 단계가 아닙니다. 선택한 작업용 보컬을 `data\dereverb\train-001-dry.wav`로 따로 복사합니다.

## 2-5. 후보 구간 만들기

3~15초 정도의 자연스러운 프레이즈부터 시작합니다. 시간은 원 보컬과 동일한 타임라인 기준으로 기록합니다. 지나치게 짧은 자음 조각, 긴 무음, 화음·코러스·다른 화자·대사·심한 반주 잔여는 피합니다.

```powershell
ffmpeg -n -ss 30 -i .\data\dereverb\train-001-dry.wav -t 10 -ar 44100 -ac 1 -c:a pcm_s24le .\data\candidates\001-001.wav
if ($LASTEXITCODE -ne 0) { throw '후보 추출 실패' }
```

본 저장소는 노래 구간을 자동으로 판정하지 않습니다. 오디오 편집기에서 파형과 실제 소리를 확인하며 시간을 정하세요. 예시 [segments.example.csv](../examples/segments.example.csv)를 개인 목록으로 복사해 원곡 번호·시작/끝·분리/잔향 모델·상태·선택 이유를 기록합니다.

## 2-6. 청취 승인과 확정

후보 파일을 하나씩 듣고 `pending_user_review` → `approved_by_user` 또는 `excluded_by_user`로 상태를 바꿉니다. 다른 사람이 불렀거나 음색이 크게 손상된 구간은 제외 이유를 적습니다. 기계 검사는 승인 판단을 대신하지 않습니다.

승인 파일만 `data\approved\voice-v1`에 복사합니다. 파일을 옮기거나 후보 원본을 지울 필요가 없습니다. 복사 후 해시를 비교하고 **승인 목록에 없는 파일이 확정 폴더에 섞이지 않았는지** 확인하세요.

```powershell
New-Item -ItemType Directory -Force .\data\approved\voice-v1 | Out-Null
if (Test-Path -LiteralPath .\data\approved\voice-v1\001-001.wav) { throw '기존 확정 파일 보존: 새 이름/버전을 사용하세요.' }
Copy-Item -LiteralPath .\data\candidates\001-001.wav -Destination .\data\approved\voice-v1\001-001.wav -ErrorAction Stop
Get-FileHash -LiteralPath .\data\candidates\001-001.wav -Algorithm SHA256
Get-FileHash -LiteralPath .\data\approved\voice-v1\001-001.wav -Algorithm SHA256
```

확정 폴더를 재사용할 때는 같은 이름의 파일이 없는지 먼저 확인하세요. 다른 버전은 `voice-v2`처럼 새 폴더로 만듭니다. 학습에는 `data\candidates` 전체가 아닌 **확정 폴더**만 입력합니다.

완료 기준: 모든 확정 파일에 청취 승인 기록이 있고, 무음·비정상 길이·다른 화자가 없으며, 원음·분리본·후보가 보존되어 있습니다.

가능하면 서로 다른 음역·발음이 있는 녹음 일부를 `data\evaluation`에 따로 보관하고 학습에 넣지 않습니다. 같은 원음의 바로 옆 구간보다 별도 녹음·곡을 평가에 쓰는 편이 일반화 확인에 도움이 됩니다. 평가용 분리도 CSV에 기록하세요.
