# 표준 라이브러리
import datetime
from io import BytesIO

# 서드파티 라이브러리
import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go

# --- 함수 정의 ---
@st.cache_data
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
                
                price_df = fdr.DataReader(stock_code, start_date, end_date)
                
                if price_df.empty:
                    st.info("해당 기간의 주가 데이터가 없습니다.")
                else:
                    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    st.caption(f"📅 데이터 조회 시점: {now}")

                    # 지표 계산
                    price_df['MA20'] = price_df['Close'].rolling(window=20).mean()
                    price_df['MA60'] = price_df['Close'].rolling(window=60).mean()
                    price_df['MA120'] = price_df['Close'].rolling(window=120).mean()

                    # 요약 지표
                    st.subheader(f"🔍 {company_name} ({stock_code}) 요약")
                    
                    curr_price = int(price_df['Close'].iloc[-1])
                    prev_price = int(price_df['Close'].iloc[-2])
                    change = curr_price - prev_price
                    change_rate = (change / prev_price) * 100
                    
                    m1, m2, m3 = st.columns(3)
                    m1.metric("현재가", f"{curr_price:,} KRW", f"{change:,} ({change_rate:.2f}%)")
                    m2.metric("거래량", f"{int(price_df['Volume'].iloc[-1]):,}")
                    m3.metric("최근 20일 평균", f"{int(price_df['MA20'].iloc[-1]):,} KRW")

                    st.write("---")
                    # 기존 st.info 부분을 제거하고 아래 코드를 넣으세요.
                    # st.markdown(
                    #     """
                    #     <div style="background-color: #e1f5fe; padding: 15px; border-radius: 5px; border-left: 5px solid #01579b; margin-bottom: 20px;">
                    #         <span style="color: #01579b; font-weight: bold;">💡 차트 조작법</span><br>
                    #         <div style="color: #01579b; font-size: 0.9rem; margin-top: 5px; line-height: 1.6;">
                    #             1. <b>X축 이동:</b> 차트 중앙 클릭 드래그<br>
                    #             2. <b>X축 기간 조절:</b> 차트 중앙 마우스 휠<br>
                    #             3. <b>가격/거래량 높이 조절:</b> 양측 숫자(축) 위에서 <b>클릭 드래그</b> 또는 <b>마우스 휠</b>
                    #         </div>
                    #     </div>
                    #     """, 
                    #     unsafe_allow_html=True
                    # )
                    # 3. Plotly 통합 차트 생성
                    fig = go.Figure()

                    # 3-1. 캔들 차트 (Y축 사용)
                    fig.add_trace(go.Candlestick(
                        x=price_df.index,
                        open=price_df['Open'], high=price_df['High'],
                        low=price_df['Low'], close=price_df['Close'],
                        name='주가',
                        yaxis='y'
                    ))

                    # 3-2. 이동평균선
                    fig.add_trace(go.Scatter(x=price_df.index, y=price_df['MA20'], name='20일선', line=dict(color='orange', width=1)))
                    fig.add_trace(go.Scatter(x=price_df.index, y=price_df['MA60'], name='60일선', line=dict(color='blue', width=1)))

                    # 3-3. 거래량 (Y2축 사용)
                    fig.add_trace(go.Bar(
                        x=price_df.index, y=price_df['Volume'], 
                        name='거래량', marker_color='lightgray', 
                        opacity=0.4, yaxis='y2'
                    ))

                    # 3-4. 레이아웃 설정
                    fig.update_layout(
                        dragmode="pan",

                        xaxis=dict(
                            title="날짜",
                            fixedrange=False,
                            rangeslider=dict(visible=False)
                        ),

                        yaxis=dict(
                            title="가격 (KRW)",
                            side="right",
                            fixedrange=True
                        ),

                        yaxis2=dict(
                            title="거래량",
                            side="left",
                            overlaying="y",
                            fixedrange=True,
                            range=[0, price_df["Volume"].max() * 1.1],
                            showgrid=False
                        ),

                        height=600
                    )


                    st.plotly_chart(
                        fig,
                        use_container_width=True,
                        config={
                            "scrollZoom": True,
                            "doubleClick": "reset",
                            "displaylogo": False,
                            "modeBarButtonsToRemove": [
                                "zoom2d",
                                "autoScale2d",
                                "select2d",
                                "lasso2d"
                            ]
                        }
                    )

                    with st.expander("📊 데이터 상세 보기 및 엑셀 다운로드"):
                        st.dataframe(price_df.sort_index(ascending=False), use_container_width=True)
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            price_df.to_excel(writer, index=True, sheet_name='Stock_Data')
                        st.download_button(label="📥 엑셀 파일 다운로드", data=output.getvalue(), file_name=f"{company_name}_주가데이터.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")