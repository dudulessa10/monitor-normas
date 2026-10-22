import { api, query } from "./api.js";
import { ORIGENS, avisar, data, dataHora, duracao, esc, hojeMenos, link, seloStatus, seloTipo } from "./util.js";

let timer = null;
let raiz = null;

export async function montar(el) {
  raiz = el;
  el.innerHTML = `
    <div class="cabecalho-tela">
      <div><h1>Painel</h1><p class="sub">Situação do monitoramento e mudanças dos últimos 7 dias.</p></div>
    </div>
    <div class="grade">
      <section class="cartao" id="c-execucao"><h2 class="cartao-titulo">Última execução</h2><div>…</div></section>
      <section class="cartao" id="c-rodar">
        <h2 class="cartao-titulo">Rodar agora</h2>
        <label>Alvo<select id="rodar-alvo"><option value="">Todos os alvos ativos</option></select></label>
        <div class="linha" style="margin-top:.75rem">
          <button class="primario" id="rodar">Rodar agora</button>
          <span class="discreto" id="rodar-info"></span>
        </div>
      </section>
      <section class="cartao" id="c-ledger"><h2 class="cartao-titulo">Integridade do ledger</h2><div>…</div></section>
      <section class="cartao" id="c-alvos"><h2 class="cartao-titulo">Alvos</h2><div>…</div></section>
    </div>
    <section class="cartao">
      <div class="linha entre"><h2>Mudanças recentes</h2><a href="#mudancas?registrado_de=${hojeMenos(7)}">ver todas</a></div>
      <div id="recentes">…</div>
    </section>`;
  el.querySelector("#rodar").addEventListener("click", rodar);
  await Promise.all([carregarExecucao(), carregarLedger(), carregarAlvos(), carregarRecentes()]);
}

export function desmontar() {
  clearTimeout(timer);
  timer = null;
  raiz = null;
}

async function carregarExecucao() {
  const el = raiz;
  if (!el) return;
  const pagina = await api(`/execucoes${query({ limite: 1 })}`);
  if (el !== raiz) return; // o usuário mudou de tela durante a requisição
  const r = pagina.itens[0];
  const caixa = el.querySelector("#c-execucao div");
  const emAndamento = r?.status === "em_andamento";
  el.querySelector("#rodar").disabled = emAndamento;
  el.querySelector("#rodar-info").textContent = emAndamento ? "aguarde a execução atual" : "";
  if (!r) {
    caixa.innerHTML = '<p class="discreto">Nenhuma execução ainda.</p>';
  } else {
    caixa.innerHTML = `
      <div class="linha">${seloStatus(r.status)} <span class="discreto">${esc(ORIGENS[r.origem] || r.origem)}</span></div>
      <p style="margin:.5rem 0 .25rem">${dataHora(r.inicio)} · ${emAndamento ? "rodando…" : duracao(r.inicio, r.fim)}</p>
      <p class="discreto" style="margin:0">${r.total} ${r.total === 1 ? "item" : "itens"} · ${r.novos} novos · ${r.alterados} alterados · ${r.removidos} removidos
        ${r.erros ? `· <span class="erro-texto">${r.erros} alvo(s) com erro</span>` : ""}</p>
      ${r.erro ? `<p class="erro-texto">${esc(r.erro)}</p>` : ""}
      <p style="margin:.5rem 0 0"><a href="#execucoes">histórico</a></p>`;
  }
  clearTimeout(timer);
  if (emAndamento) {
    timer = setTimeout(async () => {
      await carregarExecucao();
      const ainda = raiz?.querySelector("#rodar")?.disabled;
      if (!ainda && raiz) {
        avisar("Execução concluída.");
        carregarRecentes();
        carregarLedger();
        carregarAlvos();
      }
    }, 3000);
  }
}

async function rodar() {
  const alvo = raiz.querySelector("#rodar-alvo").value || null;
  raiz.querySelector("#rodar").disabled = true;
  raiz.querySelector("#rodar-info").textContent = "iniciando…";
  try {
    const resposta = await api("/execucoes", { metodo: "POST", corpo: { alvo } });
    avisar(`Execução #${resposta.rodada_id} iniciada.`);
  } catch (erro) {
    avisar(erro.message, "erro");
  }
  await carregarExecucao();
}

async function carregarLedger() {
  const el = raiz;
  if (!el) return;
  const v = await api("/ledger/verificar");
  if (el !== raiz) return;
  const caixa = el.querySelector("#c-ledger div");
  caixa.innerHTML = `
    <div class="linha">${v.ok ? '<span class="selo ok">íntegro</span>' : '<span class="selo erro">com problemas</span>'}
      <span class="discreto">${v.blocos} blocos · ${v.ancoras_conferidas} âncora(s)</span></div>
    ${v.erros.map((e) => `<p class="erro-texto">${esc(e)}</p>`).join("")}
    ${v.avisos.map((a) => `<p class="discreto">${esc(a)}</p>`).join("")}
    ${v.ancora_atual ? `<p class="discreto" style="margin:.5rem 0 .2rem">Âncora atual (guarde fora deste computador):</p>
      <div class="linha"><span class="mono">${esc(v.ancora_atual)}</span>
      <button class="pequeno" id="copiar">Copiar</button></div>` : ""}`;
  caixa.querySelector("#copiar")?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(v.ancora_atual);
      avisar("Âncora copiada.");
    } catch {
      avisar("Não foi possível copiar; selecione o texto.", "erro");
    }
  });
}

async function carregarAlvos() {
  const el = raiz;
  if (!el) return;
  const lista = await api("/alvos");
  if (el !== raiz) return;
  const select = el.querySelector("#rodar-alvo");
  const escolhido = select.value;
  select.innerHTML = '<option value="">Todos os alvos ativos</option>' + lista
    .filter((a) => a.valido)
    .map((a) => `<option value="${esc(a.id)}">${esc(a.categoria || a.id)}${a.ativo ? "" : " (inativo)"}</option>`)
    .join("");
  select.value = escolhido;
  const ativos = lista.filter((a) => a.ativo).length;
  const comErro = lista.filter((a) => a.ativo && a.ultima_execucao?.status === "erro").length;
  el.querySelector("#c-alvos div").innerHTML = `
    <div class="numero">${ativos} <span class="discreto">de ${lista.length} ativos</span></div>
    <p class="${comErro ? "erro-texto" : "discreto"}" style="margin:.25rem 0">${comErro ? `${comErro} com erro na última execução` : "nenhum com erro"}</p>
    <a href="#alvos">gerenciar</a>`;
}

async function carregarRecentes() {
  const el = raiz;
  if (!el) return;
  const pagina = await api(`/mudancas${query({ registrado_de: hojeMenos(7), limite: 10 })}`);
  if (el !== raiz) return;
  const caixa = el.querySelector("#recentes");
  if (!pagina.itens.length) {
    caixa.innerHTML = '<p class="discreto">Nenhuma norma nova, alterada ou removida nos últimos 7 dias.</p>';
    return;
  }
  caixa.innerHTML = `<ul class="lista">${pagina.itens.map((b) => `
    <li>
      <div class="linha">${seloTipo(b.tipo_mudanca)} <strong>${link(b.link, b.norma)}</strong></div>
      ${b.ementa ? `<div>${esc(b.ementa)}</div>` : ""}
      <div class="discreto">${esc(b.alvo)} · publicada em ${data(b.data_publicacao)} · detectada em ${dataHora(b.timestamp)}</div>
    </li>`).join("")}</ul>
    ${pagina.total > pagina.itens.length ? `<p class="discreto">e mais ${pagina.total - pagina.itens.length}…</p>` : ""}`;
}
