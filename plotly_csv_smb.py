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
FOLDER_PATH = "../경북대 외 데이터/데이터/서울대/DBG_EREPORT_20250701/"  # 데이터가 있는 폴더 경로
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

# 4. 날짜별 데이터셋 준비 (Timestamp 처리)
processed_dfs = {}
for date_str, df in dfs.items():
    if "Timestamp" in df.columns:
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        df = df.dropna(subset=["Timestamp"]).sort_values("Timestamp")
    else:
        df["Timestamp"] = pd.date_range(start='2025-01-01', periods=len(df), freq='1s')
        df = df.sort_values("Timestamp")
    processed_dfs[date_str] = df

# 5. 플롯 생성 (두 개 드롭다운: 날짜 + 컬럼)
fig = go.Figure()

# 모든 날짜별, 모든 컬럼별 trace 생성 (숨김)
for date_str in processed_dfs.keys():
    df = processed_dfs[date_str]
    for col in numeric_cols:
        fig.add_trace(
            go.Scatter(
                x=df["Timestamp"],
                y=df[col],
                mode="lines",
                name=f"{date_str} - {col}",
                visible=False,
                line=dict(width=1),
                hovertemplate=f'<b>{date_str} - {col}</b><br>' +
                             'Time: %{x}<br>Value: %{y:.2f}<extra></extra>'
            )
        )

# 첫 번째 날짜, 첫 번째 컬럼만 표시
if fig.data:
    fig.data[0].visible = True

# 6. 드롭다운 버튼들 생성 (연동 방식)
date_list = list(processed_dfs.keys())
num_dates = len(date_list)
num_cols = len(numeric_cols)

# 날짜 버튼 (JavaScript에서 처리)
date_buttons = []
for i, date_str in enumerate(date_list):
    date_buttons.append(dict(
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

# 7. 두 개 드롭다운 배치 + 숨겨진 annotations (상태 저장용)
fig.update_layout(
    title="NAS Data Viewer - Date & Column Selector",
    updatemenus=[
        # 왼쪽: 날짜 선택
        dict(
            buttons=date_buttons,
            direction="down",
            showactive=True,
            x=0.01,
            y=1.12,
            xanchor="left",
            yanchor="top"
        ),
        # 오른쪽: 컬럼 선택
        dict(
            buttons=col_buttons,
            direction="down",
            showactive=True,
            x=0.45,
            y=1.12,
            xanchor="left",
            yanchor="top"
        )
    ],
    xaxis_title="Timestamp",
    yaxis_title="Value",
    template="plotly_white",
    height=700,
    showlegend=True
)

# 8. 저장 및 표시 (JavaScript 후처리로 드롭다운 연동)
html_file = "nas_date_plot.html"
fig.write_html(html_file, include_plotlyjs=True, full_html=True)

# 두 드롭다운을 연동하는 JavaScript 추가 (buttonclicked 이벤트 사용)
custom_js = f"""
<script>
(function() {{
    var gd = document.querySelector('.plotly-graph-div');
    var numCols = {num_cols};
    var numDates = {num_dates};
    var dateList = {json.dumps(date_list)};
    var colList = {json.dumps(numeric_cols)};

    var currentDateIdx = 0;
    var currentColIdx = 0;
    var prevTraceIdx = 0;

    function updatePlot() {{
        var newTraceIdx = currentDateIdx * numCols + currentColIdx;

        Plotly.restyle(gd, {{'visible': false}}, [prevTraceIdx]);
        Plotly.restyle(gd, {{'visible': true}}, [newTraceIdx]);
        Plotly.relayout(gd, {{'title': 'Data Viewer - ' + dateList[currentDateIdx] + ' / ' + colList[currentColIdx]}});

        prevTraceIdx = newTraceIdx;
    }}

    gd.on('plotly_buttonclicked', function(data) {{
        var menuIdx = data.menu._index;
        var buttonIdx = data.active;

        if (menuIdx === 0) {{
            currentDateIdx = buttonIdx;
        }} else if (menuIdx === 1) {{
            currentColIdx = buttonIdx;
        }}
        updatePlot();
    }});
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

# HTTP 서버 실행 (고정 포트 8050)
PORT = 8050
os.chdir(os.path.dirname(os.path.abspath(html_file)) or '.')

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 로그 숨김

print(f"\n    Server running at http://localhost:{PORT}/{html_file}")
print("    (VSCode에서 포트 {PORT} 포워딩 후 브라우저에서 접속)")
print("    Ctrl+C to stop")

with socketserver.TCPServer(("", PORT), QuietHandler) as httpd:
    httpd.serve_forever()
