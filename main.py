import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="글로벌 주요 주식 대시보드", layout="wide")

# ── 종목 리스트 ──────────────────────────────
TICKERS = {
    "S&P 500": "^GSPC",
    "Nasdaq": "^IXIC",
    "Dow Jones": "^DJI",
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "Nikkei 225": "^N225",
    "Hang Seng": "^HSI",
    "Shanghai Composite": "000001.SS",
    "FTSE 100": "^FTSE",
    "DAX": "^GDAXI",
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "NVIDIA": "NVDA",
    "Tesla": "TSLA",
    "Samsung Electronics": "005930.KS",
}

st.title("🌍 글로벌 주요 주식 대시보드")
st.caption("Data source: Yahoo Finance (yfinance)")

# ── 사이드바 설정 ──────────────────────────────
st.sidebar.header("설정")

selected_names = st.sidebar.multiselect(
    "종목 선택",
    options=list(TICKERS.keys()),
    default=["S&P 500", "Nasdaq", "KOSPI", "Nikkei 225"]
)

period = st.sidebar.selectbox(
    "기간",
    options=["1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd", "max"],
    index=2
)

interval = st.sidebar.selectbox(
    "간격",
    options=["1d", "1wk", "1mo"],
    index=0
)

chart_type = st.sidebar.radio("차트 종류", ["캔들스틱", "라인"])

show_volume = st.sidebar.checkbox("거래량 표시", value=True)
normalize = st.sidebar.checkbox("수익률 비교 (정규화, 라인차트 전용)", value=False)

if st.sidebar.button("🔄 캐시 초기화 후 새로고침"):
    st.cache_data.clear()
    st.rerun()

if not selected_names:
    st.warning("사이드바에서 종목을 하나 이상 선택해줘.")
    st.stop()

selected_tickers = {name: TICKERS[name] for name in selected_names}

# ── 데이터 로드 (에러 메시지 포함) ──────────────────────────────
@st.cache_data(ttl=300)
def load_data(ticker, period, interval):
    try:
        tk = yf.Ticker(ticker)
        df = tk.history(period=period, interval=interval)
        if df.empty:
            return pd.DataFrame(), "빈 데이터 반환됨 (야후 서버 응답 없음 / IP 제한 가능성)"
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"예외 발생: {e}"

# ── 요약 카드 ──────────────────────────────
st.subheader("📊 현재 시세 요약")
cols = st.columns(len(selected_tickers))

summary_data = {}
error_log = {}

for col, (name, ticker) in zip(cols, selected_tickers.items()):
    df, err = load_data(ticker, period, interval)
    summary_data[name] = df
    error_log[name] = err

    if df.empty or len(df) < 2:
        col.metric(name, "N/A")
        continue

    last_price = df["Close"].iloc[-1]
    prev_price = df["Close"].iloc[-2]
    change = last_price - prev_price
    pct_change = (change / prev_price) * 100
    col.metric(
        label=name,
        value=f"{last_price:,.2f}",
        delta=f"{change:,.2f} ({pct_change:+.2f}%)"
    )

# ── 에러 요약 표시 ──────────────────────────────
failed = {name: err for name, err in error_log.items() if err}
if failed:
    with st.expander(f"⚠️ 데이터 로드 실패 종목 ({len(failed)}개) — 클릭해서 원인 확인", expanded=True):
        for name, err in failed.items():
            st.error(f"**{name}**: {err}")
        st.info(
            "야후 파이낸스가 Streamlit Cloud의 서버 IP를 일시적으로 제한하는 경우가 흔해. "
            "잠시 후 '캐시 초기화 후 새로고침' 버튼을 눌러보거나, 몇 분 뒤 다시 시도해봐."
        )

st.divider()

# ── 정규화 비교 라인 차트 (옵션) ──────────────────────────────
valid_data = {name: df for name, df in summary_data.items() if not df.empty}

if normalize and valid_data:
    st.subheader("📈 수익률 비교 (시작일 = 100 기준)")
    fig_norm = go.Figure()
    for name, df in valid_data.items():
        norm_series = df["Close"] / df["Close"].iloc[0] * 100
        fig_norm.add_trace(go.Scatter(
            x=df.index, y=norm_series, mode="lines", name=name
        ))
    fig_norm.update_layout(
        height=500,
        hovermode="x unified",
        yaxis_title="정규화 지수 (시작=100)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )
    st.plotly_chart(fig_norm, use_container_width=True)
    st.divider()

# ── 개별 종목 차트 ──────────────────────────────
st.subheader("📉 개별 종목 차트")

for name, ticker in selected_tickers.items():
    df = summary_data[name]
    if df.empty:
        st.warning(f"{name} ({ticker}) 데이터를 불러올 수 없어. 원인: {error_log.get(name)}")
        continue

    with st.expander(f"{name}  ({ticker})", expanded=True):
        if show_volume and "Volume" in df.columns:
            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                row_heights=[0.75, 0.25], vertical_spacing=0.03
            )
        else:
            fig = make_subplots(rows=1, cols=1)

        if chart_type == "캔들스틱":
            fig.add_trace(
                go.Candlestick(
                    x=df.index,
                    open=df["Open"], high=df["High"],
                    low=df["Low"], close=df["Close"],
                    name=name
                ),
                row=1, col=1
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=df.index, y=df["Close"],
                    mode="lines", name=name
                ),
                row=1, col=1
            )

        if show_volume and "Volume" in df.columns:
            colors = [
                "red" if row["Close"] < row["Open"] else "blue"
                for _, row in df.iterrows()
            ]
            fig.add_trace(
                go.Bar(x=df.index, y=df["Volume"], name="거래량", marker_color=colors),
                row=2, col=1
            )

        fig.update_layout(
            height=500,
            xaxis_rangeslider_visible=False,
            showlegend=False,
            margin=dict(t=20, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)

# ── 원본 데이터 확인 ──────────────────────────────
if valid_data:
    with st.expander("🔍 원본 데이터 보기"):
        for name, df in valid_data.items():
            st.write(f"**{name}**")
            st.dataframe(df.tail(20))

st.sidebar.divider()
st.sidebar.caption(f"마지막 갱신: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
