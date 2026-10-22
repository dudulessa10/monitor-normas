import { api } from "./api.js";
import { avisar, dataHora, esc, seloStatus } from "./util.js";

// Campos aceitos pela API (AlvoEntrada). Os demais da definição (ex.: de uma importação antiga) são descartados ao salvar.
const PERMITIDOS = ["id", "ativo", "site", "categoria", "prioridade", "url", "anos", "deteccao", "extracao", "observacoes",
  "timeout_segundos", "tentativas", "pausa_entre_requisicoes_segundos", "user_agent", "registrar_no_ledger"];

let raiz = null;
let alvos = [];
let regex = [];

export async function montar(el) {
  raiz = el;
  el.innerHTML = `
    <div class="cabecalho-tela">
      <div><h1>Alvos</h1><p class="sub">Páginas vigiadas pelo robô. Alvos inativos não rodam na execução diária.</p></div>
      <button class="primario" id="novo">Novo alvo</button>
    </div>
    <div class="tabela-envoltorio"><table>
      <thead><tr><th>Ativo</th><th>Alvo</th><th>Método</th><th class="num">Itens</th><th>Última execução</th><th></th></tr></thead>
      <tbody id="linhas"></tbody>
    </table></div>
    <dialog id="dialogo"></dialog>`;
  el.querySelector("#novo").addEventListener("click", () => abrirFormulario(null));
  el.querySelector("#linhas").addEventListener("click", acao);
  const config = await api("/configuracao");
  if (el !== raiz) return;
  regex = Object.keys(config.regex);
  await carregar();
}

export function desmontar() {
  raiz = null;
}

async function carregar() {
  const el = raiz;
  if (!el) return;
  const lista = await api("/alvos");
  if (el !== raiz) return; // o usuário mudou de tela durante a requisição
  alvos = lista;
  const tbody = el.querySelector("#linhas");
  if (!alvos.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="vazio">Nenhum alvo cadastrado. Use "Novo alvo" ou rode
      <code>python monitor.py importar-yaml</code>.</td></tr>`;
    return;
  }
  tbody.innerHTML = alvos.map((a) => {
    const u = a.ultima_execucao;
    return `<tr class="${u?.status === "erro" ? "com-erro" : ""}">
      <td><button class="interruptor" role="switch" aria-checked="${a.ativo}" aria-label="Ativar ${esc(a.id)}"
          data-acao="alternar" data-id="${esc(a.id)}"></button></td>
      <td><strong>${esc(a.categoria || a.id)}</strong>
        <div class="discreto">${esc(a.id)}${a.site ? ` · ${esc(a.site)}` : ""}</div>
        <div class="discreto mono">${esc(a.url)}</div>
        ${a.valido ? "" : `<div class="erro-texto">Definição inválida: ${esc(a.erro_config)}</div>`}</td>
      <td>${esc(a.metodo)}</td>
      <td class="num">${a.itens_vigentes}</td>
      <td>${u ? `${seloStatus(u.status)}<div class="discreto">${dataHora(u.fim || u.inicio)}</div>
          ${u.status === "ok" ? `<div class="discreto">+${u.novos} ~${u.alterados} −${u.removidos}</div>` : ""}
          ${u.erro ? `<div class="erro-texto">${esc(u.erro)}</div>` : ""}` : '<span class="discreto">nunca executado</span>'}</td>
      <td><div class="linha">
        <button class="pequeno" data-acao="editar" data-id="${esc(a.id)}">Editar</button>
        <button class="pequeno" data-acao="rodar" data-id="${esc(a.id)}" ${a.valido ? "" : "disabled"}>Rodar</button>
        <button class="pequeno perigo" data-acao="excluir" data-id="${esc(a.id)}">Excluir</button>
      </div></td></tr>`;
  }).join("");
}

async function acao(evento) {
  const botao = evento.target.closest("button[data-acao]");
  if (!botao) return;
  const { acao: tipo, id } = botao.dataset;
  const alvo = alvos.find((a) => a.id === id);
  try {
    if (tipo === "alternar") {
      botao.disabled = true;
      await api(`/alvos/${encodeURIComponent(id)}/${alvo.ativo ? "desativar" : "ativar"}`, { metodo: "POST" });
      avisar(`${alvo.categoria || id}: ${alvo.ativo ? "desativado" : "ativado"}.`);
    } else if (tipo === "editar") {
      return abrirFormulario(alvo);
    } else if (tipo === "rodar") {
      const r = await api("/execucoes", { metodo: "POST", corpo: { alvo: id } });
      avisar(`Execução #${r.rodada_id} iniciada para ${id}. Acompanhe em Execuções.`);
      return;
    } else if (tipo === "excluir") {
      if (!confirm(`Excluir o alvo "${id}"? O histórico e o ledger dele são mantidos.`)) return;
      await api(`/alvos/${encodeURIComponent(id)}`, { metodo: "DELETE" });
      avisar(`Alvo ${id} excluído.`);
    }
  } catch (erro) {
    avisar(erro.message, "erro");
  }
  await carregar();
}

// ---------------------------------------------------------------- formulário

const linhasParaMapa = (texto) => {
  const mapa = {};
  for (const linha of texto.split("\n")) {
    const i = linha.indexOf(":");
    if (i > 0) mapa[linha.slice(0, i).trim()] = linha.slice(i + 1).trim();
  }
  return mapa;
};
const mapaParaLinhas = (mapa) => Object.entries(mapa || {}).map(([k, v]) => `${k}: ${v}`).join("\n");
const lista = (texto) => texto.split(",").map((s) => s.trim()).filter(Boolean);

function abrirFormulario(alvo) {
  const d = alvo?.definicao || { ativo: false, anos: ["atual"], deteccao: {}, extracao: {} };
  const det = d.deteccao || {};
  const ext = d.extracao || {};
  const colunas = typeof ext.colunas === "object" && ext.colunas ? mapaParaLinhas(ext.colunas) : "";
  const opcao = (valor, atual, rotulo = valor) => `<option value="${esc(valor)}" ${valor === (atual ?? "") ? "selected" : ""}>${esc(rotulo)}</option>`;
  const dialogo = raiz.querySelector("#dialogo");
  dialogo.innerHTML = `
    <form method="dialog" id="form">
      <div class="dialogo-corpo">
        <h2>${alvo ? `Editar ${esc(alvo.id)}` : "Novo alvo"}</h2>
        <div id="form-erro"></div>
        <div class="form-grade">
          <label>Identificador <span class="ajuda">minúsculas, números e hífen; não muda depois</span>
            <input name="id" required pattern="[a-z0-9][a-z0-9_\\-]*" value="${esc(d.id)}" ${alvo ? "readonly" : ""}></label>
          <label>Categoria <span class="ajuda">nome exibido</span><input name="categoria" value="${esc(d.categoria)}"></label>
          <label>Site<input name="site" value="${esc(d.site)}"></label>
          <label>Prioridade<select name="prioridade">${opcao("", d.prioridade, "—")}${opcao("alta", d.prioridade)}${opcao("media", d.prioridade, "média")}${opcao("baixa", d.prioridade)}</select></label>
          <label class="largo">URL <span class="ajuda">pode conter {ano}</span>
            <input name="url" required value="${esc(d.url)}" placeholder="https://www.anac.gov.br/.../{ano}"></label>
          <label>Anos <span class="ajuda">se a URL tiver {ano}: atual, anterior ou números</span>
            <input name="anos" value="${esc((d.anos || ["atual"]).join(", "))}"></label>
          <label class="caixa"><input type="checkbox" name="ativo" ${d.ativo ? "checked" : ""}> Ativo (roda na execução diária)</label>
          <fieldset class="largo"><legend>Detecção</legend><div class="form-grade">
            <label>Método<select name="metodo">
              ${opcao("lista_itens", det.metodo || "lista_itens", "lista de itens (tabela)")}
              ${opcao("hash_conteudo", det.metodo, "hash do conteúdo")}
              ${opcao("data_modificacao", det.metodo, "data de modificação")}</select></label>
            <label>Campo-chave<input name="chave_item" value="${esc(det.chave_item || "norma")}"></label>
            <label class="largo">Campos que indicam alteração <span class="ajuda">separados por vírgula; vazio = todos</span>
              <input name="detectar_mudanca_em" value="${esc((det.detectar_mudanca_em || []).join(", "))}"></label>
          </div></fieldset>
          <fieldset class="largo"><legend>Extração (tabela)</legend><div class="form-grade">
            <label>Tabelas<select name="tabela">${opcao("primeira", ext.tabela || "primeira", "só a primeira")}${opcao("todas", ext.tabela)}</select></label>
            <label>Regex do número<select name="regex_numero">${opcao("", ext.regex_numero, "— automático —")}${regex.map((r) => opcao(r, ext.regex_numero)).join("")}</select></label>
            <label class="largo">Colunas <span class="ajuda">uma por linha, "Cabeçalho: campo"; vazio = usar o cabeçalho da tabela</span>
              <textarea name="colunas" placeholder="Norma: norma&#10;Publicação: publicacao&#10;Ementa: ementa&#10;Arquivo: link_arquivo">${esc(colunas)}</textarea></label>
            <label class="largo">Marcar status <span class="ajuda">uma por linha, "status: nome da regex"</span>
              <textarea name="marcar_status" placeholder="revogada: revogada">${esc(mapaParaLinhas(ext.marcar_status))}</textarea></label>
          </div></fieldset>
          <label class="largo">Observações<textarea name="observacoes">${esc(d.observacoes)}</textarea></label>
        </div>
      </div>
      <div class="dialogo-rodape">
        <button type="button" value="cancelar" id="cancelar">Cancelar</button>
        <button type="submit" class="primario">${alvo ? "Salvar" : "Cadastrar"}</button>
      </div>
    </form>`;
  dialogo.querySelector("#cancelar").addEventListener("click", () => dialogo.close());
  dialogo.querySelector("#form").addEventListener("submit", (e) => salvar(e, alvo));
  dialogo.showModal();
}

async function salvar(evento, alvo) {
  evento.preventDefault();
  const f = new FormData(evento.target);
  const base = Object.fromEntries(Object.entries(alvo?.definicao || {}).filter(([k]) => PERMITIDOS.includes(k)));
  const colunas = linhasParaMapa(f.get("colunas"));
  const corpo = {
    ...base,
    id: f.get("id").trim(),
    ativo: f.get("ativo") === "on",
    categoria: f.get("categoria").trim(),
    site: f.get("site").trim(),
    url: f.get("url").trim(),
    anos: lista(f.get("anos")).map((a) => (/^\d+$/.test(a) ? Number(a) : a)),
    observacoes: f.get("observacoes").trim(),
    deteccao: {
      metodo: f.get("metodo"),
      chave_item: f.get("chave_item").trim() || "norma",
      ...(lista(f.get("detectar_mudanca_em")).length ? { detectar_mudanca_em: lista(f.get("detectar_mudanca_em")) } : {}),
    },
    extracao: {
      tabela: f.get("tabela"),
      colunas: Object.keys(colunas).length ? colunas : "auto",
      ...(f.get("regex_numero") ? { regex_numero: f.get("regex_numero") } : {}),
      marcar_status: linhasParaMapa(f.get("marcar_status")),
    },
  };
  if (f.get("prioridade")) corpo.prioridade = f.get("prioridade");
  else delete corpo.prioridade;
  if (!corpo.anos.length) corpo.anos = ["atual"];
  const dialogo = raiz.querySelector("#dialogo");
  try {
    if (alvo) await api(`/alvos/${encodeURIComponent(alvo.id)}`, { metodo: "PUT", corpo });
    else await api("/alvos", { metodo: "POST", corpo });
    dialogo.close();
    avisar(alvo ? "Alvo salvo." : "Alvo cadastrado.");
    await carregar();
  } catch (erro) {
    const caixa = dialogo.querySelector("#form-erro");
    caixa.innerHTML = `<div class="erro-form">${esc(erro.message)}</div>`;
    dialogo.querySelector(".dialogo-corpo").scrollTop = 0;
  }
}
