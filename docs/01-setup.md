# 1. Windows 환경 준비

[처음으로](../README.md) · [다음: 데이터 준비](02-dataset.md)

목표는 **분리 환경과 학습 환경을 나누고, 캐시·임시 파일을 프로젝트 안에 모으는 것**입니다. 아래 명령은 이 저장소의 루트에서 순서대로 실행합니다. 기존 프로젝트의 가상환경을 다른 PC에 복사하지 마세요.

## 1-1. 저장소 받기

GitHub의 **Code → Download ZIP**으로 받아 원하는 작업 드라이브에 압축을 풉니다. Git이 있으면 이 저장소를 clone해도 됩니다. 경로 예시는 `D:\audio-cover\ai-vocal-cover-guide`입니다. 실제 경로를 사용하세요.

PowerShell에서 프로젝트 폴더로 이동합니다. 시스템 실행 정책을 영구 변경하지 않고 작업 세션만 열려면 다음처럼 실행합니다.

```powershell
Set-Location -LiteralPath 'D:\audio-cover\ai-vocal-cover-guide'
Get-Location
powershell -NoProfile -ExecutionPolicy Bypass
```

새로 열린 PowerShell에서:

```powershell
Get-Location
. .\scripts\workspace.ps1
$ProjectRoot = (Get-Location).Path
```

터미널을 새로 열 때마다 프로젝트로 이동한 뒤 `workspace.ps1`을 다시 적용합니다. 스크립트는 음원 처리·학습·전역 설정 변경을 하지 않습니다.

## 1-2. Python과 FFmpeg 확인

설치된 Python 3.12를 사용합니다. 없는 경우 [Python 공식 배포](https://www.python.org/downloads/windows/)를 확인하세요. FFmpeg는 [공식 다운로드 안내](https://ffmpeg.org/download.html#build-windows)를 통해 Windows 빌드를 받아 프로젝트의 `tools\ffmpeg\bin` 아래에 `ffmpeg.exe`, `ffprobe.exe`가 오도록 풉니다. 이미 설치된 FFmpeg를 실행해도 됩니다.

```powershell
py -3.12 --version
ffmpeg -version
ffprobe -version
```

`py`가 없다면 아래 명령의 `py -3.12`를 Python 3.12 실행 파일의 절대 경로로 바꿉니다. FFmpeg를 나중에 추가했다면 `workspace.ps1`을 다시 적용합니다.

## 1-3. 보조 도구 환경

```powershell
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'venv 생성 실패' }
$HelperPython = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& $HelperPython -m pip install -r .\requirements.txt
if ($LASTEXITCODE -ne 0) { throw '보조 도구 설치 실패' }
& $HelperPython .\scripts\audio_tools.py --help
```

이 환경에는 검사·미리듣기·믹스에 필요한 NumPy와 SoundFile만 설치합니다.

## 1-4. 분리 전용 환경

```powershell
py -3.12 -m venv .venv-separation
if ($LASTEXITCODE -ne 0) { throw '분리 venv 생성 실패' }
$SepPython = Join-Path $ProjectRoot '.venv-separation\Scripts\python.exe'
$Separator = Join-Path $ProjectRoot '.venv-separation\Scripts\audio-separator.exe'
& $SepPython -m pip install torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu130
if ($LASTEXITCODE -ne 0) { throw 'PyTorch 설치 실패' }
& $SepPython -m pip install "audio-separator[cpu]==0.47.0" -c .\examples\separation-constraints.txt
if ($LASTEXITCODE -ne 0) { throw 'audio-separator 설치 실패' }
& $SepPython -m pip check
if ($LASTEXITCODE -ne 0) { throw '분리 의존성 충돌' }
& $SepPython -c "import torch; print(torch.__version__, torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO CUDA')"
& $Separator --help
```

위 PyTorch/CUDA 조합은 학습 사례의 버전에 맞춘 설치 예시입니다. 기존 분리 실행은 별도 환경의 torch 2.13.0을 사용했으므로 이 새 조합에서의 전곡 재현 검증을 주장하지 않습니다. GPU·드라이버에 맞는 빌드는 [PyTorch 공식 설치 안내](https://pytorch.org/get-started/locally/)를 확인하고, 변경한 버전을 기록하세요. `CUDA False` 상태로 전곡 처리를 시작하지 않습니다.

`[cpu]` extra는 audio-separator가 import하는 **ONNX Runtime**을 설치합니다. 여기서 사용하는 RoFormer의 PyTorch CUDA 실행을 CPU로 바꾸는 설정이 아닙니다. torchvision도 짝이 맞는 버전으로 고정해 간접 의존성이 PyTorch를 바꾸는 것을 막습니다. GPU 빌드를 변경했다면 constraints 파일도 그 조합으로 함께 수정하세요.

## 1-5. Applio 고정 소스와 학습 전용 환경

이 가이드의 CLI는 다음 소스를 기준으로 작성했습니다.

```text
IAHispano/Applio
commit: e95ec175db434011854efc3b1bd66088b4d1e379
```

[고정 소스 ZIP](https://github.com/IAHispano/Applio/archive/e95ec175db434011854efc3b1bd66088b4d1e379.zip)을 받아 프로젝트 안에서 압축을 풀고 폴더 이름을 `tools\Applio`로 맞춥니다. `tools\Applio\core.py`가 있는지 확인합니다. 기본 `run-install.bat`은 사용자 프로필 아래 Miniconda를 설치하므로, 이 가이드에서는 아래의 별도 venv 방식을 사용합니다.

```powershell
$Applio = Join-Path $ProjectRoot 'tools\Applio'
if (-not (Test-Path -LiteralPath (Join-Path $Applio 'core.py'))) { throw 'Applio 소스 경로 확인' }
py -3.12 -m venv (Join-Path $Applio '.venv')
if ($LASTEXITCODE -ne 0) { throw '학습 venv 생성 실패' }
$TrainPython = Join-Path $Applio '.venv\Scripts\python.exe'
& $TrainPython -m pip install torch==2.11.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu130
if ($LASTEXITCODE -ne 0) { throw '학습 PyTorch 설치 실패' }
& $TrainPython -m pip install -r (Join-Path $Applio 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Applio 의존성 설치 실패' }
& $TrainPython -m pip check
if ($LASTEXITCODE -ne 0) { throw '학습 의존성 충돌' }
& $TrainPython -c "import torch, numpy, faiss; print(torch.__version__, numpy.__version__); assert torch.cuda.is_available(), 'CUDA unavailable'; print(torch.cuda.get_device_name(0))"
```

이때 설치되는 `requirements.txt`는 **Applio 쪽 파일**입니다. 저장소 루트의 보조 도구 requirements와 혼동하지 마세요. 동일 버전이라도 분리·학습 가상환경을 합치지 않습니다.

고정 소스의 CLI는 도움말을 실행할 때도 사용자 설정을 읽습니다. 먼저 설정·로그 위치를 프로젝트 안에 지정합니다. exFAT의 하드링크 오류를 피하도록 빈 JSON도 미리 만듭니다.

```powershell
$SetupRun = Join-Path $ProjectRoot 'runs\asset-setup'
New-Item -ItemType Directory -Force $SetupRun | Out-Null
$env:APPLIO_ROOT = $Applio
$env:APPLIO_CODE_ROOT = $Applio
$env:APPLIO_LOGS_DIR = Join-Path $SetupRun 'logs'
$env:APPLIO_CONFIG_FILE = Join-Path $SetupRun 'applio-user-config.json'
$env:PYTHONPATH = $Applio
$env:USE_LIBUV = '0'
if (-not (Test-Path -LiteralPath $env:APPLIO_CONFIG_FILE)) {
    [System.IO.File]::WriteAllText($env:APPLIO_CONFIG_FILE, '{}', (New-Object System.Text.UTF8Encoding($false)))
}
Push-Location -LiteralPath $Applio
try {
    & $TrainPython core.py --help
    & $TrainPython core.py preprocess --help
    & $TrainPython core.py infer --help
    & $TrainPython core.py prerequisites --pretraineds-hifigan --models --no-exe
    if ($LASTEXITCODE -ne 0) { throw 'Applio 사전 자산 다운로드 실패' }
} finally { Pop-Location }
```

`prerequisites`는 공식 자산을 `tools\Applio` 아래에 다운로드합니다. FFmpeg는 앞 단계에서 준비했으므로 `--no-exe`로 중복 다운로드를 생략합니다. 고정 소스 ZIP이 모델 가중치를 모두 포함하는 것은 아닙니다. 다음 필수 파일이 있고 크기가 0보다 큰지 확인합니다.

```powershell
$RequiredAssets = @(
    'rvc\models\pretraineds\hifi-gan\f0G40k.pth',
    'rvc\models\pretraineds\hifi-gan\f0D40k.pth',
    'rvc\models\predictors\rmvpe.pt',
    'rvc\models\embedders\contentvec\config.json',
    'rvc\models\embedders\contentvec\pytorch_model.bin',
    'logs\mute\sliced_audios\mute40000.wav',
    'logs\mute\extracted\mute.npy',
    'logs\mute\f0\mute.wav.npy',
    'logs\mute\f0_voiced\mute.wav.npy'
)
foreach ($Asset in $RequiredAssets) {
    $AssetFile = Get-Item -LiteralPath (Join-Path $Applio $Asset) -ErrorAction Stop
    if ($AssetFile.Length -le 0) { throw "빈 자산: $Asset" }
    Get-FileHash -LiteralPath $AssetFile.FullName -Algorithm SHA256
}
```

해시는 받아 온 파일을 나중에 대조하기 위한 기록입니다. 첫 다운로드의 신뢰성을 증명하려면 제작자가 제공하는 해시 또는 신뢰하는 고정 배포와 별도로 대조해야 합니다. 새 학습에서는 [학습 문서](03-training.md)의 실행별 환경 변수로 다시 지정합니다.

## 1-6. 환경 기록

설치가 끝나면 패키지를 기록합니다. `pip freeze`에 로컬 wheel 경로가 나오면 그대로 다른 PC용 requirements로 배포하지 않습니다.

```powershell
& $SepPython -m pip freeze | Set-Content -Encoding UTF8 .\outputs\separation-packages.txt
& $TrainPython -m pip freeze | Set-Content -Encoding UTF8 .\outputs\training-packages.txt
```

이 저장소에서는 보조 도구와 문서만 검증했습니다. 새 PC에서는 설치 검사 → 한 구간 분리 → 작은 데이터 전처리 → 짧은 추론 순서로 확인한 뒤 전체 작업을 실행하세요.
