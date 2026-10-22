import { BASE, api, query } from "./api.js";
import { data, dataHora, esc, link, paginacao, seloTipo } from "./util.js";

const CAMPOS = ["palavra", "alvo", "tipo", "de", "ate", "registrado_de", "registrado_ate", "incluir_linha_base"];
let raiz = null;
let filtros = {};

export async function montar(el, parametros) {
  raiz = el;
  filtros = Object.fromEntries(CAMPOS.map((c) => [c, parametros.get(c) || ""]));
  const alvos = await api("/alvos");
  if (el !== raiz) return; // o usuário mudou de tela durante a requisição
  const opcao = (valor, rotulo) => `<option value="${esc(valor)}" ${filtros.tipo === valor || filtros.alvo === valor ? "selected" : ""}>${esc(rotulo)}</option>`;
  el.innerHTML = `
    <div class="cabecalho-tela">
      <div><h1>Mudanças</h1><p class="sub">Normas novas, alteradas e removidas registradas no ledger.</p></div>
      <a class="botao" id="excel" href="#">Baixar Excel</a>
    </div>
    <form class="cartao filtros" id="filtros" style="margin-bottom:1rem">
      <label>Palavra-chave<input name="palavra" value="${esc(filtros.palavra)}" placeholder="ex.: aeródromo"></label>
      <label>Alvo<select name="alvo"><option value="">Todos</option>${alvos.map((a) => opcao(a.id, a.categoria || a.id)).join("")}</select></label>
      <label>Tipo<select name="tipo"><option value="">Novas, alteradas e removidas</option>
        ${opcao("NOVO", "Novas")}${opcao("ALTERADO", "Alteradas")}${opcao("REMOVIDO", "Removidas")}${opcao("LINHA_BASE", "Linha de base")}</select></label>
      <label>Publicadas de<input type="date" name="de" value="${esc(filtros.de)}"></label>
      <label>até<input type="date" name="ate" value="${esc(filtros.ate)}"></label>
      <label>Detectadas de<input type="date" name="registrado_de" value="${esc(filtros.registrado_de)}"></label>
      <label>até<input type="date" name="registrado_ate" value="${esc(filtros.registrado_ate)}"></label>
      <label class="caixa"><input type="checkbox" name="incluir_linha_base" ${filtros.incluir_linha_base ? "checked" : ""}>
        Incluir linha de base</label>
      <div class="linha"><button class="primario" type="submit">Filtrar</button><button type="button" id="limpar">Limpar</button></div>
    </form>
    <div id="resultado"></div>`;
  const form = el.querySelector("#filtros");
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const f = new FormData(form);
    filtros = Object.fromEntries(CAMPOS.map((c) => [c, c === "incluir_linha_base" ? (f.get(c) ? "true" : "") : f.get(c) || ""]));
    history.replaceState(null, "", `#mudancas${query(filtros)}`);
    carregar(0);
  });
  el.querySelector("#limpar").addEventListener("click", () => {
    history.replaceState(null, "", "#mudancas");
    montar(el, new URLSearchParams());
  });
  await carregar(0);
}

export function desmontar() {
  raiz = null;
}

async function carregar(deslocamento) {
  const el = raiz;
  if (!el) return;
  el.querySelector("#excel").href = `${BASE}/exportar/excel${query(filtros)}`;
  const pagina = await api(`/mudancas${query({ ...filtros, limite: 50, deslocamento })}`);
  if (el !== raiz) return;
  const caixa = el.querySelector("#resultado");
  if (!pagina.itens.length) {
    caixa.innerHTML = '<div class="cartao vazio">Nenhuma mudança encontrada com esses filtros.</div>';
    return;
  }
  caixa.innerHTML = `<div class="tabela-envoltorio"><table>
    <thead><tr><th>Detectada</th><th>Tipo</th><th>Norma</th><th>Ementa</th><th>Publicação</th><th>Alvo</th></tr></thead>
    <tbody>${pagina.itens.map((b) => `<tr>
      <td>${dataHora(b.timestamp)}</td>
      <td>${seloTipo(b.tipo_mudanca)}</td>
      <td><strong>${link(b.link, b.norma)}</strong></td>
      <td class="ementa">${esc(b.ementa)}
        ${b.palavras_chave.length ? `<div style="margin-top:.3rem">${b.palavras_chave.map((p) => `<span class="chip">${esc(p)}</span>`).join("")}</div>` : ""}</td>
      <td>${data(b.data_publicacao)}</td>
      <td class="discreto">${esc(b.alvo)}</td></tr>`).join("")}</tbody></table></div>`;
  caixa.append(paginacao(pagina, carregar));
}
