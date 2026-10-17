# 공식 자료와 버전 기준

확인일: **2026-10-18, 한국 시간**. 아래 링크는 도구 제작자·모델 제작자의 문서와 배포처다. 이 프로젝트의 고정 실행 환경과 변경될 수 있는 최신 문서를 구분해서 읽는다.

## 이 프로젝트의 재현 기준

| 구분 | 기록한 기준 | 근거 |
| --- | --- | --- |
| Python | 3.12.10, 분리용·학습용 가상환경 분리 | 원 프로젝트의 실행 환경·패키지 기록 |
| 보컬 분리 | audio-separator 0.47.0 | [공식 v0.47.0 소스와 사용법](https://github.com/nomadkaraoke/python-audio-separator/tree/v0.47.0) |
| 학습 엔진 | Applio, commit `e95ec175db434011854efc3b1bd66088b4d1e379` | 원 프로젝트의 소스 다운로드·SHA-256 기록. [기록된 고정 소스](https://github.com/IAHispano/Applio/tree/e95ec175db434011854efc3b1bd66088b4d1e379) |
| 학습 PyTorch | torch 2.11.0+cu130, torchaudio 2.11.0+cu130 | 원 프로젝트의 학습 환경 기록. [공식 2.11.0 설치 조합](https://pytorch.org/get-started/previous-versions/#v2110) |
| 학습 주요 의존성 | numpy 2.4.6, soundfile 0.14.0 | 고정 Applio의 `requirements-engine.txt`와 원 프로젝트의 패키지 기록 |
| FFmpeg | 9.0.2 | 원 프로젝트의 실행 기록. [공식 다운로드 안내](https://ffmpeg.org/download.html) |

표의 버전은 실제 작업에 사용한 기준이며 모든 컴퓨터에서 새 설치를 검증했다는 뜻은 아니다. 분리 환경의 torch 2.13.0과 학습 환경의 torch 2.11.0을 한 가상환경에 섞지 않는다. 의존성 설치 뒤 버전과 GPU 인식을 확인한다.

Python 가상환경은 프로젝트별 패키지를 분리하며, Windows에서는 해당 환경의 `Scripts/python.exe`를 직접 실행할 수 있다. 환경 폴더 자체를 다른 컴퓨터에 복사하기보다 같은 Python 버전으로 다시 만든다. [Python 3.12 venv 문서](https://docs.python.org/3.12/library/venv.html)

PyTorch 공식 문서에는 Windows용 CUDA 13.0의 torch 2.11.0·torchaudio 2.11.0 설치 조합이 있으며, 공식 wheel 목록에도 Python 3.12/Windows x64용 torch 2.11.0+cu130 파일이 있다. 이 가이드의 학습 환경 선택은 해당 배포를 기준으로 한다. [공식 설치 조합](https://pytorch.org/get-started/previous-versions/#v2110), [CUDA 13.0 wheel 목록](https://download.pytorch.org/whl/cu130/torch/)

## 보컬 분리와 잔향 제거

audio-separator 0.47.0은 Python 3.10 이상을 요구하며 3.14.1은 지원 대상에서 제외한다. `--env_info`로 환경을 확인하고, `--list_models`로 사용 가능한 파일명을 확인한다. 모델은 처음 사용할 때 내려받으므로 `--model_file_dir`를 작업 폴더 안으로 지정한다. `--mdxc_batch_size 1`, `--mdxc_overlap 4`, `--use_native_fp16`은 이 프로젝트의 CUDA RoFormer 실행 설정이다. native fp16은 모든 기기·모델에 공통으로 적용하는 설정이 아니다. [v0.47.0 공식 사용법](https://github.com/nomadkaraoke/python-audio-separator/tree/v0.47.0)

| 용도 | 명령에 넣는 정확한 `model_filename` | 출처 |
| --- | --- | --- |
| Kim 보컬 분리 | `vocals_mel_band_roformer.ckpt` | [v0.47.0 공식 모델 목록](https://github.com/nomadkaraoke/python-audio-separator/blob/v0.47.0/audio_separator/models.json) |
| Sucial V2 잔향·에코 제거 | `dereverb-echo_mel_band_roformer_sdr_13.4843_v2.ckpt` | [같은 공식 모델 목록](https://github.com/nomadkaraoke/python-audio-separator/blob/v0.47.0/audio_separator/models.json), [제작자의 모델 카드](https://huggingface.co/Sucial/Dereverb-Echo_Mel_Band_Roformer) |

`Kim`은 모델을 설명하는 이름이다. CLI 파일명 앞에 `Kim `이나 공백을 붙이지 않는다. Sucial 제작자 배포의 V2 파일명은 `dereverb_echo_mbr_v2_sdr_dry_13.4843.ckpt`이며, audio-separator 모델 목록에서는 위 표의 이름으로 제공한다. 원 프로젝트는 제작자 배포의 해시와 받아온 모델을 대조했다. [제작자 V2 모델 안내](https://huggingface.co/Sucial/Dereverb-Echo_Mel_Band_Roformer#3-v2-models)

Sucial 모델은 보컬의 잔향·딜레이 제거용이며 일부 화음도 제거할 수 있다. 모델 카드의 라이선스 표시는 CC BY-NC-SA 4.0이다. 가공 전후를 들어 보고 보컬 디테일이 훼손되지 않았는지 판단한다. [제작자 모델 카드](https://huggingface.co/Sucial/Dereverb-Echo_Mel_Band_Roformer)

## Applio 공식 학습·변환 자료

현재 공식 문서는 **Desktop**과 **Gradio**를 함께 설명한다. 두 인터페이스의 설치 방식·버전·화면 배치가 다르다. 이 프로젝트의 고정 실행은 Python/Gradio 저장소의 CLI를 사용했으므로 Desktop 화면과 메뉴 이름이 같다고 가정하지 않는다. [Applio 공식 시작 안내](https://docs.applio.org/)

| 따라갈 단계 | 공식 자료와 확인할 내용 |
| --- | --- |
| 설치 | [설치 안내](https://docs.applio.org/getting-started/installation/): 선택한 배포본의 Python·의존성 기준을 확인한다. 현재 Gradio 스크립트는 Python 3.12를 대상으로 한다. |
| 자료 선별 | [데이터셋 준비](https://docs.applio.org/guides/how-create-datasets/): 단일 화자·적은 잔향·다양한 음역을 확보하고, 원본 보존과 청취 검토를 진행한다. 평가용 음성 일부는 학습에서 빼 둔다. |
| 학습 | [모델 학습](https://docs.applio.org/getting-started/training/): 전처리 → F0·특징 추출 → 학습 → 인덱스 생성. 샘플레이트·구조와 G/D 사전학습 모델을 맞춘다. epoch 수만으로 품질을 판정하지 않는다. |
| 추론·키 조절 | [오디오 변환](https://docs.applio.org/getting-started/inference/): 학습 때와 같은 embedder, 대응하는 `.pth`·`.index`를 사용한다. Pitch는 반음 단위이며 `-1`은 반음, `-12`는 한 옥타브다. |
| 자동화 | [CLI 참조](https://docs.applio.org/reference/cli/): 최신 참조와 고정 commit의 옵션이 다를 수 있으므로 실제 실행할 `core.py --help` 및 하위 명령 도움말을 우선한다. |

작업 폴더 안에 설치를 모으려면 설치 스크립트의 경로도 확인한다. 기록된 Applio commit의 Windows `run-install.bat`는 기본 Miniconda 경로를 `%UserProfile%\Miniconda3`로 지정한다. 이 프로젝트의 폴더 경계를 유지하는 절차에서는 해당 BAT를 그대로 실행하지 않고 별도 venv를 사용한다. [고정 소스의 설치 스크립트](https://github.com/IAHispano/Applio/blob/e95ec175db434011854efc3b1bd66088b4d1e379/run-install.bat)

## FFmpeg 배포처

FFmpeg 프로젝트는 소스 코드를 배포하고, 공식 다운로드 페이지에서 Windows 실행 파일 배포처인 gyan.dev와 BtbN을 안내한다. 선택한 배포본의 버전·라이선스를 확인한 뒤 압축을 작업 폴더 안에 푼다. [FFmpeg 공식 다운로드](https://ffmpeg.org/download.html)

오디오·음성모델은 각자 이용 권한이 있는 자료로 준비한다. 이 저장소의 공개 가이드가 원본 음원이나 제삼자 음성모델의 이용 권한을 부여하지는 않는다. [Applio 공식 이용 조건](https://docs.applio.org/tos/)
