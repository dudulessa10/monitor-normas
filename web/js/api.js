// Único ponto de acesso à API. Outra aplicação usaria exatamente estes endpoints.
export const BASE = "/api/v1";

export class ErroApi extends Error {
  constructor(status, mensagem) {
    super(mensagem);
    this.status = status;
  }
}

function mensagemDeErro(dados, status) {
  const detalhe = dados && dados.detail;
  if (typeof detalhe === "string") return detalhe;
  if (Array.isArray(detalhe)) {
    // Erros de validação do FastAPI: [{loc: ["body", "url"], msg: "..."}]
    return detalhe
      .map((e) => `${(e.loc || []).filter((p) => p !== "body").join(".")}: ${String(e.msg).replace(/^Value error, /, "")}`)
      .join("; ");
  }
  return `erro HTTP ${status}`;
}

export async function api(caminho, { metodo = "GET", corpo } = {}) {
  const opcoes = { method: metodo, headers: {} };
  if (corpo !== undefined) {
    opcoes.headers["Content-Type"] = "application/json";
    opcoes.body = JSON.stringify(corpo);
  }
  let resposta;
  try {
    resposta = await fetch(BASE + caminho, opcoes);
  } catch {
    throw new ErroApi(0, "não foi possível falar com o servidor");
  }
  if (resposta.status === 204) return null;
  const dados = await resposta.json().catch(() => null);
  if (!resposta.ok) throw new ErroApi(resposta.status, mensagemDeErro(dados, resposta.status));
  return dados;
}

// {a: 1, b: "", c: null} -> "?a=1"
export function query(parametros) {
  const busca = new URLSearchParams();
  for (const [chave, valor] of Object.entries(parametros)) {
    if (valor === undefined || valor === null || valor === "" || valor === false) continue;
    busca.append(chave, valor);
  }
  const texto = busca.toString();
  return texto ? `?${texto}` : "";
}
