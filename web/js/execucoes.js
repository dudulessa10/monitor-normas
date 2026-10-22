import { api, query } from "./api.js";
import { ORIGENS, dataHora, duracao, esc, paginacao, seloStatus } from "./util.js";

let raiz = null;
let timer = null;
let deslocamentoAtual = 0;
const abertas = new Set();

export async function montar(el) {
  raiz = el;
  el.innerHTML = `
    <div class="cabecalho-tela">
      <div><h1>Execuções</h1><p class="sub">Histórico de todas as rodadas: web, linha de comando e agendadas.</p></div>
    </div>
    <div id="resultado"></div>`;
  el.querySelector("#resultado").addEventListener("click", (e) => {
    const id = e.target.closest("button[data-detalhe]")?.dataset.detalhe;
    if (!id) return;
    abertas.has(id) ? abertas.delete(id) : abertas.add(id);
    carregar(deslocamentoAtual);
  });
  await carregar(0);
}

export function desmontar() {
  clearTimeout(timer);
  raiz = null;
}

function linhaRodada(r) {
  const comErro = r.erros > 0 || ["falhou", "interrompida"].includes(r.status);
  const aberta = abertas.has(String(r.id));
  const errosAlvos = r.execucoes.filter((e) => e.erro);
  return `<tr class="${comErro ? "com-erro" : ""}">
      <td class="num">#${r.id}</td>
      <td>${dataHora(r.inicio)}<div class="discreto">${r.status === "em_andamento" ? "rodando…" : duracao(r.inicio, r.fim)}</div></td>
      <td>${esc(ORIGENS[r.origem] || r.origem)}</td>
      <td>${r.alvo ? esc(r.alvo) : '<span class="discreto">todos os ativos</span>'}</td>
      <td>${seloStatus(r.status)}</td>
      <td class="num">${r.total}</td>
      <td class="num">${r.novos} / ${r.alterados} / ${r.removidos}</td>
      <td>${r.execucoes.length ? `<button class="pequeno" data-detalhe="${r.id}" aria-expanded="${aberta}">
          ${aberta ? "Ocultar" : `${r.execucoes.length} alvo(s)`}</button>` : ""}</td>
    </tr>
    ${r.erro || errosAlvos.length ? `<tr class="com-erro"><td></td><td colspan="7">
      ${r.erro ? `<div class="erro-texto">${esc(r.erro)}</div>` : ""}
      ${errosAlvos.map((e) => `<div class="erro-texto"><strong>${esc(e.alvo)}:</strong> ${esc(e.erro)}</div>`).join("")}
    </td></tr>` : ""}
    ${aberta ? `<tr class="detalhe"><td></td><td colspan="7"><table>
      <thead><tr><th>Alvo</th><th>Status</th><th class="num">Itens</th><th class="num">Novos</th><th class="num">Alterados</th>
        <th class="num">Removidos</th><th>Duração</th><th>Página modificada em</th></tr></thead>
      <tbody>${r.execucoes.map((e) => `<tr>
        <td>${esc(e.alvo)}${e.erro ? `<div class="erro-texto">${esc(e.erro)}</div>` : ""}</td>
        <td>${seloStatus(e.status)}</td><td class="num">${e.total}</td><td class="num">${e.novos}</td>
        <td class="num">${e.alterados}</td><td class="num">${e.removidos}</td>
        <td>${duracao(e.inicio, e.fim)}</td><td>${esc(e.modificacao_pagina || "—")}</td></tr>`).join("")}</tbody>
    </table></td></tr>` : ""}`;
}

async function carregar(deslocamento) {
  const el = raiz;
  if (!el) return;
  deslocamentoAtual = deslocamento;
  const pagina = await api(`/execucoes${query({ limite: 25, deslocamento })}`);
  if (el !== raiz) return; // o usuário mudou de tela durante a requisição
  const caixa = el.querySelector("#resultado");
  if (!pagina.itens.length) {
    caixa.innerHTML = '<div class="cartao vazio">Nenhuma execução ainda.</div>';
    return;
  }
  caixa.innerHTML = `<div class="tabela-envoltorio"><table>
    <thead><tr><th class="num">Rodada</th><th>Início</th><th>Origem</th><th>Alvo</th><th>Status</th>
      <th class="num">Itens</th><th class="num">Novos / alt. / rem.</th><th></th></tr></thead>
    <tbody>${pagina.itens.map(linhaRodada).join("")}</tbody></table></div>`;
  caixa.append(paginacao(pagina, carregar));
  clearTimeout(timer);
  if (pagina.itens.some((r) => r.status === "em_andamento")) timer = setTimeout(() => carregar(deslocamentoAtual), 3000);
}
