import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 1. 기본 페이지 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)


# ---------------------------------------------------------
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# ---------------------------------------------------------
# 배포 서버가 한국 시간이 아닐 수 있기 때문에
# 서버의 현재 시간을 그대로 사용하지 않고
# Asia/Seoul 시간대를 명시적으로 사용합니다.
kst_now = datetime.now(ZoneInfo("Asia/Seoul"))
yesterday = kst_now - timedelta(days=1)

# KOBIS API에서 사용하는 날짜 형식: YYYYMMDD
target_date = yesterday.strftime("%Y%m%d")

# 화면에 보여줄 날짜 형식
display_date = yesterday.strftime("%Y년 %m월 %d일")


# ---------------------------------------------------------
# 3. KOBIS API 호출 함수
# ---------------------------------------------------------
# 같은 날짜의 결과는 1시간 동안 캐시에 저장합니다.
# 따라서 같은 날짜를 다시 조회해도 API를 계속 호출하지 않습니다.
@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    # Streamlit Cloud의 Secrets에서 인증키를 가져옵니다.
    # 실제 인증키를 코드에 직접 작성하지 않습니다.
    kobis_key = st.secrets["KOBIS_KEY"]

    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    params = {
        "key": kobis_key,
        "targetDt": target_dt
    }

    try:
        # API 요청
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류가 발생하면 예외를 발생시킵니다.
        response.raise_for_status()

        # JSON 형태로 변환
        data = response.json()

    except requests.exceptions.Timeout:
        raise RuntimeError(
            "KOBIS API 요청 시간이 초과되었습니다. "
            "잠시 후 다시 시도해 주세요."
        )

    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"KOBIS API에 접속하지 못했습니다.\n\n"
            f"인터넷 연결이나 KOBIS API 상태를 확인해 주세요.\n"
            f"오류 내용: {e}"
        )

    except ValueError:
        raise RuntimeError(
            "KOBIS API에서 정상적인 JSON 응답을 받지 못했습니다. "
            "KOBIS API 상태를 확인해 주세요."
        )

    # -----------------------------------------------------
    # 4. faultInfo 확인
    # -----------------------------------------------------
    # KOBIS는 인증키가 잘못되어도 HTTP 상태코드가 200일 수 있습니다.
    # 이 경우 faultInfo가 들어옵니다.
    if "faultInfo" in data:
        fault_info = data["faultInfo"]

        # faultInfo 안의 메시지를 최대한 읽기 쉽게 가져옵니다.
        if isinstance(fault_info, dict):
            fault_code = fault_info.get("errorCode", "")
            fault_message = fault_info.get("message", "")

            if fault_code and fault_message:
                detail = f"{fault_code}: {fault_message}"
            elif fault_message:
                detail = fault_message
            else:
                detail = str(fault_info)
        else:
            detail = str(fault_info)

        raise RuntimeError(
            "KOBIS API에서 오류를 반환했습니다.\n\n"
            "다음 사항을 확인해 주세요.\n"
            "• Streamlit Cloud의 Secrets에 KOBIS_KEY가 등록되어 있는지\n"
            "• 인증키가 정확한지\n"
            "• KOBIS Open API 사용이 가능한 상태인지\n\n"
            f"API 오류 내용: {detail}"
        )

    # -----------------------------------------------------
    # 5. boxOfficeResult와 영화 목록 확인
    # -----------------------------------------------------
    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        raise RuntimeError(
            "KOBIS 응답에 boxOfficeResult가 없습니다.\n\n"
            "KOBIS API 응답 형식과 API 상태를 확인해 주세요."
        )

    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        raise RuntimeError(
            f"{display_date}의 영화 목록이 비어 있습니다.\n\n"
            "다음 사항을 확인해 주세요.\n"
            "• 해당 날짜의 일일 박스오피스 데이터가 집계되었는지\n"
            "• 조회 날짜가 올바른지\n"
            "• KOBIS API가 정상적으로 데이터를 제공하고 있는지"
        )

    return movie_list


# ---------------------------------------------------------
# 6. 숫자 문자열을 실제 숫자로 변환하는 함수
# ---------------------------------------------------------
def to_number(value):
    """
    KOBIS API의 숫자는 문자열로 들어옵니다.
    예: "12345" → 12345

    값이 없거나 변환할 수 없는 경우 0으로 처리합니다.
    """
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------
# 7. 제목
# ---------------------------------------------------------
st.title("🎬 어제의 박스오피스")

st.caption(
    f"한국 시간 기준 {display_date}의 KOBIS 일일 박스오피스"
)


# ---------------------------------------------------------
# 8. API 데이터 가져오기
# ---------------------------------------------------------
try:
    movie_list = get_boxoffice(target_date)

except Exception as e:
    # API 오류가 발생해도 빈 화면이 나오지 않도록
    # 사용자가 무엇을 확인해야 하는지 안내합니다.
    st.error("박스오피스 데이터를 불러오지 못했습니다.")

    st.warning(
        "확인할 사항\n\n"
        "1. Streamlit Cloud의 Secrets에 `KOBIS_KEY`가 등록되어 있는지\n"
        "2. KOBIS 인증키가 정확한지\n"
        "3. KOBIS Open API가 정상적으로 작동하는지\n"
        "4. 해당 날짜의 박스오피스 데이터가 집계되었는지"
    )

    st.info(f"상세 내용: {e}")

    st.stop()


# ---------------------------------------------------------
# 9. DataFrame으로 변환
# ---------------------------------------------------------
df = pd.DataFrame(movie_list)


# ---------------------------------------------------------
# 10. 필요한 열만 선택하고 한글 이름으로 변경
# ---------------------------------------------------------
columns = {
    "rank": "순위",
    "movieNm": "영화명",
    "openDt": "개봉일",
    "audiCnt": "관객수",
    "audiAcc": "누적관객",
    "scrnCnt": "스크린수"
}

# API에서 필요한 열이 빠져 있는 경우도 대비합니다.
missing_columns = [
    column for column in columns
    if column not in df.columns
]

if missing_columns:
    st.error(
        "KOBIS API 응답에 필요한 데이터 항목이 없습니다."
    )

    st.info(
        "다음 항목이 응답에 포함되어 있는지 확인해 주세요: "
        + ", ".join(missing_columns)
    )

    st.stop()


df = df[list(columns.keys())].rename(columns=columns)


# ---------------------------------------------------------
# 11. 숫자 열을 실제 숫자로 변환
# ---------------------------------------------------------
# KOBIS API에서는 숫자도 문자열로 전달됩니다.
# 숫자로 변환해야 올바르게 정렬하고 그래프를 그릴 수 있습니다.
numeric_columns = [
    "순위",
    "관객수",
    "누적관객",
    "스크린수"
]

for column in numeric_columns:
    df[column] = df[column].apply(to_number)


# 순위 기준으로 정렬
df = df.sort_values("순위").reset_index(drop=True)


# ---------------------------------------------------------
# 12. 1위 영화 확인
# ---------------------------------------------------------
if len(df) == 0:
    st.warning(
        "영화 목록이 없습니다. "
        "KOBIS API에서 해당 날짜의 데이터가 제공되는지 확인해 주세요."
    )
    st.stop()

first_movie = df.iloc[0]


# ---------------------------------------------------------
# 13. 1위 영화 크게 보여주기
# ---------------------------------------------------------
st.subheader("🏆 오늘의 1위")

st.markdown(
    f"## {first_movie['영화명']}"
)

st.caption(
    f"개봉일: {first_movie['개봉일']}  ·  "
    f"순위: {first_movie['순위']}위"
)


# 세 개의 지표 카드를 나란히 표시
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="🎟️ 관객수",
        value=f"{first_movie['관객수']:,}명"
    )

with col2:
    st.metric(
        label="👥 누적관객",
        value=f"{first_movie['누적관객']:,}명"
    )

with col3:
    st.metric(
        label="🎞️ 스크린수",
        value=f"{first_movie['스크린수']:,}개"
    )


st.divider()


# ---------------------------------------------------------
# 14. 관객수 상위 5편 막대그래프
# ---------------------------------------------------------
st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values("관객수", ascending=False)
    .head(5)
    .copy()
)

# 영화명을 인덱스로 사용해 그래프의 항목 이름으로 표시합니다.
chart_data = top5.set_index("영화명")[["관객수"]]

st.bar_chart(
    chart_data,
    horizontal=True
)


# ---------------------------------------------------------
# 15. 전체 박스오피스 표
# ---------------------------------------------------------
st.subheader("🎬 전체 박스오피스")

# 화면에 표시할 때는 숫자를 천 단위 쉼표가 들어간 형태로 표시합니다.
display_df = df.copy()

display_df["순위"] = display_df["순위"].astype(int)

display_df["관객수"] = display_df["관객수"].apply(
    lambda x: f"{x:,}"
)

display_df["누적관객"] = display_df["누적관객"].apply(
    lambda x: f"{x:,}"
)

display_df["스크린수"] = display_df["스크린수"].apply(
    lambda x: f"{x:,}"
)

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# ---------------------------------------------------------
# 16. 데이터 출처 및 캐시 안내
# ---------------------------------------------------------
st.caption(
    "데이터 출처: 영화관입장권통합전산망(KOBIS) 일일 박스오피스 API"
)
import streamlit as st
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd


# =========================================================
# 1. 페이지 기본 설정
# =========================================================

st.set_page_config(
    page_title="일일 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일일 박스오피스")
st.caption("영화진흥위원회(KOBIS) 일일 박스오피스")


# =========================================================
# 2. 한국 시간 기준으로 날짜 계산
# =========================================================
# Streamlit Cloud 서버가 한국 시간이 아닐 수 있으므로
# 서버의 현재 시간을 그대로 사용하지 않습니다.
#
# Asia/Seoul을 지정해서 한국 시간으로 현재 날짜를 구합니다.

KST = ZoneInfo("Asia/Seoul")

now_kst = datetime.now(KST)

# 오늘 날짜에서 하루를 빼면 '어제'가 됩니다.
yesterday = now_kst.date() - timedelta(days=1)


# =========================================================
# 3. 조회 날짜 선택
# =========================================================
# 달력에서 사용자가 원하는 날짜를 선택할 수 있습니다.
#
# 가장 늦게 선택할 수 있는 날짜는 '어제'입니다.
# 따라서 오늘이나 미래 날짜는 선택할 수 없습니다.

selected_date = st.date_input(
    "조회 날짜",
    value=yesterday,
    max_value=yesterday,
    help="오늘은 아직 집계 전이므로 어제까지 선택할 수 있습니다."
)

# KOBIS API가 요구하는 날짜 형식은 yyyymmdd입니다.
target_date = selected_date.strftime("%Y%m%d")


# =========================================================
# 4. KOBIS API 호출 함수
# =========================================================
# 같은 날짜를 다시 조회했을 때 API를 매번 호출하지 않도록
# 결과를 1시간(3,600초) 동안 캐시합니다.
#
# 예:
# 2026년 9월 8일 데이터를 조회하면
# 같은 날짜의 결과는 약 1시간 동안 저장된 결과를 사용합니다.

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    """KOBIS 일일 박스오피스 API를 호출하는 함수"""

    # -----------------------------------------------------
    # Streamlit Secrets에서 인증키 가져오기
    # -----------------------------------------------------
    # 실제 인증키를 코드에 직접 적지 않습니다.
    #
    # Streamlit Cloud:
    # Settings → Secrets
    #
    # KOBIS_KEY = "발급받은 인증키"
    #
    # 형태로 저장합니다.

    try:
        api_key = st.secrets["KOBIS_KEY"]

    except Exception:
        return {
            "success": False,
            "error_type": "secret",
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 Settings → Secrets에서 "
                "KOBIS_KEY가 등록되어 있는지 확인하세요."
            )
        }

    # -----------------------------------------------------
    # KOBIS 공식 API 주소
    # -----------------------------------------------------

    url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
        "boxoffice/searchDailyBoxOfficeList.json"
    )

    # API에 전달할 요청 변수
    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    # -----------------------------------------------------
    # API 요청
    # -----------------------------------------------------

    try:
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류가 있으면 예외를 발생시킵니다.
        response.raise_for_status()

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error_type": "network",
            "message": (
                "KOBIS API 요청 시간이 초과되었습니다.\n\n"
                "잠시 후 다시 시도해 주세요."
            )
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error_type": "network",
            "message": (
                "KOBIS API에 연결하지 못했습니다.\n\n"
                "인터넷 연결이나 KOBIS API 상태를 확인해 주세요.\n\n"
                f"상세 내용: {e}"
            )
        }

    # -----------------------------------------------------
    # JSON 응답으로 변환
    # -----------------------------------------------------

    try:
        data = response.json()

    except ValueError:
        return {
            "success": False,
            "error_type": "json",
            "message": (
                "KOBIS API의 응답을 JSON으로 읽을 수 없습니다.\n\n"
                "KOBIS API가 정상적으로 응답하고 있는지 확인해 주세요."
            )
        }

    # -----------------------------------------------------
    # faultInfo 확인
    # -----------------------------------------------------
    # KOBIS API는 인증키가 틀린 경우에도 HTTP 상태코드가
    # 200으로 올 수 있습니다.
    #
    # 따라서 response.raise_for_status()만으로는
    # 인증 오류를 잡을 수 없습니다.
    #
    # 반드시 faultInfo가 있는지 확인합니다.

    if "faultInfo" in data:

        fault_info = data["faultInfo"]

        fault_code = fault_info.get("errorCode", "")
        fault_message = fault_info.get("errorMessage", "")

        return {
            "success": False,
            "error_type": "api",
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                f"오류 코드: {fault_code}\n"
                f"오류 내용: {fault_message}\n\n"
                "KOBIS_KEY가 정확한지, "
                "Streamlit Cloud의 Secrets에 올바르게 등록되어 "
                "있는지 확인해 주세요."
            )
        }

    # -----------------------------------------------------
    # boxOfficeResult 확인
    # -----------------------------------------------------

    boxoffice_result = data.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "error_type": "data",
            "message": (
                "박스오피스 결과를 찾을 수 없습니다.\n\n"
                "조회 날짜와 KOBIS API 응답을 확인해 주세요."
            )
        }

    # 영화 목록 가져오기
    movie_list = boxoffice_result.get(
        "dailyBoxOfficeList",
        []
    )

    # -----------------------------------------------------
    # 영화 목록이 비어 있는 경우
    # -----------------------------------------------------
    # 사용자가 요청한 문구를 그대로 표시하기 위해
    # 별도의 오류 유형으로 구분합니다.

    if not movie_list:
        return {
            "success": False,
            "error_type": "empty",
            "message": "그날은 아직 집계 전입니다."
        }

    # 정상적으로 영화 목록을 받은 경우
    return {
        "success": True,
        "data": movie_list
    }


# =========================================================
# 5. API 호출
# =========================================================

result = get_boxoffice(target_date)


# =========================================================
# 6. API 오류 처리
# =========================================================

if not result["success"]:

    # 영화 목록이 없는 경우
    if result["error_type"] == "empty":

        st.warning("📭 그날은 아직 집계 전입니다.")

        st.info(
            "다른 날짜를 선택해 주세요. "
            "오늘은 아직 집계가 끝나지 않았기 때문에 "
            "달력에서도 선택할 수 없습니다."
        )

    # 그 밖의 오류
    else:

        st.error(result["message"])

        st.info(
            "확인할 항목\n"
            "• Streamlit Cloud → Settings → Secrets에 KOBIS_KEY가 있는지\n"
            "• KOBIS 인증키가 정확하고 유효한지\n"
            "• 선택한 날짜에 실제 박스오피스 데이터가 있는지\n"
            "• KOBIS API가 일시적으로 장애가 없는지"
        )

    # 오류가 발생하면 아래 화면은 만들지 않습니다.
    st.stop()


# =========================================================
# 7. API 데이터를 DataFrame으로 변환
# =========================================================

movie_list = result["data"]

rows = []

for movie in movie_list:

    # -----------------------------------------------------
    # API에서 숫자도 문자열로 전달됩니다.
    #
    # 예:
    # "rank": "1"
    # "audiCnt": "12345"
    #
    # 따라서 int()를 사용해서 숫자로 변환합니다.
    # -----------------------------------------------------

    rank = int(movie.get("rank", 0))
    rank_inten = int(movie.get("rankInten", 0))
    audi_cnt = int(movie.get("audiCnt", 0))
    audi_acc = int(movie.get("audiAcc", 0))
    scrn_cnt = int(movie.get("scrnCnt", 0))

    movie_name = movie.get("movieNm", "")

    # -----------------------------------------------------
    # 누적관객이 100만 명을 넘은 영화에는
    # 영화명 앞에 트로피 이모지를 붙입니다.
    # -----------------------------------------------------

    if audi_acc > 1_000_000:
        movie_name = f"🏆 {movie_name}"

    # -----------------------------------------------------
    # 순위 변동 표시
    # -----------------------------------------------------
    # rankInten이 양수이면 순위가 올랐다는 뜻입니다.
    # rankInten이 음수이면 순위가 내려갔다는 뜻입니다.
    #
    # 표에서는 색깔이 있는 HTML을 사용합니다.
    #
    # 양수 → 빨간색 위 화살표
    # 음수 → 파란색 아래 화살표
    # 0    → 변화 없음

    if rank_inten > 0:
        rank_change = (
            f'<span style="color:red; font-weight:bold;">'
            f"▲ {rank_inten}"
            f"</span>"
        )

    elif rank_inten < 0:
        rank_change = (
            f'<span style="color:blue; font-weight:bold;">'
            f"▼ {abs(rank_inten)}"
            f"</span>"
        )

    else:
        rank_change = "-"

    rows.append({
        "순위": rank,
        "순위변동": rank_change,
        "영화명": movie_name,
        "개봉일": movie.get("openDt", ""),
        "관객수": audi_cnt,
        "누적관객": audi_acc,
        "스크린수": scrn_cnt
    })


# DataFrame 만들기
df = pd.DataFrame(rows)


# 혹시 API에서 순서가 달라져도
# 순위를 기준으로 정확하게 정렬합니다.
df = df.sort_values(
    "순위",
    ascending=True
).reset_index(drop=True)


# =========================================================
# 8. 조회 날짜 표시
# =========================================================

display_date = selected_date.strftime(
    "%Y년 %m월 %d일"
)

st.subheader(
    f"📅 {display_date} 박스오피스"
)

st.caption(
    "출처: 영화진흥위원회(KOBIS) 일일 박스오피스 API"
)


# =========================================================
# 9. 1위 영화
# =========================================================

first_movie = df.iloc[0]

st.subheader("🏆 1위 영화")

st.markdown(
    f"### {first_movie['영화명']}"
)


# ---------------------------------------------------------
# 1위 영화의 주요 지표 3개
# ---------------------------------------------------------

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="당일 관객수",
        value=f"{first_movie['관객수']:,}명"
    )

with col2:
    st.metric(
        label="누적 관객수",
        value=f"{first_movie['누적관객']:,}명"
    )

with col3:
    st.metric(
        label="스크린수",
        value=f"{first_movie['스크린수']:,}개"
    )


# =========================================================
# 10. 관객수 기준 TOP 5
# =========================================================

st.subheader("🔥 관객수 TOP 5")

# 관객수가 많은 순서로 정렬한 뒤
# 가장 위의 5편만 가져옵니다.

top5 = (
    df.sort_values(
        "관객수",
        ascending=False
    )
    .head(5)
    .copy()
)


# ---------------------------------------------------------
# TOP 5 표
# ---------------------------------------------------------
# 순위와 영화명, 관객수를 간단하게 보여줍니다.

top5_table = top5[
    ["순위", "영화명", "관객수"]
].copy()

# 화면에 표시할 때만 천 단위 쉼표를 붙입니다.
top5_table["관객수"] = top5_table[
    "관객수"
].map(lambda x: f"{x:,}명")

st.dataframe(
    top5_table,
    use_container_width=True,
    hide_index=True
)


# =========================================================
# 11. 관객수 TOP 5 막대그래프
# =========================================================

st.subheader("📊 관객수 TOP 5 그래프")

# 그래프에서는 실제 숫자를 그대로 사용해야 합니다.
# 따라서 위에서 만든 df의 숫자 값을 그대로 사용합니다.

chart_data = (
    top5[
        ["영화명", "관객수"]
    ]
    .set_index("영화명")
)

# Streamlit 기본 막대그래프
st.bar_chart(
    chart_data,
    horizontal=True
)


# =========================================================
# 12. 전체 박스오피스 표
# =========================================================

st.subheader("🎞️ 전체 박스오피스")


# ---------------------------------------------------------
# 화면에 보여 줄 DataFrame을 따로 만듭니다.
# ---------------------------------------------------------
# 원본 df의 숫자 데이터는 숫자로 유지합니다.
# 그래프와 정렬에 사용해야 하기 때문입니다.
#
# 아래 display_df에서는 화면 표시용으로만
# 천 단위 쉼표를 붙입니다.

display_df = df.copy()

display_df["관객수"] = display_df[
    "관객수"
].map(lambda x: f"{x:,}")

display_df["누적관객"] = display_df[
    "누적관객"
].map(lambda x: f"{x:,}")

display_df["스크린수"] = display_df[
    "스크린수"
].map(lambda x: f"{x:,}")


# ---------------------------------------------------------
# HTML을 이용해 순위 변동 화살표의 색상을 표시합니다.
# ---------------------------------------------------------

st.markdown(
    display_df.to_html(
        index=False,
        escape=False,
        classes="dataframe"
    ),
    unsafe_allow_html=True
)


# =========================================================
# 13. 캐시 안내
# =========================================================

st.caption(
    "💡 같은 날짜를 다시 조회하면 약 1시간 동안 "
    "저장된 API 결과를 사용합니다."
)
st.caption(
    "※ 같은 날짜의 API 결과는 약 1시간 동안 캐시되어 재사용됩니다."
)
