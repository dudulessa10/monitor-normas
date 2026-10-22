// Tudo que vem dos sites monitorados (ementas, nomes, links) é texto externo: sempre escapar.
const ENTIDADES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (valor) => String(valor ?? "").replace(/[&<>"']/g, (c) => ENTIDADES[c]);

export const urlSegura = (url) => (/^https?:\/\//i.test(url || "") ? url : null);

export function link(url, texto) {
  const seguro = urlSegura(url);
  return seguro
    ? `<a href="${esc(seguro)}" target="_blank" rel="noopener noreferrer">${esc(texto)}</a>`
    : esc(texto);
}

export function dataHora(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? esc(iso) : d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export function data(isoData) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoData || "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "—";
}

export function duracao(inicio, fim) {
  if (!inicio || !fim) return "—";
  const s = Math.max(0, Math.round((new Date(fim) - new Date(inicio)) / 1000));
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
}

export const hojeMenos = (dias) => {
  const d = new Date();
  d.setDate(d.getDate() - dias);
  return d.toISOString().slice(0, 10);
};

const STATUS = {
  em_andamento: ["info", "em andamento"],
  ok: ["ok", "ok"],
  linha_base: ["info", "linha de base"],
  com_erros: ["alerta", "com erros"],
  erro: ["erro", "erro"],
  falhou: ["erro", "falhou"],
  interrompida: ["alerta", "interrompida"],
};
export function seloStatus(status) {
  const [classe, rotulo] = STATUS[status] || ["", status];
  const giro = status === "em_andamento" ? '<span class="giro" aria-hidden="true"></span>' : "";
  return `<span class="selo ${classe}">${giro}${esc(rotulo)}</span>`;
}

const TIPOS = { NOVO: ["ok", "novo"], ALTERADO: ["alerta", "alterado"], REMOVIDO: ["erro", "removido"], LINHA_BASE: ["", "linha de base"] };
export function seloTipo(tipo) {
  const [classe, rotulo] = TIPOS[tipo] || ["", tipo];
  return `<span class="selo ${classe}">${esc(rotulo)}</span>`;
}

export const ORIGENS = { cli: "linha de comando", agendamento: "agendada", web: "web", historico: "histórico" };

export function avisar(mensagem, tipo = "") {
  const caixa = document.createElement("div");
  caixa.className = `aviso ${tipo}`;
  caixa.textContent = mensagem;
  document.getElementById("avisos").append(caixa);
  setTimeout(() => caixa.remove(), tipo === "erro" ? 8000 : 4500);
}

export function paginacao(pagina, aoMudar) {
  const { total, limite, deslocamento } = pagina;
  const fim = Math.min(total, deslocamento + limite);
  const div = document.createElement("div");
  div.className = "paginacao";
  div.innerHTML = `<span class="discreto">${total ? `${deslocamento + 1}–${fim} de ${total}` : "nenhum resultado"}</span>
    <button class="pequeno" data-ir="-1" ${deslocamento === 0 ? "disabled" : ""}>Anterior</button>
    <button class="pequeno" data-ir="1" ${fim >= total ? "disabled" : ""}>Próxima</button>`;
  div.addEventListener("click", (e) => {
    const ir = e.target.closest("button")?.dataset.ir;
    if (ir) aoMudar(Math.max(0, deslocamento + Number(ir) * limite));
  });
  return div;
}
