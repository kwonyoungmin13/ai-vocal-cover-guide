# 3. 승인한 보컬로 RVC 모델 학습하기

[환경 준비](01-setup.md)와 [데이터 준비](02-dataset.md)를 마치고, 직접 들어 본 단일 화자 보컬만 `data/approved/voice-v1`에 넣은 다음 진행한다. 이 문서는 Windows PowerShell과 Applio의 고정 소스 [`e95ec175db434011854efc3b1bd66088b4d1e379`](https://github.com/IAHispano/Applio/tree/e95ec175db434011854efc3b1bd66088b4d1e379)를 기준으로 작성했다. 원음, 후보, 승인 자료, 학습 파생본을 각각 보관한다.

## 1. 학습 전 확인

- `data/approved/voice-v1`에는 승인한 WAV만 둔다. 이번 예제는 단일 화자이므로 이 폴더 안에 하위 폴더를 만들지 않는다.
- 화음, 다른 사람의 목소리, 대사, 반주 잔여, 잔향 제거 손상은 청취해서 제외한다. 자동 에너지 검사는 화자를 구분하지 못한다.
- 파일명, 출처, 원음의 시작·끝 시각, 처리 모델, 승인 여부, SHA-256을 기록한다. 후보 폴더 전체를 학습 입력으로 지정하지 않는다.
- 학습 전에 여러 음역의 원곡·녹음 세션 일부를 평가용으로 빼고 기록하는 것을 권장한다. 같은 원음의 바로 이웃한 조각을 학습·평가로 나누면 효과를 과대평가할 수 있다. 평가 자료는 학습 입력 폴더에 넣지 않는다.
- 같은 실행 이름을 중복 실행하지 않는다. 설정이나 승인 자료가 바뀌면 새 이름으로 시작한다.
- 학습 자료와 모델을 공개할 권한은 사용자가 확보한다. 이 저장소에는 가수 음원이나 학습한 가수 모델이 포함되어 있지 않다.

다음 설정은 RTX 5060 8GB에서 수행한 사례의 시작점이다. 모든 GPU에서 메모리 사용량, 속도, 음질이 같다는 뜻은 아니다.

| 항목 | 예제 값 |
| --- | --- |
| 형식 | RVC v2, 단일 화자, F0 사용 |
| 표본율 / 보코더 | 40,000Hz / HiFi-GAN |
| F0 / 특징 추출 | RMVPE / contentvec |
| 전처리 | Automatic, 3초, overlap 0.3초 |
| 추가 effects / 정규화 | 사용 안 함 / `none` |
| 배치 / 목표 epoch | 4 / 100 |
| 저장 간격 | 10 epoch |
| GPU 데이터 캐시 / checkpointing | 사용 안 함 / 사용 안 함 |

## 2. 경로와 실행 환경 지정

저장소 최상위에서 새 PowerShell을 연다. 아래 `$ModelName`은 새 실행마다 바꾼다. 첫 실행에는 영문·숫자·밑줄로 된 이름을 권장한다.

```powershell
Get-Location
$ErrorActionPreference = 'Stop'
. .\scripts\workspace.ps1
$ProjectRoot = (Get-Location).Path
$Applio = Join-Path $ProjectRoot 'tools\Applio'
$TrainPython = Join-Path $Applio '.venv\Scripts\python.exe'
$Core = Join-Path $Applio 'core.py'
$ModelName = 'my_voice_v2_40k_001'
$Dataset = Join-Path $ProjectRoot 'data\approved\voice-v1'
$Run = Join-Path $ProjectRoot "runs\$ModelName"
$Logs = Join-Path $Run 'logs'
$Experiment = Join-Path $Logs $ModelName
$StageLogs = Join-Path $Run 'stage-logs'
$PretrainG = Join-Path $Applio 'rvc\models\pretraineds\hifi-gan\f0G40k.pth'
$PretrainD = Join-Path $Applio 'rvc\models\pretraineds\hifi-gan\f0D40k.pth'

if (Test-Path -LiteralPath $Run) { throw '새 학습은 사용하지 않은 실행 이름으로 시작하세요.' }
foreach ($p in @($TrainPython, $Core, $Dataset, $PretrainG, $PretrainD)) {
    if (-not (Test-Path -LiteralPath $p)) { throw "준비되지 않은 경로: $p" }
}
New-Item -ItemType Directory -Path $StageLogs -Force | Out-Null

$env:APPLIO_ROOT = $Applio
$env:APPLIO_CODE_ROOT = $Applio
$env:APPLIO_LOGS_DIR = $Logs
$env:APPLIO_CONFIG_FILE = Join-Path $Run 'applio-user-config.json'
$env:PYTHONPATH = $Applio
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'
$env:PYTHONNOUSERSITE = '1'
$env:USE_LIBUV = '0'
$env:OMP_NUM_THREADS = '4'
$env:MKL_NUM_THREADS = '4'
$env:TORCH_COMPILE_DISABLE = '1'
$env:TORCHDYNAMO_DISABLE = '1'
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($env:APPLIO_CONFIG_FILE, "{} `n", $utf8)
```

먼저 [환경 준비](01-setup.md)의 프로젝트 내부 TEMP·캐시 환경설정을 같은 PowerShell에 적용한다. 분리용 Python 대신 학습용 `$TrainPython`을 사용한다. 이 가이드의 수동 설치는 `.venv\Scripts\python.exe`를 만든다. 공식 `run-install.bat`은 Conda의 `env\python.exe`를 만들고 사용자 프로필에 Miniconda를 설치하므로 이 가이드에서는 실행하지 않는다.

`APPLIO_CONFIG_FILE`을 지정하고 `{}`를 미리 만드는 이유는 외부 사용자 설정에 의존하지 않고, exFAT에서 최초 설정 생성의 `os.link` 오류를 피하기 위해서다. 실행별 JSON은 기존 파일 위에 다시 쓰지 않는다.

필요한 사전 자산은 `f0G40k.pth`, `f0D40k.pth`, `rvc/models/predictors/rmvpe.pt`, `rvc/models/embedders/contentvec/{config.json,pytorch_model.bin}` 및 Applio의 `logs/mute` 자산이다. [환경 준비](01-setup.md)의 다운로드·검증을 먼저 완료한다. `logs/mute`의 40k WAV·특징·F0 2개는 고정 소스 ZIP에 포함되어 있으므로 소스의 `logs` 폴더를 지우지 않는다. 이 무음 자산은 prerequisites 다운로드 명령으로 새로 생성되지 않는다.

## 3. 승인 자료 목록과 GPU 확인

원본 승인 WAV는 이후 단계에서 수정하지 않는다. 해시 목록을 실행 폴더에 남긴다.

```powershell
$Approved = @(Get-ChildItem -LiteralPath $Dataset -File -Filter '*.wav')
if ($Approved.Count -eq 0) { throw '승인 WAV가 없습니다.' }
if (@(Get-ChildItem -LiteralPath $Dataset -Directory).Count -gt 0) {
    throw '단일 화자 예제의 승인 폴더에는 하위 폴더를 두지 마세요.'
}
$Approved | Get-FileHash -Algorithm SHA256 |
    Select-Object Path, Hash |
    Export-Csv -LiteralPath (Join-Path $Run 'approved-sha256.csv') -NoTypeInformation -Encoding UTF8

& $TrainPython -c "import torch; print(torch.__version__, torch.version.cuda); assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0))"
if ($LASTEXITCODE -ne 0) { throw '학습용 CUDA 환경을 먼저 확인하세요.' }

@'
import json, os, sys
from pathlib import Path
source = Path(sys.argv[1])
items = []
for folder, _, names in os.walk(source):
    for name in names:
        if name.lower().endswith(('.wav', '.mp3', '.flac', '.ogg')):
            items.append({'input_index': len(items), 'file': str(Path(folder) / name)})
Path(sys.argv[2]).write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
print('Recorded engine input order:', len(items))
'@ | & $TrainPython - $Dataset (Join-Path $Run 'preprocess-input-order.json')
if ($LASTEXITCODE -ne 0) { throw '전처리 입력 순서 기록 실패' }
```

외부 명령은 종료 코드를 확인하고 로그를 보관한다. 고정 버전의 `core.py`에는 하위 명령 실패를 문자열로 돌려주는 경로가 있다. 따라서 종료 코드 0이나 `successfully` 문구만으로 다음 단계로 넘어가면 안 된다.

```powershell
function Invoke-ApplioStage {
    param([string]$Stage, [string[]]$ArgumentList)
    $log = Join-Path $StageLogs ($Stage + '.log')
    if (Test-Path -LiteralPath $log) { throw "기존 로그 보존: $log" }
    Push-Location -LiteralPath $Applio
    $previousPreference = $ErrorActionPreference
    try {
        # Windows PowerShell 5.1은 정상 진행률(stderr)도 오류 레코드로 만들 수 있다.
        $ErrorActionPreference = 'Continue'
        & $TrainPython -u $Core @ArgumentList 2>&1 | Tee-Object -FilePath $log
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
        Pop-Location
    }
    if ($code -ne 0) { throw "$Stage 종료 코드 $code. 로그를 확인하세요." }
    if (Select-String -LiteralPath $log -Pattern 'Traceback|Preprocessing failed|Feature extraction failed|An error occurred reading the FAISS index' -Quiet) {
        throw "$Stage 오류 흔적이 있습니다. 결과와 로그를 확인하세요."
    }
}
```

## 4. 전처리

```powershell
Invoke-ApplioStage -Stage '01-preprocess' -ArgumentList @(
    'preprocess', '--model-name', $ModelName,
    '--dataset-path', $Dataset, '--sample-rate', '40000',
    '--cpu-cores', '4', '--cut-preprocess', 'Automatic',
    '--chunk-len', '3.0', '--overlap-len', '0.3',
    '--normalization-mode', 'none'
)
$Slices = @(Get-ChildItem -LiteralPath (Join-Path $Experiment 'sliced_audios') -File -Filter '*.wav')
if ($Slices.Count -eq 0) { throw '전처리 WAV가 없습니다.' }
"승인 입력 $($Approved.Count)개 / 파생 WAV $($Slices.Count)개"
```

`sliced_audios`에는 40kHz 모노 FLOAT WAV가 생성된다. 특징·F0 추출 단계는 이 WAV를 읽어 내부에서 16kHz로 재표본화한다. 엔진이 무음을 자르고 다시 나누므로 승인 파일 수와 파생 파일 수는 달라도 된다. 다음을 확인한다.

1. 모든 파생 WAV가 전체 디코딩되고 유한한 샘플을 가진다.
2. `0_<입력 인덱스>_<조각>.wav`의 입력 인덱스로 승인 자료의 대응을 확인한다. 엔진은 `os.walk` 순서로 입력을 번호 매기므로 정렬한 파일 목록의 순서라고 추측하지 않는다. 실제 열거 순서를 별도로 기록한다.
3. 승인 입력에 대응하는 출력이 없다면 같은 엔진의 slicer 조건으로 원인을 확인한다. 기본 Automatic 무음 문턱은 -42dB다. 무음 판정은 모든 샘플이 0이라는 뜻이 아니다.
4. 설명할 수 없는 누락, 잘못된 표본율, 비유한 샘플이 있으면 중단한다.

RMVPE 오류가 난다고 승인 WAV를 삭제하거나 일괄 패딩하지 않는다. 특히 전처리 후에만 생긴 극짧은 잔여를 확인한다. 사례에서는 0.06초의 거의 무음인 잔여가 반사 패딩 최소 길이에 못 미쳤다. 원본 승인 파일은 그대로 두고, 원인과 길이·peak·SHA를 기록한 다음 해당 **파생 WAV와 대응 특징**을 별도 보관했다. 다른 길이·다른 신호까지 같은 예외로 취급하지 않는다. 가청 발성이라면 분할 설정을 검토하고 새 실행에서 다시 처리한다.

## 5. 특징과 F0 추출

```powershell
Invoke-ApplioStage -Stage '02-extract' -ArgumentList @(
    'extract', '--model-name', $ModelName,
    '--f0-method', 'rmvpe', '--cpu-cores', '2', '--gpu', '0',
    '--sample-rate', '40000', '--embedder-model', 'contentvec',
    '--include-mutes', '2'
)
```

다음 Python 검사는 파일 개수만 맞춘 불완전한 추출도 찾는다. F0의 `foo.wav.npy`는 WAV `foo.wav`와 대응한다. 오류가 나면 학습을 시작하지 않는다.

```powershell
@'
import sys
from pathlib import Path
import numpy as np
import soundfile as sf
p = Path(sys.argv[1])
wav = {x.stem: x for x in (p / 'sliced_audios').glob('*.wav')}
feat = {x.stem: x for x in (p / 'extracted').glob('*.npy')}
coarse = {x.name.removesuffix('.wav.npy'): x for x in (p / 'f0').glob('*.wav.npy')}
fine = {x.name.removesuffix('.wav.npy'): x for x in (p / 'f0_voiced').glob('*.wav.npy')}
assert wav, 'No derived WAVs'
assert wav.keys() == feat.keys() == coarse.keys() == fine.keys(), 'WAV/feature/F0 sets differ'
for name in wav:
    a, sr = sf.read(wav[name], dtype='float32', always_2d=True)
    f, c, v = (np.load(m[name], allow_pickle=False) for m in (feat, coarse, fine))
    assert sr == 40000 and a.shape[1] == 1 and len(a) > 0, name
    assert np.isfinite(a).all(), name
    assert f.ndim == 2 and f.shape[1] == 768 and len(f) > 0, name
    assert c.ndim == v.ndim == 1 and len(c) > 0 and len(c) == len(v), name
    assert all(np.isfinite(x).all() for x in (f, c, v)), name
    assert np.all((c >= 1) & (c <= 255) & (c == np.rint(c))), name
    assert np.all(v >= 0), name
    assert abs(len(v) - len(a) / sr * 100) <= 5, name
    assert abs(len(f) * 2 - len(v)) <= 8, name
filelist = [x for x in (p / 'filelist.txt').read_text(encoding='utf-8').splitlines() if x.strip()]
assert len(filelist) == len(wav) + 2, 'Expected derived samples + 2 mute entries'
seen = set()
mutes = 0
for line in filelist:
    fields = line.split('|')
    assert len(fields) == 5 and fields[-1] == '0', line
    assert all(Path(x).is_file() for x in fields[:4]), line
    stem = Path(fields[0]).stem
    if stem.startswith('mute'):
        mutes += 1
    else:
        assert stem in wav and stem not in seen, line
        assert Path(fields[0]).resolve() == wav[stem].resolve(), line
        assert Path(fields[1]).resolve() == feat[stem].resolve(), line
        assert Path(fields[2]).resolve() == coarse[stem].resolve(), line
        assert Path(fields[3]).resolve() == fine[stem].resolve(), line
        seen.add(stem)
assert seen == set(wav) and mutes == 2
print(f'Validated {len(wav)} derived WAVs, features and F0; {len(filelist)} filelist entries')
'@ | & $TrainPython - $Experiment
if ($LASTEXITCODE -ne 0) { throw '특징/F0/filelist 검사 실패. 로그를 확인하세요.' }
```

## 6. 검색 인덱스 생성·검증

```powershell
Invoke-ApplioStage -Stage '03-index' -ArgumentList @(
    'index', '--model-name', $ModelName, '--index-algorithm', 'Faiss'
)
$Index = Join-Path $Experiment ($ModelName + '.index')
@'
import sys
from pathlib import Path
import faiss
import numpy as np
p = Path(sys.argv[1])
idx = faiss.deserialize_index(np.frombuffer(p.read_bytes(), dtype=np.uint8).copy())
assert idx.d == 768 and idx.ntotal > 0
assert idx.is_trained
print('Index dimensions:', idx.d, 'vectors:', idx.ntotal)
'@ | & $TrainPython - $Index
if ($LASTEXITCODE -ne 0) { throw '인덱스 검증 실패' }
```

고정 소스는 FAISS 파일을 바이트로 읽고 써서 Windows의 한글 경로 문제를 우회한다. 큰 데이터에서는 인덱스 생성 전에 KMeans로 벡터를 줄일 수 있으므로 인덱스 벡터 수와 원래 특징 프레임 수가 항상 같지는 않다. 같은 이름의 인덱스가 이미 있으면 엔진이 생성을 건너뛰므로 승인 자료를 바꾼 뒤 기존 인덱스를 재사용하지 않는다.

## 7. 학습

```powershell
Invoke-ApplioStage -Stage '04-train' -ArgumentList @(
    'train', '--model-name', $ModelName, '--vocoder', 'HiFi-GAN',
    '--save-every-epoch', '10', '--total-epoch', '100',
    '--sample-rate', '40000', '--batch-size', '4', '--gpu', '0',
    '--pretrained', '--custom-pretrained',
    '--g-pretrained-path', $PretrainG, '--d-pretrained-path', $PretrainD,
    '--index-algorithm', 'Faiss'
)
```

고정 CLI의 `save_every_weights` 기본값은 `True`다. `--cache-data-in-gpu`, `--checkpointing`, `--save-only-latest`, `--cleanup`은 넣지 않는다. CUDA 메모리가 부족하면 중복 GPU 작업을 확인하고 배치를 줄인 **새 실행**을 만든다. 100 epoch은 보편적인 최적값이 아니다. 중간 모델도 독립된 가이드 보컬로 비교한다.

고정 CLI의 `train`은 마지막에 인덱스 생성도 호출한다. 위에서 만든 인덱스가 있으면 다시 생성하지 않는다. 학습 중에는 `stage-logs/04-train.log`와 실행 폴더의 이벤트·체크포인트를 확인한다. 모델 파일이 생겼다는 것만으로 100 epoch 완료라고 판단하지 않는다.

중단 후 같은 자료·설정으로 재개하려면 기존 로그와 G/D 체크포인트의 완전성을 먼저 확인한다. 엔진은 같은 실험 폴더의 최신 G/D를 읽어 재개한다. 승인 해시나 설정이 달라지면 새 실행을 사용하고, 기존 폴더에 `--cleanup`을 실행하지 않는다.

## 8. 완료 확인과 모델 보관

출력은 `$Experiment`, 즉 `runs/<실행명>/logs/<실행명>`에 있다.

| 파일 | 용도 |
| --- | --- |
| `<이름>_<epoch>e_<step>s.pth` | 추론에 사용하는 compact 모델 |
| `<이름>.index` | 추론 검색 인덱스 |
| `G_<step>.pth`, `D_<step>.pth` | 학습 재개용 가중치·옵티마이저 상태 |
| `config.json`, `model_info.json`, `filelist.txt` | 학습 설정과 입력 연결 |

`G_*.pth`를 커버용 모델로 선택하지 않는다. 완료 로그의 epoch·step과 compact 모델 파일명이 맞는지, G/D가 모두 저장됐는지 확인한다. `torch.load(..., weights_only=True)`로 신뢰할 수 있는 자신의 모델을 읽고, `weight` 텐서가 유한한지, 메타데이터의 v2·40k·F0·화자 수가 계획과 일치하는지 검사한다. 손실 NaN/Inf, AMP overflow, 옵티마이저 step 누락은 로그와 체크포인트에서 따로 검토한다.

완료 로그에서 100 epoch과 실제 step을 확인한 다음, 해당 파일만 선택해 검사한다. 아래 코드가 모델을 자동으로 골라 품질을 판정하지는 않는다.

```powershell
$FinalCandidates = @(Get-ChildItem -LiteralPath $Experiment -File -Filter ($ModelName + '_100e_*s.pth'))
if ($FinalCandidates.Count -ne 1) { throw '100 epoch 모델을 로그와 대조해 확인하세요.' }
$ModelFile = $FinalCandidates[0].FullName
@'
import sys
import torch
m = torch.load(sys.argv[1], map_location='cpu', weights_only=True)
assert m.get('version') == 'v2' and m.get('f0') == 1
assert m.get('sr') in ('40k', 40000)
assert isinstance(m.get('weight'), dict) and m['weight']
for name, value in m['weight'].items():
    assert torch.is_tensor(value) and torch.isfinite(value).all(), name
assert m['weight']['emb_g.weight'].shape[0] == 1
print('Finite compact model:', m.get('version'), m.get('sr'), 'F0:', m.get('f0'))
'@ | & $TrainPython - $ModelFile
if ($LASTEXITCODE -ne 0) { throw '최종 compact 모델 검사 실패' }

$Export = Join-Path $ProjectRoot "models\$ModelName"
if (Test-Path -LiteralPath $Export) { throw '기존 모델 폴더를 덮어쓰지 않습니다.' }
New-Item -ItemType Directory -Path $Export | Out-Null
$ModelCopy = Join-Path $Export ($ModelName + '.pth')
$IndexCopy = Join-Path $Export ($ModelName + '.index')
Copy-Item -LiteralPath $ModelFile -Destination $ModelCopy
Copy-Item -LiteralPath $Index -Destination $IndexCopy
foreach ($pair in @(@($ModelFile, $ModelCopy), @($Index, $IndexCopy))) {
    if ((Get-FileHash -LiteralPath $pair[0]).Hash -ne (Get-FileHash -LiteralPath $pair[1]).Hash) {
        throw '복사 해시 불일치'
    }
}
foreach ($row in (Import-Csv -LiteralPath (Join-Path $Run 'approved-sha256.csv'))) {
    if ((Get-FileHash -LiteralPath $row.Path).Hash -ne $row.Hash) { throw '승인 원본 변경 감지' }
}
```

최종 모델과 인덱스는 새 폴더에 **복사**하며 원본 체크포인트를 보존한다. commit·패키지 버전·학습 설정·승인 목록 해시·완료 epoch/step을 JSON이나 텍스트로 함께 기록한다.

먼저 학습에 포함된 짧은 보컬을 재변환해 파일이 실제로 출력되는지 확인한다. 그다음 학습에 없는, 사용 권한이 있는 가이드 보컬로 음색·발음·고음·무성음을 청취한다. 자기보컬 재변환 성공은 새 노래에 대한 품질 검증을 대신하지 않는다. 다음은 [커버 변환·믹싱](04-cover.md)이다.

## 소스에서 확인한 동작

- [CLI 옵션과 하위 명령 실행](https://github.com/IAHispano/Applio/blob/e95ec175db434011854efc3b1bd66088b4d1e379/core.py)
- [학습·체크포인트 저장](https://github.com/IAHispano/Applio/blob/e95ec175db434011854efc3b1bd66088b4d1e379/rvc/train/train.py)
- [인덱스 생성](https://github.com/IAHispano/Applio/blob/e95ec175db434011854efc3b1bd66088b4d1e379/rvc/train/process/extract_index.py)
- [사용자 설정과 로그 경로](https://github.com/IAHispano/Applio/blob/e95ec175db434011854efc3b1bd66088b4d1e379/rvc/lib/user_config.py)
