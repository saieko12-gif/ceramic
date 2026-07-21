import streamlit as st
import pandas as pd
import pdfplumber

# --- 1. 기본 페이지 및 기업용 UI(CSS) 세팅 ---
st.set_page_config(page_title="B2B 통합 자재/물류 관리 시스템", layout="wide")

# 스트림릿 기본 요소 숨기기 및 기업용 테마(Navy/Grey) 커스텀 CSS
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 요약 지표(Metric) 카드 스타일링 */
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border-left: 5px solid #002b5e;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* 제목 폰트 색상 묵직하게 변경 */
    h1, h2, h3 {
        color: #1a202c;
    }
    </style>
""", unsafe_allow_html=True)


# --- 2. 🧠 임시 메모리(session_state) 세팅 (DB 역할) ---
# 마스터 데이터 (업체, 현장)
if 'contractors_df' not in st.session_state:
    st.session_state.contractors_df = pd.DataFrame({
        "협력사명": ["(주)제일가공", "대한세라믹", "우성산업"],
        "로그인 ID": ["jeil_01", "daehan_01", "woosung_01"],
        "초기 비밀번호": ["1234", "1234", "1234"]
    })

if 'sites_df' not in st.session_state:
    st.session_state.sites_df = pd.DataFrame({
        "현장명": ["울산 샤힌 프로젝트 (FF&E)", "MGE 목업룸 현장", "신규 건자재 현장"]
    })

# 재고 및 대시보드 매트릭스용 가상 데이터
if 'inventory_summary' not in st.session_state:
    st.session_state.inventory_summary = {
        "LIVART-CERAMIC-A1": 850,
        "LIVART-CERAMIC-B2": 420,
        "LIVART-WOOD-PANEL": 150,
        "기타 건자재 부자재": 300
    }

if 'dashboard_matrix' not in st.session_state:
    st.session_state.dashboard_matrix = pd.DataFrame({
        "투입 현장명": ["울산 샤힌 프로젝트 (FF&E)", "MGE 목업룸 현장", "울산 샤힌 프로젝트 (FF&E)"],
        "담당 협력사": ["(주)제일가공", "대한세라믹", "우성산업"],
        "품목명": ["LIVART-CERAMIC-A1", "LIVART-CERAMIC-B2", "LIVART-WOOD-PANEL"],
        "할당 재고(EA)": [500, 200, 100],
        "금일 투입(EA)": [50, 0, 20],
        "잔여 재고(EA)": [250, 150, 40],
        "현장 진도율(%)": [50.0, 25.0, 60.0],
        "오차/Loss(EA)": [0, 2, 5]
    })


# --- 3. 권한 및 메뉴 시스템 ---
st.sidebar.title("🔐 시스템 로그인")
user_role = st.sidebar.radio("접속 계정 (테스트용)", ["Admin (본사 관리자)", "User (협력사)"])

def main():
    st.sidebar.title("📌 시스템 메뉴")
    
    if "Admin" in user_role:
        menu = st.sidebar.radio("메뉴를 선택해 주십시오.", 
                                ["대시보드", "재고 입력", "재고 배분", "가공 및 시공 입력", "현장 투입 내역", "기준정보 관리"])
    else:
        menu = st.sidebar.radio("메뉴를 선택해 주십시오.", 
                                ["대시보드", "가공 및 시공 입력", "현장 투입 내역"])

    # ==========================================
    # 메뉴 1: 📊 대시보드 (Enterprise Matrix 적용)
    # ==========================================
    if menu == "대시보드":
        st.title("📊 통합 자재 및 프로젝트 대시보드")
        st.markdown("본사 원장 재고 현황 및 각 프로젝트 현장별 투입/가공 매트릭스를 조회합니다.")
        st.divider()
        
        # [1단] 품목별 원장 재고 요약
        st.subheader("📦 주요 품목별 원장 재고 현황")
        cols = st.columns(4)
        item_names = list(st.session_state.inventory_summary.keys())
        item_qtys = list(st.session_state.inventory_summary.values())
        
        for i in range(4):
            with cols[i]:
                st.metric(label=item_names[i], value=f"{item_qtys[i]:,} EA")
        
        st.text("") # 여백
        st.text("") 
        
        # [2단] 현장별 매트릭스 현황판 (엑셀 스타일)
        st.subheader("📈 프로젝트 현장별 투입 및 진도율 매트릭스")
        
        # 스트림릿 컬럼 설정을 통해 기업용 표 포맷팅 (프로그레스 바 적용)
        st.dataframe(
            st.session_state.dashboard_matrix,
            column_config={
                "현장 진도율(%)": st.column_config.ProgressColumn(
                    "현장 진도율(%)",
                    help="목표 대비 현재 시공 완료 비율",
                    format="%.1f%%",
                    min_value=0,
                    max_value=100,
                ),
                "오차/Loss(EA)": st.column_config.NumberColumn(
                    "오차/Loss(EA)",
                    help="가공 산출량 대비 현장 투입 누락 또는 파손 수량",
                    format="%d 장"
                )
            },
            hide_index=True,
            use_container_width=True,
            height=300
        )
        
        st.caption("※ 표의 헤더(열 이름)를 클릭하면 오름차순/내림차순으로 데이터 정렬이 가능합니다.")

    # ==========================================
    # 메뉴 2: 📥 재고 입력 (P/L 업로드)
    # ==========================================
    elif menu == "재고 입력":
        st.title("📥 재고 입력 (P/L 업로드)")
        st.info("수입된 P/L(Packing List) 엑셀 또는 PDF 파일을 업로드하여 원장 재고를 시스템에 등록합니다.")
        
        uploaded_file = st.file_uploader("파일 업로드 (.xlsx, .csv, .pdf 지원)", type=["xlsx", "csv", "pdf"])
        
        if uploaded_file is not None:
            try:
                df = None
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(uploaded_file, engine='openpyxl')
                elif uploaded_file.name.endswith('.pdf'):
                    with pdfplumber.open(uploaded_file) as pdf:
                        first_page = pdf.pages[0]
                        table = first_page.extract_table()
                        if table:
                            df = pd.DataFrame(table[1:], columns=table[0])
                        else:
                            st.error("PDF 파일에서 표(Table) 형식을 인식할 수 없습니다. 양식을 확인해 주십시오.")

                if df is not None:
                    st.subheader("👀 데이터 미리보기 및 수정")
                    edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")
                    
                    st.divider()
                    if st.button("✅ 재고 데이터 확정 및 DB 저장", type="primary"):
                        st.success(f"성공적으로 처리되었습니다. 총 {len(edited_df)}건의 재고가 원장에 반영되었습니다.")
                        
            except Exception as e:
                st.error(f"시스템 오류가 발생했습니다: {e}")

    # ==========================================
    # 메뉴 3: 🔄 재고 배분
    # ==========================================
    elif menu == "재고 배분":
        st.title("🔄 재고 배분 및 현장 매핑")
        st.info("본사의 원장 재고를 가공 협력사 및 최종 투입 현장과 매핑하여 배분 처리합니다.")
        
        contractor_list = st.session_state.contractors_df["협력사명"].tolist()
        site_list = st.session_state.sites_df["현장명"].tolist()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.selectbox("1. 대상 재고 선택", ["LIVART-CERAMIC-A1 (잔량: 850)", "LIVART-WOOD-PANEL (잔량: 150)"])
        with col2:
            st.selectbox("2. 담당 가공사 지정", contractor_list if contractor_list else ["등록된 업체 없음"])
        with col3:
            st.selectbox("3. 투입 현장 연결", site_list if site_list else ["등록된 현장 없음"])
            
        st.number_input("배분 수량 (EA)", min_value=1, step=1)
        
        if st.button("배분 내역 확정 및 저장", type="primary"):
            st.success("해당 가공사 및 현장으로 자재 배분이 완료되었습니다.")

    # ==========================================
    # 메뉴 4, 5: 가공 및 시공 / 현장 투입 내역
    # ==========================================
    elif menu == "가공 및 시공 입력":
        st.title("🛠️ 가공 및 시공 내역 입력")
        st.info("당일 작업한 원장 수량과 가공 후 산출된 실제 면적(m²)을 정확히 입력해 주십시오.")
        st.markdown("##### 귀사에 할당된 당일 원장 재고 잔량: **250 EA**")
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            input_ea = st.number_input("금일 투입 원장 수량 (EA)", min_value=0, step=1)
        with col2:
            input_m2 = st.number_input("금일 산출 면적 (m²)", min_value=0.0, step=0.1)
            
        if st.button("작업 내역 시스템 등록", type="primary"):
            st.success(f"입력하신 내역 ({input_ea}장 가공 / {input_m2}m² 산출)이 성공적으로 등록되었습니다.")

    elif menu == "현장 투입 내역":
        st.title("🏗️ 현장 투입 내역 등록")
        st.info("실제 현장에 시공이 완료된 최종 면적(m²)을 입력하여 전체 진도율에 반영합니다.")
        
        site_list = st.session_state.sites_df["현장명"].tolist()
        st.selectbox("대상 시공 현장 선택", site_list if site_list else ["등록된 현장 없음"])
        st.number_input("금일 시공 완료 면적 (m²)", min_value=0.0, step=0.1)
        
        if st.button("현장 투입 내역 반영", type="primary"):
            st.success("입력하신 시공 물량이 현장 진도율에 정상적으로 반영되었습니다.")

    # ==========================================
    # 메뉴 6: ⚙️ 기준정보 관리
    # ==========================================
    elif menu == "기준정보 관리":
        st.title("⚙️ 기준정보 및 계정 관리 (마스터 데이터)")
        st.info("신규 협력사 등록 및 로그인 계정(ID/PW) 발급, 신규 프로젝트 현장을 관리하는 통합 환경 설정 페이지입니다.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏢 협력사 및 계정 발급 관리")
            edited_contractors = st.data_editor(
                st.session_state.contractors_df, 
                use_container_width=True, 
                num_rows="dynamic", 
                key="contractor_editor"
            )
            if st.button("✅ 협력사 정보 DB 반영", type="primary"):
                st.session_state.contractors_df = edited_contractors
                st.success("협력사 마스터 데이터가 업데이트되었습니다. 재고 배분 시스템에 즉시 반영됩니다.")

        with col2:
            st.subheader("🏗️ 프로젝트 현장 관리")
            edited_sites = st.data_editor(
                st.session_state.sites_df, 
                use_container_width=True, 
                num_rows="dynamic", 
                key="site_editor"
            )
            if st.button("✅ 현장 목록 DB 반영", type="primary"):
                st.session_state.sites_df = edited_sites
                st.success("프로젝트 현장 마스터 데이터가 업데이트되었습니다.")

if __name__ == "__main__":
    main()
