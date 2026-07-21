import streamlit as st
import pandas as pd

# --- 기본 페이지 설정 ---
st.set_page_config(page_title="자재 물류 및 프로젝트 관리 대시보드", layout="wide")

# --- 임시 인증(로그인) 시스템 (실제 배포 시 Supabase Auth로 교체) ---
st.sidebar.title("🔐 시스템 로그인")
user_role = st.sidebar.radio("접속 계정 선택 (테스트용)", ["Admin (본사 관리자)", "User (협력사)"])

def main():
    # --- 권한별 메뉴 분리 로직 ---
    st.sidebar.title("📌 시스템 메뉴")
    
    if "Admin" in user_role:
        menu = st.sidebar.radio("이동할 페이지를 선택해 주십시오.", 
                                ["대시보드", "재고 입력", "재고 배분", "가공 및 시공 입력", "현장 투입 내역"])
    else:
        menu = st.sidebar.radio("이동할 페이지를 선택해 주십시오.", 
                                ["대시보드", "가공 및 시공 입력", "현장 투입 내역"])

    # --- 1. 대시보드 (기본 화면) ---
    if menu == "대시보드":
        st.title("📊 통합 프로젝트 대시보드")
        st.markdown("현재 전체 재고 현황 및 프로젝트 진도율을 요약하여 보여줍니다.")
        
        # 핵심 지표 (metric)
        col1, col2, col3 = st.columns(3)
        col1.metric("본사 원장 재고", "1,250 EA")
        col2.metric("전체 가공 산출량", "3,800 m²")
        col3.metric("실제 현장 투입량", "3,750 m²")
        
        st.divider()
        
        # Loss/오차 강조 영역
        st.subheader("⚠️ 가공 및 시공 오차(Loss) 현황")
        loss_diff = 3800 - 3750  # 가공 산출량 - 현장 투입량
        
        if loss_diff > 0:
            st.error(f"확인 필요: 가공 산출량 대비 현장 투입량 누락 또는 로스(Loss) 발생 ({loss_diff} m²)")
        else:
            st.success("현재 가공 산출량과 현장 투입량이 일치합니다.")

    # --- 2. 재고 입력 (P/L 업로드 - Admin) ---
    elif menu == "재고 입력":
        st.title("📥 재고 입력 (P/L 업로드)")
        st.info("수입된 P/L(Packing List) 엑셀 파일을 업로드하여 원장 재고를 시스템에 등록합니다.")
        
        uploaded_file = st.file_uploader("엑셀 파일 업로드 (.xlsx, .csv 형식 지원)", type=["xlsx", "csv"])
        
        if uploaded_file is not None:
            # P/L 데이터 추출 가상 화면
            st.write("업로드된 데이터 추출 결과 확인:")
            df_mock = pd.DataFrame({
                "품번 (Item Code)": ["CERAMIC-A1", "CERAMIC-B2"],
                "수량 (EA)": [100, 200],
                "면적 (CBM)": [1.5, 3.0]
            })
            st.data_editor(df_mock, use_container_width=True)
            
            if st.button("재고 데이터 확정 및 DB 저장", type="primary"):
                st.success("데이터베이스에 성공적으로 저장되었습니다.")

    # --- 3. 재고 배분 (Admin) ---
    elif menu == "재고 배분":
        st.title("🔄 재고 배분 및 현장 매핑")
        st.info("본사의 원장 재고를 가공 협력사 및 최종 투입 현장과 매핑하여 배분합니다.")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.selectbox("1. 대상 재고 선택", ["CERAMIC-A1 (잔량: 100 EA)", "CERAMIC-B2 (잔량: 200 EA)"])
        with col2:
            st.selectbox("2. 담당 가공사 지정", ["(주)제일가공", "대한세라믹", "우성산업"])
        with col3:
            st.selectbox("3. 투입 현장 연결", ["울산 샤힌 프로젝트", "MGE 목업룸 현장"])
            
        st.number_input("배분 수량 (EA)", min_value=1, step=1)
        
        if st.button("배분 내역 확정 및 저장", type="primary"):
            st.success("해당 가공사 및 현장으로 재고 배분이 완료되었습니다.")

    # --- 4. 가공 및 시공 입력 (협력사 공통) ---
    elif menu == "가공 및 시공 입력":
        st.title("🛠️ 가공 및 시공 내역 입력")
        st.info("당일 작업한 원장 수량과 가공 후 산출된 실제 면적(m²)을 정확히 입력해 주십시오.")
        
        # 현재 보유 잔량 안내
        st.markdown("##### 현재 귀사에 할당된 원장 재고 잔량: **50 EA**")
        st.divider()
        
        col1, col2 = st.columns(2)
        with col1:
            input_ea = st.number_input("금일 투입 원장 수량 (EA)", min_value=0, step=1)
        with col2:
            input_m2 = st.number_input("금일 산출 면적 (m²)", min_value=0.0, step=0.1)
            
        if st.button("작업 내역 시스템 등록", type="primary"):
            st.success(f"입력하신 내역({input_ea}장 가공 / {input_m2}m² 산출)이 성공적으로 등록되었습니다.")

    # --- 5. 현장 투입 내역 (협력사 공통) ---
    elif menu == "현장 투입 내역":
        st.title("🏗️ 현장 투입 내역 등록")
        st.info("실제 현장에 시공이 완료된 최종 면적(m²)을 입력하여 전체 진도율에 반영합니다.")
        
        st.selectbox("대상 시공 현장 선택", ["울산 샤힌 프로젝트", "MGE 목업룸 현장"])
        st.number_input("금일 시공 완료 면적 (m²)", min_value=0.0, step=0.1)
        
        if st.button("현장 투입 내역 반영", type="primary"):
            st.success("입력하신 시공 물량이 현장 진도율에 반영되었습니다.")

if __name__ == "__main__":
    main()
