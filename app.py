import streamlit as st
import pandas as pd
import pdfplumber
import io
import datetime
import re

# --- 1. 기본 페이지 및 기업용 UI(CSS) 세팅 ---
st.set_page_config(page_title="B2B 통합 자재/물류 관리 시스템", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    div[data-testid="metric-container"] {
        background-color: #f8f9fa;
        border-left: 5px solid #002b5e;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    h1, h2, h3 { color: #1a202c; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 🧠 임시 메모리(session_state) 세팅 ---
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

if 'dist_history' not in st.session_state:
    st.session_state.dist_history = pd.DataFrame(columns=["배분 일자", "Packing N°", "대상 재고", "담당 가공사", "투입 현장", "배분 수량(EA)"])

if 'proc_history' not in st.session_state:
    st.session_state.proc_history = pd.DataFrame(columns=["작업 일자", "담당 가공사", "가공 품목", "투입 원장(EA)", "산출 면적(m²)"])

if 'site_history' not in st.session_state:
    st.session_state.site_history = pd.DataFrame(columns=["투입 일자", "담당 협력사", "시공 현장", "투입 원장 종류", "시공 완료 면적(m²)"])

# --- 3. FLORIM P/L PDF 파싱 함수 (텍스트 패턴 추출 방식으로 무적 업그레이드) ---
def parse_florim_pdf(pdf_file):
    packing_no = ""
    dated_str = ""
    parsed_rows = []
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            
            # 1. 상단 Packing N° 및 Dated 추출
            if not packing_no:
                p_match = re.search(r'Packing\s*N[°o]?\s*:\s*(\d+)', text, re.IGNORECASE)
                if p_match: packing_no = p_match.group(1)
            if not dated_str:
                d_match = re.search(r'Dated\s*:\s*([\d\.]+)', text, re.IGNORECASE)
                if d_match: dated_str = d_match.group(1)
                
            # 2. 텍스트 라인별로 쪼개서 분석 (표 테두리가 없는 PDF 대응)
            lines = text.split('\n')
            for line in lines:
                # M2가 있고, 원장명 키워드가 있는 줄만 타겟팅
                if 'M2' in line and ('MARBLE' in line or 'HERI' in line or 'MATT' in line):
                    
                    # 패턴: [박스수량] 1 [헤베수량] M2
                    qty_match = re.search(r'\b(\d+)\s+1\s+([\d,]+)\s*M2', line)
                    
                    if qty_match:
                        boxes = qty_match.group(1)
                        # 콤마(,)를 소수점(.)으로 변경
                        m2_val = qty_match.group(2).replace(',', '.') 
                        
                        # 품명 추출 (MARBLE, HERI, MATT 시작점부터 가져오기)
                        desc_match = re.search(r'(MARBLE|HERI|MATT)', line)
                        goods_desc = "품명 인식 불가"
                        
                        if desc_match:
                            raw_desc = line[desc_match.start():]
                            # 뒤에 붙은 품번/HS CODE (6자리 이상 연속된 숫자) 싹둑 자르기
                            goods_desc = re.sub(r'\s*\b\d{6,}\b.*', '', raw_desc).strip()
                        
                        # 규격(mm) 추출 (예: 160X320 -> 1600 x 3200 mm)
                        size_match = re.search(r'(\d+)\s*[X\x88x]\s*(\d+)', goods_desc, re.IGNORECASE)
                        dimension_mm = "규격 정보 없음"
                        if size_match:
                            w_mm = int(size_match.group(1)) * 10
                            l_mm = int(size_match.group(2)) * 10
                            dimension_mm = f"{w_mm} x {l_mm} mm"
                            
                        parsed_rows.append({
                            "Packing N°": packing_no,
                            "Dated": dated_str,
                            "세라믹 원장명": goods_desc,
                            "원장 수량(N Box)": int(boxes),
                            "총 헤베(m²)": m2_val,
                            "원장 규격(mm)": dimension_mm
                        })
                        
    if parsed_rows:
        return pd.DataFrame(parsed_rows)
    else:
        return None

# --- 4. 권한 및 메뉴 시스템 ---
st.sidebar.title("🔐 시스템 로그인")
user_role = st.sidebar.radio("접속 계정 (테스트용)", ["Admin (본사 관리자)", "User ((주)제일가공 소장)"])

is_admin = "Admin" in user_role
current_contractor = "(주)제일가공" if not is_admin else None

def main():
    st.sidebar.title("📌 시스템 메뉴")
    
    if is_admin:
        menu = st.sidebar.radio("메뉴를 선택해 주십시오.", 
                                ["대시보드", "재고 입력", "재고 배분", "가공 및 시공 입력", "현장 투입 내역", "기준정보 관리"])
    else:
        menu = st.sidebar.radio("메뉴를 선택해 주십시오.", 
                                ["대시보드", "가공 및 시공 입력", "현장 투입 내역"])

    # ==========================================
    # 메뉴 1: 📊 대시보드
    # ==========================================
    if menu == "대시보드":
        st.title("📊 통합 자재 및 프로젝트 대시보드")
        
        if is_admin:
            st.markdown("본사 원장 재고 현황 및 각 프로젝트 현장별 투입/가공 매트릭스를 조회합니다.")
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                st.session_state.dist_history.to_excel(writer, sheet_name='재고배분내역', index=False)
                st.session_state.proc_history.to_excel(writer, sheet_name='가공산출내역', index=False)
                st.session_state.site_history.to_excel(writer, sheet_name='현장투입내역', index=False)
            excel_data = output.getvalue()
            
            st.download_button(
                label="📥 전체 누적 데이터 엑셀 다운로드 (관리자 전용)",
                data=excel_data,
                file_name=f"통합자재물류데이터_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.markdown(f"**{current_contractor}** 전용 대시보드입니다. 귀사의 가공 및 투입 현황만 노출됩니다.")
            
        st.divider()
        
        display_site = st.session_state.site_history if is_admin else st.session_state.site_history[st.session_state.site_history["담당 협력사"] == current_contractor]
        
        st.subheader("📈 프로젝트 누적 투입/진도율 현황")
        if not display_site.empty:
            st.dataframe(display_site, use_container_width=True, hide_index=True)
        else:
            st.info("현재 등록된 투입 내역이 없습니다.")

    # ==========================================
    # 메뉴 2: 📥 재고 입력 (P/L 자동 파싱 적용)
    # ==========================================
    elif menu == "재고 입력":
        st.title("📥 재고 입고 등록 (P/L 업로드)")
        st.info("수입된 P/L(Packing List) 엑셀 또는 PDF 파일을 업로드하여 원장 재고를 시스템에 자동 파싱합니다.")
        
        entry_date = st.date_input("입고 일자 선택", datetime.date.today())
        uploaded_file = st.file_uploader("파일 업로드 (.xlsx, .csv, .pdf 지원)", type=["xlsx", "csv", "pdf"])
        
        if uploaded_file is not None:
            df = None
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            elif uploaded_file.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(uploaded_file, engine='openpyxl')
            elif uploaded_file.name.endswith('.pdf'):
                # FLORIM PDF 맞춤형 파싱 알고리즘 실행
                df = parse_florim_pdf(uploaded_file)
            
            if df is not None:
                st.subheader("👀 P/L 자동 인식 결과 미리보기 및 수정")
                st.markdown("파싱된 Packing N°, Dated, 규격(mm) 데이터를 확인하고 필요시 셀을 **더블클릭**하여 직접 수정하십시오.")
                
                edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic", key="pl_editor")
                
                st.divider()
                if st.button("✅ 재고 데이터 확정 및 DB 저장", type="primary"):
                    st.success(f"{entry_date} 일자로 총 {len(edited_df)}건의 원장 재고 데이터가 성공적으로 확정되었습니다.")
            else:
                st.error("파일에서 P/L 표 데이터를 인식하지 못했습니다. 표준 FLORIM P/L 양식인지 확인해 주십시오.")

    # ==========================================
    # 메뉴 3: 🔄 재고 배분
    # ==========================================
    elif menu == "재고 배분":
        st.title("🔄 재고 배분 및 현장 매핑")
        
        contractor_list = st.session_state.contractors_df["협력사명"].tolist()
        site_list = st.session_state.sites_df["현장명"].tolist()
        
        st.subheader("📝 신규 재고 배분 입력")
        dist_date = st.date_input("배분 일자 선택", datetime.date.today())
        
        col1, col2, col3, col4 = st.columns(4)
        with col1: pack_no = st.text_input("Packing N° (선택)", "3110068246")
        with col2: selected_item = st.selectbox("대상 재고 선택", ["MARBLE HERI TUNDRA MATT", "MARBLE HERI MOUNTPEAK MAT"])
        with col3: selected_contractor = st.selectbox("담당 가공사 지정", contractor_list)
        with col4: selected_site = st.selectbox("투입 현장 연결", site_list)
        
        qty = st.number_input("배분 수량 (N Box / EA)", min_value=1, step=1)
        
        if st.button("배분 내역 추가", type="primary"):
            new_row = pd.DataFrame({"배분 일자": [dist_date], "Packing N°": [pack_no], "대상 재고": [selected_item], "담당 가공사": [selected_contractor], "투입 현장": [selected_site], "배분 수량(EA)": [qty]})
            st.session_state.dist_history = pd.concat([st.session_state.dist_history, new_row], ignore_index=True)
            st.success("배분 내역이 하단 표에 추가되었습니다.")

        st.divider()
        st.subheader("📋 누적 배분 내역 관리")
        st.session_state.dist_history = st.data_editor(st.session_state.dist_history, use_container_width=True, num_rows="dynamic")
        if st.button("🔄 수정 내역 시스템 반영"):
            st.success("배분 내역 수정이 완료되었습니다.")

    # ==========================================
    # 메뉴 4: 🛠️ 가공 및 시공 입력
    # ==========================================
    elif menu == "가공 및 시공 입력":
        st.title("🛠️ 가공 내역 등록")
        
        target_contractor = current_contractor if not is_admin else st.selectbox("대상 가공사 선택 (관리자용)", st.session_state.contractors_df["협력사명"].tolist())
        
        st.subheader("📝 신규 가공 내역 입력")
        proc_date = st.date_input("작업 일자 선택", datetime.date.today())
        
        col1, col2, col3 = st.columns(3)
        with col1: proc_item = st.selectbox("가공 품목 선택", ["MARBLE HERI TUNDRA MATT (1600x3200mm)", "MARBLE HERI MOUNTPEAK MAT (1600x3200mm)"])
        with col2: input_ea = st.number_input("투입 원장 수량 (EA)", min_value=0, step=1)
        with col3: input_m2 = st.number_input("산출 면적 (m²)", min_value=0.0, step=0.1)
            
        if st.button("가공 내역 추가", type="primary"):
            new_row = pd.DataFrame({"작업 일자": [proc_date], "담당 가공사": [target_contractor], "가공 품목": [proc_item], "투입 원장(EA)": [input_ea], "산출 면적(m²)": [input_m2]})
            st.session_state.proc_history = pd.concat([st.session_state.proc_history, new_row], ignore_index=True)
            st.success("가공 내역이 하단 표에 추가되었습니다.")

        st.divider()
        st.subheader("📋 누적 가공 내역 관리")
        mask = st.session_state.proc_history["담당 가공사"] == target_contractor if not is_admin else [True] * len(st.session_state.proc_history)
        filtered_proc = st.session_state.proc_history[mask]
        
        edited_proc = st.data_editor(filtered_proc, use_container_width=True, num_rows="dynamic")
        if st.button("🔄 수정 내역 시스템 반영", key="proc_save"):
            st.success("수정된 가공 내역이 시스템에 반영되었습니다.")

    # ==========================================
    # 메뉴 5: 🏗️ 현장 투입 내역
    # ==========================================
    elif menu == "현장 투입 내역":
        st.title("🏗️ 현장 투입 내역 등록")
        
        target_contractor = current_contractor if not is_admin else st.selectbox("대상 협력사 선택 (관리자용)", st.session_state.contractors_df["협력사명"].tolist())
        
        st.subheader("📝 신규 현장 투입 입력")
        site_date = st.date_input("현장 투입 일자 선택", datetime.date.today())
        
        col1, col2, col3 = st.columns(3)
        with col1: site_sel = st.selectbox("1. 시공 현장", st.session_state.sites_df["현장명"].tolist())
        with col2: item_sel = st.selectbox("2. 투입 원장 종류", ["MARBLE HERI TUNDRA MATT", "MARBLE HERI MOUNTPEAK MAT", "기타 건자재"])
        with col3: area_sel = st.number_input("3. 시공 완료 면적 (m²)", min_value=0.0, step=0.1)
        
        if st.button("투입 내역 추가", type="primary"):
            new_row = pd.DataFrame({"투입 일자": [site_date], "담당 협력사": [target_contractor], "시공 현장": [site_sel], "투입 원장 종류": [item_sel], "시공 완료 면적(m²)": [area_sel]})
            st.session_state.site_history = pd.concat([st.session_state.site_history, new_row], ignore_index=True)
            st.success("투입 내역이 하단 표에 추가되었습니다.")

        st.divider()
        st.subheader("📋 누적 현장 투입 내역 관리")
        mask2 = st.session_state.site_history["담당 협력사"] == target_contractor if not is_admin else [True] * len(st.session_state.site_history)
        filtered_site = st.session_state.site_history[mask2]
        
        edited_site = st.data_editor(filtered_site, use_container_width=True, num_rows="dynamic")
        if st.button("🔄 수정 내역 시스템 반영", key="site_save"):
            st.success("수정된 현장 투입 내역이 시스템에 반영되었습니다.")

    # ==========================================
    # 메뉴 6: ⚙️ 기준정보 관리
    # ==========================================
    elif menu == "기준정보 관리":
        st.title("⚙️ 기준정보 및 계정 관리 (마스터 데이터)")
        st.info("신규 협력사 등록 및 로그인 계정 발급, 신규 프로젝트 현장을 관리합니다.")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🏢 협력사 및 계정 발급 관리")
            st.session_state.contractors_df = st.data_editor(st.session_state.contractors_df, use_container_width=True, num_rows="dynamic")
            if st.button("✅ 협력사 정보 DB 반영", type="primary"): st.success("마스터 데이터가 업데이트되었습니다.")
        with col2:
            st.subheader("🏗️ 프로젝트 현장 관리")
            st.session_state.sites_df = st.data_editor(st.session_state.sites_df, use_container_width=True, num_rows="dynamic")
            if st.button("✅ 현장 목록 DB 반영", type="primary"): st.success("마스터 데이터가 업데이트되었습니다.")

if __name__ == "__main__":
    main()
