# plotly_csv_smb
NAS SMB 폴더의 `*_YYYYMMDD.csv` 파일을 읽어 Plotly로 시각화합니다.

## 1) 저장소 + 서브모듈 받기
```bash
git clone https://github.com/song-jisu/plotly_csv_smb.git
cd plotly_csv_smb
git submodule update --init --recursive
```

## 2) venv 생성 및 의존성 설치
```bash
python3 -m venv .venv
source .venv/bin/activate

python -m ensurepip --upgrade
python -m pip install -U pip
python -m pip install -r requirements.txt
```

## 3) 환경변수 설정 (`nas_smb/.env`)
```bash
cp nas_smb/.env.example nas_smb/.env
```

`nas_smb/.env` 예시:
```text
NAS_USER=""
NAS_PASSWORD=""
NAS_IP=""
NAS_SHARE=""
# NAS_PORT="445"
```

## 4) 실행
```bash
source .venv/bin/activate
python -m plotly_csv_smb
```

## 5) 연결/경로 테스트 예제
```bash
source .venv/bin/activate
python example/test_smb_port_connectivity.py
python example/test_smb_list_paths.py
```

## 참고
- SMB 기본 포트는 `445`입니다.
- 병렬 로딩 수는 `CSV_LOAD_WORKERS`로 조절할 수 있습니다.
```bash
CSV_LOAD_WORKERS=8 python -m plotly_csv_smb
```
