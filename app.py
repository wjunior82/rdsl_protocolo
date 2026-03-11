from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from dataclasses import dataclass
import logging
import psycopg2
import psycopg2.extras
from typing import Dict, Any, List, Annotated, Optional
import pyodbc

# configure logging with timestamp including uvicorn access logger
logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "loggers": {
        "": {  # root logger
            "handlers": ["default"],
            "level": "INFO",
        },
        "uvicorn.access": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.error": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

logging.config.dictConfig(logging_config)
app = FastAPI(title="Snapshot Diff API")

# =========================
# CONFIGURAÇÃO CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# CONFIGURAÇÃO DO BANCO
# =========================
DB_CONFIG = {
    "host": "10.150.59.246",
    "port": 5432,
    "database": "contractual-rules",
    "user": "dados_rdsl",
    "password": "uOSYfmgr4@j2onIp"
}

# configuração de conexão para banco SQL Server onde as colunas adicionais estão armazenadas
SQLSERVER_CONFIG = {
    # ajuste conforme o driver/host, nome do banco e credenciais
    "driver": "{ODBC Driver 17 for SQL Server}",
    "server": "your_sqlserver_host",
    "database": "your_database",
    "uid": "username",
    "pwd": "password",
    # opcional: port, etc
}

COLUNA_PROTOCOLO = "termo_protocolo"

# =========================
# CONFIGURAÇÃO DE TABELAS (Thread-safe)
# =========================
@dataclass
class TableConfig:
    name: str
    business_key: List[str]
    ignore_columns: List[str]
    order_by: str

TABLE_CONFIGS: Dict[str, TableConfig] = {
    "report.vw_regras_medicamentos_historico": TableConfig(
        name="report.vw_regras_medicamentos_historico",
        business_key=["contrato_id", "contrato_nome_prestador", "contrato_nome_operadora", "regra_hierarquia", "regra_escopo_subclassificacao_medicamentos"],
        ignore_columns=["termo_protocolo", "termo_data_criacao", "termo_protocolo_data_publicacao", "conjunto_regra_criado_por", "conjunto_regra_data_inclusao", "termo_ultima_versao"],
        order_by="regra_hierarquia, regra_escopo_subclassificacao_medicamentos, regra_escopo_generico, regra_escopo_tipo_plano, regra_escopo_tipo_atendimento, regra_escopo_especialidade"
    ),
    "report.vw_regras_diarias_taxas_historico": TableConfig(
        name="report.vw_regras_diarias_taxas_historico",
        business_key=["contrato_id", "contrato_nome_prestador", "contrato_nome_operadora", "regra_hierarquia", "regra_escopo_subclassificacao_diarias_taxas"],
        ignore_columns=["termo_protocolo", "termo_data_criacao", "termo_protocolo_data_publicacao", "conjunto_regra_criado_por", "conjunto_regra_data_inclusao", "termo_ultima_versao"],
        order_by="regra_hierarquia, regra_escopo_subclassificacao_diarias_taxas, regra_escopo_tipo_plano, regra_escopo_categoria_de_plano, regra_escopo_tipo_de_acomodacao, regra_escopo_tipo_atendimento, regra_escopo_principais_itens_de_transposicao, regra_escopo_outros_itens_de_transposicao"
    ),
    "report.vw_regras_pacotes_historico": TableConfig(
        name="report.vw_regras_pacotes_historico",
        business_key=["contrato_id", "contrato_nome_prestador", "contrato_nome_operadora", "regra_hierarquia", "regra_escopo_subclassificacao_pacotes"],
        ignore_columns=["termo_protocolo", "termo_data_criacao", "termo_protocolo_data_publicacao", "conjunto_regra_criado_por", "conjunto_regra_data_inclusao", "termo_ultima_versao"],
        order_by="regra_hierarquia, regra_escopo_subclassificacao_pacotes, regra_escopo_tipo_plano, regra_escopo_categoria_de_plano, regra_escopo_tipo_de_acomodacao, regra_escopo_tipo_atendimento"
    ),
    "report.vw_regras_materiais_historico": TableConfig(
        name="report.vw_regras_materiais_historico",
        business_key=["contrato_id", "contrato_nome_prestador", "contrato_nome_operadora", "regra_hierarquia", "regra_escopo_subclassificacao_materiais"],
        ignore_columns=["termo_protocolo", "termo_data_criacao", "termo_protocolo_data_publicacao", "conjunto_regra_criado_por", "conjunto_regra_data_inclusao", "termo_ultima_versao"],
        order_by="regra_hierarquia, regra_escopo_subclassificacao_materiais, regra_escopo_tipo_plano, regra_escopo_tipo_atendimento, regra_escopo_especialidade"
    ),
    "report.vw_regras_hm_sadt_historico": TableConfig(
        name="report.vw_regras_hm_sadt_historico",
        business_key=["contrato_id", "contrato_nome_prestador", "contrato_nome_operadora", "regra_hierarquia", "regra_escopo_subclassificacao_hm_sadt"],
        ignore_columns=["termo_protocolo", "termo_data_criacao", "termo_protocolo_data_publicacao", "conjunto_regra_criado_por", "conjunto_regra_data_inclusao", "termo_ultima_versao"],
        order_by="regra_hierarquia, regra_escopo_subclassificacao_hm_sadt, regra_escopo_tipo_de_plano, regra_escopo_categoria_de_plano, regra_escopo_tipo_de_acomodacao, regra_escopo_especialidades_hm_sadt, regra_escopo_tipo_de_atendimento"
    ),
}


# =========================
# NORMALIZA O RETORNO
# =========================
def normalize_value(v):
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return v

# =========================
# CONEXÕES
# =========================

def get_connection():
    """Retorna conexão com o PostgreSQL principal."""
    return psycopg2.connect(**DB_CONFIG)


def get_sqlserver_connection():
    """Cria conexão com o SQL Server usando pyodbc e as informações em SQLSERVER_CONFIG."""
    conn_str = (
        "DRIVER=SQL Server;SERVER=RDRJ2BIDB02;DATABASE=qualidade;UID=qualidadedados_aws;PWD=VitRf@20!1".format(**SQLSERVER_CONFIG)
    )
    # se precisar de porta, adicione ";PORT={port}" no conn_str
    return pyodbc.connect(conn_str)


def fetch_sqlserver_extra() -> Dict[str, Dict[str, Any]]:
    conn = get_sqlserver_connection()
    cursor = conn.cursor()
    query = "SELECT NUM_PROTOCOLO, NME_USUARIO, DTA_CONTROLE FROM SSIS_DEV.ZG_CONTROLEPROTOCOLO"
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {row[0]: {"NME_USUARIO": row[1], "DTA_CONTROLE": row[2]} for row in rows}

# =========================
# CARREGA UMA QUERY
# =========================
def load_query(query: str) -> List[Any]:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    # Se a query retornar linhas como dicts com uma única coluna,
    # normaliza para uma lista de valores simples: ['AL', 'BA', 'CE']
    if rows and isinstance(rows, list) and isinstance(rows[0], dict) and len(rows[0]) == 1:
        return [list(r.values())[0] for r in rows]

    return rows

# =========================
# CARREGA SNAPSHOT COMPLETO
# =========================
def load_snapshot(protocolo: str, config: TableConfig) -> Dict[str, Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    query = f"""
        SELECT *
        FROM {config.name}
        WHERE {COLUNA_PROTOCOLO} = %s
        ORDER BY {config.order_by}
    """

    cursor.execute(query, (protocolo,))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    snapshot = {}

    for row in rows:
        key = build_key(row, config)
        snapshot[key] = {k: normalize_value(v) for k, v in dict(row).items()}

    return snapshot


# =========================
# MONTA CHAVE LÓGICA
# =========================
def build_key(row: Dict[str, Any], config: TableConfig) -> str:
    return "|".join(str(row[col]) for col in config.business_key)

# =========================
# LISTA FILTROS DISPONÍVEIS
# =========================
def list_filters():
    return {
        "contrato_regional": load_query("""select UPPER(contrato_regional) AS contrato_regional from (
                                           select distinct contrato_regional from report.vw_regras_medicamentos_historico
                                           union 
                                           select distinct contrato_regional from report.vw_regras_diarias_taxas_historico
                                           union 
                                           select distinct contrato_regional from report.vw_regras_pacotes_historico
                                           union 
                                           select distinct contrato_regional from report.vw_regras_materiais_historico
                                           union 
                                           select distinct contrato_regional from report.vw_regras_hm_sadt_historico
                                           ) x order by contrato_regional"""),
        "contrato_nome_prestador": load_query("""select UPPER(contrato_nome_prestador) AS contrato_nome_prestador from (
                                           select distinct contrato_nome_prestador from report.vw_regras_medicamentos_historico
                                           union 
                                           select distinct contrato_nome_prestador from report.vw_regras_diarias_taxas_historico
                                           union 
                                           select distinct contrato_nome_prestador from report.vw_regras_pacotes_historico
                                           union 
                                           select distinct contrato_nome_prestador from report.vw_regras_materiais_historico
                                           union 
                                           select distinct contrato_nome_prestador from report.vw_regras_hm_sadt_historico
                                           ) x order by contrato_nome_prestador"""),
        "contrato_nome_operadora": load_query("""select UPPER(contrato_nome_operadora) AS contrato_nome_operadora from (
                                           select distinct contrato_nome_operadora from report.vw_regras_medicamentos_historico
                                           union 
                                           select distinct contrato_nome_operadora from report.vw_regras_diarias_taxas_historico
                                           union 
                                           select distinct contrato_nome_operadora from report.vw_regras_pacotes_historico
                                           union 
                                           select distinct contrato_nome_operadora from report.vw_regras_materiais_historico
                                           union 
                                           select distinct contrato_nome_operadora from report.vw_regras_hm_sadt_historico
                                           ) x order by contrato_nome_operadora"""),
         "conjunto_regra_criado_por": load_query("""select LOWER(conjunto_regra_criado_por) AS conjunto_regra_criado_por from (
                                           select distinct conjunto_regra_criado_por from report.vw_regras_medicamentos_historico
                                           union 
                                           select distinct conjunto_regra_criado_por from report.vw_regras_diarias_taxas_historico
                                           union 
                                           select distinct conjunto_regra_criado_por from report.vw_regras_pacotes_historico
                                           union 
                                           select distinct conjunto_regra_criado_por from report.vw_regras_materiais_historico
                                           union 
                                           select distinct conjunto_regra_criado_por from report.vw_regras_hm_sadt_historico
                                           ) x order by conjunto_regra_criado_por""")
    }

# =========================
# LISTA PROTOCOLOS DISPONÍVEIS
# =========================
def list_protocol(
    contrato_regional: Optional[List[str]] = None,
    contrato_nome_prestador: Optional[List[str]] = None,
    contrato_nome_operadora: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    base_query = """
        select * from (
        select distinct contrato_id, contrato_regional, contrato_nome_prestador, contrato_nome_operadora, termo_protocolo, termo_protocolo_data_publicacao, conjunto_regra_criado_por from report.vw_regras_medicamentos_historico
        union 
        select distinct contrato_id, contrato_regional, contrato_nome_prestador, contrato_nome_operadora, termo_protocolo, termo_protocolo_data_publicacao, conjunto_regra_criado_por from report.vw_regras_diarias_taxas_historico
        union 
        select distinct contrato_id, contrato_regional, contrato_nome_prestador, contrato_nome_operadora, termo_protocolo, termo_protocolo_data_publicacao, conjunto_regra_criado_por from report.vw_regras_pacotes_historico
        union 
        select distinct contrato_id, contrato_regional, contrato_nome_prestador, contrato_nome_operadora, termo_protocolo, termo_protocolo_data_publicacao, conjunto_regra_criado_por from report.vw_regras_materiais_historico
        union 
        select distinct contrato_id, contrato_regional, contrato_nome_prestador, contrato_nome_operadora, termo_protocolo, termo_protocolo_data_publicacao, conjunto_regra_criado_por from report.vw_regras_hm_sadt_historico
        ) x
    """

    conditions = []
    params = []

    if contrato_regional is not None and len(contrato_regional) > 0:
        placeholders = ",".join(["%s"] * len(contrato_regional))
        conditions.append(f"contrato_regional IN ({placeholders})")
        params.extend(contrato_regional)

    if contrato_nome_prestador is not None and len(contrato_nome_prestador) > 0:
        placeholders = ",".join(["%s"] * len(contrato_nome_prestador))
        conditions.append(f"contrato_nome_prestador IN ({placeholders})")
        params.extend(contrato_nome_prestador)

    if contrato_nome_operadora is not None and len(contrato_nome_operadora) > 0:
        placeholders = ",".join(["%s"] * len(contrato_nome_operadora))
        conditions.append(f"contrato_nome_operadora IN ({placeholders})")
        params.extend(contrato_nome_operadora)

    if conditions:
        base_query += "\n        where " + " and ".join(conditions)

    base_query += "\n        order by termo_protocolo_data_publicacao desc"

    if params:
        cursor.execute(base_query, tuple(params))
    else:
        cursor.execute(base_query)

    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    # se houver resultado, buscar colunas extras no SQL Server e mesclar
    if rows:
        # para evitar limites de parâmetros do ODBC, carregamos todos os extras
        # e deixamos o Python fazer o 'join' por termo_protocolo.
        extras = fetch_sqlserver_extra()
        # otimização: usar compreensão de lista para mesclar em memória sem loop explícito
        rows = [
            {**r, "NME_USUARIO": extras.get(r.get("termo_protocolo"), {}).get("NME_USUARIO"), "DTA_CONTROLE": extras.get(r.get("termo_protocolo"), {}).get("DTA_CONTROLE")}
            for r in rows
        ]

    return rows

# =========================
# REMOVE VALORES VAZIOS
# =========================
def remove_empty_values(data: Dict) -> Dict:
    """Remove campos com valores vazios (strings vazias)"""
    return {k: v for k, v in data.items() if v != ""}

# =========================
# COMPARA DOIS SNAPSHOTS
# =========================
def _extract_sort_key(key: str) -> tuple:
    """
    Extrai os 2 últimos tokens da key para ordenação.
    Key format: token1|token2|token3|token4|token5
    Ordena por: token5 (último), token4 (penúltimo) 
    """
    tokens = key.split("|")
    if len(tokens) >= 2:
        return (tokens[-1], tokens[-2])
    return (key,)


def diff_snapshots(old: Dict, new: Dict, config: TableConfig) -> Dict:

    result = {
        "inserted": [],
        "deleted": [],
        "updated": []
    }

    old_keys = set(old.keys())
    new_keys = set(new.keys())

    # =========================
    # INSERTS
    # =========================
    for key in new_keys - old_keys:
        result["inserted"].append({
            "key": key,
            "new_data": remove_empty_values(new[key])
        })

    # =========================
    # DELETES
    # =========================
    for key in old_keys - new_keys:
        result["deleted"].append({
            "key": key,
            "old_data": remove_empty_values(old[key])
        })

    # =========================
    # UPDATES
    # =========================
    for key in old_keys & new_keys:
        old_row = old[key]
        new_row = new[key]

        column_changes = {}

        for column in new_row.keys():

            if column in config.ignore_columns:
                continue

            old_value = old_row.get(column)
            new_value = new_row.get(column)

            if old_value != new_value:
                column_changes[column] = {
                    "old": old_value,
                    "new": new_value
                }

        if column_changes:
            result["updated"].append({
                "key": key,
                "changes": column_changes
            })

    # =========================
    # ORDENAR RESULTADOS POR ÚLTIMOS 2 TOKENS DA KEY
    # =========================
    result["inserted"].sort(key=lambda x: _extract_sort_key(x["key"]))
    result["deleted"].sort(key=lambda x: _extract_sort_key(x["key"]))
    result["updated"].sort(key=lambda x: _extract_sort_key(x["key"]))

    return result


# =========================
# ENDPOINT API DIFF
# =========================
@app.get("/diff")
def get_diff(
    scope_snapshot: Annotated[str, Query(..., alias="scope")],
    from_snapshot: Annotated[str, Query(..., alias="from")],
    to_snapshot: Annotated[str, Query(..., alias="to")]
):
    if scope_snapshot not in TABLE_CONFIGS:
        return {"error": f"Scope '{scope_snapshot}' não encontrado. Valores válidos: {list(TABLE_CONFIGS.keys())}"}
    
    config = TABLE_CONFIGS[scope_snapshot]
    old_snapshot = load_snapshot(from_snapshot, config)
    new_snapshot = load_snapshot(to_snapshot, config)

    diff_result = diff_snapshots(old_snapshot, new_snapshot, config)

    return {
        "scope": scope_snapshot,
        "from": from_snapshot,
        "to": to_snapshot,
        "summary": {
            "inserted": len(diff_result["inserted"]),
            "deleted": len(diff_result["deleted"]),
            "updated": len(diff_result["updated"])
        },
        "diff": diff_result
    }

# =========================
# ENDPOINT API FILTERS
# =========================
@app.get("/filters")
def get_filters():
    return list_filters()        

# =========================
# ENDPOINT API LIST
# =========================
@app.get("/list")
def get_list(
    contrato_regional: Annotated[Optional[List[str]], Query(..., alias="contrato_regional")] = None,
    contrato_nome_prestador: Annotated[Optional[List[str]], Query(..., alias="contrato_nome_prestador")] = None,
    contrato_nome_operadora: Annotated[Optional[List[str]], Query(..., alias="contrato_nome_operadora")] = None,
):
    return list_protocol(contrato_regional, contrato_nome_prestador, contrato_nome_operadora)        