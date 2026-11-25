"""Streamlit household ledger with local GLM-OCR receipt recognition."""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import pandas as pd
import streamlit as st
from database import DB_PATH, add_transaction, delete_transactions, initialize_database, list_transactions, update_transactions


KINDS = ["支出", "収入"]
EXPENSE_CATEGORIES = ["食費", "日用品", "交通費", "住居費", "光熱費", "通信費", "医療費", "娯楽", "その他"]
INCOME_CATEGORIES = ["給与", "賞与", "副業・事業収入", "年金", "配当・利息", "臨時収入", "その他収入"]
CATEGORY_OPTIONS = {"支出": EXPENSE_CATEGORIES, "収入": INCOME_CATEGORIES}
ALL_CATEGORIES = EXPENSE_CATEGORIES + INCOME_CATEGORIES


def ollama_generate(image: bytes, base_url: str, model: str) -> str:
    """Send an image to Ollama's local native generate endpoint."""
    prompt = """この画像はレシートです。内容を読み取り、次のキーを持つJSONだけを返してください。
{"date":"YYYY-MM-DDまたは空文字","store":"店名または空文字","amount":合計金額の整数またはnull,"category":"食費/日用品/交通費/住居費/光熱費/通信費/医療費/娯楽/その他","memo":"品目など短いメモ","ocr_text":"読み取った文字全文"}
推測で日付や金額を補わず、判読できない値は空文字またはnullにしてください。金額は支払合計を優先してください。"""
    payload = json.dumps(
        {"model": model, "prompt": prompt, "images": [base64.b64encode(image).decode("ascii")], "stream": False, "format": "json"},
        ensure_ascii=False,
    ).encode("utf-8")
    url = base_url.rstrip("/") + "/api/generate"
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(f"Ollamaに接続できません（{reason}）。Ollamaを起動し、モデルを取得してください。") from exc
    except TimeoutError as exc:
        raise RuntimeError("Ollamaの応答がタイムアウトしました。") from exc
    text = result.get("response", "").strip()
    if not text:
        raise RuntimeError("GLM-OCRから空の応答が返りました。")
    return text


def parse_ocr_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            try:
                value = json.loads(match.group())
                return value if isinstance(value, dict) else {}
            except json.JSONDecodeError:
                pass
    return {"ocr_text": text}


def valid_date(value: object) -> date:
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
    return date.today()


def valid_category(value: object, kind: str = "支出") -> str:
    categories = CATEGORY_OPTIONS.get(kind, EXPENSE_CATEGORIES)
    return str(value) if value in categories else categories[0]


def valid_amount(value: object) -> int:
    """Normalize OCR amounts without turning decimal points into extra digits."""
    if value is None or isinstance(value, bool):
        return 0
    normalized = str(value).strip().replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    if not match:
        return 0
    try:
        amount = Decimal(match.group()).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return 0
    return max(0, int(amount))


st.set_page_config(page_title="AI家計簿", page_icon="🧾", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;600;700&display=swap');
.stApp { background: #f5f7fb; color: #172033; font-family: 'DM Sans','Noto Sans JP',sans-serif; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { color: #172033; }
.stMarkdown, .stMarkdown p, [data-testid="stWidgetLabel"], label,
[data-testid="stCaptionContainer"] p { color: #344054; }
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: #101828; }
.block-container { max-width: 1160px; padding-top: 2.1rem; }
[data-testid="stMetric"] { background: #ffffff; border: 1px solid #dfe4ec; border-radius: 14px; padding: 18px 20px; }
[data-testid="stMetricLabel"] { color: #475467 !important; }
[data-testid="stMetricValue"] { color: #101828 !important; }
[data-baseweb="input"] > div, [data-baseweb="select"] > div,
[data-testid="stDateInput"] input, [data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea {
    background: #ffffff !important; color: #172033 !important; border-color: #98a2b3 !important;
}
[data-baseweb="select"] span { color: #172033 !important; }
[data-testid="stTabs"] button { color: #475467 !important; font-weight: 600; }
[data-testid="stTabs"] button[aria-selected="true"] { color: #175cd3 !important; }
[data-testid="stFileUploader"] section { background: #ffffff; border: 1px dashed #98a2b3; }
[data-testid="stFileUploader"] small, [data-testid="stFileUploader"] span { color: #344054 !important; }
</style>
""", unsafe_allow_html=True)

st.title("🧾 AI家計簿")
st.caption("レシートを読み取って、日々の支出をかんたんに記録。データはこの端末のSQLiteに保存されます。")
if saved_notice := st.session_state.pop("saved_notice", None):
    st.success(saved_notice)

with st.sidebar:
    st.header("ローカルAI設定")
    ollama_url = st.text_input("Ollama URL", value=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    model_name = st.text_input("モデル", value=os.environ.get("OLLAMA_MODEL", "glm-ocr:latest"))
    st.caption("既定設定では localhost のOllamaで画像を処理します。")
    if st.button("Ollamaに接続", use_container_width=True):
        try:
            req = urllib.request.Request(ollama_url.rstrip("/") + "/api/tags")
            with urllib.request.urlopen(req, timeout=5) as response:
                models = json.loads(response.read().decode("utf-8")).get("models", [])
            names = [m.get("name", "") for m in models]
            if any(n == model_name or n.startswith(model_name.split(":")[0] + ":") for n in names):
                st.success("Ollamaに接続しました。モデルを確認しました。")
            else:
                st.warning(f"接続できましたが、{model_name} が見つかりません。`ollama pull {model_name}` を実行してください。")
        except Exception as exc:
            st.error(f"Ollamaに接続できません: {exc}")
    st.divider()
    st.caption(f"保存先: `{DB_PATH}`")

initialize_database()
records = pd.DataFrame(list_transactions())
if records.empty:
    records = pd.DataFrame(columns=["id", "date", "kind", "category", "store", "amount", "memo", "created_at"])

today = date.today()
month = st.selectbox("表示する月", options=pd.period_range(end=today, periods=12, freq="M").astype(str).tolist()[::-1], index=0)
month_records = records[records["date"].str.startswith(month)] if not records.empty else records
expenses = int(month_records.loc[month_records["kind"] == "支出", "amount"].sum()) if not month_records.empty else 0
income = int(month_records.loc[month_records["kind"] == "収入", "amount"].sum()) if not month_records.empty else 0

m1, m2, m3 = st.columns(3)
m1.metric("今月の支出", f"¥{expenses:,}")
m2.metric("今月の収入", f"¥{income:,}")
m3.metric("収支", f"¥{income - expenses:,}")

tab_receipt, tab_manual, tab_history = st.tabs(["📷 レシートを読み取る", "✍️ 手入力", "📊 家計簿"])

with tab_receipt:
    st.subheader("レシートをアップロード")
    st.write("GLM-OCR（Ollamaローカルモデル）が画像から日付・店名・金額を読み取ります。")
    uploaded = st.file_uploader("画像ファイル", type=["png", "jpg", "jpeg", "webp"], help="PNG / JPG / WEBP")
    if uploaded:
        left, right = st.columns([1, 1.2], gap="large")
        with left:
            st.image(uploaded, caption=uploaded.name, use_container_width=True)
        with right:
            if st.button("GLM-OCRで読み取る", type="secondary", key="receipt_ocr", width="stretch"):
                with st.spinner("ローカルモデルで読み取っています…初回はモデル読み込みに時間がかかります"):
                    try:
                        response_text = ollama_generate(uploaded.getvalue(), ollama_url, model_name)
                        draft = parse_ocr_json(response_text)
                        st.session_state["receipt_draft"] = draft
                        st.session_state["receipt_kind"] = "支出"
                        st.session_state["receipt_category"] = valid_category(draft.get("category"), "支出")
                        st.success("読み取りました。内容を確認して保存してください。")
                    except Exception as exc:
                        st.error(str(exc))
            draft = st.session_state.get("receipt_draft")
            if draft:
                if st.session_state.get("receipt_kind") not in KINDS:
                    st.session_state["receipt_kind"] = "支出"
                receipt_kind = st.segmented_control("種別", options=KINDS, key="receipt_kind") or "支出"
                receipt_categories = CATEGORY_OPTIONS[receipt_kind]
                if st.session_state.get("receipt_category") not in receipt_categories:
                    st.session_state["receipt_category"] = valid_category(draft.get("category"), receipt_kind)
                with st.form("receipt_form"):
                    st.caption("読み取り内容を確認・修正")
                    r_date = st.date_input("日付", value=valid_date(draft.get("date")))
                    r_store = st.text_input("店名", value=str(draft.get("store") or ""))
                    r_amount = st.number_input("金額（円）", min_value=0, value=valid_amount(draft.get("amount")), step=100)
                    r_category = st.selectbox("カテゴリ", receipt_categories, key="receipt_category")
                    r_memo = st.text_input("メモ", value=str(draft.get("memo") or ""))
                    if st.form_submit_button("家計簿に保存", type="secondary", key="receipt_save", width="stretch"):
                        record_id = add_transaction(r_date, receipt_kind, r_category, r_store.strip(), int(r_amount), r_memo.strip())
                        st.session_state["saved_notice"] = f"記録を保存しました（ID: {record_id}）。DB: {DB_PATH}"
                        del st.session_state["receipt_draft"]
                        st.rerun()
                with st.expander("OCRの読み取り結果"):
                    st.text(str(draft.get("ocr_text") or draft))

with tab_manual:
    st.subheader("取引を追加")
    manual_kind = st.segmented_control("種別", options=KINDS, default="支出", key="manual_kind") or "支出"
    manual_categories = CATEGORY_OPTIONS[manual_kind]
    if st.session_state.get("manual_category") not in manual_categories:
        st.session_state["manual_category"] = manual_categories[0]
    with st.form("manual_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            manual_date = st.date_input("日付", value=today, key="manual_date")
            manual_category = st.selectbox("カテゴリ", manual_categories, key="manual_category")
        with c2:
            manual_store = st.text_input("店名・内容")
            manual_amount = st.number_input("金額（円）", min_value=0, step=100, key="manual_amount")
            manual_memo = st.text_input("メモ", key="manual_memo")
        if st.form_submit_button("保存する", type="primary"):
            if not manual_store.strip():
                st.error("店名・内容を入力してください")
            elif manual_amount <= 0:
                st.error("金額は1円以上を入力してください")
            else:
                record_id = add_transaction(manual_date, manual_kind, manual_category, manual_store.strip(), int(manual_amount), manual_memo.strip())
                st.session_state["saved_notice"] = f"記録を保存しました（ID: {record_id}）。DB: {DB_PATH}"
                st.rerun()

with tab_history:
    st.subheader(f"{month} の取引")
    if month_records.empty:
        st.info("この月の記録はまだありません。レシート読取または手入力から追加できます。")
    else:
        view = month_records[["id", "date", "kind", "category", "store", "amount", "memo"]].copy()
        view = view.rename(columns={"id": "ID", "date": "日付", "kind": "種別", "category": "カテゴリ", "store": "店名・内容", "amount": "金額", "memo": "メモ"})
        view["日付"] = pd.to_datetime(view["日付"]).dt.date
        view["削除"] = False
        edited = st.data_editor(
            view,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "ID": st.column_config.NumberColumn(disabled=True),
                "日付": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "金額": st.column_config.NumberColumn(format="¥%d", min_value=0),
                "種別": st.column_config.SelectboxColumn(options=KINDS),
                "カテゴリ": st.column_config.SelectboxColumn(options=ALL_CATEGORIES),
                "削除": st.column_config.CheckboxColumn(help="削除する記録にチェック"),
            },
        )
        selected_for_deletion = edited[edited["削除"]]["ID"].astype(int).tolist()
        b1, b2 = st.columns([1, 2])
        if b1.button("変更を保存", type="secondary"):
            update_transactions([
                {
                    "id": int(row["ID"]),
                    "date": row["日付"],
                    "kind": row["種別"],
                    "category": row["カテゴリ"],
                    "store": row["店名・内容"],
                    "amount": row["金額"],
                    "memo": row["メモ"],
                }
                for _, row in edited.iterrows()
            ])
            st.success("変更を保存しました")
            st.rerun()
        with b2:
            st.caption(f"{len(selected_for_deletion)}件を削除対象に選択中")
        if st.button("チェックした記録を削除", type="secondary", disabled=not selected_for_deletion):
            delete_transactions(selected_for_deletion)
            st.rerun()
        csv = month_records[["date", "kind", "category", "store", "amount", "memo"]].to_csv(index=False).encode("utf-8-sig")
        st.download_button("CSVをダウンロード", csv, file_name=f"kakeibo-{month}.csv", mime="text/csv")
