import html
import json
import logging
import math
import os
import textwrap
from collections.abc import Mapping

import pandas as pd
import plotly.express as px  # type: ignore
import queries
import streamlit as st  # type: ignore
from sqlalchemy import URL, create_engine

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="IT Jobs Market Dashboard",
    page_icon="📊",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1600px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111827 0%, #0f172a 100%);
        border-right: 1px solid #263247;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #94a3b8;
    }
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #172033 0%, #131c2d 100%);
        border: 1px solid #334155;
        border-top: 3px solid #38bdf8;
        padding: 1rem 1.1rem;
        border-radius: .85rem;
        min-height: 118px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, .16);
    }
    [data-testid="stMetric"] * {color: #f8fafc !important;}
    [data-testid="stMetricValue"] {font-size: 1.8rem; font-weight: 700;}
    [data-testid="stPlotlyChart"] {
        background: rgba(15, 23, 42, .55);
        border: 1px solid #263247;
        border-radius: .85rem;
        padding: .35rem;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid #334155;
        border-radius: .75rem;
        overflow: hidden;
    }
    h1 {letter-spacing: -.035em;}
    h2, h3 {letter-spacing: -.02em;}
    </style>
    <style>
    .dashboard-subtitle {
        color: #94a3b8;
        font-size: 1rem;
        margin-top: -.5rem;
        margin-bottom: 1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

COLORS = {
    "kaggle": "#20BEFF",
    "itviec": "#E54848",
    "topdev": "#F59E0B",
    "topcv": "#00B14F",
    "indeed": "#2164F3",
    "weworkremotely": "#8B5CF6",
    "remoteok": "#EC4899",
}

AGENCY_PATTERN = (
    r"recruit|headhunt|staffing|manpower|nh[âa]n l[ựu]c|tuy[ểe]n d[ụu]ng|"
    r"vi[ệe]c [oơ]i|nh[âa]n s[ựu]|k[ếe]t n[ốo]i nh[âa]n"
)


MARKET_COLORS = {
    "Vietnam": "#FDE047",
    "International": "#2DD4BF",
    "Unknown": "#94A3B8",
}

WORK_COLORS = {
    "Remote": "#A3E635",
    "Hybrid": "#D6A56B",
    "On-site": "#E2E8F0",
    "Unknown": "#64748B",
}


@st.cache_resource
def get_engine():

    supabase_url = os.getenv("SUPABASE_DB_URL")

    if supabase_url:
        return create_engine(
            supabase_url,
            pool_pre_ping=True,
        )

    required = ["POSTGRES_USER", "POSTGRES_PASSWORD"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            f"Missing database environment variables: {', '.join(missing)}"
        )

    url = URL.create(
        "postgresql+psycopg2",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "it_jobs_dw"),
    )
    return create_engine(url, pool_pre_ping=True)


@st.cache_data(ttl=300, show_spinner=False)
def load_data(sql: str) -> pd.DataFrame:
    return pd.read_sql_query(sql, get_engine())


def numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def money(value) -> str:
    return "—" if pd.isna(value) else f"${value:,.0f}"


def coverage_pct(rate) -> str:
    if pd.isna(rate):
        return "—"
    return f"{math.floor(float(rate) * 1000 + 1e-9) / 10:.1f}%"


def display_table(frame: pd.DataFrame, *, floor_rates: bool = False) -> pd.DataFrame:
    result = frame.drop(
        columns=["company_sk", "company_group_key"], errors="ignore"
    ).copy()
    for column in result.columns:
        if column.endswith("_usd"):
            result[column] = result[column].map(money)
        elif column.endswith("_rate") or "_share" in column:
            result[column] = result[column].map(
                coverage_pct
                if floor_rates
                else lambda v: "—" if pd.isna(v) else f"{v:.1%}"
            )
        elif result[column].dtype == object:
            result[column] = result[column].fillna("—")
    return result


def add_sample_size_ticks(
    fig, frame: pd.DataFrame, *, category: str, value: str
) -> None:
    counts = frame.groupby(category)[value].count()
    names = list(frame[category].drop_duplicates())
    fig.update_xaxes(
        tickmode="array",
        tickvals=names,
        ticktext=[f"{name}<br>n={int(counts[name]):,}" for name in names],
    )


NEAR_TIE_GAP = 0.01


def aggregate_company_totals(frame: pd.DataFrame) -> pd.DataFrame:

    label = (
        frame.sort_values("job_count", ascending=False)
        .drop_duplicates("company_group_key")
        .set_index("company_group_key")["company_name"]
    )
    totals = frame.groupby("company_group_key", as_index=False).agg(
        job_count=("job_count", "sum"),
        jobs_with_salary=("jobs_with_salary", "sum"),
        source_count=("source_name", "nunique"),
    )
    totals["company_name"] = totals["company_group_key"].map(label)
    return totals


def lowest_salary_coverage_note(valid_volume: pd.DataFrame) -> str:
    ranked = valid_volume.sort_values("salary_coverage_rate")
    lowest = ranked.iloc[0]
    tail = "Vì vậy average/median salary của nguồn này chỉ phản ánh các tin có hiển thị mức lương."
    if len(ranked) > 1:
        second = ranked.iloc[1]
        if second.salary_coverage_rate - lowest.salary_coverage_rate < NEAR_TIE_GAP:
            return (
                f"{lowest.source_name} ({lowest.salary_coverage_rate:.1%}) và "
                f"{second.source_name} ({second.salary_coverage_rate:.1%}) có tỷ lệ hiển thị "
                "mức lương thấp nhất, gần như ngang nhau. "
                "Vì vậy average/median salary của hai nguồn này chỉ phản ánh các tin có hiển thị mức lương."
            )
    return (
        f"{lowest.source_name} có tỷ lệ hiển thị mức lương thấp nhất "
        f"trong số các nguồn có đủ quy mô mẫu ({lowest.salary_coverage_rate:.1%}). "
        + tail
    )


def thin_single_category_bars(fig) -> None:

    bars = [trace for trace in fig.data if trace.type == "bar"]
    if not bars or (len(bars) > 1 and fig.layout.barmode == "group"):
        return
    axis = "y" if bars[0].orientation == "h" else "x"
    categories = {
        str(value)
        for trace in bars
        for value in (trace[axis] if trace[axis] is not None else [])
    }
    if len(categories) == 1:
        fig.update_traces(width=0.18, selector={"type": "bar"})


def median_order(frame: pd.DataFrame, category: str, value: str) -> list:

    return list(
        frame.groupby(category)[value].median().sort_values(ascending=False).index
    )


def render_chart(fig, *, height: int | None = None) -> None:
    thin_single_category_bars(fig)
    if height is not None:
        fig.update_layout(height=height)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, Segoe UI, sans-serif", "size": 13, "color": "#cbd5e1"},
        title={"font": {"size": 18, "color": "#f8fafc"}, "x": 0.01, "xanchor": "left"},
        legend={"font": {"size": 12}, "title": {"font": {"size": 12}}},
        hoverlabel={"bgcolor": "#111827", "font": {"size": 13, "color": "#f8fafc"}},
    )
    if fig.layout.showlegend is not False and len(fig.data) == 1:
        fig.update_layout(showlegend=False)
    elif fig.layout.showlegend is not False and len(fig.data) > 1:
        fig.update_layout(
            legend={
                "orientation": "h",
                "yanchor": "top",
                "y": -0.2,
                "xanchor": "center",
                "x": 0.5,
            },
            margin={"b": 110},
        )
    fig.update_xaxes(
        gridcolor="rgba(148,163,184,.16)", zerolinecolor="rgba(148,163,184,.25)"
    )
    fig.update_yaxes(
        gridcolor="rgba(148,163,184,.16)", zerolinecolor="rgba(148,163,184,.25)"
    )
    st.plotly_chart(
        fig,
        width="stretch",
        config={"displaylogo": False, "responsive": True},
    )


def format_horizontal_bar_axis(fig, labels, *, wrap_width: int = 46):
    """Giữ cho mọi nhãn trên trục y dạng phân loại đều hiển thị, kể cả những nhãn có tên dài."""
    raw_labels = [str(label) for label in labels if pd.notna(label)]
    wrapped_labels = [
        "<br>".join(
            html.escape(line)
            for line in textwrap.wrap(
                label,
                width=wrap_width,
                break_long_words=False,
                break_on_hyphens=False,
            )
        )
        for label in raw_labels
    ]
    label_line_count = sum(max(1, label.count("<br>") + 1) for label in wrapped_labels)

    fig.update_layout(
        height=max(420, 130 + label_line_count * 24),
        margin={"l": 20, "r": 20, "t": 70, "b": 50},
    )
    fig.update_yaxes(
        automargin=True,
        tickmode="array",
        tickvals=raw_labels,
        ticktext=wrapped_labels,
        ticklabeloverflow="allow",
    )
    return fig


SALARY_LOG_TICKS = [
    1_000,
    2_000,
    5_000,
    10_000,
    20_000,
    50_000,
    100_000,
    200_000,
    500_000,
]


def format_salary_log_axis(fig) -> None:
    fig.update_yaxes(
        tickmode="array",
        tickvals=SALARY_LOG_TICKS,
        ticktext=[f"${tick:,.0f}" for tick in SALARY_LOG_TICKS],
    )


LANGUAGE_REQUIREMENTS = {"english": "Tiếng Anh"}


def lead_skills(
    frame: pd.DataFrame, name_column: str, count_column: str
) -> tuple[pd.DataFrame, str]:
    """Drop language requirements from a skill ranking sorted by demand.

    Returns the technical-skill rows (original order) and, when a language
    requirement was ranked first, a sentence that says so.
    """
    is_language = frame[name_column].astype(str).str.lower().isin(LANGUAGE_REQUIREMENTS)
    technical = frame[~is_language]
    if frame.empty or technical.empty or not is_language.iloc[0]:
        return frame, ""
    top = frame.iloc[0]
    label = LANGUAGE_REQUIREMENTS[str(top[name_column]).lower()]
    return technical, (
        f"{label} cũng được yêu cầu nhiều trong các tin tuyển dụng "
        f"({int(top[count_column]):,} tin, nhiều hơn mọi kỹ năng chuyên môn), "
        "nhưng là yêu cầu ngôn ngữ nên không xếp chung với kỹ năng chuyên môn. "
        "Về kỹ năng chuyên môn, "
    )


def leader_phrase(first_value: float, second_value: float | None) -> str:
    if second_value and first_value / second_value < 1.05:
        return "dẫn đầu sát nút (chênh lệch dưới 5%)"
    return "lớn nhất"


def filter_market_year_and_sources(
    data: pd.DataFrame, *, key_prefix: str
) -> pd.DataFrame:
    years = sorted(data["market_year"].dropna().astype(int).unique())
    if not years:
        return data.iloc[0:0]

    year = st.selectbox(
        "Market year",
        years,
        index=len(years) - 1,
        key=f"{key_prefix}_year",
    )
    st.caption(
        "Phạm vi: các tin tuyển dụng thu thập trong năm 2026. Kaggle (historical 2024–04/2025)."
    )
    yearly = data[data["market_year"] == year]
    sources = sorted(yearly["source_name"].dropna().unique())
    selected_sources = st.multiselect(
        "Sources",
        sources,
        default=sources,
        key=f"{key_prefix}_sources",
    )
    return yearly[yearly["source_name"].isin(selected_sources)]


def weighted_average(frame: pd.DataFrame, value: str, weight: str):
    valid = frame[value].notna() & frame[weight].notna() & (frame[weight] > 0)  # type: ignore
    if not valid.any():
        return None
    return (frame.loc[valid, value] * frame.loc[valid, weight]).sum() / frame.loc[
        valid, weight
    ].sum()


def show_insights(insights: list[str]) -> None:
    clean_insights = [insight for insight in insights if insight]
    if not clean_insights:
        return
    with st.container(border=True):
        st.markdown("#### Phân tích nhanh")
        for insight in clean_insights:
            st.markdown(f"- {insight}".replace("$", "\\$"))


def show_empty_state(message: str) -> None:
    """Hiển thị thông báo trạng thái trống khi kho dữ liệu mới chưa có bản ghi nào."""
    st.info(message)


# --- Insight sentences ------------------------------------------------
# Văn bản insight động theo số liệu thực tế để tránh sai lệch thông tin.

DOMINANT_COUNTRY_SHARE = 0.5


def country_dominance_note(top_share: float) -> str:
    if top_share >= DOMINANT_COUNTRY_SHARE:
        return "Dataset bị chi phối bởi quốc gia này nên các chỉ số tổng hợp phản ánh chủ yếu thị trường đó."
    return "Điều này cho thấy dataset không bị chi phối hoàn toàn bởi một quốc gia duy nhất."


def recent_skill_note(
    leading_skill: str, recent_skill: str, recent_jobs: int, recent_sources: int
) -> str:
    base = (
        f"Trong cửa sổ 30 ngày gần nhất, {recent_skill} dẫn đầu với "
        f"{recent_jobs:,} tin tuyển dụng trên {recent_sources:,} nguồn dữ liệu. "
    )
    if recent_skill == leading_skill:
        return base + (
            "Skill này đứng đầu cả trong toàn bộ năm 2026 lẫn cửa sổ gần đây, "
            "cho thấy nhu cầu ổn định theo thời gian."
        )
    return base + (
        f"Skill này khác với skill dẫn đầu cả năm 2026 ({leading_skill}); "
        "khác biệt có thể đến từ cơ cấu nguồn: cửa sổ gần đây chỉ gồm các nguồn dữ liệu có ngày đăng thật."
    )


def international_salary_note(scope_salary: Mapping[str, float | None]) -> str | None:
    """So sánh lương trung bình có trọng số giữa thị trường Quốc tế và Việt Nam."""
    vietnam = scope_salary.get("Vietnam")
    international = scope_salary.get("International")
    if not vietnam or not international or vietnam <= 0:
        return None
    change = (international / vietnam - 1) * 100
    caveat = (
        "Tuy nhiên, con số này chưa phản ánh bản chất chênh lệch thu nhập thực tế do có sự khác biệt lớn về yếu tố địa lý (geography), cấp bậc (seniority) "
        "và tỷ trọng các nguồn dữ liệu (source mix) giữa hai nhóm."
    )
    if abs(change) < 1:
        return f"Salary quan sát được của International xấp xỉ Vietnam. {caveat}"
    ratio = international / vietnam
    if ratio >= 2:
        comparison = f"gấp khoảng {ratio:.1f} lần Vietnam"
    else:
        direction = "cao hơn" if change > 0 else "thấp hơn"
        comparison = f"{direction} Vietnam khoảng {abs(change):.0f}%"
    return f"Salary trung bình quan sát được của International {comparison}. {caveat}"


def overview_page():
    kpis = numeric(
        load_data(queries.OVERVIEW_KPIS),
        [
            "total_jobs",
            "source_count",
            "company_count",
            "location_count",
            "jobs_with_salary",
        ],
    ).iloc[0]
    country = numeric(
        load_data(queries.JOBS_BY_COUNTRY), ["total_jobs", "salary_coverage_rate"]
    )
    salary = numeric(
        load_data(queries.SALARY_BY_SOURCE),
        [
            "total_jobs",
            "jobs_with_salary",
            "avg_salary_usd",
            "median_salary_usd",
            "salary_coverage_rate",
        ],
    )
    hot = numeric(load_data(queries.HOT_SKILLS), ["job_count"])

    st.subheader("Market overview")
    st.caption("Phạm vi: Tin tuyển dụng thu thập trong năm 2026.")
    last_crawled = pd.to_datetime(kpis.last_crawled_at, errors="coerce")
    latest_posted = pd.to_datetime(kpis.latest_posted_date, errors="coerce")
    freshness_parts = []
    if pd.notna(last_crawled):
        freshness_parts.append(f"Last crawled: {last_crawled:%d %b %Y, %H:%M UTC}")
    if pd.notna(latest_posted):
        freshness_parts.append(f"Latest posting: {latest_posted:%d %b %Y}")
    if freshness_parts:
        st.caption("  ·  ".join(freshness_parts))

    cols = st.columns(5)
    cols[0].metric("Jobs", f"{int(kpis.total_jobs):,}")
    cols[1].metric("Sources", f"{int(kpis.source_count):,}")
    cols[2].metric("Companies", f"{int(kpis.company_count):,}")
    cols[3].metric("Locations", f"{int(kpis.location_count):,}")
    coverage = kpis.jobs_with_salary / kpis.total_jobs if kpis.total_jobs else 0
    cols[4].metric("Salary coverage", f"{coverage:.1%}")

    if not kpis.total_jobs or country.empty or hot.empty:
        show_empty_state(
            "No job data is available yet. Run the ingestion and dbt pipeline, "
            "then refresh this page."
        )
        return

    top_country = country.iloc[0]
    second_country = country.iloc[1] if len(country) > 1 else None
    technical_hot, language_note = lead_skills(
        hot.sort_values("job_count", ascending=False, kind="stable"),
        "skill_name",
        "job_count",
    )
    top_skill = technical_hot.iloc[0]
    show_insights(
        [
            (
                f"{top_country.country} là thị trường có số lượng tin tuyển dụng "
                + leader_phrase(
                    top_country.total_jobs,
                    second_country.total_jobs if second_country is not None else None,
                )
                + f" với {int(top_country.total_jobs):,} tin tuyển dụng ({top_country.total_jobs / kpis.total_jobs:.1%} tổng dữ liệu). "
                + country_dominance_note(top_country.total_jobs / kpis.total_jobs)
            ),
            (
                f"{language_note}{top_skill.skill_name} là kỹ năng được yêu cầu nhiều nhất trong 30 ngày gần nhất với "
                f"{int(top_skill.job_count):,} tin tuyển dụng. Chỉ số này chỉ tính toán trên các nguồn có ngày đăng thực tế."
            ),
            f"Tỷ lệ hiển thị mức lương (Salary Coverage) của các nguồn crawl là {coverage:.1%} ({int(kpis.jobs_with_salary):,}/{int(kpis.total_jobs):,} tin tuyển dụng).",
            (
                "Trang này tập trung vào dữ liệu thu thập của năm 2026; không dùng để kết luận về tăng trưởng thị trường theo thời gian."
            ),
        ]
    )

    left, right = st.columns(2)
    with left:
        fig = px.bar(
            country.head(12),
            x="total_jobs",
            y="country",
            orientation="h",
            title="Jobs by country",
        )
        fig.update_layout(
            yaxis={"categoryorder": "total ascending"},
            xaxis_title="Jobs",
            yaxis_title=None,
        )
        format_horizontal_bar_axis(fig, country.head(12)["country"])
        render_chart(fig, height=440)
    with right:
        median_salary = salary[salary["median_salary_usd"].notna()]
        median_salary = median_salary.sort_values("median_salary_usd", ascending=False)
        median_salary = median_salary.assign(
            bar_label=median_salary.apply(
                lambda row: (
                    f"${row['median_salary_usd']:,.0f}<br>n={row['jobs_with_salary']:,}"
                ),
                axis=1,
            )
        )
        fig = px.bar(
            median_salary,
            x="source_name",
            y="median_salary_usd",
            color="source_name",
            color_discrete_map=COLORS,
            text="bar_label",
            log_y=True,
            title="Median annual salary by source (USD, log scale)",
            labels={"median_salary_usd": "USD/year (log)", "source_name": "Source"},
        )
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_layout(showlegend=False, margin={"r": 40})
        fig.update_xaxes(automargin=True)
        low = median_salary["median_salary_usd"].min()
        high = median_salary["median_salary_usd"].max()
        ticks = [
            value
            for value in (5_000, 10_000, 20_000, 50_000, 100_000, 200_000, 500_000)
            if low / 2 <= value <= high * 2
        ]
        fig.update_yaxes(
            tickvals=ticks,
            ticktext=[f"${value // 1000}k" for value in ticks],
            minor={"showgrid": False, "ticks": ""},
            range=[math.log10(low / 2), math.log10(high * 1.8)],
        )
        render_chart(fig, height=440)

    hot_chart = hot.head(15).sort_values("job_count")
    fig = px.bar(
        hot_chart,
        x="job_count",
        y="skill_name",
        orientation="h",
        title="Top 15 skills — latest 30-day window",
    )
    fig.update_layout(xaxis_title="Jobs", yaxis_title=None)
    format_horizontal_bar_axis(fig, hot_chart["skill_name"])
    render_chart(fig)


def market_page():
    data = numeric(
        load_data(queries.MARKET_OVERVIEW),
        ["job_count", "company_count", "salary_disclosure_rate"],
    )
    data["posted_date"] = pd.to_datetime(data["posted_date"], errors="coerce")
    sources = sorted(data["source_name"].dropna().unique())
    selected = st.multiselect("Sources", sources, default=sources)
    filtered = data[data["source_name"].isin(selected)]

    st.subheader("Job market")
    st.caption("Phạm vi: Tin tuyển dụng thu thập trong năm 2026.")

    if filtered.empty:
        show_empty_state("No job market data is available for the selected sources.")
        return

    by_country = (
        filtered.groupby("country", dropna=False, as_index=False)["job_count"]
        .sum()
        .sort_values("job_count", ascending=False)  # type: ignore
        .head(15)
    )
    source_totals = (
        filtered.groupby("source_name", as_index=False)["job_count"]
        .sum()
        .sort_values("job_count", ascending=False)
    )  # type: ignore
    top_source = source_totals.iloc[0]
    top_country = by_country.iloc[0]
    show_insights(
        [
            (
                f"{top_source.source_name} đóng góp nhiều nhất trong bộ lọc hiện tại, "
                f"với {int(top_source.job_count):,} tin tuyển dụng."
            ),
            (
                f"{top_country.country} là quốc gia có số lượng tin tuyển dụng "
                + leader_phrase(
                    top_country.job_count,
                    by_country.iloc[1].job_count if len(by_country) > 1 else None,
                )
                + f" trong phạm vi đang chọn, với {int(top_country.job_count):,} tin."
            ),
        ]
    )
    dated = filtered[~filtered["posted_date_is_estimated"].astype(bool)]
    excluded_jobs = int(
        filtered.loc[
            filtered["posted_date_is_estimated"].astype(bool), "job_count"
        ].sum()
    )
    monthly = dated.assign(
        month=dated["posted_date"].dt.to_period("M").dt.to_timestamp()
    )
    monthly = monthly.groupby(["month", "source_name"], as_index=False)[
        "job_count"
    ].sum()
    if monthly.empty:
        st.info("Không có job nào có ngày đăng thật trong bộ lọc hiện tại.")
    else:
        fig = px.line(
            monthly,
            x="month",
            y="job_count",
            color="source_name",
            markers=True,
            color_discrete_map=COLORS,
            title="Job postings per month",
        )
        fig.update_layout(xaxis_title=None, yaxis_title="Jobs", legend_title="Source")
        fig.update_xaxes(
            range=[
                monthly["month"].min() - pd.Timedelta(days=15),
                monthly["month"].max() + pd.Timedelta(days=15),
            ]
        )
        render_chart(fig)
        last_posted = dated["posted_date"].max()
        if pd.notna(last_posted) and last_posted.day < last_posted.days_in_month:
            st.caption(
                f"Dữ liệu tháng {last_posted:%m/%Y} hiện tại mới được cập nhật đến ngày {last_posted:%d/%m}, "
                "do đó số liệu của tháng này chưa phản ánh đầy đủ cả tháng."
            )
        if excluded_jobs:
            st.caption(
                f"Có {excluded_jobs:,} tin tuyển dụng có ngày đăng ước tính "
                "được chủ động loại bỏ khỏi biểu đồ xu hướng thời gian này, nhưng vẫn được tính toán trong các biểu đồ phân tích khác."
            )

    fig = px.bar(
        by_country.sort_values("job_count"),
        x="job_count",
        y="country",
        orientation="h",
        title="Top countries",
    )
    fig.update_layout(xaxis_title="Jobs", yaxis_title=None)
    format_horizontal_bar_axis(fig, by_country.sort_values("job_count")["country"])
    render_chart(fig)


def salary_page():
    summary = numeric(
        load_data(queries.SALARY_BY_SOURCE),
        [
            "total_jobs",
            "jobs_with_salary",
            "salary_coverage_rate",
            "avg_salary_min_usd",
            "avg_salary_usd",
            "avg_salary_max_usd",
            "median_salary_usd",
        ],
    )
    detail = numeric(load_data(queries.SALARY_BENCHMARK), ["salary_mid_usd"])

    st.subheader("Salary benchmark")
    st.caption(
        "Mức lương đã được chuẩn hóa về đơn vị USD/năm. Phạm vi: Tin tuyển dụng thu thập trong năm 2026."
    )
    if summary.empty:
        show_empty_state(
            "No salary data is available yet. Run the ingestion and dbt pipeline, "
            "then refresh this page."
        )
        return

    salary_sources = summary[
        summary["avg_salary_usd"].notna()
        & summary["median_salary_usd"].notna()
        & (summary["jobs_with_salary"] > 0)
    ].copy()
    if salary_sources.empty:
        show_empty_state(
            "Jobs are available, but no disclosed salary observations can be "
            "benchmarked yet."
        )
        return

    highest_salary = salary_sources.loc[salary_sources["avg_salary_usd"].idxmax()]  # type: ignore
    best_coverage = summary.loc[summary["salary_coverage_rate"].idxmax()]  # type: ignore
    salary_sources["avg_median_gap"] = (
        salary_sources["avg_salary_usd"] - salary_sources["median_salary_usd"]
    ).abs() / salary_sources["median_salary_usd"].where(
        salary_sources["median_salary_usd"] > 0
    )
    skew_candidates = salary_sources[salary_sources["avg_median_gap"].notna()]
    most_skewed = (
        skew_candidates.loc[skew_candidates["avg_median_gap"].idxmax()]  # type: ignore
        if not skew_candidates.empty
        else None
    )
    show_insights(
        [
            (
                f"{highest_salary.source_name} có average salary quan sát được cao nhất, "
                f"khoảng {money(highest_salary.avg_salary_usd)}/năm, "
                f"với median ở mức {money(highest_salary.median_salary_usd)}."
            ),
            (
                f"{best_coverage.source_name} có tỷ lệ hiển thị mức lương cao nhất "
                f"({best_coverage.salary_coverage_rate:.1%}; "
                f"{int(best_coverage.jobs_with_salary):,}/{int(best_coverage.total_jobs):,} tin). "
                "Tỷ lệ này chỉ đo mức độ hiển thị và tính cả mức lương do nền tảng ước tính (ví dụ Indeed), "
                "nên không cho biết mức lương đó do nhà tuyển dụng công bố hay đáng tin cậy hơn."
            ),
            (
                f"{most_skewed.source_name} có chênh lệch tương đối giữa average và median lớn nhất "
                f"({most_skewed.avg_median_gap:.0%}: average {money(most_skewed.avg_salary_usd)} "
                f"so với median {money(most_skewed.median_salary_usd)}), "
                "gợi ý phân phối tiền lương bị phân hóa mạnh hoặc đang bị gộp chung nhiều nhóm dải lương khác nhau "
                "(ví dụ tin tuyển dụng tại Việt Nam và tin tuyển dụng quốc tế xuất hiện trong cùng một nguồn)."
                if most_skewed is not None
                else ""
            ),
            (
                "Không nên xếp hạng các nguồn tuyển dụng chỉ dựa trên tiêu chí mức lương. "
                "Các yếu tố như vị trí địa lý, cấp bậc, cơ cấu vị trí công việc, quy mô mẫu và tỷ lệ hiển thị lương đều tác động trực tiếp đến "
                "average/median salary quan sát được."
            ),
        ]
    )
    fig = px.box(
        detail,
        x="source_name",
        y="salary_mid_usd",
        color="source_name",
        color_discrete_map=COLORS,
        category_orders={
            "source_name": median_order(detail, "source_name", "salary_mid_usd")
        },
        points=False,
        log_y=True,
        title="Salary distribution by source (log scale, sorted by median)",
    )
    fig.update_layout(xaxis_title="Source", yaxis_title="USD/year", showlegend=False)
    format_salary_log_axis(fig)
    add_sample_size_ticks(fig, detail, category="source_name", value="salary_mid_usd")
    render_chart(fig)

    display = summary.copy()
    display["salary_coverage"] = display["salary_coverage_rate"].map(
        lambda value: f"{value:.1%}"
    )
    for column in [
        "avg_salary_min_usd",
        "avg_salary_usd",
        "avg_salary_max_usd",
        "median_salary_usd",
    ]:
        display[column] = display[column].map(money)
    st.dataframe(
        display[
            [
                "source_name",
                "total_jobs",
                "jobs_with_salary",
                "salary_coverage",
                "avg_salary_usd",
                "median_salary_usd",
            ]
        ],
        width="stretch",
        hide_index=True,
    )


def skills_page():
    skills = numeric(
        load_data(queries.JOBS_BY_SKILL),
        [
            "total_jobs",
            "itviec_jobs",
            "topdev_jobs",
            "topcv_jobs",
            "indeed_jobs",
            "avg_salary_usd",
        ],
    )
    hot = numeric(
        load_data(queries.HOT_SKILLS), ["job_count", "source_count", "avg_salary_usd"]
    )

    st.subheader("Skills demand")
    if skills.empty:
        show_empty_state(
            "No skill-demand data is available yet. Run the ingestion and dbt "
            "pipeline, then refresh this page."
        )
        return

    st.caption(
        "Phạm vi: Tin tuyển dụng thu thập trong năm 2026. "
        "Bảng 30 ngày gần nhất bên dưới chỉ gồm các tin tuyển dụng có ngày đăng thật."
    )
    top_n = st.slider("Number of skills", 10, 50, 15, 5)
    top = skills.head(top_n).sort_values("total_jobs")
    technical_skills, language_note = lead_skills(
        skills.sort_values("total_jobs", ascending=False, kind="stable"),
        "skill_name",
        "total_jobs",
    )
    technical_hot, _ = lead_skills(
        hot.sort_values("job_count", ascending=False, kind="stable"),
        "skill_name",
        "job_count",
    )
    technical_ranking = technical_skills[
        ~technical_skills["skill_name"]
        .astype(str)
        .str.lower()
        .isin(LANGUAGE_REQUIREMENTS)
    ]
    if technical_ranking.empty:
        technical_ranking = technical_skills
    leading_skill = technical_ranking.iloc[0]
    second_skill = technical_ranking.iloc[1] if len(technical_ranking) > 1 else None
    recent_top_skill = technical_hot.iloc[0] if not technical_hot.empty else None

    top5_jobs = skills.head(5)["total_jobs"].sum()
    top15_jobs = skills.head(15)["total_jobs"].sum()
    show_insights(
        [
            (
                f"{language_note}{leading_skill.skill_name} là kỹ năng được yêu cầu nhiều nhất với "
                f"{int(leading_skill.total_jobs):,} tin tuyển dụng."
                + (
                    f" {second_skill.skill_name} là kỹ năng cũng được yêu cầu nhiều với "
                    f"{int(second_skill.total_jobs):,} tin."
                    if second_skill is not None
                    else ""
                )
            ),
            (
                "Skill là dữ liệu multi-label: một tin tuyển dụng có thể yêu cầu nhiều kỹ năng cùng lúc."
            ),
            (
                f"Top 5 skills chiếm {top5_jobs / top15_jobs:.1%} tổng số lượt xuất hiện "
                "trong Top 15 (tính theo lượt skill, không phải theo số lượng tin tuyển dụng)."
                if top15_jobs
                else ""
            ),
            (
                recent_skill_note(
                    str(leading_skill.skill_name),
                    str(recent_top_skill.skill_name),
                    int(recent_top_skill.job_count),
                    int(recent_top_skill.source_count),
                )
                if recent_top_skill is not None
                else ""
            ),
        ]
    )
    fig = px.bar(
        top,
        x="total_jobs",
        y="skill_name",
        orientation="h",
        title="Most requested skills",
    )
    fig.update_layout(xaxis_title="Jobs", yaxis_title=None)
    format_horizontal_bar_axis(fig, top["skill_name"])
    render_chart(fig)
    st.dataframe(display_table(hot), width="stretch", hide_index=True)


def trends_page():
    data = numeric(
        load_data(queries.SKILL_TRENDS_BY_YEAR),
        [
            "market_year",
            "total_jobs",
            "overall_avg_salary_usd",
            "job_count",
            "demand_rate",
            "jobs_with_salary",
            "salary_coverage_rate",
            "avg_salary_usd",
            "median_salary_usd",
        ],
    )

    st.subheader("Skill and salary trends by year")
    st.caption(
        "Nhóm 2026 tổng hợp từ các tin tuyển dụng thu thập (crawl) thực tế trong năm 2026. "
        "Nhóm Kaggle historical dùng toàn bộ tập dữ liệu lịch sử (2024–04/2025), gộp cả hai năm. "
        "Hai nhóm (cohort) được phân tích độc lập. Nhãn năm của nhóm Kaggle ở trang này "
        "không trùng với bộ lọc Market year ở các trang khác, nơi Kaggle được tách theo năm đăng (2024 và 2025)."
    )
    tab_years = [2026, 2025]
    tabs = st.tabs(["2026 — Crawled IT sources", "Kaggle historical (2024–04/2025)"])

    for tab, year in zip(tabs, tab_years):
        with tab:
            yearly = data[data["market_year"] == year].copy()
            if yearly.empty:
                st.warning(f"No data available for {year}.")
                continue

            cols = st.columns(3)
            cols[0].metric("Jobs", f"{int(yearly.iloc[0].total_jobs):,}")
            cols[1].metric("Skills", f"{yearly.skill_name.nunique():,}")
            cols[2].metric(
                "Overall mean salary", money(yearly.iloc[0].overall_avg_salary_usd)
            )

            technical_yearly, language_note = lead_skills(
                yearly.sort_values("job_count", ascending=False, kind="stable"),
                "skill_name",
                "job_count",
            )
            top_demand_row = technical_yearly.iloc[0]
            demand = yearly.nlargest(15, "job_count").sort_values("job_count")
            salary = (
                yearly[yearly["median_salary_usd"].notna()]
                .nlargest(15, "job_count")
                .sort_values("median_salary_usd")
            )
            top_salary_row = (
                salary.loc[salary["median_salary_usd"].idxmax()]  # type: ignore
                if not salary.empty
                else None
            )
            salary_spread = (
                salary["median_salary_usd"].max() - salary["median_salary_usd"].min()
                if not salary.empty
                else None
            )
            period_label = (
                "Kaggle historical (2024–04/2025)" if year == 2025 else "năm 2026"
            )
            chart_period = (
                "Kaggle historical (2024–04/2025)" if year == 2025 else "2026"
            )
            median_of_medians = (
                salary["median_salary_usd"].median() if not salary.empty else None
            )
            salary_gap_is_noise = bool(
                salary_spread is not None
                and median_of_medians
                and salary_spread / median_of_medians < 0.10
            )
            show_insights(
                [
                    (
                        f"{language_note}{top_demand_row.skill_name} dẫn đầu về nhu cầu tuyển dụng trong {period_label} với "
                        f"{int(top_demand_row.job_count):,} tin tuyển dụng "
                        f"({top_demand_row.demand_rate:.1%} tổng nhóm dữ liệu)."
                    ),
                    (
                        f"Trong Top 15 skill theo nhu cầu, {top_salary_row.skill_name} có median salary cao nhất, "
                        f"khoảng {money(top_salary_row.median_salary_usd)}/năm "
                        f"(n={int(top_salary_row.jobs_with_salary):,} tin có hiển thị lương)."
                        if top_salary_row is not None and not salary_gap_is_noise
                        else ""
                    ),
                    (
                        f"Median salary gần như không khác biệt giữa các skill trong Top 15 "
                        f"(chênh {money(salary_spread)}, dưới 10% median), nên không dùng thu nhập để xếp hạng skill."
                        if salary_gap_is_noise
                        else (
                            f"Median cao nhất và thấp nhất trong Top 15 skill chênh nhau {money(salary_spread)}. "
                            "Con số này chỉ mô tả độ phân tán của median, không đủ để kết luận "
                            "về quan hệ giữa nhu cầu tuyển dụng và mức lương."
                            if salary_spread is not None
                            else ""
                        )
                    ),
                    (
                        "Median theo skill chưa tách yếu tố địa lý: tin tuyển dụng Việt Nam và quốc tế được tính chung, "
                        "nên skill xuất hiện nhiều trong các tin quốc tế sẽ có median cao hơn. "
                        "Vì vậy chênh lệch này có thể phản ánh cơ cấu nguồn dữ liệu chứ chưa phải giá trị riêng của từng skill. "
                        "Xem trang Vietnam vs international để so sánh theo thị trường."
                        if year != 2025 and not salary_gap_is_noise
                        else ""
                    ),
                    (
                        f"Nhóm {period_label} được phân tích độc lập với nhóm còn lại. "
                        "Do quy mô mẫu (population) và cơ cấu nguồn dữ liệu (source composition) khác nhau rất lớn, "
                        "không nên diễn giải chênh lệch giữa Kaggle historical và năm 2026 như một chỉ số tăng trưởng."
                    ),
                ]
            )

            demand = yearly.nlargest(15, "job_count").sort_values("job_count")
            fig = px.bar(
                demand,
                x="job_count",
                y="skill_name",
                orientation="h",
                title=f"Top skill demand — {chart_period}",
                labels={"job_count": "Jobs", "skill_name": "Skill"},
            )
            format_horizontal_bar_axis(fig, demand["skill_name"])
            render_chart(fig)

            salary = salary.assign(
                n_label=salary["jobs_with_salary"].map(lambda v: f"n={int(v):,}")  # type: ignore
            )
            fig = px.bar(
                salary,
                x="median_salary_usd",
                y="skill_name",
                orientation="h",
                text="n_label",
                title=f"Median annual salary for top-demanded skills — {chart_period}",
                labels={"median_salary_usd": "USD/year", "skill_name": "Skill"},
            )
            fig.update_traces(textposition="outside")
            format_horizontal_bar_axis(fig, salary["skill_name"])
            render_chart(fig)

            st.dataframe(
                display_table(
                    yearly[
                        [
                            "skill_name",
                            "job_count",
                            "demand_rate",
                            "jobs_with_salary",
                            "salary_coverage_rate",
                            "avg_salary_usd",
                            "median_salary_usd",
                        ]
                    ]
                ),
                width="stretch",
                hide_index=True,
            )


def companies_page():
    data = numeric(
        load_data(queries.COMPANY_HIRING),
        ["job_count", "active_location_count", "jobs_with_salary", "avg_salary_usd"],
    )
    hide_agency = st.checkbox(
        "Ẩn agency/headhunter (nhận diện theo tên công ty)",
        value=True,
        help="Heuristic theo từ khóa trong tên công ty (recruit, headhunt, nhân lực, tuyển dụng, việc ơi, ...).",
    )
    if hide_agency:
        data = data[
            ~data["company_name"].str.contains(
                AGENCY_PATTERN, case=False, regex=True, na=False
            )
        ]
    if "company_group_key" not in data.columns:
        data = data.assign(
            company_group_key=data["company_name"].str.lower().str.strip()
        )
    sources = sorted(data["source_name"].unique())
    source = st.selectbox("Source", ["All", *sources])
    filtered = data if source == "All" else data[data["source_name"] == source]
    if filtered.empty:
        st.subheader("Company hiring")
        show_empty_state("No company hiring data is available for the selected source.")
        return

    if source == "All":
        top = (
            filtered.sort_values(["source_name", "job_count"], ascending=[True, False])
            .groupby("source_name", group_keys=False)
            .head(5)
            .copy()
        )
        chart_title = "Top 5 hiring companies per source"
    else:
        top = filtered.nlargest(20, "job_count").copy()
        chart_title = f"Top hiring companies — {source}"

    top["company_label"] = top["company_name"] + " · " + top["source_name"]  # type: ignore
    top = top.sort_values("job_count")

    st.subheader("Company hiring")
    st.caption("Phạm vi: Tin tuyển dụng thu thập trong năm 2026.")
    leading_company = filtered.loc[filtered["job_count"].idxmax()]  # type: ignore
    merged_sources = 1
    if source == "All":
        company_totals = aggregate_company_totals(filtered)
        if not company_totals.empty:
            leading_company = company_totals.loc[company_totals["job_count"].idxmax()]  # type: ignore
            merged_sources = int(leading_company.source_count)  # type: ignore
    company_scope = "trên toàn bộ các nguồn" if source == "All" else f"ở nguồn {source}"
    show_insights(
        [
            (
                f"{leading_company.company_name} có nhiều tin tuyển dụng nhất {company_scope}, "
                f"với {int(leading_company.job_count):,} tin"  # type: ignore
                + (f" (gộp từ {merged_sources} nguồn)." if merged_sources > 1 else ".")
            ),
            (
                f"Trong số đó, {int(leading_company.jobs_with_salary):,} tin có hiển thị mức lương."
            ),
            (
                "Khi phân tích xu hướng tuyển dụng của doanh nghiệp, nên lọc (filter) theo từng nguồn dữ liệu hoặc thị trường cụ thể "
                "để tránh so sánh trực tiếp giữa các nguồn có phương pháp lấy mẫu (sampling methodology) khác nhau."
            ),
            (
                "Số tin tuyển dụng phản ánh số tin quan sát được trên các nền tảng, không đại diện cho chỉ tiêu tuyển dụng thực tế. "
                "Một công ty có thể đăng lại cùng một vị trí hoặc đăng đồng thời trên nhiều nguồn (cross-post) nên bị đếm trùng."
            ),
        ]
    )
    fig = px.bar(
        top,
        x="job_count",
        y="company_label",
        orientation="h",
        color="source_name",
        color_discrete_map=COLORS,
        title=chart_title,
    )
    fig.update_layout(xaxis_title="Jobs", yaxis_title=None)
    format_horizontal_bar_axis(fig, top["company_label"])
    render_chart(fig)
    st.dataframe(display_table(filtered.head(100)), width="stretch", hide_index=True)


def domestic_international_page():
    data = numeric(
        load_data(queries.DOMESTIC_VS_INTERNATIONAL),
        [
            "market_year",
            "job_count",
            "company_count",
            "location_count",
            "country_count",
            "jobs_with_salary",
            "avg_salary_usd",
            "median_salary_usd",
            "job_share_within_source_year",
            "salary_coverage_rate",
        ],
    )

    st.subheader("Vietnam vs international jobs")
    st.caption(
        "ITviec, TopCV và TopDev đại diện cho thị trường việc làm Việt Nam. "
        "Các nguồn quốc tế (global sources) được phân loại dựa trên quốc gia của tin tuyển dụng; trong đó nguồn thu thập và năm dữ liệu luôn được giữ tách biệt."
    )
    filtered = filter_market_year_and_sources(data, key_prefix="market_scope")
    if filtered.empty:
        st.warning("No jobs match the selected filters.")
        return

    total_jobs = int(filtered["job_count"].sum())
    jobs_with_salary = int(filtered["jobs_with_salary"].sum())
    avg_salary = weighted_average(filtered, "avg_salary_usd", "jobs_with_salary")
    vietnam_jobs = int(
        filtered.loc[filtered["market_scope"] == "Vietnam", "job_count"].sum()
    )

    cols = st.columns(4)
    cols[0].metric("Jobs", f"{total_jobs:,}")
    cols[1].metric("Vietnam jobs", f"{vietnam_jobs:,}")
    cols[2].metric(
        "Salary coverage",
        f"{jobs_with_salary / total_jobs:.1%}" if total_jobs else "0.0%",
    )
    cols[3].metric("Weighted avg salary", money(avg_salary))

    scope_summary = (
        filtered.groupby("market_scope", as_index=False)
        .agg(
            job_count=("job_count", "sum"), jobs_with_salary=("jobs_with_salary", "sum")
        )
        .sort_values("job_count", ascending=False)
    )
    dominant_scope = scope_summary.iloc[0]
    vietnam_share = vietnam_jobs / total_jobs if total_jobs else 0
    scope_coverage = {
        row.market_scope: row.jobs_with_salary / row.job_count  # type: ignore
        for row in scope_summary.itertuples()
        if row.job_count
    }
    coverage_text = ", ".join(
        f"{scope}: {coverage:.1%}" for scope, coverage in scope_coverage.items()
    )
    scope_salary = {
        scope: weighted_average(group, "avg_salary_usd", "jobs_with_salary")
        for scope, group in filtered.groupby("market_scope")
    }
    show_insights(
        [
            (
                f"Cohort đang chọn chỉ có nhóm {dominant_scope.market_scope} "
                f"({int(dominant_scope.job_count):,} tin tuyển dụng), nên không có so sánh giữa các market."
                if len(scope_summary) == 1
                else f"{dominant_scope.market_scope} là nhóm thị trường chiếm ưu thế với "
                f"{int(dominant_scope.job_count):,} tin tuyển dụng"
                + (
                    f"; riêng Vietnam chiếm {vietnam_share:.1%} tổng số tin tuyển dụng trong cohort đang chọn."
                    if vietnam_jobs and dominant_scope.market_scope != "Vietnam"
                    else "."
                )
            ),
            (international_salary_note(scope_salary) or ""),  # type: ignore
            (
                f"Tỷ lệ hiển thị mức lương chung của toàn bộ nhóm dữ liệu này đạt "
                f"{jobs_with_salary / total_jobs:.1%}"
                + (
                    f". Khi tách theo thị trường, tỷ lệ hiển thị là {coverage_text}; "
                    "do đó các phép so sánh salary cần được đọc cùng mức độ công bố salary của từng nhóm."
                    if len(scope_summary) > 1
                    else "."
                )
            ),
        ]
    )
    left, right = st.columns(2)
    with left:
        fig = px.bar(
            scope_summary,
            x="market_scope",
            y="job_count",
            color="market_scope",
            color_discrete_map=MARKET_COLORS,
            text_auto=",",
            title="Job volume by market",
            labels={"market_scope": "Market", "job_count": "Jobs"},
        )
        fig.update_layout(showlegend=False)
        render_chart(fig, height=440)
    with right:
        salary_rows = filtered[filtered["avg_salary_usd"].notna()]
        fig = px.bar(
            salary_rows,
            x="source_name",
            y="avg_salary_usd",
            color="market_scope",
            barmode="group",
            color_discrete_map=MARKET_COLORS,
            title="Average annual salary by source and market",
            labels={
                "source_name": "Source",
                "avg_salary_usd": "USD/year",
                "market_scope": "Market",
            },
        )
        render_chart(fig, height=440)

    by_source = (
        filtered.groupby(["source_name", "market_scope"], as_index=False)["job_count"]
        .sum()
        .sort_values("job_count")
    )  # type: ignore
    fig = px.bar(
        by_source,
        x="job_count",
        y="source_name",
        color="market_scope",
        barmode="group",
        orientation="h",
        color_discrete_map=MARKET_COLORS,
        title="Market mix by source",
        labels={"job_count": "Jobs", "source_name": "Source", "market_scope": "Market"},
    )
    format_horizontal_bar_axis(fig, by_source["source_name"].drop_duplicates())
    render_chart(fig)
    st.dataframe(display_table(filtered), width="stretch", hide_index=True)


def _parse_postgres_array_literal(inner: str) -> list[str]:
    """Parse mảng Postgres '{...}' thành list Python chuẩn. Giải quyết lỗi của `split(",")` khi phần tử chứa dấu phẩy."""
    items: list[str] = []
    current: list[str] = []
    in_quotes = False
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner):
            current.append(inner[i + 1])
            i += 2
            continue
        if ch == '"':
            in_quotes = not in_quotes
            i += 1
            continue
        if ch == "," and not in_quotes:
            items.append("".join(current).strip())
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    items.append("".join(current).strip())
    return [item for item in items if item]


def parse_skills(value):
    if isinstance(value, list):
        return value

    if value is None or pd.isna(value):
        return []

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return []

        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass

        if value.startswith("{") and value.endswith("}"):
            inner = value[1:-1].strip()
            if not inner:
                return []

            return _parse_postgres_array_literal(inner)

        return [item.strip() for item in value.split(",") if item.strip()]

    return []


def data_engineer_page():
    data = numeric(
        load_data(queries.DATA_ENGINEER_JOBS),
        [
            "market_year",
            "salary_min_usd",
            "salary_max_usd",
            "salary_mid_usd",
            "skill_count",
        ],
    )

    data["skills"] = data["skills"].map(parse_skills)

    st.subheader("Data Engineer jobs")
    st.caption(
        "Phạm vi phân tích bao gồm các tin tuyển dụng có tiêu đề chứa từ khóa 'Data Engineer' hoặc 'Data Engineering'. Người dùng có thể "
        "sử dụng bộ lọc năm (Market year) và nguồn (Sources) để tách biệt dữ liệu lịch sử từ Kaggle khỏi dữ liệu thu thập thực tế."
    )
    filtered = filter_market_year_and_sources(data, key_prefix="de_jobs")
    if filtered.empty:
        st.warning("No Data Engineer jobs match the selected filters.")
        return

    skill_rows = filtered[["job_sk", "skills"]].explode("skills")
    skill_rows = skill_rows[skill_rows["skills"].notna() & (skill_rows["skills"] != "")]
    salary_coverage = filtered["salary_mid_usd"].notna().mean()

    cols = st.columns(4)
    cols[0].metric("DE jobs", f"{len(filtered):,}")
    cols[1].metric("Sources", f"{filtered.source_name.nunique():,}")
    cols[2].metric("Salary coverage", f"{salary_coverage:.1%}")
    cols[3].metric("Median salary", money(filtered["salary_mid_usd"].median()))

    by_source = (
        filtered.groupby("source_name", as_index=False)
        .size()
        .rename(columns={"size": "job_count"})
        .sort_values("job_count")
    )
    top_skills = (
        skill_rows.groupby("skills", as_index=False)
        .agg(job_count=("job_sk", "nunique"))
        .nlargest(15, "job_count")
        .sort_values("job_count")
    )

    leading_source = by_source.iloc[-1]
    technical_skills, language_note = lead_skills(
        top_skills.iloc[::-1], "skills", "job_count"
    )
    leading_skill = technical_skills.iloc[0] if not technical_skills.empty else None
    leading_source_share = (
        leading_source.job_count / len(filtered) if len(filtered) else 0
    )
    salary_count = int(filtered["salary_mid_usd"].notna().sum())
    salary_source_count = filtered.loc[
        filtered["salary_mid_usd"].notna(), "source_name"
    ].nunique()
    show_insights(
        [
            (
                f"{leading_source.source_name} là nguồn đóng góp lớn nhất cho nhóm vị trí Data Engineer với "
                f"{int(leading_source.job_count):,}/{len(filtered):,} tin tuyển dụng "
                f"({leading_source_share:.1%}). "
                if len(by_source) > 1
                else ""
            ),
            (
                f"{language_note}{leading_skill.skills} là skill xuất hiện nhiều nhất trong các tin tuyển dụng Data Engineer, "
                f"xuất hiện trong {int(leading_skill.job_count):,} tin tuyển dụng."
                if leading_skill is not None
                else ""
            ),
            (
                f"Tỷ lệ hiển thị mức lương là {salary_coverage:.1%} "
                f"({salary_count:,}/{len(filtered):,} tin tuyển dụng có hiển thị lương). "
                f"Median salary {money(filtered['salary_mid_usd'].median())} vì vậy chỉ đại diện "
                "cho nhóm tin có hiển thị lương, không phải toàn bộ thị trường Data Engineer."
            ),
            (
                "Biểu đồ phân phối mức lương giữa các nguồn cần được đánh giá thận trọng do quy mô mẫu nhỏ. "
                "Những nguồn chỉ có một vài lượt ghi nhận lương có thể tạo median hoặc boxplot thiếu ổn định."
                if salary_source_count > 1
                else ""
            ),
        ]
    )

    left, right = st.columns(2)
    with left:
        fig = px.bar(
            by_source,
            x="job_count",
            y="source_name",
            orientation="h",
            color="source_name",
            color_discrete_map=COLORS,
            title="DE jobs by source",
            labels={"job_count": "Jobs", "source_name": "Source"},
        )
        fig.update_layout(showlegend=False)
        format_horizontal_bar_axis(fig, by_source["source_name"])
        render_chart(fig, height=500)
    with right:
        fig = px.bar(
            top_skills,
            x="job_count",
            y="skills",
            orientation="h",
            title="Most requested DE skills",
            labels={"job_count": "DE jobs", "skills": "Skill"},
        )
        format_horizontal_bar_axis(fig, top_skills["skills"])
        render_chart(fig, height=500)

    salary_data = filtered[filtered["salary_mid_usd"].notna()]
    if not salary_data.empty:
        fig = px.box(
            salary_data,
            x="source_name",
            y="salary_mid_usd",
            color="source_name",
            color_discrete_map=COLORS,
            category_orders={
                "source_name": median_order(
                    salary_data, "source_name", "salary_mid_usd"
                )
            },
            points=False,
            log_y=True,
            title="DE salary distribution by source (log scale, sorted by median)",
            labels={"source_name": "Source", "salary_mid_usd": "USD/year"},
        )
        fig.update_layout(showlegend=False)
        format_salary_log_axis(fig)
        add_sample_size_ticks(
            fig, salary_data, category="source_name", value="salary_mid_usd"
        )
        render_chart(fig)

    display = filtered.copy()
    display["skills"] = display["skills"].map(lambda values: ", ".join(values or []))  # type: ignore
    display["city"] = display["city"].fillna("—")
    st.dataframe(
        display_table(
            display[
                [
                    "posted_date",
                    "source_name",
                    "market_scope",
                    "job_title",
                    "company_name",
                    "city",
                    "country",
                    "employment_type",
                    "work_arrangement",
                    "experience_level",
                    "salary_mid_usd",
                    "skills",
                ]
            ]
        ),
        width="stretch",
        hide_index=True,
    )


def work_type_page():
    data = numeric(
        load_data(queries.JOBS_BY_WORK_TYPE),
        [
            "market_year",
            "job_count",
            "company_count",
            "jobs_with_salary",
            "avg_salary_usd",
            "median_salary_usd",
            "job_share_within_source_year",
            "salary_coverage_rate",
        ],
    )

    st.subheader("Employment type and work arrangement")
    st.caption(
        "Employment type (Full-time, Contract, v.v.) được tách riêng khỏi work arrangement (Remote, Hybrid, On-site)."
        " Unknown nghĩa là source không công bố rõ thông tin này."
    )
    filtered = filter_market_year_and_sources(data, key_prefix="work_type")
    if filtered.empty:
        st.warning("No jobs match the selected filters.")
        return

    total_jobs = int(filtered["job_count"].sum())
    remote_jobs = int(
        filtered.loc[filtered["work_arrangement"] == "Remote", "job_count"].sum()
    )
    hybrid_jobs = int(
        filtered.loc[filtered["work_arrangement"] == "Hybrid", "job_count"].sum()
    )
    unknown_jobs = int(
        filtered.loc[filtered["work_arrangement"] == "Unknown", "job_count"].sum()
    )

    cols = st.columns(4)
    cols[0].metric("Jobs", f"{total_jobs:,}")
    cols[1].metric("Remote", f"{remote_jobs:,}")
    cols[2].metric("Hybrid", f"{hybrid_jobs:,}")
    cols[3].metric("Unknown arrangement", f"{unknown_jobs:,}")

    employment = (
        filtered.groupby("employment_type", as_index=False)["job_count"]
        .sum()
        .sort_values("job_count", ascending=False)
    )  # type: ignore
    arrangement = (
        filtered.groupby("work_arrangement", as_index=False)["job_count"]
        .sum()
        .sort_values("job_count", ascending=False)
    )  # type: ignore

    known_employment = employment[employment["employment_type"] != "Unknown"]
    unknown_employment_jobs = int(
        employment.loc[employment["employment_type"] == "Unknown", "job_count"].sum()
    )
    if known_employment.empty:
        employment_note = ""
    else:
        leading_employment = known_employment.iloc[0]
        second_employment = (
            known_employment.iloc[1]["job_count"] if len(known_employment) > 1 else None
        )
        employment_tail = (
            f". Có tới {unknown_employment_jobs:,} tin ({unknown_employment_jobs / total_jobs:.1%}) "
            "hoàn toàn không công bố thông tin này."
            if unknown_employment_jobs
            else "."
        )
        known_counts = known_employment["job_count"]
        if len(known_counts) >= 3 and known_counts.max() <= known_counts.min() * 1.1:
            employment_note = (
                "Trong các tin có công bố employment type, các nhóm phân bố gần như đều "
                f"(từ {int(known_counts.min()):,} đến {int(known_counts.max()):,} tin)"
                + employment_tail
            )
        else:
            employment_note = (
                f"Trong các tin tuyển dụng có công khai hình thức tuyển dụng, {leading_employment.employment_type} là nhóm "
                + leader_phrase(leading_employment.job_count, second_employment)
                + f" với {int(leading_employment.job_count):,} tin"
                + employment_tail
            )
    flexible_jobs = remote_jobs + hybrid_jobs
    classified_arrangement_jobs = total_jobs - unknown_jobs
    show_insights(
        [
            employment_note,
            (
                "Mô hình làm việc Remote và Hybrid gộp chung chiếm "
                f"{flexible_jobs / total_jobs:.1%} tổng số tin tuyển dụng trong nhóm dữ liệu đang chọn"
                + (
                    f" ({flexible_jobs / classified_arrangement_jobs:.1%} trong nhóm đã xác định hình thức làm việc)."
                    if unknown_jobs and classified_arrangement_jobs
                    else "."
                )
            ),
            (
                f"Có {unknown_jobs:,} tin ({unknown_jobs / total_jobs:.1%}) không công bố rõ hình thức làm việc; "
                f"{classified_arrangement_jobs:,} tin còn lại ({classified_arrangement_jobs / total_jobs:.1%}) đã xác định được. "
                "Các tỷ lệ Remote / Hybrid / On-site nên được diễn giải trên nhóm đã xác định này, "
                "vì nhóm chưa xác định có thể làm lệch cơ cấu."
                if unknown_jobs
                else f"Cả {total_jobs:,} tin đều xác định được hình thức làm việc, "
                "nên các tỷ lệ Remote / Hybrid / On-site không bị ảnh hưởng bởi dữ liệu thiếu."
            ),
            (
                "Hình thức làm việc phụ thuộc rất lớn vào bản chất của nguồn thu thập dữ liệu: các nền tảng chuyên về việc làm từ xa (remote-focused boards) và các trang tuyển dụng tại Việt Nam "
                "có cấu trúc rất khác nhau. Vì vậy nên phân tích theo từng nguồn dữ liệu trước khi tổng hợp thành bức tranh chung cho toàn bộ thị trường."
                if filtered["source_name"].nunique() > 1
                else ""
            ),
        ]
    )

    left, right = st.columns(2)
    with left:
        fig = px.bar(
            employment,
            x="employment_type",
            y="job_count",
            text_auto=",",
            title="Jobs by employment type",
            labels={"employment_type": "Employment type", "job_count": "Jobs"},
        )
        render_chart(fig, height=440)
    with right:
        fig = px.bar(
            arrangement,
            x="work_arrangement",
            y="job_count",
            color="work_arrangement",
            color_discrete_map=WORK_COLORS,
            text_auto=",",
            title="Jobs by work arrangement",
            labels={"work_arrangement": "Arrangement", "job_count": "Jobs"},
        )
        fig.update_layout(showlegend=False)
        render_chart(fig, height=440)

    source_arrangement = filtered.groupby(
        ["source_name", "work_arrangement"], as_index=False
    )["job_count"].sum()
    fig = px.bar(
        source_arrangement,
        x="source_name",
        y="job_count",
        color="work_arrangement",
        barmode="stack",
        color_discrete_map=WORK_COLORS,
        title="Work arrangement by source",
        labels={
            "source_name": "Source",
            "job_count": "Jobs",
            "work_arrangement": "Arrangement",
        },
    )
    render_chart(fig)
    st.dataframe(display_table(filtered), width="stretch", hide_index=True)


def quality_page():
    data = numeric(
        load_data(queries.DATA_QUALITY),
        [
            "total_jobs",
            "jobs_with_invalid_salary",
            "jobs_estimated_posted_date",
            "jobs_outside_crawl_year",
            "jobs_missing_posted_date",
            "jobs_without_skills",
            "salary_coverage_rate",
            "skills_coverage_rate",
        ],
    )
    st.subheader("Data quality")

    invalid_salary_jobs = int(data["jobs_with_invalid_salary"].sum())

    missing_company_jobs = int(data["jobs_missing_company"].sum())

    missing_location_jobs = int(data["jobs_missing_location"].sum())

    missing_posted_date_jobs = int(data["jobs_missing_posted_date"].sum())

    estimated_date_jobs = int(data["jobs_estimated_posted_date"].sum())
    outside_year_jobs = int(data["jobs_outside_crawl_year"].sum())

    cols = st.columns(7)

    cols[0].metric(
        "Total jobs",
        f"{int(data['total_jobs'].sum()):,}",
    )

    cols[1].metric(
        "Invalid salary",
        f"{invalid_salary_jobs:,}",
        help=(
            "Số dòng nằm trong rejected_jobs do mức lương không hợp lệ. "
            "Không tính trong Total jobs."
        ),
    )

    cols[2].metric(
        "Missing company",
        f"{missing_company_jobs:,}",
    )

    cols[3].metric(
        "Missing location",
        f"{missing_location_jobs:,}",
    )

    cols[4].metric(
        "Missing posted date",
        f"{missing_posted_date_jobs:,}",
        help=(
            "Job bị loại khỏi Gold vì không xác định được posted_date "
            "(không tính trong Total jobs ở trên)."
        ),
    )
    cols[5].metric(
        "Estimated posted date",
        f"{estimated_date_jobs:,}",
        help=(
            "Job có ngày đăng là giá trị thay thế (ngày crawl, ví dụ Indeed). "
            "Vẫn nằm trong Total jobs nhưng bị loại khỏi các view theo thời gian."
        ),
    )
    cols[6].metric(
        "Outside 2026",
        f"{outside_year_jobs:,}",
        help=(
            "Job crawl có năm đăng khác 2026 (ngày đăng cũ hoặc parse sai). "
            "Bị loại khỏi Gold marts, không tính trong Total jobs."
        ),
    )
    valid_volume = data[data["total_jobs"] >= 10].copy()

    if valid_volume.empty:
        show_empty_state(
            "No source has enough job volume for reliable quality comparisons yet."
        )
        if not data.empty:
            st.dataframe(
                display_table(data, floor_rates=True), width="stretch", hide_index=True
            )
        return

    lowest_skills_coverage = valid_volume.loc[
        valid_volume["skills_coverage_rate"].idxmin()
    ]  # type: ignore

    best_skills_coverage = valid_volume.loc[
        valid_volume["skills_coverage_rate"].idxmax()
    ]  # type: ignore

    show_insights(
        [
            lowest_salary_coverage_note(valid_volume),
            (
                f"{lowest_skills_coverage.source_name} có tỷ lệ hiển thị kỹ năng thấp nhất "
                f"({coverage_pct(lowest_skills_coverage.skills_coverage_rate)}). "
                "Điều này làm suy giảm mức độ đại diện của dữ liệu khi tiến hành phân tích nhu cầu kỹ năng theo từng nguồn."
            ),
            (
                f"Độ đầy đủ của dữ liệu không đồng đều giữa các trường thông tin: {best_skills_coverage.source_name} có "
                f"tỷ lệ hiển thị kỹ năng {coverage_pct(best_skills_coverage.skills_coverage_rate)}, nhưng tỷ lệ hiển thị mức lương "
                f"của cùng nguồn là {best_skills_coverage.salary_coverage_rate:.1%}. "
                "Vì vậy mỗi nguồn dữ liệu cần được đánh giá độc lập theo từng chiều chất lượng riêng."
            ),
            (
                f"Hệ thống hiện có {invalid_salary_jobs:,} invalid salary row được giữ trong quarantine để phục vụ kiểm toán thay vì đưa vào Gold. Các lỗi khác: "
                f"missing company = {missing_company_jobs:,}, missing location = {missing_location_jobs:,}, "
                f"missing posted date = {missing_posted_date_jobs:,} (cũng bị loại khỏi Gold, không tính trong tổng số tin tuyển dụng). "
                + (
                    f"{outside_year_jobs:,} tin tuyển dụng thu thập được có năm đăng ngoài 2026 bị loại khỏi Gold marts."
                    if outside_year_jobs
                    else ""
                )
            ),
        ]
    )

    rates = data.melt(
        id_vars=["source_name"],
        value_vars=["salary_coverage_rate", "skills_coverage_rate"],
        var_name="metric",
        value_name="coverage",
    )
    rates["metric"] = rates["metric"].map(
        {
            "salary_coverage_rate": "Salary coverage",
            "skills_coverage_rate": "Skills coverage",
        }
    )
    fig = px.bar(
        rates,
        x="source_name",
        y="coverage",
        color="metric",
        barmode="group",
        title="Coverage by source",
        labels={"metric": "Metric"},
    )
    fig.update_layout(
        xaxis_title="Source", yaxis_title="Coverage", yaxis_tickformat=".0%"
    )
    render_chart(fig)
    st.dataframe(
        display_table(data, floor_rates=True), width="stretch", hide_index=True
    )


PAGES = {
    "Overview": overview_page,
    "Job market": market_page,
    "Salary": salary_page,
    "Skills": skills_page,
    "Trends by year": trends_page,
    "Companies": companies_page,
    "Vietnam vs international": domestic_international_page,
    "Data Engineer": data_engineer_page,
    "Work type": work_type_page,
    "Data quality": quality_page,
}

PAGE_GROUPS = {
    "Overview": ["Overview"],
    "Market": ["Job market", "Vietnam vs international", "Companies", "Work type"],
    "Skills & roles": ["Skills", "Trends by year", "Data Engineer"],
    "Compensation": ["Salary"],
    "Data trust": ["Data quality"],
}
st.title("IT Jobs Market Dashboard")
st.markdown(
    '<div class="dashboard-subtitle">Hệ thống chuyển đổi tin tuyển dụng thô thành phân tích thị trường. '
    "Dữ liệu chính là tin tuyển dụng thu thập trong năm 2026; Kaggle (historical 2024–04/2025) chỉ dùng ở các trang có bộ lọc năm.</div>",
    unsafe_allow_html=True,
)

st.sidebar.title("IT Jobs")
section = st.sidebar.selectbox("Section", list(PAGE_GROUPS))
page = st.sidebar.radio("Page", PAGE_GROUPS[section], label_visibility="collapsed")
if st.sidebar.button("Refresh data"):
    load_data.clear()
    st.rerun()
st.sidebar.caption("Cached for 5 minutes · Refresh to query latest marts")

try:
    PAGES[page]()
except Exception:
    logger.exception("Dashboard page %r failed to render", page)
    st.error(
        "Dashboard hiện không tải được dữ liệu cho trang này. Vui lòng thử lại sau."
    )
    st.stop()
