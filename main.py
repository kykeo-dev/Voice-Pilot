"""
Axialys Bot Manager — v4
"""

import streamlit as st
import requests
import json
import html
import urllib.parse
import uuid
import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# --- GESTION DES ARGUMENTS LIGNE DE COMMANDE ---
parser = argparse.ArgumentParser(description="Axialys Bot Manager")
parser.add_argument("--api-key", type=str, default="", help="Clé API Reecall (Optionnel)")
parser.add_argument("--project-id", type=str, default="", help="ID Projet / Workspace (Optionnel)")
args, _ = parser.parse_known_args()

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="Axialys Bot Manager",
    layout="wide",
    page_icon="https://media.licdn.com/dms/image/v2/D4E0BAQE_HZvoIBQM9g/company-logo_200_200/company-logo_200_200/0/1695887075709/axialys_logo?e=2147483647&v=beta&t=8NbSO8rggmFIAWcnJQ1ocq2k-wrdv5A9FXDZVzluIqM"
)

API_BASE    = "https://newprd.reecall.io/data_next"
API_ROOT    = "https://newprd.reecall.io"
METRICS_BASE = "https://newprd.reecall.io/metrics/v1"

LOGO_URL = (
    "https://media.licdn.com/dms/image/v2/D4E0BAQE_HZvoIBQM9g/"
    "company-logo_200_200/company-logo_200_200/0/1695887075709/"
    "axialys_logo?e=2147483647&v=beta&t=8NbSO8rggmFIAWcnJQ1ocq2k-wrdv5A9FXDZVzluIqM"
)

SUPPORTED_LANGUAGES = ["fr-FR", "en-US", "en-GB", "es-ES", "de-DE", "it-IT"]
SIP_HEADER_OPTIONS  = ["SIP_ALL_HEADERS", "SIP_X_HEADERS", "SIP_NO_HEADERS"]

COST_METRICS = ",".join([
    "exchangeCount", "duration", "indivisibleDuration",
    "usage.stt.audioDuration", "usage.tts.characters",
    "usage.conversational.inputTextTokens", "usage.conversational.outputTextTokens",
    "usage.conversational.cachedTextTokens",
    "usage.realtime.inputTextTokens", "usage.realtime.outputTextTokens",
    "usage.realtime.inputAudioTokens", "usage.realtime.outputAudioTokens",
    "usage.realtime.cachedAudioTokens",
    "usage.postProcessing.inputTextTokens", "usage.postProcessing.outputTextTokens",
    "usage.postProcessing.cachedTextTokens"
])

# --- CSS ---
st.markdown("""
<style>
    .stApp { background-color: var(--background-color); }
    h1, h2, h3 { color: #3D6FA3 !important; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
    div.stButton > button:first-child { background-color: #002C5F; color: white !important; border-radius: 8px; border: none; font-weight: bold; }
    div.stButton > button:first-child:hover { background-color: #004080; color: white !important; }
    .call-status-box { padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 10px; border: 1px solid rgba(128,128,128,0.3); }
    .status-off { background-color: rgba(248,215,218,0.85); color: #721c24; }
    .status-on  { background-color: rgba(212,237,218,0.85); color: #155724; }
    .exchange-card { background-color: var(--secondary-background-color); color: var(--text-color); padding: 15px; border-radius: 8px; border: 1px solid rgba(128,128,128,0.2); margin-bottom: 10px; }
    .cost-card { background-color: var(--secondary-background-color); color: var(--text-color); padding: 15px; border-radius: 8px; border: 2px solid rgba(61,111,163,0.4); margin-bottom: 10px; }
    [data-testid="stSidebar"] { background-color: var(--secondary-background-color) !important; border-right: 1px solid rgba(128,128,128,0.2) !important; }
    [data-testid="stSidebar"] img { display: block; margin: 20px auto; border-radius: 10px; }
    .extraction-row { padding: 10px; border: 1px solid rgba(128,128,128,0.2); border-radius: 8px; margin-bottom: 5px; background-color: var(--secondary-background-color); color: var(--text-color); }
    .engine-mode-card { padding: 12px 16px; border-radius: 8px; border: 2px solid rgba(61,111,163,0.3); background-color: var(--secondary-background-color); margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)


# --- UTILITAIRES ---
def esc(value):
    return html.escape(str(value)) if value else ""


# --- SESSION STATE ---
if 'form_data' not in st.session_state or not isinstance(st.session_state.form_data, dict):
    st.session_state.form_data = {}
if 'last_loaded_id'    not in st.session_state: st.session_state.last_loaded_id    = None
if 'previous_action'   not in st.session_state: st.session_state.previous_action   = "✏️ Modifier / Tester un assistant"
if 'call_data'         not in st.session_state: st.session_state.call_data          = None
if 'api_logs'          not in st.session_state: st.session_state.api_logs           = []
if 'var_edit_id'       not in st.session_state: st.session_state.var_edit_id        = None
if 'var_show_form'     not in st.session_state: st.session_state.var_show_form      = False
if 'mcp_edit_id'       not in st.session_state: st.session_state.mcp_edit_id        = None
if 'mcp_show_form'     not in st.session_state: st.session_state.mcp_show_form      = False


def reset_form():
    st.session_state.form_data = {
        "name": "", "description": "", "instructions": "Tu es un assistant utile...",
        "firstMessage": "Bonjour, bienvenue chez Axialys !", "temperature": 0.3, "language": "fr-FR",
        "timezone": "Europe/Paris", "llmId": None, "sttId": None, "ttsId": None, "voiceId": None,
        "stsId": None, "engine_mode": "Classique (STT + LLM + TTS)", "id": None,
        "knowledgeBaseIds": [], "mcpIds": [], "mcps": [], "extraction_fields": [],
        "end_conversation_enabled": False, "closing_message": "", "description_override": "", "disable_interruptions": False
    }
    st.session_state.last_loaded_id = None
    st.session_state.call_data = None


def load_assistant_into_form(assistant, tools=[]):
    llm_id    = assistant.get('llmId') or ((assistant.get('llm') or {}).get('id'))
    tts_id    = assistant.get('ttsId') or ((assistant.get('tts') or {}).get('id'))
    stt_id    = assistant.get('sttId') or ((assistant.get('stt') or {}).get('id'))
    sts_id    = assistant.get('stsId') or ((assistant.get('sts') or {}).get('id'))
    voice_uuid = assistant.get('voiceId') or ((assistant.get('voice') or {}).get('id'))
    engine_mode = "STS (Speech-to-Speech)" if sts_id else "Classique (STT + LLM + TTS)"

    kb_ids  = assistant.get('knowledgeBaseIds', []) or []
    mcp_ids = assistant.get('mcpIds', []) or []
    raw_mcps = assistant.get('mcps', []) or []
    clean_mcp_urls = []
    for item in raw_mcps:
        if isinstance(item, str): clean_mcp_urls.append(item)
        elif isinstance(item, dict) and 'url' in item: clean_mcp_urls.append(item['url'])

    extraction_fields = []
    schema_obj = assistant.get('dataExtractionSchema')
    if schema_obj and isinstance(schema_obj, dict):
        props = schema_obj.get("properties", {})
        req   = schema_obj.get("required", [])
        for k, v in props.items():
            extraction_fields.append({
                "name": k, "type": v.get("type", "string"), "description": v.get("description", ""),
                "required": k in req, "enum": ", ".join(v.get("enum", [])) if isinstance(v.get("enum"), list) else ""
            })

    end_tool = next((t for t in tools if t.get('definition', {}).get('name') == 'end_conversation'), None)
    st.session_state.form_data = {
        "name": assistant.get('name', ''), "description": assistant.get('description', ''),
        "instructions": assistant.get('instructions', ''), "firstMessage": assistant.get('firstMessage', ''),
        "temperature": assistant.get('temperature', 0.3), "language": assistant.get('language', 'fr-FR'),
        "timezone": assistant.get('timezone', 'Europe/Paris'),
        "llmId": llm_id, "sttId": stt_id, "ttsId": tts_id, "voiceId": voice_uuid,
        "stsId": sts_id, "engine_mode": engine_mode, "id": assistant.get('id'),
        "knowledgeBaseIds": kb_ids, "mcpIds": mcp_ids, "mcps": clean_mcp_urls,
        "extraction_fields": extraction_fields,
        "end_conversation_enabled": end_tool is not None,
        "closing_message": ((end_tool.get('configuration') or {}).get('closingMessage', '')) if end_tool else '',
        "description_override": (end_tool.get('descriptionOverride', '')) if end_tool else '',
        "disable_interruptions": (end_tool.get('disableInterruptions', False)) if end_tool else False
    }
    st.session_state.call_data = None


def format_date(iso_string):
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y à %H:%M:%S")
    except Exception:
        return iso_string


# --- LOGGING ---
def log_api_call(method, url, req_kwargs, response):
    if len(st.session_state.api_logs) >= 10:
        st.session_state.api_logs.pop(0)
    hdrs = req_kwargs.get("headers", {}).copy()
    if "Authorization" in hdrs: hdrs["Authorization"] = "Bearer ********"
    req_params = req_kwargs.get("params", {}).copy()
    for k, v in req_params.items():
        if isinstance(v, str):
            try: req_params[k] = json.loads(v)
            except Exception: pass
    resp_body = None
    if response is not None:
        try: resp_body = response.json()
        except Exception: resp_body = response.text
    st.session_state.api_logs.append({
        "timestamp": datetime.now(ZoneInfo("Europe/Paris")).strftime("%H:%M:%S"),
        "method": method.upper(), "url": url, "req_headers": hdrs,
        "req_body": req_kwargs.get("json", req_kwargs.get("data")),
        "req_params": req_params,
        "status_code": response.status_code if response is not None else "Erreur",
        "resp_body": resp_body
    })


def make_api_request(method, url, **kwargs):
    try:
        resp = requests.request(method, url, timeout=30, **kwargs)
        log_api_call(method, url, kwargs, resp)
        return resp
    except Exception as e:
        log_api_call(method, url, kwargs, None)
        raise e


# --- API FONCTIONS ---
@st.cache_data(ttl=300, show_spinner=False)
def fetch_lists(api_key):
    h = {'Authorization': f'Bearer {api_key}'}
    try:
        llm = requests.get(f"{API_BASE}/ai/llm",   headers=h, timeout=15)
        stt = requests.get(f"{API_BASE}/ai/stt/",  headers=h, timeout=15)
        tts = requests.get(f"{API_BASE}/ai/tts",   headers=h, timeout=15)
        sts = requests.get(f"{API_BASE}/ai/sts/",  headers=h, timeout=15)
        if any(r.status_code != 200 for r in [llm, stt, tts]): return None
        return {'llm': llm.json(), 'stt': stt.json(), 'tts': tts.json(),
                'sts': sts.json() if sts.status_code == 200 else []}
    except Exception: return None


@st.cache_data(ttl=60, show_spinner=False)
def fetch_mcps(api_key):
    h = {'Authorization': f'Bearer {api_key}'}
    try:
        resp = requests.get(f"{API_BASE}/ai/MCP/", headers=h, timeout=15)
        if resp.status_code == 200:
            d = resp.json()
            return d.get("data", d.get("items", [])) if isinstance(d, dict) else d
        return []
    except Exception: return []


@st.cache_data(ttl=30, show_spinner=False)
def fetch_assistants(api_key, project_id=""):
    h = {'Authorization': f'Bearer {api_key}'}
    params = {"where": json.dumps({"projectId": project_id})} if project_id else {}
    try:
        resp = requests.get(f"{API_BASE}/conversational/assistants/", headers=h, params=params, timeout=15)
        if resp.status_code == 200:
            d = resp.json()
            return d.get("data", d.get("items", [])) if isinstance(d, dict) else d
        return []
    except Exception: return []


@st.cache_data(ttl=60, show_spinner=False)
def check_workspace(api_key, project_id):
    h = {'Authorization': f'Bearer {api_key}'}
    try:
        resp = requests.get(f"{API_BASE}/conversational/exchanges/", headers=h,
                            params={"where": json.dumps({"projectId": project_id}), "limit": 1}, timeout=15)
        return resp.status_code == 200
    except Exception: return False


@st.cache_data(ttl=30, show_spinner=False)
def fetch_sip_channel(api_key, assistant_id):
    h = {'Authorization': f'Bearer {api_key}'}
    try:
        resp = requests.get(f"{API_BASE}/conversational/channels/", headers=h,
                            params={"where": json.dumps({"assistantId": assistant_id, "type": "SIP"})}, timeout=15)
        if resp.status_code == 200:
            d = resp.json()
            channels = d.get("data", d.get("items", d)) if isinstance(d, dict) else d
            return channels[0] if channels else None
        return None
    except Exception: return None


@st.cache_data(ttl=30, show_spinner=False)
def fetch_variables(api_key, project_id=""):
    h = {'Authorization': f'Bearer {api_key}'}
    params = {"where": json.dumps({"projectId": project_id})} if project_id else {}
    try:
        resp = requests.get(f"{API_BASE}/core/variables", headers=h, params=params, timeout=15)
        if resp.status_code == 200:
            d = resp.json()
            return d.get("data", d.get("items", [])) if isinstance(d, dict) else d
        return []
    except Exception: return []


def fetch_exchange_cost(api_key, trace_id, range_from=None, range_to=None, created_at=None):
    """Récupère le coût d'un échange.
    - range_from/range_to : fenêtre explicite (Étude de Pricing)
    - created_at          : fallback J-1/J+2 (Historique conversations)
    """
    h = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
    try:
        if range_from and range_to:
            f_dt, t_dt = range_from, range_to
        elif created_at:
            dt_c = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            f_dt = (dt_c - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")
            t_dt = (dt_c + timedelta(days=2)).strftime("%Y-%m-%dT23:59:59.999Z")
        else:
            return None
        params = {"metrics": COST_METRICS, "from": f_dt, "to": t_dt, "traceId": trace_id}
        resp = make_api_request('GET', f"{METRICS_BASE}/metrics/bulkAll", headers=h, params=params)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                total   = sum(item.get('pricing', 0) or 0 for item in data)
                details = [{"metric": item['metric'], "pricing": item.get('pricing', 0) or 0,
                            "value": item.get('data', {}).get('sum', 0)}
                           for item in data if (item.get('pricing') or 0) > 0]
                return {"total": total, "details": details}
        return None
    except Exception: return None


def fetch_cost_by_assistant(api_key, assistant_id, f_dt, t_dt):
    """Coût agrégé pour un assistant via context={assistantId}."""
    h = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
    try:
        params = {"metrics": COST_METRICS, "from": f_dt, "to": t_dt,
                  "context": json.dumps({"assistantId": assistant_id})}
        resp = make_api_request('GET', f"{METRICS_BASE}/metrics/bulkAll", headers=h, params=params)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                total      = sum(item.get('pricing', 0) or 0 for item in data)
                conv_count = next((item['data']['sum'] for item in data if item['metric'] == 'exchangeCount'), 0)
                total_dur  = next((item['data']['sum'] for item in data if item['metric'] == 'duration'), 0)
                details    = [{"metric": item['metric'], "pricing": item.get('pricing', 0) or 0,
                               "value": item.get('data', {}).get('sum', 0)}
                              for item in data if (item.get('pricing') or 0) > 0]
                return {"total": total, "conv_count": int(conv_count), "total_dur_s": total_dur, "details": details}
        return None
    except Exception: return None


def save_assistant(api_key, payload, assistant_id=None):
    h = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    if assistant_id:
        return make_api_request('PATCH', f"{API_BASE}/conversational/assistants/{assistant_id}", headers=h, json=payload), "modifié"
    return make_api_request('POST', f"{API_BASE}/conversational/assistants/", headers=h, json=payload), "créé"


def save_variable(api_key, payload, variable_id=None):
    h = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    if variable_id:
        return make_api_request('PATCH', f"{API_BASE}/core/variables/{variable_id}", headers=h, json=payload), "modifiée"
    return make_api_request('POST', f"{API_BASE}/core/variables", headers=h, json=payload), "créée"


def delete_variable(api_key, variable_id):
    return make_api_request('DELETE', f"{API_BASE}/core/variables/{variable_id}",
                            headers={'Authorization': f'Bearer {api_key}'})


def save_mcp(api_key, payload, mcp_id=None):
    h = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    if mcp_id:
        return make_api_request('PATCH', f"{API_BASE}/ai/MCP/{mcp_id}", headers=h, json=payload), "modifié"
    return make_api_request('POST', f"{API_BASE}/ai/MCP/", headers=h, json=payload), "créé"


def delete_mcp(api_key, mcp_id):
    return make_api_request('DELETE', f"{API_BASE}/ai/MCP/{mcp_id}",
                            headers={'Authorization': f'Bearer {api_key}'})


def fetch_assistant_tools(api_key, assistant_id):
    h = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
    try:
        resp = make_api_request('GET', f"{API_BASE}/ai/tools", headers=h,
                                params={"where": json.dumps({"assistantId": assistant_id})})
        return resp.json() if resp.status_code == 200 else []
    except Exception: return []


def manage_system_tools(api_key, assistant_id, project_id, enable_end_call,
                        closing_message, description_override, disable_interruptions):
    ha = {'Authorization': f'Bearer {api_key}'}
    hj = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    defs_resp = make_api_request('GET', f"{API_BASE}/ai/toolDefinitions", headers=ha)
    if defs_resp.status_code != 200: return False, f"Impossible de récupérer les définitions (HTTP {defs_resp.status_code})."
    end_def = next((d for d in defs_resp.json() if d.get('name') == 'end_conversation'), None)
    if not end_def: return False, "Définition 'end_conversation' introuvable."
    def_id = end_def['id']
    existing_tools   = fetch_assistant_tools(api_key, assistant_id)
    existing_end_tool = next((t for t in existing_tools if t.get('definitionId') == def_id), None)
    if enable_end_call:
        payload = {"assistantId": assistant_id, "projectId": project_id,
                   "definitionId": def_id, "disableInterruptions": disable_interruptions}
        if closing_message and closing_message.strip(): payload["configuration"] = {"closingMessage": closing_message.strip()}
        if description_override and description_override.strip(): payload["descriptionOverride"] = description_override.strip()
        if existing_end_tool:
            r = make_api_request('DELETE', f"{API_BASE}/ai/tools/{existing_end_tool['id']}", headers=ha)
            if r.status_code not in (200, 204): return False, f"Échec suppression ancien outil (HTTP {r.status_code})."
        r = make_api_request('POST', f"{API_BASE}/ai/tools/", headers=hj, json=payload)
        if r.status_code not in (200, 201): return False, f"Échec création outil (HTTP {r.status_code})."
    else:
        if existing_end_tool:
            r = make_api_request('DELETE', f"{API_BASE}/ai/tools/{existing_end_tool['id']}", headers=ha)
            if r.status_code not in (200, 204): return False, f"Échec suppression outil (HTTP {r.status_code})."
    return True, "OK"


def get_or_create_webrtc_channel(api_key, assistant_id, assistant_name, project_id):
    h = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    try:
        resp = make_api_request('GET', f"{API_BASE}/conversational/channels/", headers=h,
                                params={"where": json.dumps({"assistantId": assistant_id, "type": "WEBRTC"})})
        channels = resp.json()
        if isinstance(channels, dict): channels = channels.get("data", channels.get("items", []))
        if channels: return channels[0]['id']
        resp = make_api_request('POST', f"{API_BASE}/conversational/channels/", headers=h,
                                json={"name": f"WebRTC - {assistant_name}", "type": "WEBRTC",
                                      "assistantId": assistant_id, "projectId": project_id})
        return resp.json()['id'] if resp.status_code in [200, 201] else None
    except Exception as e: st.error(f"Erreur réseau WebRTC : {e}"); return None


def get_call_token(api_key, channel_id):
    try:
        resp = make_api_request('POST', f"{API_ROOT}/calls/{channel_id}",
                                headers={'Authorization': f'Bearer {api_key}'})
        return resp.json() if resp.status_code == 200 else None
    except Exception as e: st.error(f"Erreur réseau token : {e}"); return None


def save_sip_channel(api_key, channel_id, payload):
    h = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    try:
        if channel_id: return make_api_request('PATCH', f"{API_BASE}/conversational/channels/{channel_id}", headers=h, json=payload)
        return make_api_request('POST', f"{API_BASE}/conversational/channels/", headers=h, json=payload)
    except Exception as e: st.error(f"Erreur réseau SIP : {e}"); return None


def fetch_exchanges(api_key, project_id):
    h = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
    try:
        resp = make_api_request('GET', f"{API_BASE}/conversational/exchanges/", headers=h,
                                params={"where": json.dumps({"projectId": project_id}),
                                        "orderBy": json.dumps({"createdAt": "desc"}), "limit": 100})
        if resp.status_code == 200:
            d = resp.json()
            return d.get("data", d.get("items", [])) if isinstance(d, dict) else d
        return []
    except Exception as e: st.error(f"Erreur réseau : {e}"); return []


def fetch_exchanges_range(api_key, project_id, f_dt, t_dt, assistant_id=None):
    h = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
    where = {"projectId": project_id, "createdAt": {"$gte": f_dt, "$lte": t_dt}}
    if assistant_id: where["assistantId"] = assistant_id
    try:
        resp = make_api_request('GET', f"{API_BASE}/conversational/exchanges/", headers=h,
                                params={"where": json.dumps(where),
                                        "orderBy": json.dumps({"createdAt": "desc"}), "limit": 200})
        if resp.status_code == 200:
            d = resp.json()
            return d.get("data", d.get("items", [])) if isinstance(d, dict) else d
        return []
    except Exception: return []


def fetch_exchange_details(api_key, exchange_id):
    h = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
    try:
        resp = make_api_request('GET', f"{API_BASE}/conversational/exchanges/{exchange_id}/", headers=h)
        return resp.json() if resp.status_code == 200 else None
    except Exception as e: st.error(f"Erreur réseau : {e}"); return None


# =============================================================================
# SIDEBAR
# =============================================================================
with st.sidebar:
    st.image(LOGO_URL, width=150)
    st.divider()
    st.caption("🔧 Configuration Technique")

    api_key = st.text_input("Clé API", type="password", value=args.api_key)
    lists, available_mcps, api_valid = None, [], False

    if api_key:
        with st.spinner("Vérification de la clé..."):
            lists = fetch_lists(api_key)
            if lists:
                st.success("✅ Clé API valide"); api_valid = True
                available_mcps = fetch_mcps(api_key)
            else:
                st.error("❌ Clé API invalide ou mal copiée")

    project_id = st.text_input("ID Projet (Workspace)", value=args.project_id)
    project_valid = False

    if project_id:
        try: uuid.UUID(str(project_id)); is_uuid = True
        except ValueError: is_uuid = False
        if not is_uuid:
            st.error("❌ Format invalide")
        elif api_valid:
            with st.spinner("Vérification du Workspace..."):
                if check_workspace(api_key, project_id):
                    st.success("✅ Workspace connecté"); project_valid = True
                else:
                    st.error("❌ Workspace introuvable ou accès refusé")
        else:
            st.warning("⚠️ Validez d'abord votre Clé API.")

    st.divider()
    main_action = st.radio(
        "📍 Menu Principal",
        ["✏️ Modifier / Tester un assistant", "✨ Créer un nouvel assistant",
         "📜 Consulter les conversations", "💰 Étude de Pricing",
         "🔑 Variables", "🔌 Serveurs MCP", "📡 Logs API"],
        key="main_nav_radio"
    )

    assistants_list = fetch_assistants(api_key, project_id) if (api_valid and project_valid) else []

    if main_action != st.session_state.previous_action:
        if main_action == "✨ Créer un nouvel assistant": reset_form()
        st.session_state.previous_action = main_action

    if main_action == "✏️ Modifier / Tester un assistant" and assistants_list:
        st.divider()
        ass_options = {a.get('name', 'Sans nom'): a['id'] for a in assistants_list}
        selected_name = st.selectbox("Sélectionnez l'assistant :", list(ass_options.keys()))
        selected_id = ass_options[selected_name]
        if selected_id != st.session_state.last_loaded_id:
            st.session_state.last_loaded_id = selected_id
            st.session_state['_pending_load_id'] = selected_id

# Chargement différé
if st.session_state.get('_pending_load_id'):
    pending_id = st.session_state.pop('_pending_load_id')
    full_obj = next((a for a in assistants_list if a['id'] == pending_id), None)
    if full_obj:
        with st.spinner("Chargement..."):
            load_assistant_into_form(full_obj, fetch_assistant_tools(api_key, pending_id))


# =============================================================================
# ROUTING
# =============================================================================
if not api_valid or not project_valid:
    st.title("Voice Pilot")
    st.info("👋 Bienvenue ! Veuillez configurer vos accès dans le menu de gauche.")
    if api_key and not api_valid: st.error("🔒 La Clé API renseignée est incorrecte.")
    elif api_valid and project_id and not project_valid: st.error("📂 L'ID Projet est introuvable ou accès refusé.")
    elif api_valid and not project_id: st.warning("👉 Clé API validée. Renseignez l'ID Projet à gauche.")

# === VUES 1 & 2 : ASSISTANT ===
elif main_action in ["✨ Créer un nouvel assistant", "✏️ Modifier / Tester un assistant"]:
    is_creation = main_action == "✨ Créer un nouvel assistant"
    fd = st.session_state.form_data
    wks = fd.get("id") or "new"
    assistant_name_display = st.session_state.get("form_data", {}).get("name", "") or "Nouvel assistant"
    st.title("Création d'un nouvel assistant" if is_creation else f"Configuration de l'Assistant — {assistant_name_display}")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📝 Identité")
        name = st.text_input("Nom", value=fd.get("name", ""))
        desc = st.text_input("Description", value=fd.get("description", ""))
        lang = st.selectbox("Langue", SUPPORTED_LANGUAGES,
                            index=SUPPORTED_LANGUAGES.index(fd.get("language", "fr-FR"))
                            if fd.get("language") in SUPPORTED_LANGUAGES else 0)
    with c2:
        st.subheader("🧠 Comportement")
        inst = st.text_area("System Prompt", value=fd.get("instructions", ""), height=130)
        first_msg = st.text_input("Message d'accueil", value=fd.get("firstMessage", ""))
        temp = st.slider("Température", 0.0, 1.0, float(fd.get("temperature", 0.3)))

    st.divider()
    st.subheader("☎️ Contrôle d'Appel")
    st.info("Autorisez le bot à mettre fin à l'appel de sa propre initiative.")
    cs1, cs2 = st.columns(2)
    with cs1:
        enable_end_call = st.checkbox("Activer le raccrochage automatique", value=fd.get("end_conversation_enabled", False), key=f"end_call_{wks}")
        closing_msg = st.text_input("Message de clôture", value=fd.get("closing_message", ""), disabled=not enable_end_call, key=f"close_msg_{wks}")
        disable_interruptions = st.checkbox("Désactiver les interruptions pendant la clôture", value=fd.get("disable_interruptions", False), disabled=not enable_end_call, key=f"dis_int_{wks}")
    with cs2:
        desc_override = st.text_area("Consignes de raccrochage", value=fd.get("description_override", ""), disabled=not enable_end_call, height=100, key=f"desc_over_{wks}")

    st.divider()
    st.subheader("📊 Variables à extraire")
    fields = fd.get("extraction_fields", [])
    if fields:
        hc = st.columns([2, 1.5, 3, 2, 1, 0.5])
        for lbl in ["Clé", "Type", "Description", "Choix imposés", "Oblig.", ""]: hc.pop(0).caption(lbl)
    for i, field in enumerate(fields):
        st.markdown("<div class='extraction-row'>", unsafe_allow_html=True)
        col1, col2, col3, col4, col5, col6 = st.columns([2, 1.5, 3, 2, 1, 0.5])
        with col1: field['name'] = st.text_input("N", value=field.get('name',''), key=f"fn_{wks}_{i}", label_visibility="collapsed")
        with col2:
            t_opts = ["string", "boolean", "number"]
            field['type'] = st.selectbox("T", t_opts, index=t_opts.index(field.get('type','string')) if field.get('type','string') in t_opts else 0, key=f"ft_{wks}_{i}", label_visibility="collapsed")
        with col3: field['description'] = st.text_input("D", value=field.get('description',''), key=f"fd_{wks}_{i}", label_visibility="collapsed")
        with col4: field['enum'] = st.text_input("E", value=field.get('enum',''), key=f"fe_{wks}_{i}", disabled=field['type']!='string', label_visibility="collapsed")
        with col5:
            st.markdown("<div style='margin-top:5px'></div>", unsafe_allow_html=True)
            field['required'] = st.checkbox("", value=field.get('required', False), key=f"fr_{wks}_{i}")
        with col6:
            if st.button("❌", key=f"fdel_{wks}_{i}"):
                st.session_state.form_data['extraction_fields'].pop(i); st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    if st.button("➕ Ajouter une variable"):
        st.session_state.form_data.setdefault('extraction_fields', []).append({"name":"","type":"string","description":"","enum":"","required":False}); st.rerun()

    st.divider()
    st.subheader("🔌 Outils & Intégrations (MCP)")
    cm1, cm2 = st.columns(2)
    with cm1:
        st.markdown("**Catalogue MCP (Reecall)**")
        mcp_options = {m.get('name','Sans nom'): m['id'] for m in available_mcps} if available_mcps else {}
        default_mcp_names = [n for n, mid in mcp_options.items() if mid in fd.get("mcpIds", [])]
        selected_mcp_names = st.multiselect("Serveurs à activer :", options=list(mcp_options.keys()), default=default_mcp_names, key=f"mcp_sel_{wks}")
        selected_mcp_ids = [mcp_options[n] for n in selected_mcp_names]
    with cm2:
        st.markdown("**URLs personnalisées**")
        mcp_urls_str = st.text_area("URLs SSE :", value="\n".join(fd.get("mcps",[])), height=68, placeholder="https://a1b2.ngrok.app/sse", label_visibility="collapsed", key=f"mcp_urls_{wks}")
        mcp_urls_list = [u.strip() for u in mcp_urls_str.split("\n") if u.strip()]

    st.divider()
    st.subheader("⚙️ Moteur Technique")
    ENGINE_MODES = ["Classique (STT + LLM + TTS)", "STS (Speech-to-Speech)"]
    cur_mode = fd.get("engine_mode", "Classique (STT + LLM + TTS)")
    engine_mode = st.radio("Mode moteur", ENGINE_MODES, index=ENGINE_MODES.index(cur_mode) if cur_mode in ENGINE_MODES else 0, horizontal=True, key=f"eng_{wks}")

    def get_idx(opts, target): return list(opts.values()).index(target) if target in opts.values() else 0
    final_llm_id = final_stt_id = final_tts_id = final_voice_id = final_sts_id = None

    if engine_mode == "Classique (STT + LLM + TTS)":
        st.markdown("<div class='engine-mode-card'>", unsafe_allow_html=True)
        tc1, tc2, tc3 = st.columns(3)
        with tc1:
            st.markdown("**🧠 LLM**")
            llm_opts = {i['name']: i['id'] for i in lists['llm']}
            final_llm_id = llm_opts[st.selectbox("LLM", list(llm_opts.keys()), index=get_idx(llm_opts, fd.get("llmId")), key=f"llm_{wks}")]
        with tc2:
            st.markdown("**🎤 STT**")
            stt_opts = {i['name']: i['id'] for i in lists['stt']}
            final_stt_id = stt_opts[st.selectbox("STT", list(stt_opts.keys()), index=get_idx(stt_opts, fd.get("sttId")), key=f"stt_{wks}")]
        with tc3:
            st.markdown("**🔊 TTS**")
            tts_map = {p['name']: p for p in lists['tts']}
            prov_names = list(tts_map.keys())
            prov_idx = 0
            if fd.get("ttsId"):
                for i, pn in enumerate(prov_names):
                    if tts_map[pn]['id'] == fd.get("ttsId"): prov_idx = i; break
            prov_data = tts_map[st.selectbox("Fournisseur", prov_names, index=prov_idx, key=f"tts_{wks}")]
            final_tts_id = prov_data['id']
            voices = prov_data.get('voices', [])
            if voices:
                v_opts = {v['name']: v['id'] for v in voices}
                final_voice_id = v_opts[st.selectbox("Voix", list(v_opts.keys()), index=get_idx(v_opts, fd.get("voiceId")), key=f"voice_{wks}")]
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='engine-mode-card'>", unsafe_allow_html=True)
        sts_list = lists.get('sts', [])
        if not sts_list:
            st.warning("Aucun modèle STS disponible.")
        else:
            sc1, sc2 = st.columns(2)
            with sc1:
                st.markdown("**🎙️ Modèle STS**")
                sts_active = [m for m in sts_list if not m.get('disabled', False)]
                sts_opts = {f"{m['name']} ({m.get('provider','')})": m for m in sts_active}
                sts_idx = 0
                if fd.get("stsId"):
                    for i, m in enumerate(sts_active):
                        if m['id'] == fd.get("stsId"): sts_idx = i; break
                sel_sts = sts_opts[st.selectbox("STS", list(sts_opts.keys()), index=sts_idx, key=f"sts_{wks}")]
                final_sts_id = sel_sts['id']
                st.caption(sel_sts.get('description', ''))
            with sc2:
                st.markdown("**🔊 Voix**")
                sts_voices = sel_sts.get('voices', [])
                if sts_voices:
                    v_opts = {}
                    for v in sts_voices:
                        g = "👨" if v.get('gender') == 'male' else ("👩" if v.get('gender') == 'female' else "🧑")
                        v_opts[f"{g} {v['name']} [{v.get('language','')}]"] = v['id']
                    v_idx = 0
                    if fd.get("voiceId") and fd.get("voiceId") in list(v_opts.values()):
                        v_idx = list(v_opts.values()).index(fd.get("voiceId"))
                    sel_lbl = st.selectbox("Voix STS", list(v_opts.keys()), index=v_idx, key=f"sts_voice_{wks}")
                    final_voice_id = v_opts[sel_lbl]
                    sv = next((v for v in sts_voices if v['id'] == final_voice_id), {})
                    if sv.get('description'): st.caption(sv['description'])
                    if sv.get('multilingual'): st.caption("🌍 Voix multilingue")
        st.markdown("</div>", unsafe_allow_html=True)
        st.caption("ℹ️ En mode STS, LLM/STT/TTS sont gérés nativement par le modèle.")

    st.divider()
    col_save, col_deploy = st.columns(2)
    with col_save:
        lbl = "🚀 CRÉER L'ASSISTANT" if is_creation else "💾 SAUVEGARDER LES MODIFICATIONS"
        if st.button(lbl, type="primary", use_container_width=True):
            errs = []
            if not name or not name.strip(): errs.append("Le **Nom** est obligatoire.")
            if not inst or not inst.strip(): errs.append("Le **System Prompt** est obligatoire.")
            if engine_mode == "Classique (STT + LLM + TTS)" and not final_voice_id: errs.append("La **Voix** est obligatoire.")
            if engine_mode == "STS (Speech-to-Speech)" and not final_sts_id: errs.append("Le **modèle STS** est obligatoire.")
            if errs:
                for e in errs: st.error(e)
            else:
                parsed_schema = None
                vf = [f for f in fields if f.get('name','').strip()]
                if vf:
                    props, req_f = {}, []
                    for f in vf:
                        vn = f['name'].strip()
                        prop = {"type": f['type'], "description": f['description'].strip()}
                        if f['enum'].strip() and f['type'] == 'string':
                            prop["enum"] = [e.strip() for e in f['enum'].split(",") if e.strip()]
                        props[vn] = prop
                        if f['required']: req_f.append(vn)
                    req_f = [r for r in req_f if r in props]
                    parsed_schema = {"type": "object", "properties": props, "required": req_f, "additionalProperties": False}
                payload = {"name": name.strip(), "description": desc, "instructions": inst, "language": lang,
                           "projectId": project_id, "firstMessage": first_msg, "timezone": "Europe/Paris",
                           "temperature": temp, "knowledgeBaseIds": fd.get("knowledgeBaseIds",[]),
                           "mcpIds": selected_mcp_ids, "mcps": mcp_urls_list, "dataExtractionSchema": parsed_schema}
                if engine_mode == "STS (Speech-to-Speech)":
                    payload.update({"stsId": final_sts_id, "voiceId": final_voice_id, "llmId": None, "sttId": None, "ttsId": None})
                else:
                    payload.update({"llmId": final_llm_id, "ttsId": final_tts_id, "sttId": final_stt_id, "voiceId": final_voice_id, "stsId": None})
                target_id = fd.get("id") if not is_creation else None
                with st.spinner('Envoi en cours...'):
                    resp, act = save_assistant(api_key, payload, target_id)
                    if resp.status_code in [200, 201]:
                        assistant_id = resp.json().get('id')
                        if assistant_id:
                            tok, tmsg = manage_system_tools(api_key, assistant_id, project_id, enable_end_call, closing_msg, desc_override, disable_interruptions)
                            if not tok: st.warning(f"Assistant {act}, mais outil raccrochage échoué : {tmsg}")
                            else: st.success(f"Succès ({act}) !")
                            st.session_state.form_data['id'] = assistant_id
                            if is_creation:
                                st.session_state.previous_action = "✏️ Modifier / Tester un assistant"
                                st.session_state.last_loaded_id = None
                            fetch_assistants.clear(); st.rerun()
                    else:
                        try: err_detail = resp.json()
                        except Exception: err_detail = resp.text
                        st.error(f"Échec sauvegarde (HTTP {resp.status_code}) : {err_detail}")

    with col_deploy:
        if fd.get("id") and project_id:
            tab_test, tab_sip = st.tabs(["💻 Test Navigateur", "☎️ Ligne de Production SIP"])
            with tab_test:
                if st.session_state.call_data:
                    creds = st.session_state.call_data
                    magic_link = f"https://meet.livekit.io/custom?liveKitUrl={urllib.parse.quote(creds['wsUrl'].strip(), safe='')}&token={urllib.parse.quote(creds['token'].strip(), safe='')}"
                    st.markdown(f'<a href="{esc(magic_link)}" target="_blank" style="text-decoration:none;"><div style="background-color:#28a745;color:white;padding:10px;border-radius:8px;text-align:center;font-weight:bold;margin-bottom:15px;">📞 LANCER L\'APPEL TEST</div></a>', unsafe_allow_html=True)
                    if st.button("❌ Raccrocher / Réinitialiser", use_container_width=True):
                        st.session_state.call_data = None; st.rerun()
                else:
                    if st.button("📞 GÉNÉRER UN APPEL TEST", use_container_width=True):
                        with st.spinner("Génération de la ligne..."):
                            channel_id = get_or_create_webrtc_channel(api_key, fd.get("id"), name, project_id)
                            if channel_id:
                                creds = get_call_token(api_key, channel_id)
                                if creds: st.session_state.call_data = creds; st.rerun()
            with tab_sip:
                sip_channel = fetch_sip_channel(api_key, fd.get("id"))
                existing_sip_id = sip_channel.get("id") if sip_channel else None
                if sip_channel: st.markdown('<div class="call-status-box status-on">🟢 <b>LIGNE SIP ACTIVE</b></div>', unsafe_allow_html=True)
                else: st.markdown('<div class="call-status-box status-off">🔴 <b>NON CONFIGURÉE</b></div>', unsafe_allow_html=True)
                existing_nums = sip_channel.get("inboundNumbersWhitelist",[]) if sip_channel else []
                existing_ips  = sip_channel.get("inboundAddressesWhitelist",[]) if sip_channel else []
                existing_sip_hdr = sip_channel.get("includeSipHeaders","SIP_ALL_HEADERS") if sip_channel else "SIP_ALL_HEADERS"
                existing_krisp   = sip_channel.get("krispEnabled", False) if sip_channel else False
                sip_nums_str = st.text_area("Numéros Autorisés (E.164)", value="\n".join(existing_nums), height=68)
                sip_ips_str  = st.text_area("Adresses IP Autorisées",   value="\n".join(existing_ips),  height=68)
                st.markdown("**Paramètres Avancés**")
                sip_hdr_opt  = st.selectbox("Transmission des Headers SIP", options=SIP_HEADER_OPTIONS,
                                            index=SIP_HEADER_OPTIONS.index(existing_sip_hdr) if existing_sip_hdr in SIP_HEADER_OPTIONS else 0)
                krisp_enabled = st.checkbox("Réduction de bruit Krisp", value=existing_krisp)
                if st.button("💾 Mettre à jour la ligne SIP" if sip_channel else "🔌 Créer la Ligne SIP", use_container_width=True):
                    nums_list = [n.strip() for n in sip_nums_str.split("\n") if n.strip()]
                    ips_list  = [ip.strip() for ip in sip_ips_str.split("\n") if ip.strip()]
                    if not nums_list and not ips_list: st.error("⚠️ Renseignez au moins un numéro ou une IP.")
                    else:
                        with st.spinner("Configuration en cours..."):
                            r = save_sip_channel(api_key, existing_sip_id,
                                                 {"name": f"SIP Trunk - {name}", "type": "SIP",
                                                  "assistantId": fd.get("id"), "projectId": project_id,
                                                  "inboundNumbersWhitelist": nums_list, "inboundAddressesWhitelist": ips_list,
                                                  "includeSipHeaders": sip_hdr_opt, "krispEnabled": krisp_enabled})
                            if r and r.status_code in [200,201]: st.success("✅ Configuration SIP enregistrée !"); fetch_sip_channel.clear(); st.rerun()
                            else: st.error(f"Échec : {r.text if r else 'Erreur de connexion'}")

# === VUE 3 : HISTORIQUE ===
elif main_action == "📜 Consulter les conversations":
    st.title("Historique des Conversations")
    if project_id:
        ass_dict = {"Tous les assistants": None}
        id_to_name = {}
        for a in (assistants_list or []):
            ass_dict[a.get('name','?')] = a.get('id')
            id_to_name[a.get('id')] = a.get('name','?')

        col_f1, _ = st.columns([1, 2])
        with col_f1:
            selected_ass_name = st.selectbox("🤖 Filtrer par Assistant", list(ass_dict.keys()))
            selected_ass_id   = ass_dict[selected_ass_name]
        st.divider()

        with st.spinner("Récupération de l'historique..."):
            all_exchanges = fetch_exchanges(api_key, project_id)
            filtered = []
            for exc in all_exchanges:
                cur_ass_id = next((r.get("value") for r in exc.get("resources",[]) if r.get("key")=="assistant_id"), None)
                if not selected_ass_id or cur_ass_id == selected_ass_id:
                    exc["_assistant_name"] = id_to_name.get(cur_ass_id, "Assistant Inconnu")
                    filtered.append(exc)

        if filtered:
            exchange_options = {f"{format_date(e.get('createdAt',''))} - {esc(e.get('_assistant_name',''))} - [{esc(e.get('status','').upper())}]": e['id'] for e in filtered}
            selected_label = st.selectbox("Sélectionnez une conversation :", list(exchange_options.keys()))
            selected_exchange_id = exchange_options[selected_label]
            st.divider()

            with st.spinner("Chargement..."):
                exc_detail = fetch_exchange_details(api_key, selected_exchange_id)

            if exc_detail:
                col_info, col_chat = st.columns([1, 2])
                with col_info:
                    st.subheader("ℹ️ Informations")
                    res_map = {r['key']: r['value'] for r in (exc_detail.get("resources",[]) or []) if isinstance(r, dict)}
                    dur_s = exc_detail.get("duration") or res_map.get("session_end.duration_seconds") or 0
                    dur_str = f"{int(dur_s)//60}m {int(dur_s)%60}s" if dur_s else "N/A"
                    caller = res_map.get("dynamic_config.caller_phone_number","N/A")
                    called = res_map.get("dynamic_config.called_phone_number","N/A")
                    llm_   = res_map.get("assistant_config.llm","N/A")
                    stt_   = res_map.get("assistant_config.stt_model","N/A")
                    tts_   = res_map.get("assistant_config.tts_model","N/A")
                    voice_ = res_map.get("assistant_config.tts_voice","")
                    conn_  = res_map.get("dynamic_config.connection_type","N/A").upper()
                    st.markdown(f"""
                    <div class="exchange-card">
                        <b>Status :</b> {esc(exc_detail.get('status','N/A'))} &nbsp;|&nbsp; <b>Type :</b> {esc(exc_detail.get('type','N/A'))} &nbsp;|&nbsp; <b>Canal :</b> {esc(conn_)}<br>
                        <b>Date :</b> {esc(format_date(exc_detail.get('createdAt','')))}<br>
                        <b>Durée :</b> {esc(dur_str)}<br>
                        <hr style="margin:8px 0;opacity:0.2">
                        <b>📞 Appelant :</b> {esc(caller)}<br>
                        <b>📲 Appelé :</b> {esc(called)}<br>
                        <hr style="margin:8px 0;opacity:0.2">
                        <b>🧠 LLM :</b> {esc(llm_)}<br>
                        <b>🎤 STT :</b> {esc(stt_)}<br>
                        <b>🔊 TTS :</b> {esc(tts_)}{f" / {esc(voice_)}" if voice_ else ""}
                    </div>
                    """, unsafe_allow_html=True)

                    trace_id = exc_detail.get("traceId")
                    if trace_id:
                        with st.spinner("Calcul du coût..."):
                            cost_data = fetch_exchange_cost(api_key, trace_id, created_at=exc_detail.get("createdAt"))
                        if cost_data and cost_data["total"] > 0:
                            dur_min = float(dur_s) / 60 if dur_s else 0
                            cpm = cost_data["total"] / dur_min if dur_min > 0 else 0
                            st.markdown(f"""
                            <div class="cost-card">
                                <b>💰 Coût estimé</b><br>
                                <span style="font-size:1.5em;font-weight:bold;color:#3D6FA3;">{cost_data['total']:.4f} €</span><br>
                                <span style="font-size:0.9em;opacity:0.8;">⏱️ <b>{cpm:.4f} € / min</b> &nbsp;|&nbsp; durée : {esc(dur_str)}</span>
                            </div>
                            """, unsafe_allow_html=True)
                            with st.expander("📊 Détail du coût par composant"):
                                for item in cost_data["details"]:
                                    st.markdown(f"**{item['metric'].replace('usage.','').replace('.',' › ')}** : `{item['pricing']:.6f} €`")
                        elif cost_data is not None:
                            st.info("💰 Coût : 0,00 €")

                    with st.expander("🛠️ Événements"):
                        ev = exc_detail.get("events")
                        if ev: st.json(ev)
                        else: st.info("Aucun événement.")
                    with st.expander("📊 Données extraites"):
                        xd = exc_detail.get("data")
                        if xd:
                            if isinstance(xd, str):
                                try: xd = json.loads(xd)
                                except Exception: pass
                            st.json(xd)
                        else: st.info("Aucune donnée d'extraction.")

                with col_chat:
                    audio_url = exc_detail.get("audioUrl") or exc_detail.get("recordingUrl")
                    if not audio_url:
                        for ev in (exc_detail.get("events") or []):
                            for fld in ["audioUrl","recordingUrl","recording","mediaUrl"]:
                                if ev.get(fld): audio_url = ev[fld]; break
                            if audio_url: break
                    if audio_url: st.subheader("🎧 Enregistrement"); st.audio(audio_url)
                    st.subheader("💬 Transcription")
                    messages = exc_detail.get("messages", [])
                    if not messages: st.info("Aucun message enregistré.")
                    else:
                        for msg in messages:
                            with st.chat_message("user" if msg.get("from")=="user" else "assistant"):
                                st.write(msg.get("message","")); st.caption(format_date(msg.get("time","")))
        else:
            st.info("Aucune conversation trouvée.")

# === VUE 4 : ÉTUDE DE PRICING ===
elif main_action == "💰 Étude de Pricing":
    st.title("💰 Étude de Pricing")
    st.info("Vue rapide : **1 appel API par assistant** via `context={assistantId}`. Vue détaillée : 1 appel par conversation (traceId), limitée à 50.")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1: date_from = st.date_input("📅 Du", value=datetime.now(ZoneInfo("Europe/Paris")).date().replace(day=1))
    with col_f2: date_to   = st.date_input("📅 Au", value=datetime.now(ZoneInfo("Europe/Paris")).date())
    with col_f3:
        ass_dict_p = {"Tous les assistants": None}
        for a in (assistants_list or []): ass_dict_p[a.get('name','Sans nom')] = a['id']
        selected_ass_p = st.selectbox("🤖 Assistant", list(ass_dict_p.keys()))
        selected_ass_id_p = ass_dict_p[selected_ass_p]

    col_p1, col_p2 = st.columns([1, 3])
    with col_p1:
        prix_vente_min = st.number_input("💶 Prix de vente (€ / min)", min_value=0.0, value=0.20, step=0.01, format="%.4f",
                                         help="Prix facturé au client par minute d'appel. Permet de calculer la marge brute.")
    mode_detail = st.checkbox("🔍 Charger le détail par conversation (plus lent, limité à 50 conv.)", value=False)

    if st.button("🔍 Lancer l'analyse", type="primary"):
        f_dt = date_from.strftime("%Y-%m-%dT00:00:00.000Z")
        t_dt = date_to.strftime("%Y-%m-%dT23:59:59.999Z")

        # --- MODE RAPIDE ---
        if not mode_detail:
            to_analyze = []
            if selected_ass_id_p:
                to_analyze = [(selected_ass_id_p, next((a.get('name','?') for a in assistants_list if a['id']==selected_ass_id_p),'?'))]
            else:
                to_analyze = [(a['id'], a.get('name','?')) for a in (assistants_list or [])]

            if not to_analyze:
                st.warning("Aucun assistant trouvé.")
            else:
                results_agg = []
                prog = st.progress(0)
                for i, (aid, aname) in enumerate(to_analyze):
                    prog.progress((i+1)/len(to_analyze))
                    data = fetch_cost_by_assistant(api_key, aid, f_dt, t_dt)
                    if data and data['conv_count'] > 0:
                        results_agg.append({"assistant": aname, **data})
                prog.empty()

                if not results_agg:
                    st.info("Aucune donnée de coût disponible sur cette période.")
                else:
                    st.divider()
                    tot_cost = sum(r['total'] for r in results_agg)
                    tot_conv = sum(r['conv_count'] for r in results_agg)
                    tot_dur  = sum(r['total_dur_s'] for r in results_agg)
                    tot_min  = tot_dur / 60 if tot_dur else 0
                    avg_c    = tot_cost / tot_conv if tot_conv else 0
                    avg_cpm  = tot_cost / tot_min  if tot_min  else 0
                    avg_d    = tot_dur  / tot_conv if tot_conv else 0

                    m1,m2,m3,m4,m5 = st.columns(5)
                    m1.metric("💬 Conversations", int(tot_conv))
                    m2.metric("💰 Coût total",     f"{tot_cost:.4f} €")
                    m3.metric("📊 Coût / conv.",   f"{avg_c:.4f} €")
                    m4.metric("⏱️ Coût / min",     f"{avg_cpm:.4f} €")
                    m5.metric("⏳ Durée moy.",      f"{int(avg_d//60)}m {int(avg_d%60)}s")

                    # --- MARGE ---
                    if prix_vente_min > 0 and tot_min > 0:
                        revenu_total  = prix_vente_min * tot_min
                        marge_total   = revenu_total - tot_cost
                        marge_pct     = (marge_total / revenu_total * 100) if revenu_total > 0 else 0
                        marge_min     = prix_vente_min - avg_cpm
                        revenu_conv   = prix_vente_min * (avg_d / 60) if avg_d else 0
                        marge_conv    = revenu_conv - avg_c

                        color = "rgba(212,237,218,0.6)" if marge_total >= 0 else "rgba(248,215,218,0.6)"
                        sign  = "+" if marge_total >= 0 else ""
                        st.markdown(f"""
                        <div style="padding:15px;border-radius:8px;background:{color};border:1px solid rgba(128,128,128,0.2);margin:10px 0;">
                            <b>📈 Analyse de marge</b> &nbsp;|&nbsp; Prix de vente : <b>{prix_vente_min:.4f} € / min</b><br><br>
                            <span style="font-size:1.3em;font-weight:bold;">{sign}{marge_total:.4f} € de marge brute</span>
                            &nbsp;&nbsp;
                            <span style="font-size:1.1em;font-weight:bold;color:{'#155724' if marge_total>=0 else '#721c24'}">
                                {sign}{marge_pct:.1f}%
                            </span><br>
                            <small>
                                Revenu total : <b>{revenu_total:.4f} €</b> &nbsp;|&nbsp;
                                Marge / min : <b>{sign}{marge_min:.4f} €</b> &nbsp;|&nbsp;
                                Marge / conv. : <b>{sign}{marge_conv:.4f} €</b>
                            </small>
                        </div>
                        """, unsafe_allow_html=True)
                    st.divider()

                    st.subheader("📋 Résumé par assistant")
                    h0,h1,h2,h3,h4,h5 = st.columns([2.5,1,1.5,1.5,1.5,1.5])
                    h0.caption("Assistant"); h1.caption("Conv."); h2.caption("Coût total (€)")
                    h3.caption("Coût/conv. (€)"); h4.caption("Coût/min (€)"); h5.caption("Durée moy.")
                    st.divider()
                    for r in sorted(results_agg, key=lambda x: x['total'], reverse=True):
                        dm = r['total_dur_s']/60 if r['total_dur_s'] else 0
                        revenu_r = prix_vente_min * dm if prix_vente_min > 0 and dm > 0 else 0
                        marge_r  = revenu_r - r['total']
                        marge_r_pct = (marge_r / revenu_r * 100) if revenu_r > 0 else 0
                        sign_r = "+" if marge_r >= 0 else ""

                        rc = st.columns([2, 1, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2])
                        rc[0].markdown(f"**{esc(r['assistant'])}**")
                        rc[1].markdown(str(r['conv_count']))
                        rc[2].markdown(f"`{r['total']:.4f}`")
                        rc[3].markdown(f"`{r['total']/r['conv_count']:.4f}`" if r['conv_count'] else "—")
                        rc[4].markdown(f"`{r['total']/dm:.4f}`" if dm else "—")
                        rc[5].markdown(f"{int(r['total_dur_s']//r['conv_count']//60)}m {int(r['total_dur_s']//r['conv_count']%60)}s" if r['conv_count'] else "—")
                        if prix_vente_min > 0 and dm > 0:
                            clr = "🟢" if marge_r >= 0 else "🔴"
                            rc[6].markdown(f"{clr} `{sign_r}{marge_r:.4f}`")
                            rc[7].markdown(f"`{sign_r}{marge_r_pct:.1f}%`")
                        else:
                            rc[6].markdown("—"); rc[7].markdown("—")
                        pct = (r['total']/tot_cost*100) if tot_cost else 0
                        st.progress(min(pct/100, 1.0))
                        with st.expander(f"📊 Détail composants — {r['assistant']}"):
                            for item in sorted(r['details'], key=lambda x: x['pricing'], reverse=True):
                                st.markdown(f"**{item['metric'].replace('usage.','').replace('.',' › ')}** : `{item['pricing']:.6f} €`  ·  valeur : `{item['value']}`")

        # --- MODE DÉTAIL ---
        else:
            with st.spinner("Récupération des conversations..."):
                exchanges = fetch_exchanges_range(api_key, project_id, f_dt, t_dt, selected_ass_id_p)

            if not exchanges:
                st.warning("Aucune conversation trouvée.")
            else:
                valid = [e for e in exchanges if e.get("traceId")]
                st.info(f"**{len(exchanges)}** conversations — coût pour **{len(valid)}** échanges avec traceId...")
                if len(valid) > 50: st.warning(f"⚠️ Limité aux 50 plus récentes."); valid = valid[:50]

                prog = st.progress(0)
                results = []
                itn = {a['id']: a.get('name','?') for a in (assistants_list or [])}
                for i, exc in enumerate(valid):
                    prog.progress((i+1)/len(valid))
                    cd = fetch_exchange_cost(api_key, exc["traceId"], range_from=f_dt, range_to=t_dt)
                    dur_s = exc.get("duration") or 0
                    aname = "?"

                    # Extraire le stack technique depuis les resources
                    res_map = {r['key']: r['value'] for r in (exc.get("resources") or []) if isinstance(r, dict)}
                    for r in (exc.get("resources") or []):
                        if r.get("key") == "assistant_id": aname = itn.get(r.get("value"),"?"); break

                    llm_used = res_map.get("assistant_config.llm", "")
                    stt_used = res_map.get("assistant_config.stt_model", "")
                    tts_used = res_map.get("assistant_config.tts_model", "")
                    # Détecter STS : si le LLM contient "realtime" ou "ultravox" ou "gemini-realtime"
                    is_sts = any(k in llm_used.lower() for k in ["realtime", "ultravox"]) if llm_used else False
                    if is_sts:
                        stack_label = f"STS · {llm_used.split('/')[-1] if '/' in llm_used else llm_used}"
                    else:
                        stack_label = f"{llm_used.split('/')[-1] if llm_used and '/' in llm_used else llm_used or '?'}"

                    results.append({"date": format_date(exc.get("createdAt","")), "assistant": aname,
                                    "durée_s": dur_s, "statut": exc.get("status","?"),
                                    "coût": round(cd["total"], 6) if cd else 0.0,
                                    "traceId": exc.get("traceId",""),
                                    "llm": llm_used, "stt": stt_used, "tts": tts_used,
                                    "is_sts": is_sts, "stack": stack_label})
                prog.empty()

                st.divider()
                tot_cost = sum(r["coût"] for r in results)
                tot_dur  = sum(r["durée_s"] for r in results)
                tot_min  = tot_dur/60 if tot_dur else 0
                avg_c    = tot_cost/len(results) if results else 0
                avg_cpm  = tot_cost/tot_min if tot_min else 0
                avg_d    = tot_dur/len(results) if results else 0
                max_item = max(results, key=lambda x: x["coût"]) if results else None

                m1,m2,m3,m4,m5 = st.columns(5)
                m1.metric("💬 Conversations", len(results))
                m2.metric("💰 Coût total",    f"{tot_cost:.4f} €")
                m3.metric("📊 Coût / conv.",  f"{avg_c:.4f} €")
                m4.metric("⏱️ Coût / min",    f"{avg_cpm:.4f} €")
                m5.metric("⏳ Durée moy.",     f"{int(avg_d//60)}m {int(avg_d%60)}s")
                if max_item: st.caption(f"💡 Conv. la plus coûteuse : **{max_item['date']}** — `{max_item['coût']:.4f} €`")

                # --- MARGE MODE DÉTAIL ---
                if prix_vente_min > 0 and tot_min > 0:
                    revenu_total = prix_vente_min * tot_min
                    marge_total  = revenu_total - tot_cost
                    marge_pct    = (marge_total / revenu_total * 100) if revenu_total > 0 else 0
                    sign = "+" if marge_total >= 0 else ""
                    color = "rgba(212,237,218,0.6)" if marge_total >= 0 else "rgba(248,215,218,0.6)"
                    st.markdown(f"""
                    <div style="padding:15px;border-radius:8px;background:{color};border:1px solid rgba(128,128,128,0.2);margin:10px 0;">
                        <b>📈 Analyse de marge</b> &nbsp;|&nbsp; Prix de vente : <b>{prix_vente_min:.4f} € / min</b><br><br>
                        <span style="font-size:1.3em;font-weight:bold;">{sign}{marge_total:.4f} € de marge brute</span>
                        &nbsp;&nbsp;
                        <span style="font-size:1.1em;font-weight:bold;color:{'#155724' if marge_total>=0 else '#721c24'}">
                            {sign}{marge_pct:.1f}%
                        </span><br>
                        <small>
                            Revenu total : <b>{revenu_total:.4f} €</b> &nbsp;|&nbsp;
                            Marge / min : <b>{sign}{prix_vente_min - avg_cpm:.4f} €</b> &nbsp;|&nbsp;
                            Marge / conv. : <b>{sign}{(revenu_total - tot_cost)/len(results):.4f} €</b>
                        </small>
                    </div>
                    """, unsafe_allow_html=True)

                st.divider()
                st.subheader("📋 Détail par conversation")
                h0,h1,h2,h3,h4,h5,h6,h7,h8 = st.columns([0.3,1.6,1.2,1,0.6,0.8,0.8,1,1.8])
                h0.caption("#"); h1.caption("Date"); h2.caption("Assistant")
                h3.caption("Durée"); h4.caption("Statut"); h5.caption("Coût (€)"); h6.caption("€/min")
                h7.caption("Marge (€)"); h8.caption("Stack / TraceId")
                st.divider()
                for idx, r in enumerate(sorted(results, key=lambda x: x["date"], reverse=True), 1):
                    ds = r["durée_s"]
                    dur_str = f"{int(ds)//60}m {int(ds)%60}s" if ds else "—"
                    cpm = r["coût"]/(ds/60) if ds > 0 else 0
                    dur_min_r = ds/60 if ds > 0 else 0
                    revenu_r = prix_vente_min * dur_min_r if prix_vente_min > 0 and dur_min_r > 0 else 0
                    marge_r  = revenu_r - r["coût"] if revenu_r > 0 else None
                    marge_r_pct = (marge_r / revenu_r * 100) if revenu_r > 0 else None

                    # Stack label
                    if r.get("is_sts"):
                        stack_str = f"🎙️ STS · `{r['llm'].split('/')[-1] if '/' in r['llm'] else r['llm']}`"
                    else:
                        parts = []
                        if r.get("llm"): parts.append(f"🧠`{r['llm'].split('/')[-1] if '/' in r['llm'] else r['llm']}`")
                        if r.get("stt"): parts.append(f"🎤`{r['stt'].split('/')[-1] if '/' in r['stt'] else r['stt']}`")
                        if r.get("tts"): parts.append(f"🔊`{r['tts']}`")
                        stack_str = " ".join(parts) if parts else "—"

                    rc = st.columns([0.3,1.6,1.2,1,0.6,0.8,0.8,1,1.8])
                    rc[0].caption(str(idx)); rc[1].caption(r["date"])
                    rc[2].markdown(f"**{esc(r['assistant'])}**"); rc[3].markdown(dur_str)
                    rc[4].markdown(r["statut"]); rc[5].markdown(f"`{r['coût']:.4f}`")
                    rc[6].markdown(f"`{cpm:.4f}`")
                    if marge_r is not None:
                        sign_r = "+" if marge_r >= 0 else ""
                        clr = "🟢" if marge_r >= 0 else "🔴"
                        rc[7].markdown(f"{clr} `{sign_r}{marge_r:.4f}`  \n`{sign_r}{marge_r_pct:.1f}%`")
                    else:
                        rc[7].markdown("—")
                    rc[8].markdown(stack_str + f"  \n`{r.get('traceId','—')[:20]}…`" if r.get('traceId') else stack_str)

                if not selected_ass_id_p and len(results) > 1:
                    st.divider(); st.subheader("📊 Répartition par assistant")
                    ac, ad = {}, {}
                    for r in results:
                        ac[r['assistant']] = ac.get(r['assistant'],0) + r["coût"]
                        ad[r['assistant']] = ad.get(r['assistant'],0) + r["durée_s"]
                    for a, c in sorted(ac.items(), key=lambda x: x[1], reverse=True):
                        pct = (c/tot_cost*100) if tot_cost else 0
                        dm = ad[a]/60 if ad.get(a) else 0
                        st.markdown(f"**{esc(a)}** — `{c:.4f} €` ({pct:.1f}%)" + (f" · `{c/dm:.4f} €/min`" if dm else ""))
                        st.progress(min(pct/100, 1.0))

                # --- SYNTHÈSE PAR TECHNOLOGIE ---
                st.divider()
                st.subheader("🔬 Synthèse par technologie")

                # Grouper par stack
                stack_costs = {}
                stack_dur   = {}
                stack_count = {}
                for r in results:
                    if r.get("is_sts"):
                        model_name = r['llm'].split('/')[-1] if r.get('llm') and '/' in r['llm'] else r.get('llm','STS')
                        key = f"🎙️ STS · {model_name}"
                    else:
                        llm_short = r['llm'].split('/')[-1] if r.get('llm') and '/' in r['llm'] else r.get('llm','?')
                        key = f"🧠 {llm_short}"
                    stack_costs[key] = stack_costs.get(key, 0) + r["coût"]
                    stack_dur[key]   = stack_dur.get(key, 0)   + r["durée_s"]
                    stack_count[key] = stack_count.get(key, 0) + 1

                hs1,hs2,hs3,hs4,hs5,hs6 = st.columns([2.5,1,1.5,1.5,1.5,1.5])
                hs1.caption("Stack / Modèle"); hs2.caption("Conv."); hs3.caption("Coût total (€)")
                hs4.caption("Coût/conv. (€)"); hs5.caption("Coût/min (€)"); hs6.caption("Marge/min (€)")
                st.divider()
                for key, c in sorted(stack_costs.items(), key=lambda x: x[1], reverse=True):
                    cnt = stack_count[key]
                    dm  = stack_dur[key]/60 if stack_dur.get(key) else 0
                    cpm = c/dm if dm else 0
                    mpm = prix_vente_min - cpm if prix_vente_min > 0 else None
                    sign_m = "+" if mpm and mpm >= 0 else ""
                    clr_m  = "🟢" if mpm and mpm >= 0 else "🔴"
                    rc = st.columns([2.5,1,1.5,1.5,1.5,1.5])
                    rc[0].markdown(f"**{esc(key)}**")
                    rc[1].markdown(str(cnt))
                    rc[2].markdown(f"`{c:.4f}`")
                    rc[3].markdown(f"`{c/cnt:.4f}`" if cnt else "—")
                    rc[4].markdown(f"`{cpm:.4f}`" if dm else "—")
                    if mpm is not None: rc[5].markdown(f"{clr_m} `{sign_m}{mpm:.4f}`")
                    else: rc[5].markdown("—")
                    pct = (c/tot_cost*100) if tot_cost else 0
                    st.progress(min(pct/100, 1.0))

                # STT breakdown (mode classique uniquement)
                stt_costs  = {}
                stt_counts = {}
                for r in results:
                    if not r.get("is_sts") and r.get("stt"):
                        stt_short = r['stt'].split('/')[-1] if '/' in r['stt'] else r['stt']
                        key = f"🎤 {stt_short}"
                        stt_costs[key]  = stt_costs.get(key, 0)  + r["coût"]
                        stt_counts[key] = stt_counts.get(key, 0) + 1
                if stt_costs:
                    st.caption("**STT utilisés**")
                    for key, c in sorted(stt_costs.items(), key=lambda x: x[1], reverse=True):
                        pct = (c/tot_cost*100) if tot_cost else 0
                        st.markdown(f"{esc(key)} — `{c:.4f} €` ({pct:.1f}%) · {stt_counts[key]} conv.")

                # TTS breakdown
                tts_costs  = {}
                tts_counts = {}
                for r in results:
                    if not r.get("is_sts") and r.get("tts"):
                        key = f"🔊 {r['tts']}"
                        tts_costs[key]  = tts_costs.get(key, 0)  + r["coût"]
                        tts_counts[key] = tts_counts.get(key, 0) + 1
                if tts_costs:
                    st.caption("**TTS utilisés**")
                    for key, c in sorted(tts_costs.items(), key=lambda x: x[1], reverse=True):
                        pct = (c/tot_cost*100) if tot_cost else 0
                        st.markdown(f"{esc(key)} — `{c:.4f} €` ({pct:.1f}%) · {tts_counts[key]} conv.")

# === VUE 5 : VARIABLES ===
elif main_action == "🔑 Variables":
    st.title("Gestion des Variables")
    st.info("Syntaxe d'injection : `{ ma_variable }`")
    ch, cb = st.columns([4,1])
    with ch: scope_filter = st.radio("Périmètre", ["Toutes","Organisation","Projet"], horizontal=True, key="var_scope")
    with cb:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("➕ Nouvelle variable", use_container_width=True):
            st.session_state.var_edit_id = None; st.session_state.var_show_form = True
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.var_show_form:
        st.divider()
        st.subheader("✏️ Modifier" if st.session_state.var_edit_id else "➕ Nouvelle variable")
        pf = {}
        if st.session_state.var_edit_id:
            pf = next((v for v in fetch_variables(api_key, project_id) if v['id']==st.session_state.var_edit_id), {})
        with st.form("var_form"):
            fc1, fc2 = st.columns(2)
            with fc1:
                v_key = st.text_input("Clé *", value=pf.get("key",""), placeholder="ex: companyName")
                v_scope = st.radio("Périmètre", ["Organisation","Projet"], horizontal=True, index=0 if not pf.get("projectId") else 1)
            with fc2:
                v_secret = st.checkbox("🔒 Valeur secrète", value=pf.get("isSecret", False))
                v_value  = st.text_input("Valeur *", value="" if pf.get("isSecret") else pf.get("value",""),
                                         type="password" if v_secret else "default")
            fc3, fc4 = st.columns(2)
            with fc3: sub = st.form_submit_button("💾 Enregistrer", type="primary", use_container_width=True)
            with fc4: can = st.form_submit_button("Annuler", use_container_width=True)
        if can: st.session_state.var_show_form=False; st.session_state.var_edit_id=None; st.rerun()
        if sub:
            if not v_key.strip(): st.error("La **Clé** est obligatoire.")
            elif not v_value.strip(): st.error("La **Valeur** est obligatoire.")
            else:
                pv = {"key": v_key.strip(), "value": v_value.strip(), "isSecret": v_secret}
                if v_scope == "Projet": pv["projectId"] = project_id
                with st.spinner("Enregistrement..."):
                    rv, av = save_variable(api_key, pv, st.session_state.var_edit_id)
                    if rv.status_code in (200,201):
                        st.success(f"Variable **{v_key}** {av} !"); fetch_variables.clear()
                        st.session_state.var_show_form=False; st.session_state.var_edit_id=None; st.rerun()
                    else:
                        try: st.error(f"Échec (HTTP {rv.status_code}) : {rv.json()}")
                        except Exception: st.error(f"Échec (HTTP {rv.status_code}) : {rv.text}")

    st.divider()
    all_vars = fetch_variables(api_key, project_id)
    if scope_filter == "Organisation": displayed = [v for v in all_vars if not v.get("projectId")]
    elif scope_filter == "Projet":     displayed = [v for v in all_vars if v.get("projectId")]
    else:                              displayed = all_vars

    if not displayed: st.info("Aucune variable trouvée.")
    else:
        h1,h2,h3,h4,h5 = st.columns([2,3,1.5,0.7,0.7])
        h1.caption("Clé"); h2.caption("Valeur"); h3.caption("Périmètre"); h4.caption("Modifier"); h5.caption("Supprimer")
        st.divider()
        for var in displayed:
            c1,c2,c3,c4,c5 = st.columns([2,3,1.5,0.7,0.7])
            with c1: st.markdown(f"`{esc(var.get('key',''))}`")
            with c2:
                if var.get("isSecret"): st.markdown("🔒 *valeur masquée*")
                else: st.code(str(var.get("value","")), language=None)
            with c3: st.markdown("🏷️ Projet" if var.get("projectId") else "🌐 Organisation")
            with c4:
                if st.button("✏️", key=f"ve_{var['id']}"):
                    st.session_state.var_edit_id=var['id']; st.session_state.var_show_form=True; st.rerun()
            with c5:
                if st.button("🗑️", key=f"vd_{var['id']}"):
                    r = delete_variable(api_key, var['id'])
                    if r.status_code in (200,204): st.success("Supprimée."); fetch_variables.clear(); st.rerun()
                    else: st.error(f"Échec (HTTP {r.status_code}).")

# === VUE 6 : SERVEURS MCP ===
elif main_action == "🔌 Serveurs MCP":
    st.title("Gestion des Serveurs MCP")
    st.info("Utilisez `{ ma_variable }` dans l'URL et les headers pour injecter des secrets.")
    ch, cb = st.columns([4,1])
    with ch: mcp_scope = st.radio("Périmètre", ["Tous","Projet","Organisation"], horizontal=True, key="mcp_scope")
    with cb:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("➕ Nouveau serveur MCP", use_container_width=True):
            st.session_state.mcp_edit_id=None; st.session_state.mcp_show_form=True
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.mcp_show_form:
        st.divider()
        st.subheader("✏️ Modifier" if st.session_state.mcp_edit_id else "➕ Nouveau serveur MCP")
        mp = {}
        if st.session_state.mcp_edit_id:
            mp = next((m for m in fetch_mcps(api_key) if m['id']==st.session_state.mcp_edit_id), {})
        eh = mp.get("headers",{})
        hstr = "\n".join(f"{k}: {v}" for k,v in eh.items()) if isinstance(eh,dict) else ""
        with st.form("mcp_form"):
            mf1, mf2 = st.columns(2)
            with mf1:
                m_name  = st.text_input("Nom *",     value=mp.get("name",""))
                m_url   = st.text_input("URL SSE *", value=mp.get("url",""),  placeholder="https://api.example.com/mcp/sse")
                m_scope = st.radio("Périmètre", ["Projet","Organisation"], horizontal=True, index=0 if mp.get("projectId") else 1)
            with mf2:
                m_desc  = st.text_area("Description", value=mp.get("description",""), height=80)
                m_hstr  = st.text_area("Headers HTTP", value=hstr, height=100, placeholder="Authorization: Bearer { token }")
            mf3, mf4 = st.columns(2)
            with mf3: ms = st.form_submit_button("💾 Enregistrer", type="primary", use_container_width=True)
            with mf4: mc = st.form_submit_button("Annuler", use_container_width=True)
        if mc: st.session_state.mcp_show_form=False; st.session_state.mcp_edit_id=None; st.rerun()
        if ms:
            if not m_name.strip(): st.error("Le **Nom** est obligatoire.")
            elif not m_url.strip(): st.error("L'**URL** est obligatoire.")
            else:
                ph = {}
                for line in m_hstr.strip().split("\n"):
                    line = line.strip()
                    if ": " in line: k,v = line.split(": ",1); ph[k.strip()]=v.strip()
                pm = {"name":m_name.strip(),"url":m_url.strip(),"description":m_desc.strip(),"headers":ph}
                if m_scope == "Projet": pm["projectId"] = project_id
                with st.spinner("Enregistrement..."):
                    rm, am = save_mcp(api_key, pm, st.session_state.mcp_edit_id)
                    if rm.status_code in (200,201):
                        st.success(f"Serveur **{m_name}** {am} !"); fetch_mcps.clear()
                        st.session_state.mcp_show_form=False; st.session_state.mcp_edit_id=None; st.rerun()
                    else:
                        try: st.error(f"Échec (HTTP {rm.status_code}) : {rm.json()}")
                        except Exception: st.error(f"Échec (HTTP {rm.status_code}) : {rm.text}")

    st.divider()
    all_mcps_list = fetch_mcps(api_key)
    if mcp_scope == "Projet":       dm = [m for m in all_mcps_list if m.get("projectId")]
    elif mcp_scope == "Organisation": dm = [m for m in all_mcps_list if not m.get("projectId")]
    else:                              dm = all_mcps_list

    if not dm: st.info("Aucun serveur MCP trouvé.")
    else:
        h1,h2,h3,h4,h5,h6 = st.columns([2,3,1,1.5,0.7,0.7])
        h1.caption("Nom"); h2.caption("URL"); h3.caption("Headers"); h4.caption("Périmètre"); h5.caption("Modifier"); h6.caption("Supprimer")
        st.divider()
        for mcp in dm:
            c1,c2,c3,c4,c5,c6 = st.columns([2,3,1,1.5,0.7,0.7])
            with c1: st.markdown(f"**{esc(mcp.get('name',''))}**"); mcp.get("description") and st.caption(esc(mcp.get("description","")))
            with c2: st.code(mcp.get("url",""), language=None)
            with c3:
                h = mcp.get("headers",{})
                st.markdown(f"✅ {len(h)}" if h and isinstance(h,dict) and len(h)>0 else "—")
            with c4: st.markdown("🏷️ Projet" if mcp.get("projectId") else "🌐 Organisation")
            with c5:
                if st.button("✏️", key=f"me_{mcp['id']}"):
                    st.session_state.mcp_edit_id=mcp['id']; st.session_state.mcp_show_form=True; st.rerun()
            with c6:
                if st.button("🗑️", key=f"md_{mcp['id']}"):
                    r = delete_mcp(api_key, mcp['id'])
                    if r.status_code in (200,204): st.success("Supprimé."); fetch_mcps.clear(); st.rerun()
                    else: st.error(f"Échec (HTTP {r.status_code}).")

# === VUE 7 : LOGS API ===
elif main_action == "📡 Logs API":
    st.title("Logs Réseau (10 dernières requêtes)")
    col_btn, _ = st.columns([1,4])
    with col_btn:
        if st.button("🗑️ Vider les logs", use_container_width=True):
            st.session_state.api_logs = []; st.rerun()
    st.divider()
    if not st.session_state.api_logs:
        st.info("Aucune requête API enregistrée pendant cette session.")
    else:
        for log in reversed(st.session_state.api_logs):
            status = log['status_code']
            icon = "🟢" if isinstance(status,int) and 200<=status<300 else ("🟠" if isinstance(status,int) and 400<=status<500 else "🔴") if isinstance(status,int) else "❌"
            with st.expander(f"{icon} [{log['timestamp']}] {log['method']} — {log['url']} (Status: {status})"):
                cr, cr2 = st.columns(2)
                with cr:
                    st.markdown("### 📤 Requête")
                    if log['req_params']: st.caption("Paramètres :"); st.json(log['req_params'])
                    if log['req_body']:   st.caption("Corps :"); st.json(log['req_body'])
                    elif not log['req_params']: st.info("Aucun paramètre ni corps.")
                with cr2:
                    st.markdown("### 📥 Réponse")
                    if log['resp_body']: st.json(log['resp_body'])
                    else: st.info("Aucun contenu retourné.")
