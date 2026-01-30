import pandas as pd
import plotly.graph_objects as go
import fsspec
import re
import json
import http.server
import socketserver
import threading
from package.nas_smb.nas_smb import NasSMB
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# NAS 연결
nas = NasSMB()

# 1. 폴더에서 *_YYYYMMDD.csv 파일들 자동 찾기
FOLDER_PATH = "../path/to/data/"  # 데이터가 있는 폴더 경로
PORT = 8050
csv_files = nas.list_files(FOLDER_PATH)

# *_YYYYMMDD.csv 패턴 추출
date_pattern = re.compile(r'.*?(\d{8})\.csv$')  # YYYYMMDD 추출
dated_files = []
for f in csv_files:
    match = date_pattern.search(f)
    if match:
        date_str = match.group(1)
        try:
            date_obj = datetime.strptime(date_str, '%Y%m%d')
            dated_files.append((f, date_str, date_obj))
        except ValueError:
            continue

# 날짜순 정렬
dated_files.sort(key=lambda x: x[2])
print(f"    발견된 날짜 파일: {len(dated_files)}개")
for f, date_str, _ in dated_files[:5]:
    print(f"  {f} ({date_str})")

# 2. 모든 파일 로드 (메모리 최적화)
print("    데이터 로딩 중...")
dfs = {}
for file_path, date_str, date_obj in dated_files:
    try:
        df = nas.load_csv(file_path, nrows=50000)  # 각 파일 5만행 제한
        dfs[date_str] = df
        print(f"        {date_str}: {len(df):,}행")
    except Exception as e:
        print(f"        {date_str}: {e}")

if not dfs:
    print("❌ No files loaded.")
    exit()

# 3. 통합 데이터셋 준비
sample_df = next(iter(dfs.values()))  # 첫 번째 파일로 컬럼 구조 파악
numeric_cols = sample_df.select_dtypes(include=["number"]).columns.tolist()
if "Power" in numeric_cols:
    numeric_cols.remove("Power")
    numeric_cols.insert(0, "Power")

print(f"    Number Columns: {len(numeric_cols)}개")

# 4. 날짜별 데이터셋 준비 (Timestamp 처리) 및 통합
processed_dfs = {}
for date_str, df in dfs.items():
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        df = df.dropna(subset=["Timestamp"]).sort_values("Timestamp")
    else:
        # Timestamp 없으면 날짜 기반으로 생성
        base_date = datetime.strptime(date_str, '%Y%m%d')
        df["Timestamp"] = pd.date_range(start=base_date, periods=len(df), freq='1s')
        df = df.sort_values("Timestamp")
    processed_dfs[date_str] = df

# 모든 날짜 데이터를 하나로 합침
all_data = pd.concat(processed_dfs.values(), ignore_index=True)
all_data = all_data.sort_values("Timestamp")
print(f"    통합 데이터: {len(all_data):,}행")

# 날짜 리스트 (YYYYMMDD 형식, 정렬됨)
date_list = sorted(processed_dfs.keys())
num_dates = len(date_list)
num_cols = len(numeric_cols)

# 날짜를 ISO 형식으로 변환 (JavaScript용)
date_iso_list = [datetime.strptime(d, '%Y%m%d').strftime('%Y-%m-%d') for d in date_list]
# 마지막 날짜 다음날 추가 (끝 범위용)
last_date = datetime.strptime(date_list[-1], '%Y%m%d')
next_day = (last_date + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
end_date_iso_list = date_iso_list + [next_day]

# 5. 플롯 생성 (컬럼별 하나의 trace)
fig = go.Figure()

for col in numeric_cols:
    fig.add_trace(
        go.Scatter(
            x=all_data["Timestamp"],
            y=all_data[col],
            mode="lines",
            name=col,
            visible=False,
            line=dict(width=1),
            hovertemplate=f'<b>{col}</b><br>' +
                         'Time: %{x}<br>Value: %{y:.2f}<extra></extra>'
        )
    )

# 첫 번째 컬럼만 표시
if fig.data:
    fig.data[0].visible = True

# 6. 드롭다운 버튼들 생성
# 시작 날짜 버튼
start_date_buttons = []
for i, date_str in enumerate(date_list):
    start_date_buttons.append(dict(
        label=date_str,
        method="relayout",
        args=[{}]
    ))

# 끝 날짜 버튼 (다음날 자정까지 포함)
end_date_buttons = []
for i, date_str in enumerate(date_list):
    end_date_buttons.append(dict(
        label=date_str,
        method="relayout",
        args=[{}]
    ))

# 컬럼 버튼
col_buttons = []
for i, col in enumerate(numeric_cols):
    col_buttons.append(dict(
        label=col,
        method="relayout",
        args=[{}]
    ))

# 7. 세 개 드롭다운 배치
fig.update_layout(
    title="NAS Data Viewer - Date Range & Column Selector",
    updatemenus=[
        # 시작 날짜
        dict(
            buttons=start_date_buttons,
            direction="down",
            showactive=True,
            x=0.01,
            y=1.15,
            xanchor="left",
            yanchor="top"
        ),
        # 끝 날짜
        dict(
            buttons=end_date_buttons,
            direction="down",
            showactive=True,
            x=0.20,
            y=1.15,
            xanchor="left",
            yanchor="top"
        ),
        # 컬럼 선택
        dict(
            buttons=col_buttons,
            direction="down",
            showactive=True,
            x=0.40,
            y=1.15,
            xanchor="left",
            yanchor="top"
        )
    ],
    # 라벨 추가
    annotations=[
        dict(text="시작:", x=0.01, y=1.20, xref="paper", yref="paper", showarrow=False, font=dict(size=12)),
        dict(text="끝:", x=0.20, y=1.20, xref="paper", yref="paper", showarrow=False, font=dict(size=12)),
        dict(text="컬럼:", x=0.40, y=1.20, xref="paper", yref="paper", showarrow=False, font=dict(size=12)),
    ],
    xaxis_title="Timestamp",
    yaxis_title="Value",
    template="plotly_white",
    height=700,
    showlegend=True,
    margin=dict(t=120)
)

# 8. 저장 및 표시 (JavaScript 후처리로 드롭다운 연동)
html_file = "nas_date_plot.html"
fig.write_html(html_file, include_plotlyjs=True, full_html=True)

# 세 드롭다운을 연동하는 JavaScript 추가
custom_js = f"""
<script>
(function() {{
    var gd = document.querySelector('.plotly-graph-div');
    var numCols = {num_cols};
    var dateList = {json.dumps(date_list)};
    var dateIsoList = {json.dumps(date_iso_list)};
    var endDateIsoList = {json.dumps(end_date_iso_list)};
    var colList = {json.dumps(numeric_cols)};

    var startDateIdx = 0;
    var endDateIdx = 0;
    var currentColIdx = 0;
    var prevColIdx = 0;

    function updatePlot() {{
        // 시작 날짜 자정
        var startDate = dateIsoList[startDateIdx] + ' 00:00:00';
        // 끝 날짜 다음날 자정 (해당 날짜 포함)
        var endDate = endDateIsoList[endDateIdx + 1] + ' 00:00:00';

        // 컬럼 변경
        if (currentColIdx !== prevColIdx) {{
            Plotly.restyle(gd, {{'visible': false}}, [prevColIdx]);
            Plotly.restyle(gd, {{'visible': true}}, [currentColIdx]);
            prevColIdx = currentColIdx;
        }}

        // x축 범위 설정 + 타이틀 업데이트
        Plotly.relayout(gd, {{
            'xaxis.range': [startDate, endDate],
            'title': 'Data Viewer - ' + dateList[startDateIdx] + ' ~ ' + dateList[endDateIdx] + ' / ' + colList[currentColIdx]
        }});
    }}

    gd.on('plotly_buttonclicked', function(data) {{
        var menuIdx = data.menu._index;
        var buttonIdx = data.active;

        if (menuIdx === 0) {{
            startDateIdx = buttonIdx;
            // 끝 날짜가 시작보다 작으면 조정
            if (endDateIdx < startDateIdx) {{
                endDateIdx = startDateIdx;
            }}
        }} else if (menuIdx === 1) {{
            endDateIdx = buttonIdx;
            // 시작 날짜가 끝보다 크면 조정
            if (startDateIdx > endDateIdx) {{
                startDateIdx = endDateIdx;
            }}
        }} else if (menuIdx === 2) {{
            currentColIdx = buttonIdx;
        }}
        updatePlot();
    }});

    // 초기 x축 범위 설정
    updatePlot();
}})();
</script>
"""

# HTML 파일에 JavaScript 삽입
with open(html_file, 'r', encoding='utf-8') as f:
    html_content = f.read()

html_content = html_content.replace('</body>', custom_js + '</body>')

with open(html_file, 'w', encoding='utf-8') as f:
    f.write(html_content)

print("    Saved nas_date_plot.html")
print(f"        Totally {len(dfs)} files loaded, {len(processed_dfs)} dates processed.")

# HTTP 서버 실행
os.chdir(os.path.dirname(os.path.abspath(html_file)) or '.')

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 로그 숨김

print(f"\n    Server running at http://localhost:{PORT}/{html_file}")
print("    Ctrl+C to stop")

with socketserver.TCPServer(("", PORT), QuietHandler) as httpd:
    httpd.serve_forever()
