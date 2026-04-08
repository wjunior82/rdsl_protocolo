from fastapi import FastAPI, Query, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from dataclasses import dataclass
import logging
import psycopg2
import psycopg2.extras
from typing import Dict, Any, List, Annotated, Optional
import pyodbc
from pydantic import BaseModel, config
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

from config import settings
from security import verify_api_key, validate_protocolo, validate_scope, validate_filter_list, RequestLogger, sanitize_string

# =========================
# PYDANTIC MODELS
# =========================
class ControleProtocoloInsert(BaseModel):
    """Model for inserting controle protocolo."""
    NUM_PROTOCOLO: str
    NME_USUARIO: str

class ControleProtocoloDelete(BaseModel):
    """Model for deleting controle protocolo."""
    NUM_PROTOCOLO: str

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
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_origins,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# =========================
# CONFIGURAÇÃO DO BANCO
# =========================
DB_CONFIG = {
    "host": settings.postgres_host,
    "port": settings.postgres_port,
    "database": settings.postgres_database,
    "user": settings.postgres_user,
    "password": settings.postgres_password
}

# configuração de conexão para banco SQL Server onde as colunas adicionais estão armazenadas
SQLSERVER_CONFIG = {
    "driver": settings.sqlserver_driver,
    "server": settings.sqlserver_server,
    "database": settings.sqlserver_database,
    "SCHEME": settings.sqlserver_scheme,
    "uid": settings.sqlserver_uid,
    "pwd": settings.sqlserver_password,
}

COLUNA_PROTOCOLO = "termo_protocolo"

# =========================
# CONFIGURAÇÃO DE TABELAS (Thread-safe)
# =========================
@dataclass
class TableConfig:
    name: str
    business_key: List[str]
    columns: str
    ignore_columns: List[str]
    order_by: str

TABLE_CONFIGS: Dict[str, TableConfig] = {
    "report.vw_regras_diarias_taxas_historico": TableConfig(
        name="report.vw_regras_diarias_taxas_historico",
        business_key=["contrato_id", "contrato_nome_prestador", "contrato_nome_operadora", "Escopo", "Hierarquia", "Subclassificação Diárias / Taxas", "Tipo de plano", "Categoria de plano", "Tipo de acomodação", "Tipo de atendimento", "Principais itens de transposição", "Outros itens de transposição"],
        columns="contrato_id, contrato_regional, contrato_nome_prestador, contrato_nome_operadora, TO_CHAR(termo_data_inicio_vigencia, 'DD/MM/YYYY') AS \"Detalhes da Vigência\", conjunto_regra_indice + 1 AS \"Escopo\", regra_hierarquia AS \"Hierarquia\", regra_escopo_regra_de_transposicao AS \"Regra de Transposição\", regra_escopo_subclassificacao_diarias_taxas AS \"Subclassificação Diárias / Taxas\", regra_escopo_tipo_plano AS \"Tipo de plano\", regra_escopo_categoria_de_plano AS \"Categoria de plano\", regra_escopo_tipo_de_acomodacao AS \"Tipo de acomodação\", regra_escopo_tipo_atendimento AS \"Tipo de atendimento\", regra_escopo_principais_itens_de_transposicao AS \"Principais itens de transposição\", regra_escopo_outros_itens_de_transposicao AS \"Outros itens de transposição\", regra_tipo AS \"Tipo de Regra\", concat(regra_tabela_tabela, ' - ', regra_tabela_versao) AS \"Tabela\", case when ((regra_reajuste_tipo is null) or (regra_reajuste_ajuste is null)) then '' else concat(regra_reajuste_tipo, ' de ', regra_reajuste_ajuste, '%') end AS \"Reajuste %\", case when ((regra_rsfd_taxa_comercializacao_tipo is null) or (regra_rsfd_taxa_comercializacao_ajuste is null)) then '' else concat(regra_rsfd_taxa_comercializacao_tipo, ' de ', regra_rsfd_taxa_comercializacao_ajuste, '%') end AS \"Taxa de Comercialização\", regra_entrantes AS \"Entrantes\", regra_regra_de_entrantes AS \"Regra de Entrantes\", regra_periodicidade_entrantes AS \"Periodicidade entrantes\", regra_observacoes_entrantes AS \"Observações Entrantes\", regra_descontinuados AS \"Descontinuados\", regra_regra_de_descontinuados AS \"Regra de Descontinuados\", regra_periodicidade_descontinuados AS \"Periodicidade descontinuados\", regra_observacoes_descontinuados AS \"Observações Descontinuados\", regra_observacoes AS \"Observações\", regra_tipo_de_alteracao AS \"Tipo de Alteração\"",
        ignore_columns=["termo_protocolo", "termo_data_criacao", "termo_protocolo_data_publicacao", "conjunto_regra_criado_por", "conjunto_regra_data_inclusao", "termo_ultima_versao"],
        order_by="conjunto_regra_indice, regra_hierarquia, regra_escopo_subclassificacao_diarias_taxas, regra_escopo_tipo_plano, regra_escopo_categoria_de_plano, regra_escopo_tipo_de_acomodacao, regra_escopo_tipo_atendimento, regra_escopo_principais_itens_de_transposicao, regra_escopo_outros_itens_de_transposicao"
    ),
    "report.vw_regras_hm_sadt_historico": TableConfig(
        name="report.vw_regras_hm_sadt_historico",
        business_key=["contrato_id", "contrato_nome_prestador", "contrato_nome_operadora", "conjunto_regra_indice", "regra_hierarquia", "regra_escopo_subclassificacao_hm_sadt"],
        columns="*",
        ignore_columns=["termo_protocolo", "termo_data_criacao", "termo_protocolo_data_publicacao", "conjunto_regra_criado_por", "conjunto_regra_data_inclusao", "termo_ultima_versao"],
        order_by="conjunto_regra_indice, regra_hierarquia, regra_escopo_subclassificacao_hm_sadt, regra_escopo_tipo_de_plano, regra_escopo_categoria_de_plano, regra_escopo_tipo_de_acomodacao, regra_escopo_especialidades_hm_sadt, regra_escopo_tipo_de_atendimento"
    ),
    "report.vw_regras_materiais_historico": TableConfig(
        name="report.vw_regras_materiais_historico",
        business_key=["contrato_id", "contrato_nome_prestador", "contrato_nome_operadora", "Escopo", "Hierarquia", "Subclassificação Materiais", "Tipo de plano", "Tipo de atendimento", "Especialidade"],
        columns="contrato_id, contrato_regional, contrato_nome_prestador, contrato_nome_operadora, TO_CHAR(termo_data_inicio_vigencia, 'DD/MM/YYYY') AS \"Detalhes da Vigência\", conjunto_regra_indice + 1 AS \"Escopo\", regra_hierarquia AS \"Hierarquia\", regra_escopo_subclassificacao_materiais AS \"Subclassificação Materiais\", regra_escopo_tipo_plano AS \"Tipo de plano\", regra_escopo_tipo_atendimento AS \"Tipo de atendimento\", regra_escopo_especialidade AS \"Especialidade\", \
        regra_escopo_negociacao_direta AS \"Negociação Direta\", regra_escopo_itens_excecao AS \"Itens de Exceção\", \
        regra_tipo AS \"Tipo de Regra\", concat(regra_tabela_tabela, ' - ', regra_tabela_versao) AS \"Tabela\", \
        regra_brasindice_congelado AS \"Brasindice Congelado\", regra_simpro_congelado AS \"SIMPRO Congelado\", \
        regra_preco_de_referencia AS \"Preço de referência\", \
        regra_fracionamento AS \"Fracionamento\", regra_tipo_preco AS \"Tipo preço\", \
        case when regra_tipo IN ('Brasíndice', 'Simpro', 'Tabela Preço Fixo', 'Tabela Própria') then case when ((regra_reajuste_tipo is null) or (regra_reajuste_ajuste is null)) then '' else concat(regra_reajuste_tipo, ' de ', regra_reajuste_ajuste, '%') end else '' end AS \"Reajuste %\", \
        case when regra_tipo IN ('Brasíndice', 'Valoração variavel') then case when ((regra_margem_tipo is null) or (regra_margem_ajuste is null)) then '' else concat(regra_margem_tipo, ' de ', regra_margem_ajuste, '%') end else '' end AS \"Margem %\", \
        case when regra_tipo IN ('Tabela Própria', 'Valoração variavel') then case when ((regra_rsfd_taxa_comercializacao_tipo is null) or (regra_rsfd_taxa_comercializacao_ajuste is null)) then '' else concat(regra_rsfd_taxa_comercializacao_tipo, ' de ', regra_rsfd_taxa_comercializacao_ajuste, '%') end else '' end AS \"Taxa de Comercialização\", \
        regra_aliquota AS \"Aliquota\", regra_entrantes AS \"Entrantes\", regra_regra_de_entrantes AS \"Regra de Entrantes\", regra_inclusao_automatica_entrantes AS \"Inclusão automática entrantes\", regra_periodicidade_entrantes AS \"Periodicidade entrantes\", regra_observacoes_entrantes AS \"Observações Entrantes\", regra_descontinuados AS \"Descontinuados\", regra_regra_de_descontinuados AS \"Regra de Descontinuados\", regra_inclusao_automatica_descontinuados AS \"Inclusão automática descontinuados\", regra_periodicidade_descontinuados AS \"Periodicidade descontinuados\", regra_observacoes_descontinuados AS \"Observações Descontinuados\", regra_observacoes AS \"Observações\", regra_tipo_de_alteracao AS \"Tipo de Alteração\", \
        case when regra_tipo IN ('Brasíndice') then case when ((regra_tabela_fracionamento_tabela is null) or (regra_tabela_fracionamento_versao is null)) then '' else concat(regra_tabela_fracionamento_tabela, ' - ', regra_tabela_fracionamento_versao) end else '' end AS \"Tabela Fracionamento\", \
        case when regra_tipo IN ('Brasíndice') then case when ((regra_tabela_planos_tabela is null) or (regra_tabela_planos_versao is null)) then '' else concat(regra_tabela_planos_tabela, ' - ', regra_tabela_planos_versao) end else '' end AS \"Tabela de Planos\"",
        ignore_columns=["termo_protocolo", "termo_data_criacao", "termo_protocolo_data_publicacao", "conjunto_regra_criado_por", "conjunto_regra_data_inclusao", "termo_ultima_versao"],
        order_by="conjunto_regra_indice, regra_hierarquia, regra_escopo_subclassificacao_materiais, regra_escopo_tipo_plano, regra_escopo_tipo_atendimento, regra_escopo_especialidade"
    ),
    "report.vw_regras_medicamentos_historico": TableConfig(
        name="report.vw_regras_medicamentos_historico",
        business_key=["contrato_id", "contrato_nome_prestador", "contrato_nome_operadora", "Escopo", "Hierarquia", "Subclassificação Medicamentos", "Tipo de plano", "Tipo de atendimento", "Especialidade"],
        columns="contrato_id, contrato_regional, contrato_nome_prestador, contrato_nome_operadora, TO_CHAR(termo_data_inicio_vigencia, 'DD/MM/YYYY') AS \"Detalhes da Vigência\", conjunto_regra_indice + 1 AS \"Escopo\", regra_hierarquia AS \"Hierarquia\", regra_escopo_subclassificacao_medicamentos AS \"Subclassificação Medicamentos\", regra_escopo_generico AS \"Genérico\", regra_escopo_tipo_plano AS \"Tipo de plano\", regra_escopo_tipo_atendimento AS \"Tipo de atendimento\", regra_escopo_especialidade AS \"Especialidade\", regra_tipo AS \"Tipo de Regra\", concat(regra_tabela_tabela, ' - ', regra_tabela_versao) AS \"Tabela\", \
        regra_preco_de_referencia AS \"Preço de referência\", \
        regra_brasindice_congelado AS \"Brasindice Congelado\", regra_simpro_congelado AS \"SIMPRO Congelado\", \
        regra_fracionamento AS \"Fracionamento\", regra_tipo_preco AS \"Tipo preço\", \
        case when regra_tipo IN ('Brasíndice', 'Simpro', 'Tabela Preço Fixo', 'Tabela Própria') then case when ((regra_reajuste_tipo is null) or (regra_reajuste_ajuste is null)) then '' else concat(regra_reajuste_tipo, ' de ', regra_reajuste_ajuste, '%') end else '' end AS \"Reajuste %\", \
        case when regra_tipo IN ('Brasíndice', 'Valoração variavel') then case when ((regra_margem_tipo is null) or (regra_margem_ajuste is null)) then '' else concat(regra_margem_tipo, ' de ', regra_margem_ajuste, '%') end else '' end AS \"Margem %\", \
        case when regra_tipo IN ('Tabela Própria', 'Valoração variavel') then case when ((regra_rsfd_taxa_comercializacao_tipo is null) or (regra_rsfd_taxa_comercializacao_ajuste is null)) then '' else concat(regra_rsfd_taxa_comercializacao_tipo, ' de ', regra_rsfd_taxa_comercializacao_ajuste, '%') end else '' end AS \"Taxa de Comercialização\", \
        regra_aliquota AS \"Aliquota\", regra_entrantes AS \"Entrantes\", regra_regra_de_entrantes AS \"Regra de Entrantes\", regra_inclusao_automatica_entrantes AS \"Inclusão automática entrantes\", regra_periodicidade_entrantes AS \"Periodicidade entrantes\", regra_observacoes_entrantes AS \"Observações Entrantes\", regra_descontinuados AS \"Descontinuados\", regra_regra_de_descontinuados AS \"Regra de Descontinuados\", regra_inclusao_automatica_descontinuados AS \"Inclusão automática descontinuados\", regra_periodicidade_descontinuados AS \"Periodicidade descontinuados\", regra_observacoes_descontinuados AS \"Observações Descontinuados\", regra_observacoes AS \"Observações\", regra_tipo_de_alteracao AS \"Tipo de Alteração\", \
        case when regra_tipo IN ('Brasíndice') then case when ((regra_tabela_fracionamento_tabela is null) or (regra_tabela_fracionamento_versao is null)) then '' else concat(regra_tabela_fracionamento_tabela, ' - ', regra_tabela_fracionamento_versao) end else '' end AS \"Tabela Fracionamento\", \
        case when regra_tipo IN ('Brasíndice') then case when ((regra_tabela_planos_tabela is null) or (regra_tabela_planos_versao is null)) then '' else concat(regra_tabela_planos_tabela, ' - ', regra_tabela_planos_versao) end else '' end AS \"Tabela de Planos\"",              
        ignore_columns=["termo_protocolo", "termo_data_criacao", "termo_protocolo_data_publicacao", "conjunto_regra_criado_por", "conjunto_regra_data_inclusao", "termo_ultima_versao"],
        order_by="conjunto_regra_indice, regra_hierarquia, regra_escopo_subclassificacao_medicamentos, regra_escopo_tipo_plano, regra_escopo_tipo_atendimento, regra_escopo_especialidade"
    ),
    "report.vw_regras_pacotes_historico": TableConfig(
        name="report.vw_regras_pacotes_historico",
        business_key=["contrato_id", "contrato_nome_prestador", "contrato_nome_operadora", "Escopo", "Hierarquia", "Subclassificação Pacotes", "Tipo de plano", "Categoria de plano", "Tipo de acomodação", "Tipo de atendimento"],
        columns="contrato_id, contrato_regional, contrato_nome_prestador, contrato_nome_operadora, TO_CHAR(termo_data_inicio_vigencia, 'DD/MM/YYYY') AS \"Detalhes da Vigência\", conjunto_regra_indice + 1 AS \"Escopo\", regra_hierarquia AS \"Hierarquia\", regra_escopo_subclassificacao_pacotes AS \"Subclassificação Pacotes\", regra_escopo_tipo_plano AS \"Tipo de plano\", regra_escopo_categoria_de_plano AS \"Categoria de plano\", regra_escopo_tipo_de_acomodacao AS \"Tipo de acomodação\", regra_escopo_tipo_atendimento AS \"Tipo de atendimento\", regra_tipo AS \"Tipo de Regra\", concat(regra_tabela_tabela, ' - ', regra_tabela_versao) AS \"Tabela\", case when ((regra_reajuste_tipo is null) or (regra_reajuste_ajuste is null)) then '' else concat(regra_reajuste_tipo, ' de ', regra_reajuste_ajuste, '%') end AS \"Reajuste %\", case when ((regra_rsfd_taxa_comercializacao_tipo is null) or (regra_rsfd_taxa_comercializacao_ajuste is null)) then '' else concat(regra_rsfd_taxa_comercializacao_tipo, ' de ', regra_rsfd_taxa_comercializacao_ajuste, '%') end AS \"Taxa de Comercialização\", regra_entrantes AS \"Entrantes\", regra_regra_de_entrantes AS \"Regra de Entrantes\", regra_periodicidade_entrantes AS \"Periodicidade entrantes\", regra_observacoes_entrantes AS \"Observações Entrantes\", regra_descontinuados AS \"Descontinuados\", regra_regra_de_descontinuados AS \"Regra de Descontinuados\", regra_periodicidade_descontinuados AS \"Periodicidade descontinuados\", regra_observacoes_descontinuados AS \"Observações Descontinuados\", regra_observacoes AS \"Observações\", regra_tipo_de_alteracao AS \"Tipo de Alteração\"",
        ignore_columns=["termo_protocolo", "termo_data_criacao", "termo_protocolo_data_publicacao", "conjunto_regra_criado_por", "conjunto_regra_data_inclusao", "termo_ultima_versao"],
        order_by="conjunto_regra_indice, regra_hierarquia, regra_escopo_subclassificacao_pacotes, regra_escopo_tipo_plano, regra_escopo_categoria_de_plano, regra_escopo_tipo_de_acomodacao, regra_escopo_tipo_atendimento"
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
    try:
        conn_str = (
            f"DRIVER={SQLSERVER_CONFIG['driver']};SERVER={SQLSERVER_CONFIG['server']};"
            f"DATABASE={SQLSERVER_CONFIG['database']};UID={SQLSERVER_CONFIG['uid']};"
            f"PWD={SQLSERVER_CONFIG['pwd']}"
        )
        return pyodbc.connect(conn_str)
    except Exception as e:
        logging.error(f"Erro ao conectar ao SQL Server: {str(e)}")
        raise


def fetch_sqlserver_extra() -> Dict[str, Dict[str, Any]]:
    conn = get_sqlserver_connection()
    cursor = conn.cursor()
    query = f"SELECT NUM_PROTOCOLO, NME_USUARIO, DTA_CONTROLE FROM {settings.sqlserver_scheme}.ZG_CONTROLEPROTOCOLO"
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return {row[0]: {"NME_USUARIO": row[1], "DTA_CONTROLE": row[2]} for row in rows}

# =========================
# BUSCA CONTROLE PROTOCOLO ESPECÍFICO
# =========================
def fetch_controle_protocolo(protocolo: str) -> Optional[Dict[str, Any]]:
    conn = get_sqlserver_connection()
    cursor = conn.cursor()
    query = f"SELECT NME_USUARIO, DTA_CONTROLE FROM {settings.sqlserver_scheme}.ZG_CONTROLEPROTOCOLO WHERE NUM_PROTOCOLO = ?"
    cursor.execute(query, (protocolo,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return {"NME_USUARIO": row[0], "DTA_CONTROLE": row[1]}
    return None

# =========================
# INSERE REGISTRO NO SQL SERVER
# =========================
def insert_controle_protocolo(data: dict) -> bool:
    conn = None
    cursor = None
    try:
        conn = get_sqlserver_connection()
        cursor = conn.cursor()
        query = f"INSERT INTO {settings.sqlserver_scheme}.ZG_CONTROLEPROTOCOLO (NUM_PROTOCOLO, NME_USUARIO, DTA_CONTROLE) VALUES (?, ?, GETDATE())"
        cursor.execute(query, (data["NUM_PROTOCOLO"], data["NME_USUARIO"]))
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Erro ao inserir registro: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def delete_controle_protocolo(data: dict) -> bool:
    conn = None
    cursor = None
    try:
        conn = get_sqlserver_connection()
        cursor = conn.cursor()
        query = f"DELETE FROM {settings.sqlserver_scheme}.ZG_CONTROLEPROTOCOLO WHERE NUM_PROTOCOLO = ?"
        cursor.execute(query, (data["NUM_PROTOCOLO"],))
        conn.commit()
        return True
    except Exception as e:
        logging.error(f"Erro ao excluir registro: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

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
    colunas_escapadas = config.columns.replace('%', '%%')
    query = f"""
        SELECT {colunas_escapadas}
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
                                           select distinct UPPER(TRIM(REPLACE(contrato_nome_operadora, CHR(160), ''))) as contrato_nome_operadora from report.vw_regras_medicamentos_historico
                                           union 
                                           select distinct UPPER(TRIM(REPLACE(contrato_nome_operadora, CHR(160), ''))) as contrato_nome_operadora from report.vw_regras_diarias_taxas_historico
                                           union 
                                           select distinct UPPER(TRIM(REPLACE(contrato_nome_operadora, CHR(160), ''))) as contrato_nome_operadora from report.vw_regras_pacotes_historico
                                           union 
                                           select distinct UPPER(TRIM(REPLACE(contrato_nome_operadora, CHR(160), ''))) as contrato_nome_operadora from report.vw_regras_materiais_historico
                                           union 
                                           select distinct UPPER(TRIM(REPLACE(contrato_nome_operadora, CHR(160), ''))) as contrato_nome_operadora from report.vw_regras_hm_sadt_historico
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
        select distinct contrato_id, contrato_regional, contrato_nome_prestador, UPPER(TRIM(REPLACE(contrato_nome_operadora, CHR(160), ''))) as contrato_nome_operadora, termo_protocolo, termo_protocolo_data_publicacao, conjunto_regra_criado_por from report.vw_regras_medicamentos_historico
        union 
        select distinct contrato_id, contrato_regional, contrato_nome_prestador, UPPER(TRIM(REPLACE(contrato_nome_operadora, CHR(160), ''))) as contrato_nome_operadora, termo_protocolo, termo_protocolo_data_publicacao, conjunto_regra_criado_por from report.vw_regras_diarias_taxas_historico
        union 
        select distinct contrato_id, contrato_regional, contrato_nome_prestador, UPPER(TRIM(REPLACE(contrato_nome_operadora, CHR(160), ''))) as contrato_nome_operadora, termo_protocolo, termo_protocolo_data_publicacao, conjunto_regra_criado_por from report.vw_regras_pacotes_historico
        union 
        select distinct contrato_id, contrato_regional, contrato_nome_prestador, UPPER(TRIM(REPLACE(contrato_nome_operadora, CHR(160), ''))) as contrato_nome_operadora, termo_protocolo, termo_protocolo_data_publicacao, conjunto_regra_criado_por from report.vw_regras_materiais_historico
        union 
        select distinct contrato_id, contrato_regional, contrato_nome_prestador, UPPER(TRIM(REPLACE(contrato_nome_operadora, CHR(160), ''))) as contrato_nome_operadora, termo_protocolo, termo_protocolo_data_publicacao, conjunto_regra_criado_por from report.vw_regras_hm_sadt_historico
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
    Extrai todos os tokens da key para ordenação.
    Key format: token1|token2|token3|token4|token5
    Ordena por: token1, token2, token3, token4, token5
    """
    tokens = key.split("|")
    converted = []
    for token in tokens:
        try:
            converted.append(int(token))
        except ValueError:
            converted.append(token)
    return tuple(converted)


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
    # ORDENAR RESULTADOS POR ÚLTIMOS 3 TOKENS DA KEY
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
    to_snapshot: Annotated[str, Query(..., alias="to")],
    api_key: str = Depends(verify_api_key)
):
    try:
        # Validate inputs
        scope_snapshot = validate_scope(scope_snapshot)
        from_snapshot = validate_protocolo(from_snapshot)
        to_snapshot = validate_protocolo(to_snapshot)
        
        # Log request
        RequestLogger.log_request("/diff", api_key, {
            "scope": scope_snapshot,
            "from": from_snapshot,
            "to": to_snapshot
        })
        
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
    except ValueError as e:
        RequestLogger.log_error("/diff", str(e), "WARNING")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        RequestLogger.log_error("/diff", str(e), "ERROR")
        logging.error(f"Error in /diff scope: {scope_snapshot} endpoint: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

# =========================
# ENDPOINT API FILTERS
# =========================
@app.get("/filters")
def get_filters(api_key: str = Depends(verify_api_key)):
    try:
        RequestLogger.log_request("/filters", api_key)
        return list_filters()
    except Exception as e:
        RequestLogger.log_error("/filters", str(e), "ERROR")
        logging.error(f"Error in /filters endpoint: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")        

# =========================
# ENDPOINT API LIST
# =========================
@app.get("/list")
def get_list(
    contrato_regional: Annotated[Optional[List[str]], Query(..., alias="contrato_regional")] = None,
    contrato_nome_prestador: Annotated[Optional[List[str]], Query(..., alias="contrato_nome_prestador")] = None,
    contrato_nome_operadora: Annotated[Optional[List[str]], Query(..., alias="contrato_nome_operadora")] = None,
    api_key: str = Depends(verify_api_key)
):
    try:
        # Validate and sanitize filter inputs
        contrato_regional = validate_filter_list(contrato_regional)
        contrato_nome_prestador = validate_filter_list(contrato_nome_prestador)
        contrato_nome_operadora = validate_filter_list(contrato_nome_operadora)
        
        RequestLogger.log_request("/list", api_key, {
            "contrato_regional": len(contrato_regional) if contrato_regional else 0,
            "contrato_nome_prestador": len(contrato_nome_prestador) if contrato_nome_prestador else 0,
            "contrato_nome_operadora": len(contrato_nome_operadora) if contrato_nome_operadora else 0,
        })
        
        return list_protocol(contrato_regional, contrato_nome_prestador, contrato_nome_operadora)
    except ValueError as e:
        RequestLogger.log_error("/list", str(e), "WARNING")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        RequestLogger.log_error("/list", str(e), "ERROR")
        logging.error(f"Error in /list endpoint: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")        

# =========================
# ENDPOINT API insert controle protocolo
# =========================
@app.post("/insert-controle-protocolo")
def post_insert_controle_protocolo(
    data: ControleProtocoloInsert, 
    api_key: str = Depends(verify_api_key)
):
    try:
        # Validate protocolo field
        protocolo = validate_protocolo(data.NUM_PROTOCOLO)
        usuario = sanitize_string(data.NME_USUARIO, max_length=100)
        
        RequestLogger.log_request("/insert-controle-protocolo", api_key, {
            "protocolo": protocolo
        })
        
        result = insert_controle_protocolo({
            "NUM_PROTOCOLO": protocolo,
            "NME_USUARIO": usuario
        })
        if result:
            return {
                "success": result,
                "message": "Protocolo inserted successfully"
            }
        else:
            # Fetch existing data
            existing = fetch_controle_protocolo(protocolo)
            response = {
                "success": result,
                "message": "Failed to insert protocolo"
            }
            if existing:
                response.update(existing)
            return response
    except ValueError as e:
        RequestLogger.log_error("/insert-controle-protocolo", str(e), "WARNING")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        RequestLogger.log_error("/insert-controle-protocolo", str(e), "ERROR")
        logging.error(f"Error in /insert-controle-protocolo endpoint: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@app.post("/delete-controle-protocolo")
def post_delete_controle_protocolo(
    data: ControleProtocoloDelete, 
    api_key: str = Depends(verify_api_key)
):
    try:
        # Validate protocolo field
        protocolo = validate_protocolo(data.NUM_PROTOCOLO)
        
        RequestLogger.log_request("/delete-controle-protocolo", api_key, {
            "protocolo": protocolo
        })
        
        result = delete_controle_protocolo({
            "NUM_PROTOCOLO": protocolo
        })
        return {
            "success": result,
            "message": "Protocolo deleted successfully" if result else "Failed to delete protocolo"
        }
    except ValueError as e:
        RequestLogger.log_error("/delete-controle-protocolo", str(e), "WARNING")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        RequestLogger.log_error("/delete-controle-protocolo", str(e), "ERROR")
        logging.error(f"Error in /delete-controle-protocolo endpoint: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
