# 표준 라이브러리
import datetime
from io import BytesIO

# 서드파티 라이브러리
import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go

# --- 함수 정의 ---
@st.cache_data # 데이터 로딩 속도 향상을 위한 캐시 처리
def get_krx_company_list() -> pd.DataFrame:
    try:
        url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13'
        df_listing = pd.read_html(url, header=0, flavor='bs4', encoding='EUC-KR')[0]
        
        df_listing = df_listing[['회사명', '종목코드']].copy()
        df_listing['종목코드'] = df_listing['종목코드'].apply(lambda x: f'{x:06}')
        return df_listing
    except Exception as e:
        st.error(f"상장사 명단을 불러오는 데 실패했습니다: {e}")
        return pd.DataFrame(columns=['회사명', '종목코드'])

def get_stock_code_by_company(company_name: str) -> str:
    if company_name.isdigit() and len(company_name) == 6:
        return company_name
    
    company_df = get_krx_company_list()
    codes = company_df[company_df['회사명'] == company_name]['종목코드'].values
    if len(codes) > 0:
        return codes[0]
    else:
        raise ValueError(f"'{company_name}'을 찾을 수 없습니다. 종목코드 6자리를 직접 입력해보세요.")

# --- 사이드바 구성 ---
with st.sidebar:
    st.title("📈 주식 분석 프로")
    
    today = datetime.datetime.now()
    start_default = datetime.date(2020, 1, 1)

    # 년/월 선택을 쉽게 하려면 min/max_value를 지정하는 것이 좋습니다.
    selected_dates = st.date_input(
        '조회 기간 선택',
        (start_default, today),
        min_value=datetime.date(1990, 1, 1),
        max_value=today,
        format="MM.DD.YYYY"
    )

    company_name = st.text_input('회사명 입력', placeholder="예: 삼성전자")
    confirm_btn = st.button('데이터 조회하기', use_container_width=True)

# --- 메인 로직 ---
if confirm_btn:
    if not company_name:
        st.warning("조회할 회사 이름을 입력하세요.")
    elif len(selected_dates) < 2:
        st.error("시작일과 종료일을 모두 선택해 주세요.")
    else:
        try:
            with st.spinner('실시간 데이터를 분석 중입니다...'):
                stock_code = get_stock_code_by_company(company_name)
                start_date = selected_dates[0].strftime("%Y%m%d")
                end_date = selected_dates[1].strftime("%Y%m%d")
                
                # 데이터 수집
                price_df = fdr.DataReader(stock_code, start_date, end_date)
                
                if price_df.empty:
                    st.info("해당 기간의 주가 데이터가 없습니다.")
                else:
                    # 🕒 조회 시점 출력
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    st.caption(f"📅 데이터 조회 시점: {now}")

                    # 1. 기술적 지표 계산
                    price_df['MA20'] = price_df['Close'].rolling(window=20).mean()
                    price_df['MA60'] = price_df['Close'].rolling(window=60).mean()
                    price_df['MA120'] = price_df['Close'].rolling(window=120).mean()

                    # 2. 상단 요약 지표 (Metrics)
                    st.subheader(f"🔍 {company_name} ({stock_code}) 요약")
                    
                    curr_price = int(price_df['Close'].iloc[-1])
                    prev_price = int(price_df['Close'].iloc[-2])
                    change = curr_price - prev_price
                    change_rate = (change / prev_price) * 100
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("현재가", f"{curr_price:,} KRW", f"{change:,} ({change_rate:.2f}%)")
                    m2.metric("거래량", f"{int(price_df['Volume'].iloc[-1]):,}")
                    m3.metric("최근 20일 평균", f"{int(price_df['MA20'].iloc[-1]):,} KRW")

                    # 3. Plotly 통합 차트 생성
                    fig = go.Figure()

                    # 3-1. 캔들 차트 추가
                    fig.add_trace(go.Candlestick(
                        x=price_df.index,
                        open=price_df['Open'],
                        high=price_df['High'],
                        low=price_df['Low'],
                        close=price_df['Close'],
                        name='주가'
                    ))

                    # 3-2. 이동평균선 추가
                    fig.add_trace(go.Scatter(x=price_df.index, y=price_df['MA20'], name='20일선', line=dict(color='orange', width=1)))
                    fig.add_trace(go.Scatter(x=price_df.index, y=price_df['MA60'], name='60일선', line=dict(color='blue', width=1)))

                    # 3-3. 거래량 (보조 Y축 사용)
                    fig.add_trace(go.Bar(
                        x=price_df.index, y=price_df['Volume'], 
                        name='거래량', marker_color='lightgray', 
                        opacity=0.4, yaxis='y2'
                    ))

                    # 3-4. 레이아웃 설정 (트레이딩뷰 스타일 조작감 반영)
                    fig.update_layout(
                        title=f"<b>{company_name}</b> 캔들 분석 차트",
                        template="plotly_white",
                        xaxis_rangeslider_visible=False,
                        hovermode="x unified",
                        dragmode='pan',
                        xaxis=dict(
                            fixedrange=False,
                            title="날짜"
                        ),
                        yaxis=dict(
                            title="가격 (KRW)",
                            side="left",
                            fixedrange=False,
                            autorange=True
                        ),
                        yaxis2=dict(
                            title="거래량",
                            overlaying='y',
                            side='right',
                            showgrid=False,
                            fixedrange=False
                        ),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )

                    # 3-5. 차트 출력 (휠 줌 설정 포함)
                    st.plotly_chart(
                        fig, 
                        use_container_width=True, 
                        config={
                            'scrollZoom': True,
                            'displayModeBar': True,
                            'displaylogo': False,
                            'modeBarButtonsToRemove': ['select2d', 'lasso2d']
                        }
                    )

                    # 4. 데이터프레임 및 다운로드
                    with st.expander("데이터 상세 보기"):
                        st.dataframe(price_df.sort_index(ascending=False), use_container_width=True)
                        
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            price_df.to_excel(writer, index=True, sheet_name='Stock_Data')
                        
                        st.download_button(
                            label="📥 분석 데이터 엑셀 다운로드",
                            data=output.getvalue(),
                            file_name=f"{company_name}_analysis.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")