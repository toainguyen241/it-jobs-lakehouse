import json

from streamlit.testing.v1 import AppTest  # type: ignore

PAGES = [
    "Overview",
    "Job market",
    "Salary",
    "Skills",
    "Trends by year",
    "Companies",
    "Vietnam vs international",
    "Data Engineer",
    "Work type",
    "Data quality",
]

PAGE_SECTIONS = {
    "Overview": "Overview",
    "Job market": "Market",
    "Vietnam vs international": "Market",
    "Companies": "Market",
    "Work type": "Market",
    "Skills": "Skills & roles",
    "Trends by year": "Skills & roles",
    "Data Engineer": "Skills & roles",
    "Salary": "Compensation",
    "Data quality": "Data trust",
}

EQUAL_HEIGHT_CHART_PAIRS = {
    "Overview": (0, 1),
    "Vietnam vs international": (0, 1),
    "Data Engineer": (0, 1),
    "Work type": (0, 1),
}


def assert_horizontal_axis_labels(page: str, app: AppTest) -> None:
    for chart_index, chart in enumerate(app.get("plotly_chart"), start=1):
        spec = json.loads(chart.proto.spec)
        horizontal_traces = [
            trace for trace in spec.get("data", []) if trace.get("orientation") == "h"
        ]
        if not horizontal_traces:
            continue

        expected_labels = {
            str(label) for trace in horizontal_traces for label in trace.get("y", [])
        }
        yaxis = spec.get("layout", {}).get("yaxis", {})
        rendered_labels = {str(label) for label in yaxis.get("tickvals", [])}
        missing_labels = expected_labels - rendered_labels

        if missing_labels:
            raise RuntimeError(
                f"{page} chart {chart_index} omits y-axis labels: "
                f"{sorted(missing_labels)}"
            )
        if yaxis.get("automargin") is not True:
            raise RuntimeError(
                f"{page} chart {chart_index} does not enable y-axis automargin"
            )


def assert_equal_chart_pair_height(page: str, app: AppTest) -> None:
    pair = EQUAL_HEIGHT_CHART_PAIRS.get(page)
    if pair is None:
        return

    charts = app.get("plotly_chart")
    heights = [
        json.loads(charts[index].proto.spec)["layout"].get("height") for index in pair
    ]
    if any(height is None for height in heights) or len(set(heights)) != 1:
        raise RuntimeError(f"{page} paired charts have unequal heights: {heights}")


for page in PAGES:
    app = AppTest.from_file("/app/dashboard/app.py", default_timeout=30)
    app.run()
    if page != "Overview":
        app.sidebar.selectbox[0].set_value(PAGE_SECTIONS[page])
        app.run()
        app.sidebar.radio[0].set_value(page)
        app.run()

    if app.exception or app.error:
        messages = "; ".join(
            [str(exception.value) for exception in app.exception]
            + [str(error.value) for error in app.error]
        )
        raise RuntimeError(f"{page} failed: {messages}")

    has_interpretation = any(
        "Phân tích nhanh" in str(markdown.value) for markdown in app.markdown
    )
    has_empty_state = bool(app.info or app.warning)
    if not has_interpretation and not has_empty_state:
        raise RuntimeError(
            f"Trang '{page}' chưa cấu hình cả biểu đồ phân tích lẫn trạng thái trống."
        )

    if has_interpretation:
        assert_horizontal_axis_labels(page, app)
        assert_equal_chart_pair_height(page, app)

    print(f"PASS: {page}")
