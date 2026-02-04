# plotly_csv_smb
nas의 폴더에 있는 *_YYYYMMDD.csv 형식의 데이터를 날짜별/컬럼별로 plot
하고 싶었으나 아직은 날짜 누르면 해당 컬럼 한꺼번에, 컬럼 누르면 해당 컬럼의 모든 날짜 한꺼번에 나온다.

```
git clone https://github.com/song-jisu/plotly_csv_smb.git
cd plotly_csv_smb

mkdir package
cd package
touch __init__.py
git clone https://github.com/song-jisu/nas_smb.git
cd nas_smb
vim .env
```

자신의 정보에 맞게 `.env`를 아래의 형식으로 작성
```text
NAS_USER=""
NAS_PASSWORD=""
NAS_IP=""
NAS_SHARE=""
```

실행:
```
python -m plotly_csv_smb
```
