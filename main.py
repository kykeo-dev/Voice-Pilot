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

API_BASE = "https://newprd.reecall.io/data_next"
API_ROOT = "https://newprd.reecall.io"
METRICS_BASE = "https://newprd.reecall.io/metrics/v1"

LOGO_URL = (
    "https://media.licdn.com/dms/image/v2/D4E0BAQE_HZvoIBQM9g/"
    "company-logo_200_200/company-logo_200_200/0/1695887075709/"
    "axialys_logo?e=2147483647&v=beta&t=8NbSO8rggmFIAWcnJQ1ocq2k-wrdv5A9FXDZVzluIqM"
)

SUPPORTED_LANGUAGES = ["fr-FR", "en-US", "en-GB", "es-ES", "de-DE", "it-IT"]
SIP_HEADER_OPTIONS = ["SIP_ALL_HEADERS", "SIP_X_HEADERS", "SIP_NO_HEADERS"]

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

# --- CSS AXIALYS ---
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
    .log-method { font-weight: bold; color: #3D6FA3; }
    .extraction-row { padding: 10px; border: 1px solid rgba(128,128,128,0.2); border-radius: 8px; margin-bottom: 5px; background-color: var(--secondary-background-color); color: var(--text-color); }
    .engine-mode-card { padding: 12px 16px; border-radius: 8px; border: 2px solid rgba(61,111,163,0.3); background-color: var(--secondary-background-color); margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)


# --- UTILITAIRES ---
def esc(value):
    return html.escape(str(value)) if value else ""


# --- GESTION DE L'ETAT ---
if 'form_data' not in st.session_state or not isinstance(st.session_state.form_data, dict):
    st.session_state.form_data = {}
if 'last_loaded_id' not in st.session_state:
    st.session_state.last_loaded_id = None
if 'previous_action' not in st.session_state:
    st.session_state.previous_action = "✏️ Modifier / Tester un assistant"
if 'call_data' not in st.session_state:
    st.session_state.call_data = None
if 'api_logs' not in st.session_state:
    st.session_state.api_logs = []
if 'var_edit_id' not in st.session_state:
    st.session_state.var_edit_id = None
if 'var_show_form' not in st.session_state:
    st.session_state.var_show_form = False
if 'mcp_edit_id' not in st.session_state:
    st.session_state.mcp_edit_id = None
if 'mcp_show_form' not in st.session_state:
    st.session_state.mcp_show_form = False


def reset_form():
    st.session_state.form_data = {
        "name": "", "description": "", "instructions": "Tu es un assistant utile...",
        "firstMessage": "Bonjour, bienvenue chez Axialys !", "temperature": 0.3, "language": "fr-FR",
        "timezone": "Europe/Paris", "llmId": None, "sttId": None, "ttsId": None, "voiceId": None,
        "stsId": None, "engine_mode": "Classique (STT + LLM + TTS)", "id": None,
        "knowledgeBaseIds": [], "mcpIds": [], "mcps": [],
        "extraction_fields": [],
        "end_conversation_enabled": False, "closing_message": "",
        "description_override": "", "disable_interruptions": False
    }
    st.session_state.last_loaded_id = None
    st.session_state.call_data = None


def load_assistant_into_form(assistant, tools=[]):
    llm_id = assistant.get('llmId') or ((assistant.get('llm') or {}).get('id'))
    tts_id = assistant.get('ttsId') or ((assistant.get('tts') or {}).get('id'))
    stt_id = assistant.get('sttId') or ((assistant.get('stt') or {}).get('id'))
    sts_id = assistant.get('stsId') or ((assistant.get('sts') or {}).get('id'))
    voice_uuid = assistant.get('voiceId')
    if not voice_uuid and assistant.get('voice'):
        voice_uuid = assistant.get('voice').get('id')

    engine_mode = "STS (Speech-to-Speech)" if sts_id else "Classique (STT + LLM + TTS)"

    kb_ids = assistant.get('knowledgeBaseIds', [])
    if not isinstance(kb_ids, list): kb_ids = []
    mcp_ids = assistant.get('mcpIds', [])
    if not isinstance(mcp_ids, list): mcp_ids = []

    raw_mcps = assistant.get('mcps', [])
    clean_mcp_urls = []
    if isinstance(raw_mcps, list):
        for item in raw_mcps:
            if isinstance(item, str): clean_mcp_urls.append(item)
            elif isinstance(item, dict) and 'url' in item: clean_mcp_urls.append(item['url'])

    extraction_fields = []
    schema_obj = assistant.get('dataExtractionSchema')
    if schema_obj and isinstance(schema_obj, dict):
        props = schema_obj.get("properties", {})
        req = schema_obj.get("required", [])
        for k, v in props.items():
            extraction_fields.append({
                "name": k, "type": v.get("type", "string"),
                "description": v.get("description", ""), "required": k in req,
                "enum": ", ".join(v.get("enum", [])) if isinstance(v.get("enum"), list) else ""
            })

    end_tool = next((t for t in tools if t.get('definition', {}).get('name') == 'end_conversation'), None)

    st.session_state.form_data = {
        "name": assistant.get('name', ''), "description": assistant.get('description', ''),
        "instructions": assistant.get('instructions', ''), "firstMessage": assistant.get('firstMessage', ''),
        "temperature": assistant.get('temperature', 0.3), "language": assistant.get('language', 'fr-FR'),
        "timezone": assistant.get('timezone', 'Europe/Paris'),
        "llmId": llm_id, "sttId": stt_id, "ttsId": tts_id, "voiceId": voice_uuid,
        "stsId": sts_id, "engine_mode": engine_mode,
        "id": assistant.get('id'),
        "knowledgeBaseIds": kb_ids, "mcpIds": mcp_ids, "mcps": clean_mcp_urls,
        "extraction_fields": extraction_fields,
        "end_conversation_enabled": end_tool is not None,
        "closing_message": (end_tool.get('configuration') or {}).get('closingMessage', '') if end_tool else '',
        "description_override": end_tool.get('descriptionOverride', '') if end_tool else '',
        "disable_interruptions": end_tool.get('disableInterruptions', False) if end_tool else False
    }
    st.session_state.call_data = None


def format_date(iso_string):
    try:
        clean_str = iso_string.replace('Z', '+00:00')
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y à %H:%M:%S")
    except Exception:
        return iso_string


# --- SYSTEME DE LOGGING API ---
def log_api_call(method, url, req_kwargs, response):
    if len(st.session_state.api_logs) >= 10:
        st.session_state.api_logs.pop(0)
    headers = req_kwargs.get("headers", {}).copy()
    if "Authorization" in headers:
        headers["Authorization"] = "Bearer ********"
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
        "method": method.upper(), "url": url, "req_headers": headers,
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


# --- API CORE ---
@st.cache_data(ttl=300, show_spinner=False)
def fetch_lists(api_key):
    headers = {'Authorization': f'Bearer {api_key}'}
    try:
        llm = requests.get(f"{API_BASE}/ai/llm", headers=headers, timeout=15)
        stt = requests.get(f"{API_BASE}/ai/stt/", headers=headers, timeout=15)
        tts = requests.get(f"{API_BASE}/ai/tts", headers=headers, timeout=15)
        sts = requests.get(f"{API_BASE}/ai/sts/", headers=headers, timeout=15)
        if any(r.status_code != 200 for r in [llm, stt, tts]):
            return None
        sts_data = sts.json() if sts.status_code == 200 else []
        return {'llm': llm.json(), 'stt': stt.json(), 'tts': tts.json(), 'sts': sts_data}
    except Exception:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def fetch_mcps(api_key):
    headers = {'Authorization': f'Bearer {api_key}'}
    try:
        resp = requests.get(f"{API_BASE}/ai/MCP/", headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict): return data.get("data", data.get("items", []))
            if isinstance(data, list): return data
        return []
    except Exception:
        return []


@st.cache_data(ttl=30, show_spinner=False)
def fetch_assistants(api_key, project_id=""):
    headers = {'Authorization': f'Bearer {api_key}'}
    params = {}
    if project_id:
        params["where"] = json.dumps({"projectId": project_id})
    try:
        resp = requests.get(f"{API_BASE}/conversational/assistants/", headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict): return data.get("data", data.get("items", []))
            if isinstance(data, list): return data
        return []
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def check_workspace(api_key, project_id):
    headers = {'Authorization': f'Bearer {api_key}'}
    where_param = json.dumps({"projectId": project_id})
    try:
        resp = requests.get(f"{API_BASE}/conversational/exchanges/", headers=headers,
                            params={"where": where_param, "limit": 1}, timeout=15)
        return resp.status_code == 200
    except Exception:
        return False


@st.cache_data(ttl=30, show_spinner=False)
def fetch_sip_channel(api_key, assistant_id):
    headers = {'Authorization': f'Bearer {api_key}'}
    params = {"where": json.dumps({"assistantId": assistant_id, "type": "SIP"})}
    try:
        resp = requests.get(f"{API_BASE}/conversational/channels/", headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            channels = data.get("data", data.get("items", data)) if isinstance(data, dict) else data
            return channels[0] if channels else None
        return None
    except Exception:
        return None


@st.cache_data(ttl=30, show_spinner=False)
def fetch_variables(api_key, project_id=""):
    headers = {'Authorization': f'Bearer {api_key}'}
    params = {}
    if project_id:
        params["where"] = json.dumps({"projectId": project_id})
    try:
        resp = requests.get(f"{API_BASE}/core/variables", headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict): return data.get("data", data.get("items", []))
            if isinstance(data, list): return data
        return []
    except Exception:
        return []


def fetch_exchange_cost(api_key, trace_id, created_at, updated_at):
    headers = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
    try:
        from_day = (created_at or "")[:10] + "T00:00:00Z"
        to_day   = (created_at or "")[:10] + "T23:59:59Z"
        params = {"metrics": COST_METRICS, "from": from_day, "to": to_day, "traceId": trace_id}
        resp = make_api_request('GET', f"{METRICS_BASE}/metrics/bulkAll", headers=headers, params=params)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                total = sum(item.get('pricing', 0) or 0 for item in data)
                details = [
                    {"metric": item['metric'], "pricing": item.get('pricing', 0) or 0,
                     "value": item.get('data', {}).get('sum', 0)}
                    for item in data if (item.get('pricing') or 0) > 0
                ]
                return {"total": total, "details": details}
        return None
    except Exception:
        return None


def fetch_cost_by_assistant(api_key, assistant_id, from_iso, to_iso):
    """Coût agrégé sur la période pour un assistant via le paramètre context."""
    headers = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
    try:
        params = {
            "metrics": COST_METRICS,
            "from": from_iso,
            "to": to_iso,
            "context": json.dumps({"assistantId": assistant_id})
        }
        resp = make_api_request('GET', f"{METRICS_BASE}/metrics/bulkAll", headers=headers, params=params)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                total      = sum(item.get('pricing', 0) or 0 for item in data)
                conv_count = next((item['data']['sum'] for item in data if item['metric'] == 'exchangeCount'), 0)
                total_dur  = next((item['data']['sum'] for item in data if item['metric'] == 'duration'), 0)
                details    = [
                    {"metric": item['metric'], "pricing": item.get('pricing', 0) or 0,
                     "value": item.get('data', {}).get('sum', 0)}
                    for item in data if (item.get('pricing') or 0) > 0
                ]
                return {"total": total, "conv_count": int(conv_count), "total_dur_s": total_dur, "details": details}
        return None
    except Exception:
        return None


def fetch_cost_global(api_key, project_id, from_iso, to_iso):
    """Coût agrégé global sur la période (tous assistants) — 1 seul appel API."""
    headers = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
    try:
        params = {"metrics": COST_METRICS, "from": from_iso, "to": to_iso, "projectId": project_id}
        resp = make_api_request('GET', f"{METRICS_BASE}/metrics/bulkAll", headers=headers, params=params)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                total = sum(item.get('pricing', 0) or 0 for item in data)
                conv_count = next((item['data']['sum'] for item in data if item['metric'] == 'exchangeCount'), 0)
                total_dur  = next((item['data']['sum'] for item in data if item['metric'] == 'duration'), 0)
                details = [
                    {"metric": item['metric'], "pricing": item.get('pricing', 0) or 0,
                     "value": item.get('data', {}).get('sum', 0)}
                    for item in data if (item.get('pricing') or 0) > 0
                ]
                return {"total": total, "conv_count": int(conv_count), "total_dur_s": total_dur, "details": details}
        return None
    except Exception:
        return None
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    if assistant_id:
        return make_api_request('PATCH', f"{API_BASE}/conversational/assistants/{assistant_id}",
                                headers=headers, json=payload), "modifié"
    else:
        return make_api_request('POST', f"{API_BASE}/conversational/assistants/",
                                headers=headers, json=payload), "créé"


def save_variable(api_key, payload, variable_id=None):
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    if variable_id:
        return make_api_request('PATCH', f"{API_BASE}/core/variables/{variable_id}",
                                headers=headers, json=payload), "modifiée"
    else:
        return make_api_request('POST', f"{API_BASE}/core/variables",
                                headers=headers, json=payload), "créée"


def delete_variable(api_key, variable_id):
    headers = {'Authorization': f'Bearer {api_key}'}
    return make_api_request('DELETE', f"{API_BASE}/core/variables/{variable_id}", headers=headers)


def save_mcp(api_key, payload, mcp_id=None):
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    if mcp_id:
        return make_api_request('PATCH', f"{API_BASE}/ai/MCP/{mcp_id}", headers=headers, json=payload), "modifié"
    else:
        return make_api_request('POST', f"{API_BASE}/ai/MCP/", headers=headers, json=payload), "créé"


def delete_mcp(api_key, mcp_id):
    headers = {'Authorization': f'Bearer {api_key}'}
    return make_api_request('DELETE', f"{API_BASE}/ai/MCP/{mcp_id}", headers=headers)


def fetch_assistant_tools(api_key, assistant_id):
    headers = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
    where_param = json.dumps({"assistantId": assistant_id})
    try:
        resp = make_api_request('GET', f"{API_BASE}/ai/tools", headers=headers, params={"where": where_param})
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception:
        return []


def manage_system_tools(api_key, assistant_id, project_id, enable_end_call,
                        closing_message, description_override, disable_interruptions):
    headers_auth = {'Authorization': f'Bearer {api_key}'}
    headers_json = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    defs_resp = make_api_request('GET', f"{API_BASE}/ai/toolDefinitions", headers=headers_auth)
    if defs_resp.status_code != 200:
        return False, f"Impossible de récupérer les définitions (HTTP {defs_resp.status_code})."
    defs = defs_resp.json()
    end_def = next((d for d in defs if d.get('name') == 'end_conversation'), None)
    if not end_def:
        return False, "Définition 'end_conversation' introuvable."
    def_id = end_def['id']
    existing_tools = fetch_assistant_tools(api_key, assistant_id)
    existing_end_tool = next((t for t in existing_tools if t.get('definitionId') == def_id), None)
    if enable_end_call:
        payload = {"assistantId": assistant_id, "projectId": project_id,
                   "definitionId": def_id, "disableInterruptions": disable_interruptions}
        if closing_message and closing_message.strip():
            payload["configuration"] = {"closingMessage": closing_message.strip()}
        if description_override and description_override.strip():
            payload["descriptionOverride"] = description_override.strip()
        if existing_end_tool:
            del_resp = make_api_request('DELETE', f"{API_BASE}/ai/tools/{existing_end_tool['id']}",
                                        headers=headers_auth)
            if del_resp.status_code not in (200, 204):
                return False, f"Échec suppression ancien outil (HTTP {del_resp.status_code})."
        create_resp = make_api_request('POST', f"{API_BASE}/ai/tools/", headers=headers_json, json=payload)
        if create_resp.status_code not in (200, 201):
            return False, f"Échec création outil (HTTP {create_resp.status_code})."
    else:
        if existing_end_tool:
            del_resp = make_api_request('DELETE', f"{API_BASE}/ai/tools/{existing_end_tool['id']}",
                                        headers=headers_auth)
            if del_resp.status_code not in (200, 204):
                return False, f"Échec suppression outil (HTTP {del_resp.status_code})."
    return True, "OK"


# --- API CHANNELS & EXCHANGES ---
def get_or_create_webrtc_channel(api_key, assistant_id, assistant_name, project_id):
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    try:
        params = {"where": json.dumps({"assistantId": assistant_id, "type": "WEBRTC"})}
        resp = make_api_request('GET', f"{API_BASE}/conversational/channels/", headers=headers, params=params)
        channels = resp.json()
        if isinstance(channels, dict):
            channels = channels.get("data", channels.get("items", []))
        if channels:
            return channels[0]['id']
        payload = {"name": f"WebRTC - {assistant_name}", "type": "WEBRTC",
                   "assistantId": assistant_id, "projectId": project_id}
        resp = make_api_request('POST', f"{API_BASE}/conversational/channels/", headers=headers, json=payload)
        if resp.status_code in [200, 201]:
            return resp.json()['id']
        st.error(f"Création du canal WebRTC échouée (HTTP {resp.status_code}).")
        return None
    except Exception as exc:
        st.error(f"Erreur réseau WebRTC : {exc}")
        return None


def get_call_token(api_key, channel_id):
    headers = {'Authorization': f'Bearer {api_key}'}
    try:
        resp = make_api_request('POST', f"{API_ROOT}/calls/{channel_id}", headers=headers)
        if resp.status_code == 200:
            return resp.json()
        st.error(f"Impossible de générer le token (HTTP {resp.status_code}).")
        return None
    except Exception as exc:
        st.error(f"Erreur réseau token : {exc}")
        return None


def save_sip_channel(api_key, channel_id, payload):
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    try:
        if channel_id:
            return make_api_request('PATCH', f"{API_BASE}/conversational/channels/{channel_id}",
                                    headers=headers, json=payload)
        else:
            return make_api_request('POST', f"{API_BASE}/conversational/channels/",
                                    headers=headers, json=payload)
    except Exception as exc:
        st.error(f"Erreur réseau SIP : {exc}")
        return None


def fetch_exchanges(api_key, project_id):
    headers = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
    where_param = json.dumps({"projectId": project_id})
    order_by_param = json.dumps({"createdAt": "desc"})
    try:
        resp = make_api_request('GET', f"{API_BASE}/conversational/exchanges/", headers=headers,
                                params={"where": where_param, "orderBy": order_by_param, "limit": 100})
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict): return data.get("data", data.get("items", []))
            return data
        st.warning(f"Impossible de charger les conversations (HTTP {resp.status_code}).")
        return []
    except Exception as exc:
        st.error(f"Erreur réseau : {exc}")
        return []


def fetch_exchanges_range(api_key, project_id, from_iso, to_iso, assistant_id=None):
    headers = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
    where = {"projectId": project_id, "createdAt": {"$gte": from_iso, "$lte": to_iso}}
    if assistant_id:
        where["assistantId"] = assistant_id
    try:
        resp = make_api_request('GET', f"{API_BASE}/conversational/exchanges/", headers=headers,
                                params={"where": json.dumps(where),
                                        "orderBy": json.dumps({"createdAt": "desc"}),
                                        "limit": 200})
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict): return data.get("data", data.get("items", []))
            return data
        return []
    except Exception:
        return []


def fetch_exchange_details(api_key, exchange_id):
    headers = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
    try:
        resp = make_api_request('GET', f"{API_BASE}/conversational/exchanges/{exchange_id}/", headers=headers)
        if resp.status_code == 200:
            return resp.json()
        st.warning(f"Détails indisponibles (HTTP {resp.status_code}).")
        return None
    except Exception as exc:
        st.error(f"Erreur réseau : {exc}")
        return None


# =============================================================================
# --- SIDEBAR & NAVIGATION ---
# =============================================================================
with st.sidebar:
    st.image(LOGO_URL, width=150)
    st.divider()
    st.caption("🔧 Configuration Technique")

    api_key = st.text_input("Clé API", type="password", value=args.api_key, help="Entrez votre clé API Reecall")
    lists = None
    available_mcps = []
    api_valid = False

    if api_key:
        with st.spinner("Vérification de la clé..."):
            lists = fetch_lists(api_key)
            if lists:
                st.success("✅ Clé API valide")
                api_valid = True
                available_mcps = fetch_mcps(api_key)
            else:
                st.error("❌ Clé API invalide ou mal copiée")

    project_id = st.text_input("ID Projet (Workspace)", value=args.project_id, help="Entrez l'UUID de votre projet/workspace")
    project_valid = False

    if project_id:
        try:
            uuid.UUID(str(project_id))
            is_uuid = True
        except ValueError:
            is_uuid = False

        if not is_uuid:
            st.error("❌ Format invalide (L'ID doit ressembler à 123e4567-...)")
        elif api_valid:
            with st.spinner("Vérification du Workspace..."):
                if check_workspace(api_key, project_id):
                    st.success("✅ Workspace connecté")
                    project_valid = True
                else:
                    st.error("❌ Workspace introuvable ou accès refusé")
        else:
            st.warning("⚠️ Validez d'abord votre Clé API au-dessus.")

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
        if main_action == "✨ Créer un nouvel assistant":
            reset_form()
        st.session_state.previous_action = main_action

    if main_action == "✏️ Modifier / Tester un assistant" and assistants_list:
        st.divider()
        ass_options = {a.get('name', 'Sans nom'): a['id'] for a in assistants_list}
        selected_name = st.selectbox("Sélectionnez l'assistant :", list(ass_options.keys()))
        selected_id = ass_options[selected_name]
        if selected_id != st.session_state.last_loaded_id:
            st.session_state.last_loaded_id = selected_id
            st.session_state['_pending_load_id'] = selected_id

# =============================================================================
# CHARGEMENT DIFFÉRÉ — hors sidebar
# =============================================================================
if st.session_state.get('_pending_load_id'):
    pending_id = st.session_state.pop('_pending_load_id')
    full_obj = next((a for a in assistants_list if a['id'] == pending_id), None)
    if full_obj:
        with st.spinner("Chargement de l'assistant et de ses outils..."):
            tools = fetch_assistant_tools(api_key, pending_id)
            load_assistant_into_form(full_obj, tools)


# =============================================================================
# --- MAIN PAGE ROUTING ---
# =============================================================================
if not api_valid or not project_valid:
    st.title("Voice Pilot")
    st.info("👋 Bienvenue ! Veuillez configurer vos accès dans le menu de gauche pour démarrer l'application.")
    if api_key and not api_valid:
        st.error("🔒 La Clé API renseignée est incorrecte.")
    elif api_valid and project_id and not project_valid:
        st.error("📂 L'ID Projet renseigné est introuvable, mal formaté, ou vous n'y avez pas accès.")
    elif api_valid and not project_id:
        st.warning("👉 Clé API validée. Il ne vous reste plus qu'à renseigner l'ID Projet à gauche.")

# === VUES 1 & 2 : CRÉATION OU MODIFICATION ===
elif main_action in ["✨ Créer un nouvel assistant", "✏️ Modifier / Tester un assistant"]:
    is_creation = main_action == "✨ Créer un nouvel assistant"
    fd = st.session_state.form_data
    widget_key_suffix = fd.get("id") or "new"

    assistant_name_display = st.session_state.get("form_data", {}).get("name", "") or "Nouvel assistant"
    st.title("Création d'un nouvel assistant" if is_creation else f"Configuration de l'Assistant — {assistant_name_display}")

    with st.container():
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

    # --- OUTILS SYSTÈME ---
    st.subheader("☎️ Contrôle d'Appel (Outils Système)")
    st.info("Autorisez le bot à exécuter des actions système, comme mettre fin à l'appel de sa propre initiative.")
    st.caption("ℹ️ **Comportement natif :** Par défaut, l'IA décide de raccrocher lorsque l'utilisateur dit explicitement au revoir.")

    col_sys1, col_sys2 = st.columns(2)
    with col_sys1:
        enable_end_call = st.checkbox("Activer le raccrochage automatique",
                                      value=fd.get("end_conversation_enabled", False),
                                      key=f"end_call_{widget_key_suffix}")
        closing_msg = st.text_input("Message de clôture (Optionnel)", value=fd.get("closing_message", ""),
                                    disabled=not enable_end_call, placeholder="Merci pour votre appel, à bientôt !",
                                    key=f"close_msg_{widget_key_suffix}")
        disable_interruptions = st.checkbox("Désactiver les interruptions pendant la clôture",
                                            value=fd.get("disable_interruptions", False),
                                            disabled=not enable_end_call,
                                            key=f"dis_int_{widget_key_suffix}")
    with col_sys2:
        desc_override = st.text_area("Consignes de raccrochage (descriptionOverride)",
                                     value=fd.get("description_override", ""), disabled=not enable_end_call,
                                     placeholder="Ex: Raccroche UNIQUEMENT si le client a validé son rendez-vous...",
                                     height=100, key=f"desc_over_{widget_key_suffix}")

    st.divider()

    # --- DATA EXTRACTION ---
    st.subheader("📊 Variables à extraire (Data Extraction)")
    st.info("Définissez les informations que l'IA doit structurer à la fin de la conversation.")
    fields = fd.get("extraction_fields", [])

    if len(fields) > 0:
        hc1, hc2, hc3, hc4, hc5, hc6 = st.columns([2, 1.5, 3, 2, 1, 0.5])
        hc1.caption("Clé"); hc2.caption("Type"); hc3.caption("Description pour l'IA")
        hc4.caption("Choix imposés (A, B)"); hc5.caption("Oblig.")

    for i, field in enumerate(fields):
        with st.container():
            st.markdown("<div class='extraction-row'>", unsafe_allow_html=True)
            col1, col2, col3, col4, col5, col6 = st.columns([2, 1.5, 3, 2, 1, 0.5])
            with col1:
                field['name'] = st.text_input("Nom", value=field.get('name', ''),
                                              key=f"f_name_{widget_key_suffix}_{i}", label_visibility="collapsed")
            with col2:
                t_opts = ["string", "boolean", "number"]
                c_val = field.get('type', 'string')
                field['type'] = st.selectbox("Type", t_opts, index=t_opts.index(c_val) if c_val in t_opts else 0,
                                             key=f"f_type_{widget_key_suffix}_{i}", label_visibility="collapsed")
            with col3:
                field['description'] = st.text_input("Desc", value=field.get('description', ''),
                                                     key=f"f_desc_{widget_key_suffix}_{i}",
                                                     label_visibility="collapsed", placeholder="Sert à...")
            with col4:
                field['enum'] = st.text_input("Enum", value=field.get('enum', ''),
                                              key=f"f_enum_{widget_key_suffix}_{i}",
                                              disabled=field['type'] != 'string',
                                              label_visibility="collapsed", placeholder="Tech, Vente")
            with col5:
                st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
                field['required'] = st.checkbox("", value=field.get('required', False),
                                                key=f"f_req_{widget_key_suffix}_{i}")
            with col6:
                if st.button("❌", key=f"f_del_{widget_key_suffix}_{i}"):
                    st.session_state.form_data['extraction_fields'].pop(i)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    if st.button("➕ Ajouter une variable"):
        if "extraction_fields" not in st.session_state.form_data:
            st.session_state.form_data['extraction_fields'] = []
        st.session_state.form_data['extraction_fields'].append(
            {"name": "", "type": "string", "description": "", "enum": "", "required": False})
        st.rerun()

    st.divider()

    # --- MCP ---
    st.subheader("🔌 Outils & Intégrations (MCP)")
    col_mcp1, col_mcp2 = st.columns(2)
    with col_mcp1:
        st.markdown("**Catalogue MCP (Reecall)**")
        mcp_options = {m.get('name', 'Sans nom'): m['id'] for m in available_mcps} if available_mcps else {}
        default_mcp_names = [n for n, mid in mcp_options.items() if mid in fd.get("mcpIds", [])]
        selected_mcp_names = st.multiselect("Sélectionnez les serveurs à activer :",
                                            options=list(mcp_options.keys()), default=default_mcp_names,
                                            key=f"mcp_select_{widget_key_suffix}")
        selected_mcp_ids = [mcp_options[n] for n in selected_mcp_names]
    with col_mcp2:
        st.markdown("**URLs personnalisées (Tests locaux)**")
        mcp_urls_str = st.text_area("Adresses SSE directes (une par ligne) :",
                                    value="\n".join(fd.get("mcps", [])), height=68,
                                    placeholder="https://a1b2.ngrok.app/sse", label_visibility="collapsed",
                                    key=f"mcp_urls_{widget_key_suffix}")
        mcp_urls_list = [url.strip() for url in mcp_urls_str.split("\n") if url.strip()]

    st.divider()

    # --- MOTEUR TECHNIQUE ---
    st.subheader("⚙️ Moteur Technique")
    ENGINE_MODES = ["Classique (STT + LLM + TTS)", "STS (Speech-to-Speech)"]
    cur_mode = fd.get("engine_mode", "Classique (STT + LLM + TTS)")
    engine_mode = st.radio("Mode du moteur vocal", ENGINE_MODES,
                           index=ENGINE_MODES.index(cur_mode) if cur_mode in ENGINE_MODES else 0,
                           horizontal=True, key=f"engine_mode_{widget_key_suffix}",
                           help="**Classique** : pipeline STT → LLM → TTS séparé. **STS** : modèle natif audio unifié, latence réduite.")

    def get_idx(opts, target):
        return list(opts.values()).index(target) if target in opts.values() else 0

    final_llm_id = final_stt_id = final_tts_id = final_voice_id = final_sts_id = None

    if engine_mode == "Classique (STT + LLM + TTS)":
        st.markdown("<div class='engine-mode-card'>", unsafe_allow_html=True)
        tc1, tc2, tc3 = st.columns(3)
        with tc1:
            st.markdown("**🧠 LLM**")
            llm_opts = {i['name']: i['id'] for i in lists['llm']}
            final_llm_id = llm_opts[st.selectbox("Modèle LLM", list(llm_opts.keys()),
                                                  index=get_idx(llm_opts, fd.get("llmId")),
                                                  key=f"llm_{widget_key_suffix}")]
        with tc2:
            st.markdown("**🎤 STT**")
            stt_opts = {i['name']: i['id'] for i in lists['stt']}
            final_stt_id = stt_opts[st.selectbox("Modèle STT", list(stt_opts.keys()),
                                                  index=get_idx(stt_opts, fd.get("sttId")),
                                                  key=f"stt_{widget_key_suffix}")]
        with tc3:
            st.markdown("**🔊 TTS**")
            tts_map = {p['name']: p for p in lists['tts']}
            prov_names = list(tts_map.keys())
            prov_idx = 0
            if fd.get("ttsId"):
                for i, pn in enumerate(prov_names):
                    if tts_map[pn]['id'] == fd.get("ttsId"): prov_idx = i; break
            prov_data = tts_map[st.selectbox("Fournisseur TTS", prov_names, index=prov_idx,
                                             key=f"tts_prov_{widget_key_suffix}")]
            final_tts_id = prov_data['id']
            voices = prov_data.get('voices', [])
            if voices:
                v_opts = {v['name']: v['id'] for v in voices}
                final_voice_id = v_opts[st.selectbox("Voix", list(v_opts.keys()),
                                                     index=get_idx(v_opts, fd.get("voiceId")),
                                                     key=f"voice_{widget_key_suffix}")]
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='engine-mode-card'>", unsafe_allow_html=True)
        sts_list = lists.get('sts', [])
        if not sts_list:
            st.warning("Aucun modèle STS disponible via l'API.")
        else:
            sc1, sc2 = st.columns(2)
            with sc1:
                st.markdown("**🎙️ Modèle STS**")
                sts_active = [m for m in sts_list if not m.get('disabled', False)]
                sts_opts = {f"{m['name']} ({m.get('provider','')})": m for m in sts_active}
                sts_default_idx = 0
                if fd.get("stsId"):
                    for i, m in enumerate(sts_active):
                        if m['id'] == fd.get("stsId"): sts_default_idx = i; break
                selected_sts = sts_opts[st.selectbox("Modèle STS", list(sts_opts.keys()),
                                                     index=sts_default_idx, key=f"sts_model_{widget_key_suffix}")]
                final_sts_id = selected_sts['id']
                st.caption(selected_sts.get('description', ''))
            with sc2:
                st.markdown("**🔊 Voix**")
                sts_voices = selected_sts.get('voices', [])
                if sts_voices:
                    v_opts = {}
                    for v in sts_voices:
                        g = "👨" if v.get('gender') == 'male' else ("👩" if v.get('gender') == 'female' else "🧑")
                        v_opts[f"{g} {v['name']} [{v.get('language','')}]"] = v['id']
                    voice_default_idx = 0
                    if fd.get("voiceId") and fd.get("voiceId") in list(v_opts.values()):
                        voice_default_idx = list(v_opts.values()).index(fd.get("voiceId"))
                    sel_lbl = st.selectbox("Voix STS", list(v_opts.keys()),
                                          index=voice_default_idx, key=f"sts_voice_{widget_key_suffix}")
                    final_voice_id = v_opts[sel_lbl]
                    sel_v = next((v for v in sts_voices if v['id'] == final_voice_id), {})
                    if sel_v.get('description'): st.caption(sel_v['description'])
                    if sel_v.get('multilingual'): st.caption("🌍 Voix multilingue")
        st.markdown("</div>", unsafe_allow_html=True)
        st.caption("ℹ️ En mode STS, le LLM, STT et TTS sont gérés nativement par le modèle sélectionné.")

    st.divider()

    # --- SAUVEGARDE & DÉPLOIEMENT ---
    col_save, col_deploy = st.columns(2)
    with col_save:
        lbl = "🚀 CRÉER L'ASSISTANT" if is_creation else "💾 SAUVEGARDER LES MODIFICATIONS"
        if st.button(lbl, type="primary", use_container_width=True):
            validation_errors = []
            if not name or not name.strip(): validation_errors.append("Le **Nom** est obligatoire.")
            if not inst or not inst.strip(): validation_errors.append("Le **System Prompt** est obligatoire.")
            if engine_mode == "Classique (STT + LLM + TTS)" and not final_voice_id:
                validation_errors.append("La **Voix** est obligatoire.")
            if engine_mode == "STS (Speech-to-Speech)" and not final_sts_id:
                validation_errors.append("Le **modèle STS** est obligatoire.")
            if validation_errors:
                for err in validation_errors: st.error(err)
            else:
                parsed_schema = None
                valid_fields = [f for f in fields if f.get('name', '').strip()]
                if valid_fields:
                    properties = {}
                    required_fields = []
                    for f in valid_fields:
                        v_name = f['name'].strip()
                        prop = {"type": f['type'], "description": f['description'].strip()}
                        if f['enum'].strip() and f['type'] == 'string':
                            prop["enum"] = [e.strip() for e in f['enum'].split(",") if e.strip()]
                        properties[v_name] = prop
                        if f['required']: required_fields.append(v_name)
                    required_fields = [r for r in required_fields if r in properties]
                    parsed_schema = {"type": "object", "properties": properties,
                                     "required": required_fields, "additionalProperties": False}

                payload = {"name": name.strip(), "description": desc, "instructions": inst, "language": lang,
                           "projectId": project_id, "firstMessage": first_msg,
                           "timezone": "Europe/Paris", "temperature": temp,
                           "knowledgeBaseIds": fd.get("knowledgeBaseIds", []),
                           "mcpIds": selected_mcp_ids, "mcps": mcp_urls_list,
                           "dataExtractionSchema": parsed_schema}

                if engine_mode == "STS (Speech-to-Speech)":
                    payload.update({"stsId": final_sts_id, "voiceId": final_voice_id,
                                    "llmId": None, "sttId": None, "ttsId": None})
                else:
                    payload.update({"llmId": final_llm_id, "ttsId": final_tts_id,
                                    "sttId": final_stt_id, "voiceId": final_voice_id, "stsId": None})

                target_id = fd.get("id") if not is_creation else None
                with st.spinner('Envoi en cours...'):
                    resp, act = save_assistant(api_key, payload, target_id)
                    if resp.status_code in [200, 201]:
                        assistant_id = resp.json().get('id')
                        if not assistant_id:
                            st.error("L'API a répondu avec succès mais sans renvoyer d'ID.")
                        else:
                            tool_ok, tool_msg = manage_system_tools(
                                api_key, assistant_id, project_id,
                                enable_end_call, closing_msg, desc_override, disable_interruptions)
                            if not tool_ok: st.warning(f"Assistant {act}, mais outil raccrochage échoué : {tool_msg}")
                            else: st.success(f"Succès ({act}) !")
                            st.session_state.form_data['id'] = assistant_id
                            if is_creation:
                                st.session_state.previous_action = "✏️ Modifier / Tester un assistant"
                                st.session_state.last_loaded_id = None
                            fetch_assistants.clear()
                            st.rerun()
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
                    enc_url = urllib.parse.quote(creds['wsUrl'].strip(), safe="")
                    enc_token = urllib.parse.quote(creds['token'].strip(), safe="")
                    magic_link = f"https://meet.livekit.io/custom?liveKitUrl={enc_url}&token={enc_token}"
                    st.markdown(f"""
                        <a href="{esc(magic_link)}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;">
                            <div style="background-color:#28a745;color:white;padding:10px;border-radius:8px;text-align:center;font-weight:bold;margin-bottom:15px;">
                                 📞 LANCER L'APPEL TEST
                            </div>
                        </a>
                    """, unsafe_allow_html=True)
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
                if sip_channel:
                    st.markdown('<div class="call-status-box status-on">🟢 <b>LIGNE SIP ACTIVE</b><br><span style="font-size:0.8em">Cet assistant est raccordé au réseau.</span></div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="call-status-box status-off">🔴 <b>NON CONFIGURÉE</b><br><span style="font-size:0.8em">Cet assistant ne peut pas recevoir d\'appels réels.</span></div>', unsafe_allow_html=True)

                existing_nums = sip_channel.get("inboundNumbersWhitelist", []) if sip_channel else []
                existing_ips = sip_channel.get("inboundAddressesWhitelist", []) if sip_channel else []
                existing_sip_headers = sip_channel.get("includeSipHeaders", "SIP_ALL_HEADERS") if sip_channel else "SIP_ALL_HEADERS"
                existing_krisp = sip_channel.get("krispEnabled", False) if sip_channel else False

                sip_nums_str = st.text_area("Numéros Autorisés (E.164)", value="\n".join(existing_nums),
                                            placeholder="+879...\n+33000040001", height=68)
                sip_ips_str = st.text_area("Adresses IP Autorisées", value="\n".join(existing_ips),
                                           placeholder="192.168.1.100", height=68)
                st.markdown("**Paramètres Avancés**")
                sip_headers_option = st.selectbox("Transmission des Headers SIP", options=SIP_HEADER_OPTIONS,
                                                  index=SIP_HEADER_OPTIONS.index(existing_sip_headers)
                                                  if existing_sip_headers in SIP_HEADER_OPTIONS else 0)
                krisp_enabled = st.checkbox("Réduction de bruit Krisp", value=existing_krisp)

                lbl_sip = "💾 Mettre à jour la ligne SIP" if sip_channel else "🔌 Créer la Ligne SIP"
                if st.button(lbl_sip, use_container_width=True):
                    nums_list = [n.strip() for n in sip_nums_str.split("\n") if n.strip()]
                    ips_list = [ip.strip() for ip in sip_ips_str.split("\n") if ip.strip()]
                    if not nums_list and not ips_list:
                        st.error("⚠️ Sécurité Reecall : Renseignez au moins un numéro ou une IP.")
                    else:
                        payload_sip = {"name": f"SIP Trunk - {name}", "type": "SIP",
                                       "assistantId": fd.get("id"), "projectId": project_id,
                                       "inboundNumbersWhitelist": nums_list, "inboundAddressesWhitelist": ips_list,
                                       "includeSipHeaders": sip_headers_option, "krispEnabled": krisp_enabled}
                        with st.spinner("Configuration en cours..."):
                            resp_sip = save_sip_channel(api_key, existing_sip_id, payload_sip)
                            if resp_sip and resp_sip.status_code in [200, 201]:
                                st.success("✅ Configuration SIP enregistrée !")
                                fetch_sip_channel.clear(); st.rerun()
                            else:
                                st.error(f"Échec configuration SIP : {resp_sip.text if resp_sip else 'Erreur de connexion'}")

# === VUE 3 : HISTORIQUE DES CONVERSATIONS ===
elif main_action == "📜 Consulter les conversations":
    st.title("Historique des Conversations")

    if project_id:
        ass_dict = {"Tous les assistants": None}
        id_to_name = {}
        if assistants_list:
            for a in assistants_list:
                ass_dict[a.get('name', 'Assistant sans nom')] = a.get('id')
                id_to_name[a.get('id')] = a.get('name', 'Assistant sans nom')

        col_f1, _ = st.columns([1, 2])
        with col_f1:
            selected_ass_name = st.selectbox("🤖 Filtrer par Assistant", list(ass_dict.keys()))
            selected_ass_id = ass_dict[selected_ass_name]

        st.divider()

        with st.spinner("Récupération de l'historique..."):
            all_exchanges = fetch_exchanges(api_key, project_id)
            filtered_exchanges = []
            for exc in all_exchanges:
                current_exc_ass_id = None
                for res in exc.get("resources", []):
                    if res.get("key") == "assistant_id":
                        current_exc_ass_id = res.get("value"); break
                if not selected_ass_id or current_exc_ass_id == selected_ass_id:
                    exc["_assistant_name"] = id_to_name.get(current_exc_ass_id, "Assistant Inconnu")
                    filtered_exchanges.append(exc)

        if filtered_exchanges:
            exchange_options = {}
            for exc in filtered_exchanges:
                date_str = format_date(exc.get("createdAt", ""))
                label = f"{date_str} - {esc(exc.get('_assistant_name',''))} - [{esc(exc.get('status','').upper())}]"
                exchange_options[label] = exc['id']

            selected_label = st.selectbox("Sélectionnez une conversation :", list(exchange_options.keys()))
            selected_exchange_id = exchange_options[selected_label]
            st.divider()

            with st.spinner("Chargement de la transcription..."):
                exchange_detail = fetch_exchange_details(api_key, selected_exchange_id)

            if exchange_detail:
                col_info, col_chat = st.columns([1, 2])
                with col_info:
                    st.subheader("ℹ️ Informations")
                    resources = exchange_detail.get("resources", []) or []
                    res = {r['key']: r['value'] for r in resources if isinstance(r, dict)}

                    duration_s = exchange_detail.get("duration") or res.get("session_end.duration_seconds") or 0
                    duration_str = f"{int(duration_s) // 60}m {int(duration_s) % 60}s" if duration_s else "N/A"
                    caller = res.get("dynamic_config.caller_phone_number", "N/A")
                    called = res.get("dynamic_config.called_phone_number", "N/A")
                    llm   = res.get("assistant_config.llm", "N/A")
                    stt   = res.get("assistant_config.stt_model", "N/A")
                    tts   = res.get("assistant_config.tts_model", "N/A")
                    voice = res.get("assistant_config.tts_voice", "")
                    conn  = res.get("dynamic_config.connection_type", "N/A").upper()

                    st.markdown(f"""
                    <div class="exchange-card">
                        <b>Status :</b> {esc(exchange_detail.get('status','N/A'))} &nbsp;|&nbsp;
                        <b>Type :</b> {esc(exchange_detail.get('type','N/A'))} &nbsp;|&nbsp;
                        <b>Canal :</b> {esc(conn)}<br>
                        <b>Date :</b> {esc(format_date(exchange_detail.get('createdAt','')))}<br>
                        <b>Durée :</b> {esc(duration_str)}<br>
                        <hr style="margin:8px 0; opacity:0.2">
                        <b>📞 Appelant :</b> {esc(caller)}<br>
                        <b>📲 Appelé :</b> {esc(called)}<br>
                        <hr style="margin:8px 0; opacity:0.2">
                        <b>🧠 LLM :</b> {esc(llm)}<br>
                        <b>🎤 STT :</b> {esc(stt)}<br>
                        <b>🔊 TTS :</b> {esc(tts)}{f" / {esc(voice)}" if voice else ""}
                    </div>
                    """, unsafe_allow_html=True)

                    # --- COÛT DE L'ÉCHANGE ---
                    trace_id = exchange_detail.get("traceId")
                    if trace_id:
                        with st.spinner("Calcul du coût..."):
                            cost_data = fetch_exchange_cost(
                                api_key, trace_id,
                                exchange_detail.get("createdAt"),
                                exchange_detail.get("updatedAt")
                            )
                        if cost_data and cost_data["total"] > 0:
                            dur_min = float(duration_s) / 60 if duration_s else 0
                            cost_per_min = cost_data["total"] / dur_min if dur_min > 0 else 0
                            st.markdown(f"""
                            <div class="cost-card">
                                <b>💰 Coût estimé</b><br>
                                <span style="font-size:1.5em; font-weight:bold; color:#3D6FA3;">
                                    {cost_data['total']:.4f} €
                                </span><br>
                                <span style="font-size:0.9em; opacity:0.8;">
                                    ⏱️ <b>{cost_per_min:.4f} € / min</b>
                                    &nbsp;|&nbsp; durée : {esc(duration_str)}
                                </span>
                            </div>
                            """, unsafe_allow_html=True)
                            with st.expander("📊 Détail du coût par composant"):
                                for item in cost_data["details"]:
                                    label = item["metric"].replace("usage.", "").replace(".", " › ")
                                    st.markdown(f"**{label}** : `{item['pricing']:.6f} €`")
                        elif cost_data is not None:
                            st.info("💰 Coût : 0,00 € (données insuffisantes ou non facturées)")
                        else:
                            st.caption("💰 Coût non disponible pour cet échange.")

                    with st.expander("🛠️ Événements (Events)"):
                        events_data = exchange_detail.get("events")
                        if events_data: st.json(events_data)
                        else: st.info("Aucun événement.")

                    with st.expander("📊 Données extraites (Data)"):
                        extra_data = exchange_detail.get("data")
                        if extra_data:
                            if isinstance(extra_data, str):
                                try: extra_data = json.loads(extra_data)
                                except Exception: pass
                            st.json(extra_data)
                        else:
                            st.info("Aucune donnée d'extraction disponible.")

                with col_chat:
                    audio_url = (exchange_detail.get("audioUrl") or exchange_detail.get("recordingUrl")
                                 or exchange_detail.get("recording") or exchange_detail.get("mediaUrl"))
                    if not audio_url:
                        for ev in (exchange_detail.get("events") or []):
                            for field in ["audioUrl", "recordingUrl", "recording", "mediaUrl"]:
                                if ev.get(field): audio_url = ev[field]; break
                            if audio_url: break

                    if audio_url:
                        st.subheader("🎧 Enregistrement")
                        st.audio(audio_url)

                    st.subheader("💬 Transcription")
                    messages = exchange_detail.get("messages", [])
                    if not messages:
                        st.info("Aucun message enregistré pour cette conversation.")
                    else:
                        for msg in messages:
                            role = "user" if msg.get("from") == "user" else "assistant"
                            with st.chat_message(role):
                                st.write(msg.get("message", ""))
                                st.caption(format_date(msg.get("time", "")))
        else:
            st.info("Aucune conversation trouvée pour cet assistant.")

# === VUE 4 : ÉTUDE DE PRICING ===
elif main_action == "💰 Étude de Pricing":
    st.title("💰 Étude de Pricing")
    st.info("Analysez le coût des conversations sur une période donnée. La vue rapide utilise **1 appel API par assistant**, la vue détaillée charge chaque conversation individuellement.")

    # --- FILTRES ---
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        date_from = st.date_input("📅 Du", value=datetime.now(ZoneInfo("Europe/Paris")).date().replace(day=1))
    with col_f2:
        date_to = st.date_input("📅 Au", value=datetime.now(ZoneInfo("Europe/Paris")).date())
    with col_f3:
        ass_dict_pricing = {"Tous les assistants": None}
        if assistants_list:
            for a in assistants_list:
                ass_dict_pricing[a.get('name', 'Sans nom')] = a['id']
        selected_ass_pricing = st.selectbox("🤖 Assistant", list(ass_dict_pricing.keys()))
        selected_ass_id_pricing = ass_dict_pricing[selected_ass_pricing]

    mode_detail = st.checkbox("🔍 Charger le détail par conversation (plus lent, limité à 50 conv.)",
                              value=False,
                              help="Sans cette option, les coûts sont agrégés par assistant en 1 appel API — beaucoup plus rapide.")

    if st.button("🔍 Lancer l'analyse", type="primary"):
        from_iso = date_from.strftime("%Y-%m-%dT00:00:00.000Z")
        to_iso   = date_to.strftime("%Y-%m-%dT23:59:59.999Z")

        # =========================================================
        # MODE RAPIDE : 1 appel par assistant via context={"assistantId": ...}
        # =========================================================
        if not mode_detail:
            assistants_to_analyze = []
            if selected_ass_id_pricing:
                assistants_to_analyze = [(selected_ass_id_pricing,
                                          next((a.get('name','?') for a in assistants_list
                                                if a['id'] == selected_ass_id_pricing), '?'))]
            else:
                assistants_to_analyze = [(a['id'], a.get('name','?')) for a in assistants_list]

            if not assistants_to_analyze:
                st.warning("Aucun assistant trouvé dans ce workspace.")
            else:
                results_agg = []
                prog = st.progress(0)
                for i, (ass_id, ass_name) in enumerate(assistants_to_analyze):
                    prog.progress((i + 1) / len(assistants_to_analyze))
                    data = fetch_cost_by_assistant(api_key, ass_id, from_iso, to_iso)
                    if data and data['conv_count'] > 0:
                        results_agg.append({"assistant": ass_name, **data})
                prog.empty()

                if not results_agg:
                    st.info("Aucune donnée de coût disponible sur cette période.")
                else:
                    st.divider()
                    total_cost_all = sum(r['total'] for r in results_agg)
                    total_conv     = sum(r['conv_count'] for r in results_agg)
                    total_dur_s    = sum(r['total_dur_s'] for r in results_agg)
                    total_dur_min  = total_dur_s / 60 if total_dur_s else 0
                    avg_cost_conv  = total_cost_all / total_conv if total_conv else 0
                    avg_cost_min   = total_cost_all / total_dur_min if total_dur_min else 0
                    avg_dur        = total_dur_s / total_conv if total_conv else 0

                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("💬 Conversations", int(total_conv))
                    m2.metric("💰 Coût total", f"{total_cost_all:.4f} €")
                    m3.metric("📊 Coût moy. / conv.", f"{avg_cost_conv:.4f} €")
                    m4.metric("⏱️ Coût moy. / min", f"{avg_cost_min:.4f} €")
                    m5.metric("⏳ Durée moy.", f"{int(avg_dur // 60)}m {int(avg_dur % 60)}s")

                    st.divider()
                    st.subheader("📋 Résumé par assistant")
                    h0, h1, h2, h3, h4, h5 = st.columns([2.5, 1, 1.5, 1.5, 1.5, 1.5])
                    h0.caption("Assistant"); h1.caption("Conv."); h2.caption("Coût total (€)")
                    h3.caption("Coût / conv. (€)"); h4.caption("Coût / min (€)"); h5.caption("Durée moy.")
                    st.divider()

                    for r in sorted(results_agg, key=lambda x: x['total'], reverse=True):
                        dur_min = r['total_dur_s'] / 60 if r['total_dur_s'] else 0
                        cpm   = r['total'] / dur_min if dur_min > 0 else 0
                        avg_c = r['total'] / r['conv_count'] if r['conv_count'] else 0
                        avg_d = r['total_dur_s'] / r['conv_count'] if r['conv_count'] else 0

                        rc = st.columns([2.5, 1, 1.5, 1.5, 1.5, 1.5])
                        rc[0].markdown(f"**{esc(r['assistant'])}**")
                        rc[1].markdown(str(r['conv_count']))
                        rc[2].markdown(f"`{r['total']:.4f}`")
                        rc[3].markdown(f"`{avg_c:.4f}`")
                        rc[4].markdown(f"`{cpm:.4f}`")
                        rc[5].markdown(f"{int(avg_d // 60)}m {int(avg_d % 60)}s")

                        pct = (r['total'] / total_cost_all * 100) if total_cost_all > 0 else 0
                        st.progress(min(pct / 100, 1.0))

                        with st.expander(f"📊 Détail composants — {r['assistant']}"):
                            for item in sorted(r['details'], key=lambda x: x['pricing'], reverse=True):
                                label = item["metric"].replace("usage.", "").replace(".", " › ")
                                st.markdown(f"**{label}** : `{item['pricing']:.6f} €`  ·  valeur : `{item['value']}`")

        # =========================================================
        # MODE DÉTAIL : 1 appel par conversation (traceId)
        # =========================================================
        else:
            with st.spinner("Récupération des conversations..."):
                exchanges = fetch_exchanges_range(api_key, project_id, from_iso, to_iso, selected_ass_id_pricing)

            if not exchanges:
                st.warning("Aucune conversation trouvée pour cette période.")
            else:
                valid = [e for e in exchanges if e.get("traceId")]
                st.info(f"**{len(exchanges)}** conversations — récupération du coût pour **{len(valid)}** échanges avec traceId...")

                if len(valid) > 50:
                    st.warning(f"⚠️ Limité aux 50 plus récentes ({len(valid)} trouvées).")
                    valid = valid[:50]

                progress_bar = st.progress(0)
                results = []
                id_to_name_p = {a['id']: a.get('name', '?') for a in assistants_list}

                for i, exc in enumerate(valid):
                    progress_bar.progress((i + 1) / len(valid))
                    cost_data = fetch_exchange_cost(
                        api_key, exc["traceId"],
                        range_from=from_iso, range_to=to_iso
                    )
                    duration_s = exc.get("duration") or 0
                    ass_name = "?"
                    for r in (exc.get("resources") or []):
                        if r.get("key") == "assistant_id":
                            ass_name = id_to_name_p.get(r.get("value"), "?"); break
                    total_cost = round(cost_data["total"], 6) if cost_data else 0.0
                    results.append({"date": format_date(exc.get("createdAt", "")), "assistant": ass_name,
                                    "durée_s": duration_s, "statut": exc.get("status", "?"), "coût": total_cost,
                                    "traceId": exc.get("traceId", "")})

                progress_bar.empty()

                # Métriques globales
                st.divider()
                total_cost_all = sum(r["coût"] for r in results)
                total_dur_s    = sum(r["durée_s"] for r in results)
                total_dur_min  = total_dur_s / 60 if total_dur_s else 0
                avg_cost       = total_cost_all / len(results) if results else 0
                avg_cost_min   = total_cost_all / total_dur_min if total_dur_min > 0 else 0
                avg_dur        = total_dur_s / len(results) if results else 0
                max_item       = max(results, key=lambda x: x["coût"]) if results else None

                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("💬 Conversations", len(results))
                m2.metric("💰 Coût total", f"{total_cost_all:.4f} €")
                m3.metric("📊 Coût moy. / conv.", f"{avg_cost:.4f} €")
                m4.metric("⏱️ Coût moy. / min", f"{avg_cost_min:.4f} €")
                m5.metric("⏳ Durée moy.", f"{int(avg_dur // 60)}m {int(avg_dur % 60)}s")
                if max_item:
                    st.caption(f"💡 Conv. la plus coûteuse : **{max_item['date']}** — `{max_item['coût']:.4f} €`")

                st.divider()
                st.subheader("📋 Détail par conversation")
                h0, h1, h2, h3, h4, h5, h6, h7 = st.columns([0.4, 2, 1.5, 1.2, 0.8, 1, 1, 2.5])
                h0.caption("#"); h1.caption("Date"); h2.caption("Assistant")
                h3.caption("Durée"); h4.caption("Statut"); h5.caption("Coût (€)"); h6.caption("€/min")
                h7.caption("TraceId")
                st.divider()

                for idx, r in enumerate(sorted(results, key=lambda x: x["coût"], reverse=True), 1):
                    dur_s = r["durée_s"]
                    dur_str = f"{int(dur_s) // 60}m {int(dur_s) % 60}s" if dur_s else "—"
                    cpm = (r["coût"] / (dur_s / 60)) if dur_s > 0 else 0
                    rc = st.columns([0.4, 2, 1.5, 1.2, 0.8, 1, 1, 2.5])
                    rc[0].caption(str(idx)); rc[1].caption(r["date"])
                    rc[2].markdown(f"**{esc(r['assistant'])}**"); rc[3].markdown(dur_str)
                    rc[4].markdown(r["statut"]); rc[5].markdown(f"`{r['coût']:.4f}`")
                    rc[6].markdown(f"`{cpm:.4f}`")
                    rc[7].code(r.get("traceId", "—"), language=None)

                # Répartition par assistant
                if not selected_ass_id_pricing and len(results) > 1:
                    st.divider()
                    st.subheader("📊 Répartition par assistant")
                    ass_costs = {}
                    ass_dur_map = {}
                    for r in results:
                        ass_costs[r['assistant']] = ass_costs.get(r['assistant'], 0) + r["coût"]
                        ass_dur_map[r['assistant']] = ass_dur_map.get(r['assistant'], 0) + r["durée_s"]
                    for a, c in sorted(ass_costs.items(), key=lambda x: x[1], reverse=True):
                        pct = (c / total_cost_all * 100) if total_cost_all > 0 else 0
                        dur_min_a = ass_dur_map[a] / 60 if ass_dur_map.get(a) else 0
                        cpm_a = c / dur_min_a if dur_min_a > 0 else 0
                        st.markdown(f"**{esc(a)}** — `{c:.4f} €` ({pct:.1f}%) · `{cpm_a:.4f} €/min`")
                        st.progress(min(pct / 100, 1.0))

# === VUE 5 : VARIABLES ===
elif main_action == "🔑 Variables":
    st.title("Gestion des Variables")
    st.info("Les variables permettent d'injecter des valeurs dynamiques dans les instructions, URLs MCP ou headers. Syntaxe : `{ ma_variable }`")

    col_hdr, col_btn = st.columns([4, 1])
    with col_hdr:
        scope_filter = st.radio("Périmètre affiché", ["Toutes", "Organisation", "Projet"],
                                horizontal=True, key="var_scope_filter")
    with col_btn:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("➕ Nouvelle variable", use_container_width=True):
            st.session_state.var_edit_id = None
            st.session_state.var_show_form = True
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.var_show_form:
        st.divider()
        is_var_edit = st.session_state.var_edit_id is not None
        st.subheader("✏️ Modifier la variable" if is_var_edit else "➕ Nouvelle variable")
        prefill = {}
        if is_var_edit:
            all_vars_prefill = fetch_variables(api_key, project_id)
            prefill = next((v for v in all_vars_prefill if v['id'] == st.session_state.var_edit_id), {})

        with st.form("var_form"):
            fc1, fc2 = st.columns(2)
            with fc1:
                v_key = st.text_input("Clé *", value=prefill.get("key", ""), placeholder="ex: companyName, apiToken...")
                v_scope = st.radio("Périmètre", ["Organisation", "Projet"], horizontal=True,
                                   index=0 if not prefill.get("projectId") else 1)
            with fc2:
                v_secret = st.checkbox("🔒 Valeur secrète (chiffrée)", value=prefill.get("isSecret", False))
                v_value = st.text_input("Valeur *",
                                        value="" if prefill.get("isSecret") else prefill.get("value", ""),
                                        type="password" if v_secret else "default",
                                        placeholder="La valeur à injecter à l'exécution")
            fc3, fc4 = st.columns(2)
            with fc3: submitted = st.form_submit_button("💾 Enregistrer", type="primary", use_container_width=True)
            with fc4: cancelled = st.form_submit_button("Annuler", use_container_width=True)

        if cancelled:
            st.session_state.var_show_form = False; st.session_state.var_edit_id = None; st.rerun()
        if submitted:
            if not v_key.strip(): st.error("La **Clé** est obligatoire.")
            elif not v_value.strip(): st.error("La **Valeur** est obligatoire.")
            else:
                payload_var = {"key": v_key.strip(), "value": v_value.strip(), "isSecret": v_secret}
                if v_scope == "Projet": payload_var["projectId"] = project_id
                with st.spinner("Enregistrement..."):
                    resp_v, act_v = save_variable(api_key, payload_var, st.session_state.var_edit_id)
                    if resp_v.status_code in (200, 201):
                        st.success(f"Variable **{v_key}** {act_v} avec succès !")
                        fetch_variables.clear(); st.session_state.var_show_form = False
                        st.session_state.var_edit_id = None; st.rerun()
                    else:
                        try: err = resp_v.json()
                        except Exception: err = resp_v.text
                        st.error(f"Échec (HTTP {resp_v.status_code}) : {err}")

    st.divider()
    with st.spinner("Chargement des variables..."):
        all_variables = fetch_variables(api_key, project_id)

    if scope_filter == "Organisation": displayed = [v for v in all_variables if not v.get("projectId")]
    elif scope_filter == "Projet": displayed = [v for v in all_variables if v.get("projectId")]
    else: displayed = all_variables

    if not displayed:
        st.info("Aucune variable trouvée pour ce périmètre.")
    else:
        h1, h2, h3, h4, h5 = st.columns([2, 3, 1.5, 0.7, 0.7])
        h1.caption("Clé"); h2.caption("Valeur"); h3.caption("Périmètre")
        h4.caption("Modifier"); h5.caption("Supprimer")
        st.divider()
        for var in displayed:
            c1, c2, c3, c4, c5 = st.columns([2, 3, 1.5, 0.7, 0.7])
            with c1: st.markdown(f"`{esc(var.get('key', ''))}`")
            with c2:
                if var.get("isSecret"): st.markdown("🔒 *valeur masquée*")
                else: st.code(str(var.get("value", "")), language=None)
            with c3:
                st.markdown("🏷️ Projet" if var.get("projectId") else "🌐 Organisation")
            with c4:
                if st.button("✏️", key=f"var_edit_{var['id']}"):
                    st.session_state.var_edit_id = var['id']; st.session_state.var_show_form = True; st.rerun()
            with c5:
                if st.button("🗑️", key=f"var_del_{var['id']}"):
                    with st.spinner("Suppression..."):
                        r = delete_variable(api_key, var['id'])
                        if r.status_code in (200, 204):
                            st.success(f"Variable **{var.get('key')}** supprimée.")
                            fetch_variables.clear(); st.rerun()
                        else:
                            st.error(f"Échec suppression (HTTP {r.status_code}).")

# === VUE 6 : SERVEURS MCP ===
elif main_action == "🔌 Serveurs MCP":
    st.title("Gestion des Serveurs MCP")
    st.info("Les serveurs MCP permettent à vos assistants d'utiliser des outils externes via SSE. Utilisez `{ ma_variable }` dans l'URL et les headers pour injecter des secrets.")

    col_hdr, col_btn = st.columns([4, 1])
    with col_hdr:
        mcp_scope_filter = st.radio("Périmètre affiché", ["Tous", "Projet", "Organisation"],
                                    horizontal=True, key="mcp_scope_filter")
    with col_btn:
        st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
        if st.button("➕ Nouveau serveur MCP", use_container_width=True):
            st.session_state.mcp_edit_id = None; st.session_state.mcp_show_form = True
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.mcp_show_form:
        st.divider()
        is_mcp_edit = st.session_state.mcp_edit_id is not None
        st.subheader("✏️ Modifier le serveur MCP" if is_mcp_edit else "➕ Nouveau serveur MCP")
        mcp_prefill = {}
        if is_mcp_edit:
            all_mcps_prefill = fetch_mcps(api_key)
            mcp_prefill = next((m for m in all_mcps_prefill if m['id'] == st.session_state.mcp_edit_id), {})

        existing_headers = mcp_prefill.get("headers", {})
        headers_str = "\n".join(f"{k}: {v}" for k, v in existing_headers.items()) if isinstance(existing_headers, dict) else ""

        with st.form("mcp_form"):
            mf1, mf2 = st.columns(2)
            with mf1:
                m_name = st.text_input("Nom *", value=mcp_prefill.get("name", ""), placeholder="ex: Freshdesk MCP")
                m_url  = st.text_input("URL SSE *", value=mcp_prefill.get("url", ""), placeholder="https://api.example.com/mcp/sse")
                m_scope = st.radio("Périmètre", ["Projet", "Organisation"], horizontal=True,
                                   index=0 if mcp_prefill.get("projectId") else 1)
            with mf2:
                m_desc = st.text_area("Description", value=mcp_prefill.get("description", ""),
                                      height=80, placeholder="Décrivez les capacités de ce serveur...")
                m_headers_str = st.text_area("Headers HTTP (un par ligne, format `Clé: Valeur`)",
                                             value=headers_str, height=100,
                                             placeholder="Authorization: Bearer { mcpApiToken }")
            mf3, mf4 = st.columns(2)
            with mf3: m_submitted = st.form_submit_button("💾 Enregistrer", type="primary", use_container_width=True)
            with mf4: m_cancelled = st.form_submit_button("Annuler", use_container_width=True)

        if m_cancelled:
            st.session_state.mcp_show_form = False; st.session_state.mcp_edit_id = None; st.rerun()
        if m_submitted:
            if not m_name.strip(): st.error("Le **Nom** est obligatoire.")
            elif not m_url.strip(): st.error("L'**URL** est obligatoire.")
            else:
                parsed_headers = {}
                for line in m_headers_str.strip().split("\n"):
                    line = line.strip()
                    if ": " in line:
                        k, v = line.split(": ", 1)
                        parsed_headers[k.strip()] = v.strip()
                payload_mcp = {"name": m_name.strip(), "url": m_url.strip(),
                               "description": m_desc.strip(), "headers": parsed_headers}
                if m_scope == "Projet": payload_mcp["projectId"] = project_id
                with st.spinner("Enregistrement..."):
                    resp_m, act_m = save_mcp(api_key, payload_mcp, st.session_state.mcp_edit_id)
                    if resp_m.status_code in (200, 201):
                        st.success(f"Serveur MCP **{m_name}** {act_m} avec succès !")
                        fetch_mcps.clear(); st.session_state.mcp_show_form = False
                        st.session_state.mcp_edit_id = None; st.rerun()
                    else:
                        try: err = resp_m.json()
                        except Exception: err = resp_m.text
                        st.error(f"Échec (HTTP {resp_m.status_code}) : {err}")

    st.divider()
    with st.spinner("Chargement des serveurs MCP..."):
        all_mcps_list = fetch_mcps(api_key)

    if mcp_scope_filter == "Projet": displayed_mcps = [m for m in all_mcps_list if m.get("projectId")]
    elif mcp_scope_filter == "Organisation": displayed_mcps = [m for m in all_mcps_list if not m.get("projectId")]
    else: displayed_mcps = all_mcps_list

    if not displayed_mcps:
        st.info("Aucun serveur MCP trouvé pour ce périmètre.")
    else:
        h1, h2, h3, h4, h5, h6 = st.columns([2, 3, 1, 1.5, 0.7, 0.7])
        h1.caption("Nom"); h2.caption("URL"); h3.caption("Headers")
        h4.caption("Périmètre"); h5.caption("Modifier"); h6.caption("Supprimer")
        st.divider()
        for mcp in displayed_mcps:
            c1, c2, c3, c4, c5, c6 = st.columns([2, 3, 1, 1.5, 0.7, 0.7])
            with c1:
                st.markdown(f"**{esc(mcp.get('name', ''))}**")
                if mcp.get("description"): st.caption(esc(mcp.get("description", "")))
            with c2: st.code(mcp.get("url", ""), language=None)
            with c3:
                h = mcp.get("headers", {})
                st.markdown(f"✅ {len(h)} header{'s' if len(h) > 1 else ''}" if h and isinstance(h, dict) and len(h) > 0 else "—")
            with c4:
                st.markdown("🏷️ Projet" if mcp.get("projectId") else "🌐 Organisation")
            with c5:
                if st.button("✏️", key=f"mcp_edit_{mcp['id']}"):
                    st.session_state.mcp_edit_id = mcp['id']; st.session_state.mcp_show_form = True; st.rerun()
            with c6:
                if st.button("🗑️", key=f"mcp_del_{mcp['id']}"):
                    with st.spinner("Suppression..."):
                        r = delete_mcp(api_key, mcp['id'])
                        if r.status_code in (200, 204):
                            st.success(f"Serveur MCP **{mcp.get('name')}** supprimé.")
                            fetch_mcps.clear(); st.rerun()
                        else:
                            st.error(f"Échec suppression (HTTP {r.status_code}).")

# === VUE 7 : LOGS API ===
elif main_action == "📡 Logs API":
    st.title("Logs Réseau (Les 10 dernières requêtes API)")

    col_btn, _ = st.columns([1, 4])
    with col_btn:
        if st.button("🗑️ Vider les logs", use_container_width=True):
            st.session_state.api_logs = []; st.rerun()

    st.divider()

    if not st.session_state.api_logs:
        st.info("Aucune requête API n'a encore été enregistrée pendant cette session.")
    else:
        for log in reversed(st.session_state.api_logs):
            status = log['status_code']
            if isinstance(status, int):
                icon = "🟢" if 200 <= status < 300 else ("🟠" if 400 <= status < 500 else "🔴")
            else:
                icon = "❌"
            label = f"{icon} [{log['timestamp']}] {log['method']} — {log['url']} (Status: {status})"
            with st.expander(label):
                col_req, col_resp = st.columns(2)
                with col_req:
                    st.markdown("### 📤 Requête Envoyée")
                    if log['req_params']:
                        st.caption("Paramètres d'URL :"); st.json(log['req_params'])
                    if log['req_body']:
                        st.caption("Corps (JSON) :"); st.json(log['req_body'])
                    elif not log['req_params']:
                        st.info("Aucun paramètre ni corps envoyé.")
                with col_resp:
                    st.markdown("### 📥 Réponse Reçue")
                    if log['resp_body']: st.json(log['resp_body'])
                    else: st.info("Aucun contenu retourné par le serveur.")
