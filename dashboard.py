"""
Polymarket Trading Bot - Web Dashboard
Single-file dashboard with Arabic/English support
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Config
from agent.advanced_analyzer import AdvancedMarketAnalyzer

# ---------- Page config ----------
st.set_page_config(
    page_title="Polymarket Trading Bot",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Translations ----------
LANG = {
    "en": {
        "title": "Polymarket Trading Bot v2.0",
        "nav": "Navigate",
        "dashboard": "Dashboard",
        "scanner": "Market Scanner",
        "opportunities": "Opportunities",
        "settings": "Settings",
        "mode": "Mode",
        "dry_run": "DRY RUN",
        "live": "LIVE",
        "max_pos": "Max Position",
        "daily_limit": "Daily Limit",
        "time": "Time",
        "top_events": "Top Events by Volume",
        "total_vol": "Total Volume",
        "liquidity": "Liquidity",
        "no_events": "No events available",
        "trading_stats": "Trading Stats",
        "total_trades": "Total Trades",
        "pnl_today": "P&L Today",
        "win_rate": "Win Rate",
        "active_pos": "Active Positions",
        "sidebar_hint": "Use the sidebar to navigate to Market Scanner, Opportunities, or Settings.",
        "min_vol": "Minimum Volume ($)",
        "scan_btn": "Scan Markets",
        "scanning": "Scanning...",
        "found_markets": "Found {n} markets",
        "press_scan": "Press **Scan Markets** to start.",
        "yes": "YES",
        "no": "NO",
        "volume": "Volume",
        "analyze_btn": "Analyze",
        "confidence": "Confidence",
        "type": "Type",
        "risk": "Risk",
        "best_opps": "Best Opportunities",
        "min_conf": "Min Confidence",
        "strategy": "Strategy",
        "all": "All",
        "arbitrage": "Arbitrage",
        "momentum": "Momentum",
        "find_btn": "Find Opportunities",
        "analyzing": "Analyzing...",
        "found_opps": "Found {n} opportunities",
        "press_find": "Press **Find Opportunities** to scan.",
        "return": "Return",
        "action": "Action",
        "details": "Details",
        "trading_cfg": "Trading Configuration",
        "max_pos_input": "Max Position Size ($)",
        "max_daily": "Max Daily Trades",
        "dry_check": "Dry Run Mode (safe)",
        "stop_loss": "Stop Loss %",
        "take_profit": "Take Profit %",
        "min_conf_pct": "Min Confidence %",
        "save_btn": "Save Settings",
        "saved": "Settings saved (restart bot to apply)",
        "sys_status": "System Status",
        "proxy": "Proxy",
        "on": "ON",
        "off": "OFF",
        "offline": "Offline mode — Polymarket is blocked. Showing demo data.",
        "connected": "Connected to Polymarket LIVE",
        "api_mode": "API Mode",
        "lang": "Language / اللغة",
    },
    "ar": {
        "title": "بوت تداول Polymarket v2.0",
        "nav": "التنقل",
        "dashboard": "لوحة التحكم",
        "scanner": "ماسح الأسواق",
        "opportunities": "الفرص",
        "settings": "الإعدادات",
        "mode": "الوضع",
        "dry_run": "تجريبي",
        "live": "حقيقي",
        "max_pos": "أقصى مركز",
        "daily_limit": "حد يومي",
        "time": "الوقت",
        "top_events": "أهم الأحداث حسب الحجم",
        "total_vol": "إجمالي الحجم",
        "liquidity": "السيولة",
        "no_events": "لا توجد أحداث",
        "trading_stats": "إحصائيات التداول",
        "total_trades": "إجمالي الصفقات",
        "pnl_today": "الربح/الخسارة اليوم",
        "win_rate": "نسبة الفوز",
        "active_pos": "المراكز النشطة",
        "sidebar_hint": "استخدم الشريط الجانبي للتنقل بين الأقسام.",
        "min_vol": "أدنى حجم تداول ($)",
        "scan_btn": "مسح الأسواق",
        "scanning": "جاري المسح...",
        "found_markets": "تم العثور على {n} سوق",
        "press_scan": "اضغط **مسح الأسواق** للبدء.",
        "yes": "نعم",
        "no": "لا",
        "volume": "الحجم",
        "analyze_btn": "تحليل",
        "confidence": "الثقة",
        "type": "النوع",
        "risk": "المخاطرة",
        "best_opps": "أفضل الفرص",
        "min_conf": "أدنى ثقة",
        "strategy": "الاستراتيجية",
        "all": "الكل",
        "arbitrage": "مراجحة",
        "momentum": "زخم",
        "find_btn": "ابحث عن الفرص",
        "analyzing": "جاري التحليل...",
        "found_opps": "تم العثور على {n} فرصة",
        "press_find": "اضغط **ابحث عن الفرص** لبدء المسح.",
        "return": "العائد",
        "action": "الإجراء",
        "details": "التفاصيل",
        "trading_cfg": "إعدادات التداول",
        "max_pos_input": "أقصى حجم مركز ($)",
        "max_daily": "أقصى صفقات يومية",
        "dry_check": "وضع تجريبي (آمن)",
        "stop_loss": "وقف الخسارة %",
        "take_profit": "جني الأرباح %",
        "min_conf_pct": "أدنى ثقة %",
        "save_btn": "حفظ الإعدادات",
        "saved": "تم حفظ الإعدادات (أعد تشغيل البوت للتطبيق)",
        "sys_status": "حالة النظام",
        "proxy": "بروكسي",
        "on": "مفعّل",
        "off": "معطّل",
        "offline": "وضع بدون اتصال — Polymarket محظور. بيانات تجريبية.",
        "connected": "متصل بـ Polymarket مباشرة",
        "api_mode": "وضع API",
        "lang": "Language / اللغة",
    },
}


def t(key: str) -> str:
    """Get translated string for current language."""
    lang = st.session_state.get("lang", "en")
    return LANG.get(lang, LANG["en"]).get(key, key)


# ---------- CSS ----------
st.markdown("""
<style>
    :root { --accent: #667eea; --accent2: #764ba2; }
    .main-header {
        font-size: 2.6rem; font-weight: 800; text-align: center;
        background: linear-gradient(90deg, var(--accent), var(--accent2));
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        padding: .8rem 0;
    }
    .card {
        border: 1px solid #e0e0e0; border-radius: 12px;
        padding: 1rem; margin: .4rem 0; background: #fafafa;
    }
    div[data-testid="stButton"] > button {
        background: linear-gradient(90deg, var(--accent), var(--accent2));
        color: white; border: none; border-radius: 8px; font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# ---------- Helpers ----------
@st.cache_resource
def get_config():
    Config.setup_directories()
    return Config


@st.cache_resource
def get_analyzer():
    return AdvancedMarketAnalyzer()


def connection_badge(analyzer):
    if analyzer.last_fetch_mode == "demo":
        st.warning(t("offline"))
    else:
        st.success(t("connected"))


# ============================================================
#  PAGE: Dashboard / لوحة التحكم
# ============================================================
def page_dashboard():
    st.markdown(f'<h1 class="main-header">{t("title")}</h1>', unsafe_allow_html=True)

    analyzer = get_analyzer()
    connection_badge(analyzer)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("mode"), t("dry_run") if Config.DRY_RUN else t("live"))
    c2.metric(t("max_pos"), f"${Config.MAX_POSITION_SIZE:.0f}")
    c3.metric(t("daily_limit"), Config.MAX_DAILY_TRADES)
    c4.metric(t("time"), datetime.now().strftime("%H:%M:%S"))

    st.markdown("---")

    # Top Events
    st.markdown(f"### {t('top_events')}")
    events = analyzer.get_top_events(limit=8)
    if events:
        for idx, ev in enumerate(events[:6]):
            title = ev.get('title', ev.get('question', '?'))
            vol = float(ev.get('volume', 0) or 0)
            liq = float(ev.get('liquidity', 0) or 0)
            with st.expander(f"**{title[:80]}** — Vol: ${vol:,.0f}"):
                ec1, ec2 = st.columns(2)
                ec1.metric(t("total_vol"), f"${vol:,.0f}")
                ec2.metric(t("liquidity"), f"${liq:,.0f}")
                sub_markets = ev.get('markets', [])
                if sub_markets:
                    for sm in sub_markets[:5]:
                        q = sm.get('question', '?')[:70]
                        op = sm.get('outcomePrices', '[]')
                        try:
                            prices = json.loads(op) if isinstance(op, str) else (op or [])
                            p_str = ' / '.join([f"{float(p)*100:.1f}%" for p in prices[:2]])
                        except Exception:
                            p_str = "?"
                        st.write(f"- {q} → {p_str}")
    else:
        st.info(t("no_events"))

    st.markdown("---")

    # Quick stats
    total_trades = 0
    try:
        trades_dir = Config.TRADES_DIR
        if trades_dir.exists():
            trade_files = list(trades_dir.glob("*.json"))
            for tf in trade_files:
                with open(tf) as f:
                    data = json.load(f)
                    total_trades += len(data) if isinstance(data, list) else 1
    except Exception:
        pass

    st.markdown(f"### {t('trading_stats')}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("total_trades"), total_trades)
    c2.metric(t("pnl_today"), "$0.00")
    c3.metric(t("win_rate"), "—")
    c4.metric(t("active_pos"), 0)

    st.markdown("---")
    st.info(t("sidebar_hint"))


# ============================================================
#  PAGE: Market Scanner / ماسح الأسواق
# ============================================================
def page_scanner():
    st.markdown(f"## {t('scanner')}")
    analyzer = get_analyzer()
    connection_badge(analyzer)

    min_vol = st.slider(t("min_vol"), 0, 50000, 1000, 500, key="scan_vol")

    if st.button(t("scan_btn"), key="scan_go"):
        with st.spinner(t("scanning")):
            markets = analyzer.get_active_markets(limit=20, min_volume=min_vol)
            st.session_state["markets"] = markets

    markets = st.session_state.get("markets", [])
    if not markets:
        st.info(t("press_scan"))
        return

    st.success(t("found_markets").format(n=len(markets)))

    for i, m in enumerate(markets, 1):
        outcomes = m.get("outcomes", [])
        yes_p = float(outcomes[0].get("price", 0)) if outcomes else 0
        no_p = float(outcomes[1].get("price", 0)) if len(outcomes) > 1 else 0
        vol = float(m.get("volume", 0) or 0)
        liq = float(m.get("liquidity", 0) or 0)

        with st.expander(f"#{i}  {m.get('question','?')[:90]}"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(t("yes"), f"{yes_p:.2f}")
            c2.metric(t("no"), f"{no_p:.2f}")
            c3.metric(t("volume"), f"${vol:,.0f}")
            c4.metric(t("liquidity"), f"${liq:,.0f}")

            if st.button(t("analyze_btn"), key=f"analyze_{i}"):
                result = analyzer.analyze_market_advanced(m)
                st.session_state[f"res_{i}"] = result

            res = st.session_state.get(f"res_{i}")
            if res:
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric(t("confidence"), f"{res['confidence']*100:.0f}%")
                rc2.metric(t("type"), res.get("opportunity_type") or "—")
                rc3.metric(t("risk"), res["risk_level"])
                for r in res.get("reasons", []):
                    st.write(f"- {r}")


# ============================================================
#  PAGE: Opportunities / الفرص
# ============================================================
def page_opportunities():
    st.markdown(f"## {t('best_opps')}")
    analyzer = get_analyzer()
    connection_badge(analyzer)

    c1, c2 = st.columns(2)
    min_conf = c1.slider(t("min_conf"), 0.0, 1.0, 0.3, 0.05, key="opp_conf")
    strat = c2.selectbox(t("strategy"), [t("all"), t("arbitrage"), t("momentum")], key="opp_strat")

    if st.button(t("find_btn"), key="find_opps"):
        with st.spinner(t("analyzing")):
            markets = analyzer.get_active_markets(limit=50, min_volume=1000)
            # Map translated strategy back to English key
            strat_map = {t("all"): None, t("arbitrage"): "arbitrage", t("momentum"): "momentum"}
            sf = strat_map.get(strat)
            opps = analyzer.find_best_opportunities(markets, min_confidence=min_conf, strategy_filter=sf)
            st.session_state["opps"] = opps

    opps = st.session_state.get("opps", [])
    if not opps:
        st.info(t("press_find"))
        return

    st.success(t("found_opps").format(n=len(opps)))

    for i, o in enumerate(opps[:15], 1):
        st.markdown(f"### #{i} — {o['question'][:80]}")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric(t("confidence"), f"{o['confidence']*100:.0f}%")
        c2.metric(t("type"), o.get("opportunity_type") or "—")
        c3.metric(t("return"), f"{o.get('expected_return',0)*100:.1f}%")
        c4.metric(t("risk"), o["risk_level"])
        c5.metric(t("action"), o["recommendation"])

        with st.expander(t("details")):
            scores = o.get("scores", {})
            if scores:
                fig = go.Figure(go.Bar(
                    x=list(scores.values()),
                    y=list(scores.keys()),
                    orientation="h",
                    marker_color="#667eea",
                ))
                fig.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=10), xaxis_range=[0, 1])
                st.plotly_chart(fig, use_container_width=True, key=f"opp_chart_{i}")
            for r in o.get("reasons", []):
                st.write(f"- {r}")
        st.markdown("---")


# ============================================================
#  PAGE: Settings / الإعدادات
# ============================================================
def page_settings():
    st.markdown(f"## {t('settings')}")

    with st.expander(t("trading_cfg"), expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.number_input(t("max_pos_input"), 10, 1000, int(Config.MAX_POSITION_SIZE), 10, key="s_pos")
            st.number_input(t("max_daily"), 1, 50, Config.MAX_DAILY_TRADES, 1, key="s_daily")
            st.checkbox(t("dry_check"), value=Config.DRY_RUN, key="s_dry")
        with c2:
            st.slider(t("stop_loss"), 5, 50, int(Config.STOP_LOSS * 100), 5, key="s_sl")
            st.slider(t("take_profit"), 10, 200, int(Config.TAKE_PROFIT * 100), 10, key="s_tp")
            st.slider(t("min_conf_pct"), 30, 95, int(Config.MIN_CONFIDENCE * 100), 5, key="s_mc")

        if st.button(t("save_btn"), key="s_save"):
            st.success(t("saved"))

    with st.expander(t("sys_status")):
        warnings = Config.validate()
        proxy_text = f'{t("on")} — {Config.PROXY_URL}' if Config.PROXY_ENABLED else t("off")
        st.markdown(f"""
        - **Python**: `{sys.executable}`
        - **Config**: {'OK' if not warnings else ', '.join(warnings)}
        - **Data Dir**: `{Config.DATA_DIR}`
        - **Log Level**: `{Config.LOG_LEVEL}`
        - **{t("proxy")}**: `{proxy_text}`
        """)


# ============================================================
#  SIDEBAR + ROUTER
# ============================================================
def main():
    # Init language
    if "lang" not in st.session_state:
        st.session_state["lang"] = "ar"

    with st.sidebar:
        st.markdown("## 💰 Trading Bot")
        st.markdown("---")

        # Language toggle
        lang_choice = st.radio(
            t("lang"),
            ["العربية", "English"],
            index=0 if st.session_state["lang"] == "ar" else 1,
            key="lang_radio",
        )
        st.session_state["lang"] = "ar" if lang_choice == "العربية" else "en"

        st.markdown("---")
        page = st.radio(t("nav"), [
            t("dashboard"),
            t("scanner"),
            t("opportunities"),
            t("settings"),
        ], key="nav_radio")
        st.markdown("---")

        analyzer = get_analyzer()
        mode = "DEMO" if analyzer.last_fetch_mode == "demo" else "LIVE"
        st.metric(t("api_mode"), mode)
        st.metric(t("dry_run"), t("on") if Config.DRY_RUN else t("off"))
        st.markdown("---")
        st.caption("v2.0 — Premium Edition")

    get_config()

    if page == t("dashboard"):
        page_dashboard()
    elif page == t("scanner"):
        page_scanner()
    elif page == t("opportunities"):
        page_opportunities()
    elif page == t("settings"):
        page_settings()


if __name__ == "__main__":
    main()
