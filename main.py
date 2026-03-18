"""
Axialys Bot Manager — v3
"""

import streamlit as st
import requests
import json
import html
import urllib.parse
import uuid
import argparse
from datetime import datetime
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

LOGO_URL = (
    "https://media.licdn.com/dms/image/v2/D4E0BAQE_HZvoIBQM9g/"
    "company-logo_200_200/company-logo_200_200/0/1695887075709/"
    "axialys_logo?e=2147483647&v=beta&t=8NbSO8rggmFIAWcnJQ1ocq2k-wrdv5A9FXDZVzluIqM"
)

SUPPORTED_LANGUAGES = ["fr-FR", "en-US", "en-GB", "es-ES", "de-DE", "it-IT"]
SIP_HEADER_OPTIONS = ["SIP_ALL_HEADERS", "SIP_X_HEADERS", "SIP_NO_HEADERS"]

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
    [data-testid="stSidebar"] { background-color: var(--secondary-background-color) !important; border-right: 1px solid rgba(128,128,128,0.2) !important; }
    [data-testid="stSidebar"] img { display: block; margin: 20px auto; border-radius: 10px; }
    .log-method { font-weight: bold; color: #3D6FA3; }
    .extraction-row { padding: 10px; border: 1px solid rgba(128,128,128,0.2); border-radius: 8px; margin-bottom: 5px; background-color: var(--secondary-background-color); color: var(--text-color); }
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


def reset_form():
    st.session_state.form_data = {
        "name": "", "description": "", "instructions": "Tu es un assistant utile...",
        "firstMessage": "Bonjour, bienvenue chez Axialys !", "temperature": 0.3, "language": "fr-FR",
        "timezone": "Europe/Paris", "llmId": None, "sttId": None, "ttsId": None, "voiceId": None, "id": None,
        "knowledgeBaseIds": [], "mcpIds": [], "mcps": [],
        "extraction_fields": [],
        "end_conversation_enabled": False, "closing_message": "",
        "description_override": "", "disable_interruptions": False
    }
    st.session_state.last_loaded_id = None
    st.session_state.call_data = None


def load_assistant_into_form(assistant, tools=[]):
    llm_id = assistant.get('llmId') or (assistant.get('llm', {}).get('id'))
    tts_id = assistant.get('ttsId') or (assistant.get('tts', {}).get('id'))
    stt_id = assistant.get('sttId') or (assistant.get('stt', {}).get('id'))
    voice_uuid = assistant.get('voiceId')
    if not voice_uuid and assistant.get('voice'):
        voice_uuid = assistant.get('voice').get('id')

    kb_ids = assistant.get('knowledgeBaseIds', [])
    if not isinstance(kb_ids, list): kb_ids = []

    mcp_ids = assistant.get('mcpIds', [])
    if not isinstance(mcp_ids, list): mcp_ids = []

    raw_mcps = assistant.get('mcps', [])
    clean_mcp_urls = []
    if isinstance(raw_mcps, list):
        for item in raw_mcps:
            if isinstance(item, str):
                clean_mcp_urls.append(item)
            elif isinstance(item, dict) and 'url' in item:
                clean_mcp_urls.append(item['url'])

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
            try:
                req_params[k] = json.loads(v)
            except Exception:
                pass

    resp_body = None
    if response is not None:
        try:
            resp_body = response.json()
        except Exception:
            resp_body = response.text

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
        if any(r.status_code != 200 for r in [llm, stt, tts]):
            return None
        return {'llm': llm.json(), 'stt': stt.json(), 'tts': tts.json()}
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


def save_assistant(api_key, payload, assistant_id=None):
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    if assistant_id:
        return make_api_request('PATCH', f"{API_BASE}/conversational/assistants/{assistant_id}",
                                headers=headers, json=payload), "modifié"
    else:
        return make_api_request('POST', f"{API_BASE}/conversational/assistants/",
                                headers=headers, json=payload), "créé"


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
        payload = {
            "assistantId": assistant_id, "projectId": project_id,
            "definitionId": def_id, "disableInterruptions": disable_interruptions
        }
        if closing_message and closing_message.strip():
            payload["configuration"] = {"closingMessage": closing_message.strip()}
        if description_override and description_override.strip():
            payload["descriptionOverride"] = description_override.strip()

        if existing_end_tool:
            del_resp = make_api_request('DELETE', f"{API_BASE}/ai/tools/{existing_end_tool['id']}",
                                        headers=headers_auth)
            if del_resp.status_code not in (200, 204):
                return False, f"Échec suppression ancien outil (HTTP {del_resp.status_code}). Création annulée."

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
         "📜 Consulter les conversations", "📡 Logs API"],
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

        # On pose uniquement un flag — pas de st.rerun() ici
        if selected_id != st.session_state.last_loaded_id:
            st.session_state.last_loaded_id = selected_id
            st.session_state['_pending_load_id'] = selected_id

# =============================================================================
# CHARGEMENT DIFFÉRÉ — hors sidebar, pour ne pas bloquer le radio
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
    assistant_name_display = fd.get("name", "") or "Nouvel assistant"
    st.title("Création d'un nouvel assistant" if is_creation else f"Configuration de l'Assistant — {assistant_name_display}")

    fd = st.session_state.form_data
    widget_key_suffix = fd.get("id") or "new"

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

    # --- OUTILS SYSTÈME (RACCROCHAGE) ---
    st.subheader("☎️ Contrôle d'Appel (Outils Système)")
    st.info("Autorisez le bot à exécuter des actions système, comme mettre fin à l'appel de sa propre initiative.")
    st.caption("ℹ️ **Comportement natif :** Par défaut, l'IA décide de raccrocher lorsque l'utilisateur dit explicitement au revoir.")

    col_sys1, col_sys2 = st.columns(2)
    with col_sys1:
        enable_end_call = st.checkbox("Activer le raccrochage automatique",
                                      value=fd.get("end_conversation_enabled", False),
                                      help="Le bot raccrochera lorsqu'il jugera la conversation terminée.",
                                      key=f"end_call_{widget_key_suffix}")
        closing_msg = st.text_input("Message de clôture (Optionnel)", value=fd.get("closing_message", ""),
                                    disabled=not enable_end_call, placeholder="Merci pour votre appel, à bientôt !",
                                    help="Phrase prononcée juste avant la coupure de la ligne.",
                                    key=f"close_msg_{widget_key_suffix}")
        disable_interruptions = st.checkbox("Désactiver les interruptions pendant la clôture",
                                            value=fd.get("disable_interruptions", False),
                                            disabled=not enable_end_call,
                                            help="Empêche l'appelant d'interrompre le message de fin.",
                                            key=f"dis_int_{widget_key_suffix}")
    with col_sys2:
        desc_override = st.text_area("Consignes de raccrochage (descriptionOverride)",
                                     value=fd.get("description_override", ""), disabled=not enable_end_call,
                                     placeholder="Ex: Raccroche UNIQUEMENT si le client a validé son rendez-vous...",
                                     height=100,
                                     help="Écrase les instructions par défaut de l'outil pour forcer des règles métier strictes.",
                                     key=f"desc_over_{widget_key_suffix}")

    st.divider()

    # --- DATA EXTRACTION ---
    st.subheader("📊 Variables à extraire (Data Extraction)")
    st.info("Définissez les informations que l'IA doit structurer à la fin de la conversation.")

    fields = fd.get("extraction_fields", [])

    if len(fields) > 0:
        hc1, hc2, hc3, hc4, hc5, hc6 = st.columns([2, 1.5, 3, 2, 1, 0.5])
        hc1.caption("Clé (ex: motif)")
        hc2.caption("Type")
        hc3.caption("Description pour l'IA")
        hc4.caption("Choix imposés (A, B)")
        hc5.caption("Oblig.")

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
                idx = t_opts.index(c_val) if c_val in t_opts else 0
                field['type'] = st.selectbox("Type", t_opts, index=idx,
                                             key=f"f_type_{widget_key_suffix}_{i}", label_visibility="collapsed")
            with col3:
                field['description'] = st.text_input("Desc", value=field.get('description', ''),
                                                     key=f"f_desc_{widget_key_suffix}_{i}",
                                                     label_visibility="collapsed", placeholder="Sert à...")
            with col4:
                dis_enum = field['type'] != 'string'
                field['enum'] = st.text_input("Enum", value=field.get('enum', ''),
                                              key=f"f_enum_{widget_key_suffix}_{i}", disabled=dis_enum,
                                              label_visibility="collapsed", placeholder="Tech, Vente")
            with col5:
                st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
                field['required'] = st.checkbox("", value=field.get('required', False),
                                                key=f"f_req_{widget_key_suffix}_{i}")
            with col6:
                if st.button("❌", key=f"f_del_{widget_key_suffix}_{i}", help="Supprimer cette variable"):
                    st.session_state.form_data['extraction_fields'].pop(i)
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    if st.button("➕ Ajouter une variable"):
        if "extraction_fields" not in st.session_state.form_data:
            st.session_state.form_data['extraction_fields'] = []
        st.session_state.form_data['extraction_fields'].append({
            "name": "", "type": "string", "description": "", "enum": "", "required": False
        })
        st.rerun()

    st.divider()

    # --- MCP ---
    st.subheader("🔌 Outils & Intégrations (MCP)")
    col_mcp1, col_mcp2 = st.columns(2)

    with col_mcp1:
        st.markdown("**Catalogue MCP (Reecall)**")
        mcp_options = {m.get('name', 'Sans nom'): m['id'] for m in available_mcps} if available_mcps else {}
        default_mcp_ids = fd.get("mcpIds", [])
        default_mcp_names = [n for n, mid in mcp_options.items() if mid in default_mcp_ids]
        selected_mcp_names = st.multiselect(
            "Sélectionnez les serveurs à activer :",
            options=list(mcp_options.keys()), default=default_mcp_names,
            help="Ces outils sont déjà hébergés ou déclarés dans votre espace Reecall.",
            key=f"mcp_select_{widget_key_suffix}")
        selected_mcp_ids = [mcp_options[n] for n in selected_mcp_names]

    with col_mcp2:
        st.markdown("**URLs personnalisées (Tests locaux)**")
        mcp_urls_str = st.text_area(
            "Adresses SSE directes (une par ligne) :",
            value="\n".join(fd.get("mcps", [])), height=68,
            placeholder="https://a1b2.ngrok.app/sse", label_visibility="collapsed",
            key=f"mcp_urls_{widget_key_suffix}")
        mcp_urls_list = [url.strip() for url in mcp_urls_str.split("\n") if url.strip()]

    st.divider()

    # --- MOTEUR TECHNIQUE ---
    st.subheader("⚙️ Moteur Technique")
    tc1, tc2, tc3 = st.columns(3)

    def get_idx(opts, target):
        return list(opts.values()).index(target) if target in opts.values() else 0

    with tc1:
        st.markdown("**LLM**")
        llm_opts = {i['name']: i['id'] for i in lists['llm']}
        final_llm_id = llm_opts[
            st.selectbox("Modèle LLM", list(llm_opts.keys()), index=get_idx(llm_opts, fd.get("llmId")))]
    with tc2:
        st.markdown("**STT**")
        stt_opts = {i['name']: i['id'] for i in lists['stt']}
        final_stt_id = stt_opts[
            st.selectbox("Modèle STT", list(stt_opts.keys()), index=get_idx(stt_opts, fd.get("sttId")))]
    with tc3:
        st.markdown("**TTS**")
        tts_map = {p['name']: p for p in lists['tts']}
        prov_names = list(tts_map.keys())
        prov_idx = 0
        if fd.get("ttsId"):
            for i, pname in enumerate(prov_names):
                if tts_map[pname]['id'] == fd.get("ttsId"): prov_idx = i; break
        prov_data = tts_map[st.selectbox("Fournisseur", prov_names, index=prov_idx)]
        final_tts_id = prov_data['id']
        voices = prov_data.get('voices', [])
        final_voice_id = None
        if voices:
            v_opts = {f"{v['name']}": v['id'] for v in voices}
            final_voice_id = v_opts[
                st.selectbox("Voix", list(v_opts.keys()), index=get_idx(v_opts, fd.get("voiceId")))]

    st.divider()

    # --- SAUVEGARDE & DÉPLOIEMENT ---
    col_save, col_deploy = st.columns(2)

    with col_save:
        lbl = "🚀 CRÉER L'ASSISTANT" if is_creation else "💾 SAUVEGARDER LES MODIFICATIONS"
        if st.button(lbl, type="primary", use_container_width=True):

            validation_errors = []
            if not name or not name.strip():
                validation_errors.append("Le **Nom** est obligatoire.")
            if not inst or not inst.strip():
                validation_errors.append("Le **System Prompt** (instructions) est obligatoire.")
            if not final_voice_id:
                validation_errors.append("La **Voix** est obligatoire (sélectionnez un fournisseur TTS avec des voix).")

            if validation_errors:
                for err in validation_errors:
                    st.error(err)
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
                        if f['required']:
                            required_fields.append(v_name)

                    required_fields = [r for r in required_fields if r in properties]

                    parsed_schema = {
                        "type": "object",
                        "properties": properties,
                        "required": required_fields,
                        "additionalProperties": False
                    }

                payload = {
                    "name": name.strip(), "description": desc, "instructions": inst, "language": lang,
                    "llmId": final_llm_id, "ttsId": final_tts_id, "sttId": final_stt_id,
                    "voiceId": final_voice_id,
                    "projectId": project_id, "firstMessage": first_msg,
                    "timezone": "Europe/Paris", "temperature": temp,
                    "knowledgeBaseIds": fd.get("knowledgeBaseIds", []),
                    "mcpIds": selected_mcp_ids, "mcps": mcp_urls_list,
                    "dataExtractionSchema": parsed_schema
                }

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
                            if not tool_ok:
                                st.warning(f"Assistant {act}, mais outil raccrochage échoué : {tool_msg}")
                            else:
                                st.success(f"Succès ({act}) !")

                            st.session_state.form_data['id'] = assistant_id
                            if is_creation:
                                st.session_state.previous_action = "✏️ Modifier / Tester un assistant"
                                st.session_state.last_loaded_id = None
                            fetch_assistants.clear()
                            st.rerun()
                    else:
                        try:
                            err_detail = resp.json()
                        except Exception:
                            err_detail = resp.text
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
                    safe_link = esc(magic_link)

                    st.markdown(f"""
                        <a href="{safe_link}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;">
                            <div style="background-color:#28a745;color:white;padding:10px;border-radius:8px;text-align:center;font-weight:bold;margin-bottom:15px;box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                                 📞 LANCER L'APPEL TEST
                            </div>
                        </a>
                    """, unsafe_allow_html=True)

                    if st.button("❌ Raccrocher / Réinitialiser", use_container_width=True):
                        st.session_state.call_data = None
                        st.rerun()
                else:
                    if st.button("📞 GÉNÉRER UN APPEL TEST", use_container_width=True):
                        with st.spinner("Génération de la ligne..."):
                            channel_id = get_or_create_webrtc_channel(api_key, fd.get("id"), name, project_id)
                            if channel_id:
                                creds = get_call_token(api_key, channel_id)
                                if creds:
                                    st.session_state.call_data = creds
                                    st.rerun()

            with tab_sip:
                sip_channel = fetch_sip_channel(api_key, fd.get("id"))
                existing_sip_id = sip_channel.get("id") if sip_channel else None

                if sip_channel:
                    st.markdown(
                        '<div class="call-status-box status-on">🟢 <b>LIGNE SIP ACTIVE</b>'
                        '<br><span style="font-size: 0.8em; font-weight:normal;">Cet assistant est raccordé au réseau.</span></div>',
                        unsafe_allow_html=True)
                else:
                    st.markdown(
                        '<div class="call-status-box status-off">🔴 <b>NON CONFIGURÉE</b>'
                        '<br><span style="font-size: 0.8em; font-weight:normal;">Cet assistant ne peut pas recevoir d\'appels réels.</span></div>',
                        unsafe_allow_html=True)

                existing_nums = sip_channel.get("inboundNumbersWhitelist", []) if sip_channel else []
                existing_ips = sip_channel.get("inboundAddressesWhitelist", []) if sip_channel else []
                existing_sip_headers = sip_channel.get("includeSipHeaders", "SIP_ALL_HEADERS") if sip_channel else "SIP_ALL_HEADERS"
                existing_krisp = sip_channel.get("krispEnabled", False) if sip_channel else False

                sip_nums_str = st.text_area("Numéros Autorisés (E.164)", value="\n".join(existing_nums),
                                            placeholder="+879...\n+33000040001", height=68,
                                            help="Autoriser les appels à destination de ces numéros.")
                sip_ips_str = st.text_area("Adresses IP Autorisées", value="\n".join(existing_ips),
                                           placeholder="192.168.1.100", height=68,
                                           help="Autoriser les serveurs Axialys à router vers ce bot.")

                st.markdown("**Paramètres Avancés**")

                sip_headers_option = st.selectbox(
                    "Transmission des Headers SIP",
                    options=SIP_HEADER_OPTIONS,
                    index=SIP_HEADER_OPTIONS.index(existing_sip_headers)
                    if existing_sip_headers in SIP_HEADER_OPTIONS else 0,
                    help="ALL = tous les headers, X = uniquement X-headers, NO = aucun.")

                krisp_enabled = st.checkbox("Réduction de bruit Krisp", value=existing_krisp,
                                            help="Active la suppression de bruit Krisp sur le canal SIP.")

                lbl_sip = "💾 Mettre à jour la ligne SIP" if sip_channel else "🔌 Créer la Ligne SIP"
                if st.button(lbl_sip, use_container_width=True):
                    nums_list = [n.strip() for n in sip_nums_str.split("\n") if n.strip()]
                    ips_list = [ip.strip() for ip in sip_ips_str.split("\n") if ip.strip()]

                    if not nums_list and not ips_list:
                        st.error("⚠️ Sécurité Reecall : Renseignez au moins un numéro ou une IP.")
                    else:
                        payload_sip = {
                            "name": f"SIP Trunk - {name}", "type": "SIP",
                            "assistantId": fd.get("id"), "projectId": project_id,
                            "inboundNumbersWhitelist": nums_list,
                            "inboundAddressesWhitelist": ips_list,
                            "includeSipHeaders": sip_headers_option,
                            "krispEnabled": krisp_enabled
                        }

                        with st.spinner("Configuration en cours..."):
                            resp_sip = save_sip_channel(api_key, existing_sip_id, payload_sip)
                            if resp_sip and resp_sip.status_code in [200, 201]:
                                st.success("✅ Configuration SIP enregistrée !")
                                fetch_sip_channel.clear()
                                st.rerun()
                            else:
                                err_text = resp_sip.text if resp_sip else "Erreur de connexion"
                                st.error(f"Échec configuration SIP : {err_text}")

# === VUE 3 : HISTORIQUE DES CONVERSATIONS ===
elif main_action == "📜 Consulter les conversations":
    st.title("Historique des Conversations")

    if project_id:
        ass_dict = {"Tous les assistants": None}
        id_to_name = {}
        if assistants_list:
            for a in assistants_list:
                nom = a.get('name', 'Assistant sans nom')
                a_id = a.get('id')
                ass_dict[nom] = a_id
                id_to_name[a_id] = nom

        col_f1, col_f2 = st.columns([1, 2])
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
                        current_exc_ass_id = res.get("value")
                        break
                if not selected_ass_id or current_exc_ass_id == selected_ass_id:
                    exc["_assistant_name"] = id_to_name.get(current_exc_ass_id, "Assistant Inconnu")
                    filtered_exchanges.append(exc)

        if filtered_exchanges:
            exchange_options = {}
            for exc in filtered_exchanges:
                date_str = format_date(exc.get("createdAt", ""))
                status = esc(exc.get("status", "inconnu").upper())
                ass_name = esc(exc.get("_assistant_name", ""))
                label = f"{date_str} - {ass_name} - [{status}]"
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
                    safe_status = esc(exchange_detail.get('status', 'N/A'))
                    safe_type = esc(exchange_detail.get('type', 'N/A'))
                    safe_created = esc(format_date(exchange_detail.get('createdAt', '')))
                    safe_updated = esc(format_date(exchange_detail.get('updatedAt', '')))
                    st.markdown(f"""
                    <div class="exchange-card">
                        <b>Status:</b> {safe_status}<br>
                        <b>Type:</b> {safe_type}<br>
                        <b>Création:</b> {safe_created}<br>
                        <b>Dernière maj:</b> {safe_updated}
                    </div>
                    """, unsafe_allow_html=True)

                    with st.expander("🛠️ Événements (Events)"):
                        events_data = exchange_detail.get("events")
                        if events_data:
                            st.json(events_data)
                        else:
                            st.info("Aucun événement.")

                    with st.expander("📊 Données (Data)"):
                        extra_data = exchange_detail.get("data")
                        if extra_data:
                            if isinstance(extra_data, str):
                                try:
                                    extra_data = json.loads(extra_data)
                                except Exception:
                                    pass
                            st.json(extra_data)
                        else:
                            st.info("Aucune donnée d'extraction disponible pour cet appel.")

                with col_chat:
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

# === VUE 4 : LOGS API ===
elif main_action == "📡 Logs API":
    st.title("Logs Réseau (Les 10 dernières requêtes API)")

    col_btn, _ = st.columns([1, 4])
    with col_btn:
        if st.button("🗑️ Vider les logs", use_container_width=True):
            st.session_state.api_logs = []
            st.rerun()

    st.divider()

    if not st.session_state.api_logs:
        st.info("Aucune requête API n'a encore été enregistrée pendant cette session.")
    else:
        for log in reversed(st.session_state.api_logs):
            status = log['status_code']
            if isinstance(status, int):
                if 200 <= status < 300: icon = "🟢"
                elif 400 <= status < 500: icon = "🟠"
                else: icon = "🔴"
            else:
                icon = "❌"

            label = f"{icon} [{log['timestamp']}] {log['method']} — {log['url']} (Status: {status})"

            with st.expander(label):
                col_req, col_resp = st.columns(2)

                with col_req:
                    st.markdown("### 📤 Requête Envoyée")
                    if log['req_params']:
                        st.caption("Paramètres d'URL (Query String):")
                        st.json(log['req_params'])
                    if log['req_body']:
                        st.caption("Corps (JSON Payload):")
                        st.json(log['req_body'])
                    elif not log['req_params']:
                        st.info("Aucun paramètre ni corps envoyé.")

                with col_resp:
                    st.markdown("### 📥 Réponse Reçue")
                    if log['resp_body']:
                        st.json(log['resp_body'])
                    else:
                        st.info("Aucun contenu retourné par le serveur.")
