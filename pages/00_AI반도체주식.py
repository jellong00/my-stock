import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="AI 반도체 주식 분석", layout="wide")

# ── AI 반도체 관련 종목 리스트 ──────────────────────────────
AI_CHIP_TICKERS = {
    "NVIDIA": "NVDA",
    "AMD": "AMD",
    "Broadcom": "AVGO",
    "TSMC": "TSM",
    "Intel": "INTC",
    "Micron": "MU",
    "Marvell": "MRVL",
    "Qualcomm": "QCOM",
    "ASML": "ASML",
    "SK Hynix": "000660.KS",
    "Samsung Electronics": "005930.KS",
    "Arm Holdings": "ARM",
}

BENCHMARK = {"필라델피아 반도체지수 (SOXX)": "SOXX", "S&P 500": "^GSPC"}

st.title("🤖 AI 반도체 주식 전문 분석")
st.caption("Data source: Yahoo Finance (yfinance) · 실시간 투자 조언 아님, 참고용 데이터입니다")

# ── 사이드바 설정 ──────────────────────────────
st.sidebar.header("설정")

selected_names = st.sidebar.multiselect(
    "분석 종목 선택",
    options=list(AI_CHIP_TICKERS.keys()),
    default=["NVIDIA", "AMD", "TSMC", "Broadcom", "SK Hynix", "Samsung Electronics"]
)

benchmark_name = st.sidebar.selectbox("벤치마크 지수", options=list(BENCHMARK.keys()))

period = st.sidebar.selectbox(
    "분석 기간",
    options=["3mo", "6mo", "1y", "2y", "5y"],
    index=2
)

if st.sidebar.button("🔄 캐시 초기화 후 새로고침"):
    st.cache_data.clear()
    st.rerun()

if not selected_names:
    st.warning("사이드바에서 종목을 하나 이상 선택해줘.")
    st.stop()

selected_tickers = {name: AI_CHIP_TICKERS[name] for name in selected_names}
benchmark_ticker = BENCHMARK[benchmark_name]


# ── 데이터 로드 함수 ──────────────────────────────
@st.cache_data(ttl=300)
def load_price(ticker, period):
    try:
        df = yf.Ticker(ticker).history(period=period)
        if df.empty:
            return pd.DataFrame(), "빈 데이터 반환됨"
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"예외: {e}"


@st.cache_data(ttl=1800)
def load_fundamentals(ticker):
    try:
        info = yf.Ticker(ticker).info
        return {
            "시가총액": info.get("marketCap"),
            "PER (trailing)": info.get("trailingPE"),
            "PER (forward)": info.get("forwardPE"),
            "PBR": info.get("priceToBook"),
            "매출성장률": info.get("revenueGrowth"),
            "영업이익률": info.get("operatingMargins"),
            "52주 최고": info.get("fiftyTwoWeekHigh"),
            "52주 최저": info.get("fiftyTwoWeekLow"),
            "배당수익률": info.get("dividendYield"),
            "목표주가(평균)": info.get("targetMeanPrice"),
            "애널리스트 추천": info.get("recommendationKey"),
        }, None
    except Exception as e:
        return {}, f"예외: {e}"


def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ── 데이터 로딩 ──────────────────────────────
price_data = {}
error_log = {}
for name, ticker in selected_tickers.items():
    df, err = load_price(ticker, period)
    price_data[name] = df
    error_log[name] = err

bench_df, bench_err = load_price(benchmark_ticker, period)

failed = {name: err for name, err in error_log.items() if err}
if failed:
    with st.expander(f"⚠️ 로드 실패 종목 ({len(failed)}개)", expanded=True):
        for name, err in failed.items():
            st.error(f"**{name}**: {err}")

valid_data = {name: df for name, df in price_data.items() if not df.empty}

if not valid_data:
    st.error("불러온 데이터가 없어. 새로고침하거나 잠시 후 다시 시도해봐.")
    st.stop()

# ══════════════════════════════════════════════════
# 1. 현재 시세 + 등락률 요약
# ══════════════════════════════════════════════════
st.subheader("📊 현재 시세 요약")
cols = st.columns(len(valid_data))
for col, (name, df) in zip(cols, valid_data.items()):
    if len(df) < 2:
        col.metric(name, "N/A")
        continue
    last = df["Close"].iloc[-1]
    prev = df["Close"].iloc[-2]
    change = last - prev
    pct = (change / prev) * 100
    col.metric(name, f"${last:,.2f}", delta=f"{pct:+.2f}%")

st.divider()

# ══════════════════════════════════════════════════
# 2. 상대 수익률 비교 (벤치마크 포함)
# ══════════════════════════════════════════════════
st.subheader("📈 상대 수익률 비교 (시작일 = 100 기준)")

fig_perf = go.Figure()
for name, df in valid_data.items():
    norm = df["Close"] / df["Close"].iloc[0] * 100
    fig_perf.add_trace(go.Scatter(x=df.index, y=norm, mode="lines", name=name))

if not bench_df.empty:
    norm_bench = bench_df["Close"] / bench_df["Close"].iloc[0] * 100
    fig_perf.add_trace(go.Scatter(
        x=bench_df.index, y=norm_bench, mode="lines", name=benchmark_name,
        line=dict(dash="dash", color="gray", width=3)
    ))

fig_perf.update_layout(
    height=500, hovermode="x unified",
    yaxis_title="정규화 지수 (시작=100)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02)
)
st.plotly_chart(fig_perf, use_container_width=True)

st.divider()

# ══════════════════════════════════════════════════
# 3. 밸류에이션 비교 테이블
# ══════════════════════════════════════════════════
st.subheader("💰 밸류에이션 및 펀더멘털 비교")

fund_rows = {}
fund_errors = {}
with st.spinner("펀더멘털 데이터 불러오는 중..."):
    for name, ticker in selected_tickers.items():
        data, err = load_fundamentals(ticker)
        fund_rows[name] = data
        fund_errors[name] = err

fund_df = pd.DataFrame(fund_rows).T

if not fund_df.empty:
    display_df = fund_df.copy()
    if "시가총액" in display_df:
        display_df["시가총액"] = display_df["시가총액"].apply(
            lambda x: f"${x/1e9:,.1f}B" if pd.notna(x) else "N/A"
        )
    for col in ["PER (trailing)", "PER (forward)", "PBR"]:
        if col in display_df:
            display_df[col] = display_df[col].apply(
                lambda x: f"{x:.1f}" if pd.notna(x) else "N/A"
            )
    for col in ["매출성장률", "영업이익률", "배당수익률"]:
        if col in display_df:
            display_df[col] = display_df[col].apply(
                lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A"
            )
    for col in ["52주 최고", "52주 최저", "목표주가(평균)"]:
        if col in display_df:
            display_df[col] = display_df[col].apply(
                lambda x: f"${x:,.2f}" if pd.notna(x) else "N/A"
            )

    st.dataframe(display_df, use_container_width=True)
    st.caption("PER = 주가수익비율, PBR = 주가순자산비율. 데이터는 야후 파이낸스 제공 기준이며 실시간과 오차가 있을 수 있음.")

st.divider()

# ══════════════════════════════════════════════════
# 4. 개별 종목 상세 차트 (이동평균 + RSI)
# ══════════════════════════════════════════════════
st.subheader("📉 개별 종목 기술적 분석")

for name, df in valid_data.items():
    with st.expander(f"{name} ({selected_tickers[name]})", expanded=False):
        df = df.copy()
        df["MA20"] = df["Close"].rolling(20).mean()
        df["MA60"] = df["Close"].rolling(60).mean()
        df["RSI"] = calc_rsi(df["Close"])

        fig = make_subplots(
            rows=3, cols=1, shared_xaxes=True,
            row_heights=[0.55, 0.2, 0.25], vertical_spacing=0.03,
            subplot_titles=("가격 + 이동평균", "거래량", "RSI (14일)")
        )

        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="가격"
        ), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MA20"], name="MA20", line=dict(width=1.2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MA60"], name="MA60", line=dict(width=1.2)), row=1, col=1)

        colors = ["red" if row["Close"] < row["Open"] else "blue" for _, row in df.iterrows()]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="거래량", marker_color=colors), row=2, col=1)

        fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(color="purple")), row=3, col=1)
        fig.add_hline(y=70, line_dash="dot", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dot", line_color="green", row=3, col=1)

        fig.update_layout(height=700, xaxis_rangeslider_visible=False, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

        latest_rsi = df["RSI"].iloc[-1]
        if pd.notna(latest_rsi):
            if latest_rsi >= 70:
                st.warning(f"현재 RSI {latest_rsi:.1f} → 과매수 구간")
            elif latest_rsi <= 30:
                st.info(f"현재 RSI {latest_rsi:.1f} → 과매도 구간")
            else:
                st.write(f"현재 RSI {latest_rsi:.1f} → 중립 구간")

st.divider()

# ══════════════════════════════════════════════════
# 5. 종목 간 상관관계 히트맵
# ══════════════════════════════════════════════════
st.subheader("🔗 종목 간 상관관계 (일간 수익률 기준)")

returns_df = pd.DataFrame({
    name: df["Close"].pct_change() for name, df in valid_data.items()
}).dropna()

if len(returns_df.columns) >= 2:
    corr = returns_df.corr()
    fig_corr = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=corr.columns,
        y=corr.columns,
        colorscale="RdBu_r",
        zmid=0,
        text=corr.round(2).values,
        texttemplate="%{text}",
        colorbar=dict(title="상관계수")
    ))
    fig_corr.update_layout(height=500)
    st.plotly_chart(fig_corr, use_container_width=True)
    st.caption("1에 가까울수록 같은 방향으로 움직임, -1에 가까울수록 반대로 움직임")
else:
    st.info("상관관계 분석은 2개 이상 종목 선택 시 표시돼.")

st.sidebar.divider()
st.sidebar.caption(f"마지막 갱신: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
