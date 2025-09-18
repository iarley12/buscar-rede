import requests
import pandas as pd
import streamlit as st

# ===========================
# Configurações originais
# ===========================
RECIPROCIDADE_ID = "23030305"
PLANOS_COM_RECIPROCIDADE = {"9", "13", "83", "11", "123", "124", "7", "3", "2", "5", "1"}

# ===========================
# Funções auxiliares com cache
# ===========================

@st.cache_data(show_spinner=False)
def requisicao_lista(params, nome):
    url = "https://apicore.geap.com.br/Beneficiario/v1/RedeCredenciada/Listar"
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json().get("resultData", [])
    except Exception as e:
        st.error(f"Erro ao buscar {nome}: {e}")
        return []

@st.cache_data(show_spinner=False)
def listar_estados():
    return requisicao_lista({"TipoDominio": "Estados"}, "Estados")

@st.cache_data(show_spinner=False)
def listar_cidades(uf):
    return requisicao_lista({"TipoDominio": "Cidades", "uf": uf}, "Cidades")

@st.cache_data(show_spinner=False)
def listar_planos(uf, municipioId):
    return requisicao_lista({
        "TipoDominio": "PlanosGeap",
        "tipoConsulta": "1",
        "uf": uf,
        "municipioId": municipioId
    }, "Planos")

@st.cache_data(show_spinner=False)
def listar_estabelecimentos():
    return requisicao_lista({"TipoDominio": "Estabelecimentos", "tipoConsulta": "1"}, "Estabelecimentos")

@st.cache_data(show_spinner=False)
def listar_especialidades(nroPlano, nroTpoEstabelecimento):
    return requisicao_lista({
        "TipoDominio": "Especialidades",
        "tipoConsulta": "1",
        "NroPlano": nroPlano,
        "NroTipoEstabelecimento": nroTpoEstabelecimento
    }, "Especialidades")

@st.cache_data(show_spinner=False)
def obter_municipios_limitrofes(municipio_id):
    try:
        df = pd.read_excel("BR_Municipios_2024_LIMITROFES.xls", dtype=str)
        df.columns = df.columns.str.strip()
        df["CD_MUN"] = df["CD_MUN"].str.zfill(7)
        df["CD_LIM"] = df["CD_LIM"].str.zfill(7)
        return df[df["CD_MUN"] == str(municipio_id).zfill(7)][["CD_LIM", "NM_LIM"]].drop_duplicates().values.tolist()
    except Exception as e:
        st.warning(f"Erro ao ler municípios limítrofes: {e}")
        return []

def filtrar_cidades_principais(cidades):
    principais = {}
    for c in cidades:
        cod_mun = str(c["nroMunicipio"]).zfill(7)
        nome = c["nmeCidade"]
        if cod_mun not in principais or "(" in principais[cod_mun]["nmeCidade"]:
            if "(" not in nome:
                principais[cod_mun] = c
    return principais

def consultar_rede(parameters, label, usar_reciprocidade=False):
    """Consulta a API e retorna os dados, sem exibir corpo clínico."""
    url = "https://apicore.geap.com.br/Beneficiario/v1/RedeCredenciada/ConsultaRedeCredenciada"
    page = 1
    resultados = []

    while True:
        params = {
            "Parameters": parameters + (f"reciprocidadeId:{RECIPROCIDADE_ID};" if usar_reciprocidade else ""),
            "PageSize": 50,
            "pageNumber": page
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            json_data = response.json()
            if not isinstance(json_data, dict) or "resultData" not in json_data or json_data["resultData"] is None:
                break

            data = json_data["resultData"]
            items = data.get("items", [])
            total_pages = data.get("totalPages", 1)

            for item in items:
                endereco = item.get("endereco", {})
                resultados.append({
                    "Nome": item.get("nmeFantasia") or item.get("nmeContratado"),
                    "Telefone": item.get("telefone"),
                    "Endereco": f"{endereco.get('nmeCidade','')} / {endereco.get('sglEstado','')} / {endereco.get('bairro','')}",
                    "Especialidades": ", ".join([e.get("esp") for e in item.get("especialidades", [])])
                })
        except Exception as e:
            st.error(f"❌ Erro na consulta {label} página {page}: {e}")
            break

        if page >= total_pages:
            break
        page += 1

    return resultados

# ===========================
#        INTERFACE
# ===========================
st.title("Consulta Rede Credenciada GEAP")
st.write("Selecione os filtros para buscar prestadores de serviço.")

# ---------------------------
# Estado e Cidade
# ---------------------------
estados = listar_estados()
if not estados:
    st.stop()

uf_label = st.selectbox(
    "Estado",
    [e['nmeEstado'] for e in estados],  # exibe apenas o nome do estado
    key="uf_select"
)
# Captura a sigla do estado correspondente
sglUF = next(e['sglEstado'] for e in estados if e['nmeEstado'] == uf_label)

cidades = listar_cidades(sglUF)
principais = filtrar_cidades_principais(cidades)
municipio_to_cidade = {str(c["nroMunicipio"]).zfill(7): c["nroCidade"] for c in principais.values()}
municipio_to_nome   = {str(c["nroMunicipio"]).zfill(7): c["nmeCidade"] for c in principais.values()}

cidade_nome = st.selectbox(
    "Cidade",
    [c["nmeCidade"] for c in cidades],
    key="cidade_select"
)
nroCidade = next(c["nroCidade"] for c in cidades if c["nmeCidade"] == cidade_nome)
municipioId = next(str(c["nroMunicipio"]).zfill(7) for c in cidades if c["nroCidade"] == nroCidade)

# ---------------------------
# Plano, Tipo e Especialidade
# ---------------------------
planos = listar_planos(sglUF, municipioId)
plano_nome = st.selectbox("Plano", [p["nmePlano"] for p in planos], key="plano_select")
nroPlano = next(p["nroPlano"] for p in planos if p["nmePlano"] == plano_nome)

tipos = listar_estabelecimentos()
tipo_nome = st.selectbox("Tipo de Estabelecimento", [t["nmeTpoEstabelecimento"] for t in tipos], key="tipo_select")
nroTpoEstabelecimento = next(t["nroTpoEstabelecimento"] for t in tipos if t["nmeTpoEstabelecimento"] == tipo_nome)

especialidades = listar_especialidades(nroPlano, nroTpoEstabelecimento)
esp_nome = st.selectbox("Especialidade", [e["desEspAtendimento"] for e in especialidades], key="esp_select")
nroEspAtendimento = next(e["nroEspAtendimento"] for e in especialidades if e["desEspAtendimento"] == esp_nome)

# ---------------------------
# Botão de Consulta
# ---------------------------
if st.button("Consultar"):
    parametros_base = (
        f"tipoConsulta:1;NroPlano:{nroPlano};SglUF:{sglUF};"
        f"NroCidade:{nroCidade};NroTpoEstabelecimento:{nroTpoEstabelecimento};"
        f"NroEspAtendimento:{nroEspAtendimento};Bairro:;NmeFantasia:;"
        f"StaUrgEmerg:;StaHoraMarcada:;NroContratado:;"
    )
    usar_reciprocidade = nroPlano in PLANOS_COM_RECIPROCIDADE

    st.subheader("Município Principal")
    resultados_principal = consultar_rede(parametros_base, "Município Principal", usar_reciprocidade=False)
    if resultados_principal:
        for r in resultados_principal:
            st.write(f"**{r['Nome']}**")
            st.write(f"Telefone: {r['Telefone']}")
            st.write(f"Endereço: {r['Endereco']}")
            st.write(f"Especialidades: {r['Especialidades']}")
            st.write("---")
    else:
        st.write("Nenhum prestador encontrado.")

    if usar_reciprocidade:
        st.subheader("Município Principal (Reciprocidade)")
        resultados_recip = consultar_rede(parametros_base, "Município Principal (Reciprocidade)", usar_reciprocidade=True)
        if resultados_recip:
            for r in resultados_recip:
                st.write(f"**{r['Nome']}**")
                st.write(f"Telefone: {r['Telefone']}")
                st.write(f"Endereço: {r['Endereco']}")
                st.write(f"Especialidades: {r['Especialidades']}")
                st.write("---")
        else:
            st.write("Nenhum prestador encontrado.")

    limitrofes = obter_municipios_limitrofes(municipioId)
    if limitrofes:
        for cod_mun, nome_mun in limitrofes:
            cod_mun = str(cod_mun).zfill(7)
            nroCidade_lim = municipio_to_cidade.get(cod_mun)
            nomeCidade_lim = municipio_to_nome.get(cod_mun)
            if not nroCidade_lim or not nomeCidade_lim:
                st.warning(f"Município limítrofe ignorado: {cod_mun} - {nome_mun}")
                continue
            st.subheader(f"Município limítrofe: {nomeCidade_lim}")
            parametros_lim = parametros_base.replace(f"NroCidade:{nroCidade}", f"NroCidade:{nroCidade_lim}")
            resultados_lim = consultar_rede(parametros_lim, nomeCidade_lim, usar_reciprocidade=False)
            if resultados_lim:
                for r in resultados_lim:
                    st.write(f"**{r['Nome']}**")
                    st.write(f"Telefone: {r['Telefone']}")
                    st.write(f"Endereço: {r['Endereco']}")
                    st.write(f"Especialidades: {r['Especialidades']}")
                    st.write("---")
            else:
                st.write("Nenhum prestador encontrado.")
            if usar_reciprocidade:
                st.subheader(f"{nomeCidade_lim} (Reciprocidade)")
                resultados_lim_recip = consultar_rede(parametros_lim, nomeCidade_lim + " (Reciprocidade)", usar_reciprocidade=True)
                if resultados_lim_recip:
                    for r in resultados_lim_recip:
                        st.write(f"**{r['Nome']}**")
                        st.write(f"Telefone: {r['Telefone']}")
                        st.write(f"Endereço: {r['Endereco']}")
                        st.write(f"Especialidades: {r['Especialidades']}")
                        st.write("---")
                else:
                    st.write("Nenhum prestador encontrado.")
