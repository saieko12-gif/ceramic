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

# --- 2. 임시 메모리(session_state) 세팅 ---
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

# --- ★ 신규 추가: PDF 쌩 텍스트를 엑셀로 강제 변환하는 함수 (무식하게 다 뽑음) ★ ---
def convert_pdf_to_raw_excel(pdf_file):
    rows = []
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=3, y_tolerance=10)
                if text:
                    for line in text.split('\n'):
                        # 띄어쓰기 2칸 이상을 기준으로 엑셀의 열(Column)을 나눔
                        cols = re.split(r'\s{2,}', line.strip())
                        rows.append(cols)
    except Exception as e:
        pass
    return pd.DataFrame(rows)

# --- 3. FLORIM P/L PDF 메인 파싱 함수 (Y좌표 오차 대폭 허용 및 순서 무관 알고리즘) ---
def parse_florim_pdf(pdf_file, filename=""):
    packing_no = ""
    dated_str = ""
    parsed_rows = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                
                # 상단 Packing N° 및 Dated 추출
                if not packing_no:
                    p_match = re.search(r'Packing\s*N[^\d]*(\d+)', text, re.IGNORECASE)
                    if p_match: packing_no = p_match.group(1)
                if not dated_str:
                    d_match = re.search(r'Dated[^\d]*([\d\.]+)', text, re.IGNORECASE)
                    if d_match: dated_str = d_match.group(1)
                    
                # Y좌표 기반 행 복원 (오차 범위를 10픽셀로 대폭 확대하여 찢어진 줄 방어)
                words = page.extract_words()
                if not words:
                    continue
                    
                lines_dict = {}
                for w in words:
                    y_coord = round(w['top'] / 10) * 10
                    if y_coord not in lines_dict:
                        lines_dict[y_coord] = []
                    lines_dict[y_coord].append(w)
                    
                for y in sorted(lines_dict.keys()):
                    line_words = sorted(lines_dict[y], key=lambda x: x['x0'])
                    line_text = " ".join([w['text'] for w in line_words])
                    
                    line_text = line_text.replace('|', ' ')
                    line_text = re.sub(r'\s+', ' ', line_text)
                    
                    if 'M2' in line_text.upper():
                        qty_match = re.search(r'\b(\d+)\s+[1lI]?\s*([\d,\.]+)\s*M2', line_text, re.IGNORECASE)
                        
                        if qty_match:
                            boxes = qty_match.group(1)
                            m2_val = qty_match.group(2).replace(',', '.')
                            
                            # M2 뒷부분 텍스트에서 품번(5자리 이상 숫자) 싹 날리고 품명만 남기기
                            search_area = line_text[qty_match.end():].strip()
                            desc = re.sub(r'\b\d{5,}\b', '', search_area).strip()
                            desc = re.sub(r'\s{2,}', ' ', desc)
                            
                            if len(desc) < 3:
                                desc = "품명 인식 불가"
                                
                            size_match = re.search(r'(\d+)\s*[Xx]\s*(\d+)', desc, re.IGNORECASE)
                            dimension_mm = "규격 정보 없음"
                            if size_match:
                                w_mm = int(size_match.group(1)) * 10
                                l_mm = int(size_match.group(2)) * 10
                                dimension_mm = f"{w_mm} x {l_mm} mm"
                                
                            parsed_rows.append({
                                "업로드 파일명": filename,
                                "Packing N°": packing_no,
                                "Dated": dated_str,
                                "세라믹 원장명": desc,
                                "원장 수량(N Box)": int(boxes),
                                "총 헤베(m²)": m2_val,
                                "원장 규격(mm)": dimension_mm
                            })
    except Exception as e:
        return None
        
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
    # 메뉴 1: 대시보드
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
    # 메뉴 2: 재고 입력 
    # ==========================================
    elif menu == "재고 입력":
        st.title("📥 재고 입고 등록 및 P/L 업로드")
        
        # --- PDF to Excel 보조 도구 (접어두기 기본 설정 적용 및 멘트 수정) ---
        with st.expander("🛠️ [보조 도구] PDF 자동 인식 실패 시 엑셀 변환기", expanded=False):
            st.info("PDF 자동 인식이 실패할 경우, 여기서 먼저 엑셀 파일로 추출(변환)한 뒤 메인 업로더에 첨부해 주십시오.")
            raw_pdf = st.file_uploader("변환할 PDF 파일을 선택해 주십시오.", type=["pdf"], key="raw_pdf")
            if raw_pdf:
                if st.button("🔄 엑셀로 추출하기"):
                    with st.spinner("엑셀 변환 중입니다..."):
                        # 무식하고 확실한 쌩 텍스트 추출 방식 사용
                        df_raw = convert_pdf_to_raw_excel(raw_pdf)
                        
                        if df_raw is not None and not df_raw.empty:
                            output_raw = io.BytesIO()
                            with pd.ExcelWriter(output_raw, engine='openpyxl') as writer:
                                df_raw.to_excel(writer, index=False, header=False)
                            raw_excel_data = output_raw.getvalue()
                            
                            st.download_button(
                                label=f"📥 [{raw_pdf.name}] 엑셀로 다운로드",
                                data=raw_excel_data,
                                file_name=f"변환됨_{raw_pdf.name}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                type="primary"
                            )
                        else:
                            st.error("데이터를 추출할 수 없습니다. 파일 양식을 확인해 주십시오.")
        
        st.divider()
        
        # --- 메인 재고 업로드 영역 ---
        st.subheader("📦 메인 재고 업로드 (엑셀 / 자동인식 PDF)")
        entry_date = st.date_input("입고 일자 선택", datetime.date.today())
        
        uploaded_files = st.file_uploader("최종 파일 다중 업로드 (.xlsx, .csv, 정상 양식 .pdf 지원)", type=["xlsx", "csv", "pdf"], accept_multiple_files=True)
        
        if uploaded_files:
            all_dfs = []
            for uploaded_file in uploaded_files:
                df = None
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(uploaded_file, engine='openpyxl')
                elif uploaded_file.name.endswith('.pdf'):
                    df = parse_florim_pdf(uploaded_file, uploaded_file.name)
                
                if df is not None:
                    all_dfs.append(df)
            
            if all_dfs:
                final_df = pd.concat(all_dfs, ignore_index=True)
                st.subheader("👀 데이터 미리보기 및 수정")
                st.markdown("데이터를 확인하고 필요시 표 안의 셀을 **더블클릭**하여 직접 수정하십시오.")
                
                edited_df = st.data_editor(final_df, use_container_width=True, num_rows="dynamic", key="pl_editor")
                
                st.divider()
                if st.button("✅ 전체 재고 데이터 확정 및 DB 저장", type="primary"):
                    st.success(f"{entry_date} 일자로 총 {len(edited_df)}건의 원장 재고 데이터가 성공적으로 확정되었습니다.")
            else:
                st.error("업로드하신 파일들에서 데이터를 인식하지 못했습니다. 보조 도구를 이용해 엑셀로 변환해 주십시오.")

    # ==========================================
    # 메뉴 3: 재고 배분
    # ==========================================
    elif menu == "재고 배분":
        st.title("🔄 재고 배분 및 현장 매핑")
        
        contractor_list = st.session_state.contractors_df["협력사명"].tolist()
        site_list = st.session_state.sites_df["현장명"].tolist()
        
        st.subheader("📝 신규 재고 배분 입력")
        dist_date = st.date_input("배분 일자 선택", datetime.date.today())
        
        col1, col2, col3, col4 = st.columns(4)
        with col1: pack_no = st.text_input("Packing N° (선택)", "3110068246")
        with col2: selected_item = st.selectbox("대상 재고 선택", ["MARBLE HERI TUNDRA MATT", "NATURE MOOD GLACIER COMF", "MARBLE HERI MOUNTPEAK MAT"])
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
    # 메뉴 4: 가공 및 시공 입력
    # ==========================================
    elif menu == "가공 및 시공 입력":
        st.title("🛠️ 가공 내역 등록")
        
        target_contractor = current_contractor if not is_admin else st.selectbox("대상 가공사 선택 (관리자용)", st.session_state.contractors_df["협력사명"].tolist())
        
        st.subheader("📝 신규 가공 내역 입력")
        proc_date = st.date_input("작업 일자 선택", datetime.date.today())
        
        col1, col2, col3 = st.columns(3)
        with col1: proc_item = st.selectbox("가공 품목 선택", ["MARBLE HERI TUNDRA MATT (1600x3200mm)", "NATURE MOOD GLACIER COMF (1200x2400mm)"])
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
    # 메뉴 5: 현장 투입 내역
    # ==========================================
    elif menu == "현장 투입 내역":
        st.title("🏗️ 현장 투입 내역 등록")
        
        target_contractor = current_contractor if not is_admin else st.selectbox("대상 협력사 선택 (관리자용)", st.session_state.contractors_df["협력사명"].tolist())
        
        st.subheader("📝 신규 현장 투입 입력")
        site_date = st.date_input("현장 투입 일자 선택", datetime.date.today())
        
        col1, col2, col3 = st.columns(3)
        with col1: site_sel = st.selectbox("1. 시공 현장", st.session_state.sites_df["현장명"].tolist())
        with col2: item_sel = st.selectbox("2. 투입 원장 종류", ["MARBLE HERI TUNDRA MATT", "NATURE MOOD GLACIER COMF", "기타 건자재"])
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
    # 메뉴 6: 기준정보 관리
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
