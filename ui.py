"""
ui.py — shared visual theme for the whole app.

Everything that controls "how it looks" lives here so every page stays
visually consistent: dark sidebar, light card-based main area, styled
metrics/buttons/tables. Pages still use normal Streamlit calls
(st.metric, st.dataframe, st.button, ...) — this file only re-skins
them with CSS, plus a couple of small HTML helpers for the page title
block and the sidebar brand header.

Import and call `inject_css()` once, as early as possible (in app.py,
before the navigation runs). Nothing else here changes behaviour —
only appearance.
"""
import streamlit as st

BRAND_NAME = "Danish Cattle Feed"
BRAND_TAGLINE = "Daily Register"
BRAND_ICON = "🐄"


def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

        /* ---------- App background ---------- */
        [data-testid="stAppViewContainer"] > .main {
            background-color: #eef1f7;
        }
        [data-testid="stHeader"] { background: transparent; }
        .block-container { padding-top: 2rem; padding-bottom: 3rem; }

        /* ---------- Sidebar ---------- */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #101a2e 0%, #0b1322 100%);
            border-right: 1px solid rgba(255,255,255,0.06);
        }
        section[data-testid="stSidebar"] * { color: #cbd5e1; }
        section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
            padding-top: 0.5rem;
        }

        /* Sidebar brand block */
        .sb-brand {
            display: flex; align-items: center; gap: 12px;
            padding: 4px 4px 18px 4px;
            margin-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }
        .sb-brand-icon {
            width: 42px; height: 42px; min-width: 42px;
            border-radius: 12px;
            background: linear-gradient(135deg, #2563eb, #1d4ed8);
            display: flex; align-items: center; justify-content: center;
            font-size: 22px;
            box-shadow: 0 4px 10px rgba(37,99,235,0.35);
        }
        .sb-brand-text { line-height: 1.15; }
        .sb-brand-title { font-weight: 800; font-size: 1.05rem; color: #ffffff; }
        .sb-brand-sub { font-size: 0.78rem; color: #7c8aab; font-weight: 500; }

        /* Section labels above each group of page links */
        .sb-section-label {
            font-size: 0.7rem; font-weight: 700; letter-spacing: 0.08em;
            color: #5b6b8c; text-transform: uppercase;
            margin: 18px 0 4px 6px;
        }

        /* Page links rendered via st.page_link */
        section[data-testid="stSidebar"] [data-testid="stPageLink"] {
            margin: 1px 0;
        }
        section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {
            border-radius: 9px !important;
            padding: 9px 12px !important;
            transition: background-color 0.15s ease;
        }
        section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] span {
            color: #b6c2dc !important;
            font-size: 0.93rem !important;
        }
        section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {
            background-color: rgba(255,255,255,0.07) !important;
        }
        /* Active page gets a bold label from Streamlit automatically —
           use that to also light up the background + text colour. */
        section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:has(strong) {
            background-color: rgba(37,99,235,0.22) !important;
        }
        section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:has(strong) span,
        section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:has(strong) strong {
            color: #ffffff !important;
        }

        /* Sidebar footer */
        .sb-footer {
            margin-top: 22px; padding-top: 14px;
            border-top: 1px solid rgba(255,255,255,0.08);
            font-size: 0.74rem; color: #5b6b8c; text-align: center;
        }

        /* ---------- Page header (title block) ---------- */
        .ph-wrap { display: flex; justify-content: space-between; align-items: flex-end;
                    margin-bottom: 1.4rem; flex-wrap: wrap; gap: 10px; }
        .ph-title { font-size: 2rem; font-weight: 800; color: #111827; margin: 0; line-height: 1.2; }
        .ph-sub { font-size: 0.95rem; color: #6b7280; margin-top: 4px; }

        /* ---------- Metrics as stat cards ---------- */
        [data-testid="stMetric"] {
            background: #ffffff;
            border-radius: 16px;
            padding: 18px 20px 14px 20px;
            box-shadow: 0 1px 3px rgba(16,24,40,0.06), 0 1px 2px rgba(16,24,40,0.04);
            border: 1px solid #eef0f4;
            border-top: 3px solid #2563eb;
        }
        [data-testid="stMetricLabel"] {
            text-transform: uppercase;
            font-size: 0.72rem !important;
            font-weight: 700 !important;
            letter-spacing: 0.04em;
            color: #2563eb !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.9rem !important;
            font-weight: 800 !important;
            color: #0f172a !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-of-type(4n+2) [data-testid="stMetric"] {
            border-top-color: #9333ea;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-of-type(4n+2) [data-testid="stMetricLabel"] {
            color: #9333ea !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-of-type(4n+3) [data-testid="stMetric"] {
            border-top-color: #15803d;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-of-type(4n+3) [data-testid="stMetricLabel"] {
            color: #15803d !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-of-type(4n+4) [data-testid="stMetric"] {
            border-top-color: #c2410c;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="column"]:nth-of-type(4n+4) [data-testid="stMetricLabel"] {
            color: #c2410c !important;
        }

        /* ---------- Cards (forms, expanders act as content cards) ---------- */
        [data-testid="stForm"] {
            background: #ffffff;
            border-radius: 16px;
            padding: 22px 22px 8px 22px;
            border: 1px solid #eef0f4;
            box-shadow: 0 1px 3px rgba(16,24,40,0.05);
        }
        [data-testid="stExpander"] {
            background: #ffffff;
            border-radius: 14px !important;
            border: 1px solid #eef0f4 !important;
        }

        /* ---------- Buttons ---------- */
        .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
            border-radius: 10px;
            font-weight: 600;
            border: 1px solid #e2e5ec;
        }
        .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"],
        .stDownloadButton > button[kind="primary"] {
            background-color: #2563eb;
            border-color: #2563eb;
        }
        .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover,
        .stDownloadButton > button[kind="primary"]:hover {
            background-color: #1d4ed8;
            border-color: #1d4ed8;
        }

        /* ---------- Inputs ---------- */
        [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
        [data-testid="stDateInput"] input, [data-baseweb="select"] > div {
            border-radius: 9px !important;
        }

        /* ---------- Dataframes ---------- */
        [data-testid="stDataFrame"] {
            border-radius: 14px;
            overflow: hidden;
            border: 1px solid #eef0f4;
        }

        /* ---------- Misc ---------- */
        hr { margin: 1.4rem 0; opacity: 0.5; }
        [data-testid="stCaptionContainer"] { color: #8a93a6; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str | None = None):
    """Bold dark title + muted subtitle line, matching the dashboard header style."""
    sub_html = f'<div class="ph-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="ph-wrap">
            <div>
                <p class="ph-title">{title}</p>
                {sub_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(nav_sections: dict):
    """
    Draws the brand header, grouped page links, and footer inside the
    sidebar. `nav_sections` is the same {section_label: [st.Page, ...]}
    dict passed into st.navigation, so the links and the groupings
    can never drift out of sync with each other.
    """
    with st.sidebar:
        st.markdown(
            f"""
            <div class="sb-brand">
                <div class="sb-brand-icon">{BRAND_ICON}</div>
                <div class="sb-brand-text">
                    <div class="sb-brand-title">{BRAND_NAME}</div>
                    <div class="sb-brand-sub">{BRAND_TAGLINE}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for section_label, page_list in nav_sections.items():
            st.markdown(f'<div class="sb-section-label">{section_label}</div>', unsafe_allow_html=True)
            for page in page_list:
                st.page_link(page)

        st.markdown(
            '<div class="sb-footer">Danish Cattle Feed · Daily Register</div>',
            unsafe_allow_html=True,
        )
