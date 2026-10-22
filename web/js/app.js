// Navegação entre as 4 telas pelo endereço (#painel, #alvos, #mudancas?alvo=x, #execucoes).
import * as painel from "./painel.js";
import * as alvos from "./alvos.js";
import * as mudancas from "./mudancas.js";
import * as execucoes from "./execucoes.js";

const TELAS = { painel, alvos, mudancas, execucoes };
const TITULOS = { painel: "Painel", alvos: "Alvos", mudancas: "Mudanças", execucoes: "Execuções" };
let atual = null;

async function navegar() {
  const [nome, busca = ""] = location.hash.slice(1).split("?");
  const tela = TELAS[nome] ? nome : "painel";
  atual?.desmontar?.();
  atual = TELAS[tela];
  document.querySelectorAll(".menu a").forEach((a) => a.classList.toggle("ativo", a.dataset.tela === tela));
  document.title = `${TITULOS[tela]} · Monitor de Normas`;
  const el = document.getElementById("tela");
  el.innerHTML = '<p class="discreto">Carregando…</p>';
  try {
    await atual.montar(el, new URLSearchParams(busca));
  } catch (erro) {
    el.innerHTML = "";
    const p = document.createElement("p");
    p.className = "erro-form";
    p.textContent = `Não foi possível carregar a tela: ${erro.message}`;
    el.append(p);
  }
}

window.addEventListener("hashchange", navegar);
navegar();
