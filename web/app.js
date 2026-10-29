"use strict";

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const semAcento = (t) => String(t ?? "").toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "");
const dataBR = (iso) => (iso ? new Date(iso).toLocaleDateString("pt-BR") : "—");
const dataHoraBR = (iso) => (iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—");

const ORGAO = "/ Vara Estadual do Meio Ambiente (VEMA) / Juiz de Direito (Titular)";
// Siglas de classe no estilo da lista de tarefas do PJe
const SIGLAS = {
  "Ação Civil Pública": "ACP",
  "Inquérito Policial": "InqPol",
  "Ação Penal - Procedimento Ordinário": "APOrd",
  "Procedimento Comum Cível": "ProceComCiv",
  "Cumprimento de Sentença": "CumSen",
  "Termo Circunstanciado": "TCO",
  "Representação Criminal/Notícia de Crime": "RepCrim",
  "Auto de Prisão em Flagrante": "APFD",
  "Pedido de Relaxamento de Prisão": "RelPris",
};
const sigla = (classe) => SIGLAS[classe] || classe;

let modo = "equilibrado";
let servidores = [];
let fila = [];
let selecionado = null;

async function api(caminho, opcoes = {}) {
  const r = await fetch(caminho, { headers: { "Content-Type": "application/json" }, ...opcoes });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}

function toast(msg, erro = false) {
  const t = $("#toast");
  t.innerHTML = msg;
  t.className = "toast" + (erro ? " erro" : "");
  t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.hidden = true), 6000);
}

// ---------- prioridade: pílula com ícone + rótulo, nunca só cor ----------
const ICONES = { 1: "▲", 2: "◆", 3: "●" };
const CURTO = { tutela_urgencia: "Tutela/liminar", reu_preso: "Réu preso", idoso: "Idoso" };
const ICONE_BALANCA = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11 3h2v2.1l5.5 1.4-.5 1.9-1.3-.3L19.5 14a3.5 3.5 0 0 1-7 0l2.6-6.4L13 7.1V19h4v2H7v-2h4V7.1l-2.1.5L11.5 14a3.5 3.5 0 0 1-7 0l2.8-6-1.3.3-.5-1.9L11 5.1zM8 9.6 6.4 13.5h3.2zm8 0-1.6 3.9h3.2z"/></svg>';
const nivelDe = (p) => Math.min(...(p.alertas || []).map((a) => a.nivel), 9);

function pilula(a) {
  const div = a.fonte === "divergência";
  return `<span class="pilula n${a.nivel}${div ? " div" : ""}" title="${esc(a.rotulo)}">${div ? "?" : ICONES[a.nivel]} ${esc(CURTO[a.tipo])}${div ? " (conferir)" : ""}</span>`;
}

// ---------- painéis superiores ----------
function renderResumo(e) {
  const t = e.ultima_triagem;
  const pend = e.propostas > 0;
  const linhas = [
    ["Novos na fila do PJe", pend ? e.propostas : 0, false],
    ["Com alerta de prioridade", pend ? e.urgentes : 0, pend && e.urgentes > 0],
    ["Duplicados bloqueados", pend && t ? t.duplicados.length : 0, false],
    ["Com processos vinculados", pend ? e.com_vinculo : 0, false],
    ["Acervo distribuído (planilha)", e.acervo_total, false],
  ];
  $("#kpis").innerHTML = linhas.map(([r, n, alerta]) =>
    `<li class="${alerta ? "alerta" : ""}"><span class="marcador"></span>${r}<span class="n">${n}</span></li>`).join("");
  $("#marco-info").textContent = `Desde a última triagem aprovada: ${dataHoraBR(e.marco)}`;
  $("#btn-aprovar").disabled = !pend;
}

function renderCarga(e) {
  const max = Math.max(...e.servidores.map((s) => s.acervo + s.propostos), 1);
  $("#grafico-carga").innerHTML = e.servidores.map((s) => `
    <div class="linha-carga">
      <span class="nome">${esc(s.nome)}<small>${s.peso < 1 ? "3 dias/sem" : "5 dias/sem"}</small></span>
      <div class="trilho">
        <div class="seg-barra s1${s.propostos ? "" : " so"}" style="width:${(s.acervo / max) * 100}%" data-tip="${esc(s.nome)}: ${s.acervo} no acervo"></div>
        ${s.propostos ? `<div class="seg-barra s2" style="width:${(s.propostos / max) * 100}%" data-tip="${esc(s.nome)}: +${s.propostos} na proposta de hoje"></div>` : ""}
      </div>
      <span class="total">${s.acervo + s.propostos}</span>
    </div>`).join("");
  $("#tabela-carga").innerHTML = "<tr><th>Servidor</th><th>Peso</th><th>Acervo</th><th>Hoje</th><th>Total</th></tr>" +
    e.servidores.map((s) => `<tr><td>${esc(s.nome)}</td><td>${s.peso}</td><td>${s.acervo}</td><td>${s.propostos}</td><td>${s.acervo + s.propostos}</td></tr>`).join("");
}

document.addEventListener("mousemove", (ev) => {
  const alvo = ev.target.closest("[data-tip]");
  const tip = $("#tooltip");
  if (!alvo) { tip.hidden = true; return; }
  tip.textContent = alvo.dataset.tip;
  tip.style.left = ev.clientX + 12 + "px";
  tip.style.top = ev.clientY + 12 + "px";
  tip.hidden = false;
});

// ---------- lista de processos (cards no padrão PJe) ----------
function card(p) {
  const n = nivelDe(p);
  const opcoes = servidores.map((s) => `<option ${s.nome === p.servidor ? "selected" : ""}>${esc(s.nome)}</option>`).join("");
  return `<div class="card${n < 9 ? " n" + n : ""}${p.numero === selecionado ? " selecionado" : ""}" data-numero="${esc(p.numero)}" tabindex="0">
    <div class="card-topo">
      <a href="#" class="num-link">${esc(sigla(p.classe))} ${esc(p.numero)}</a>
      <span class="pilulas">${(p.alertas || []).map(pilula).join("")}${p.vinculos ? `<span class="pilula cinza" title="Processos vinculados">🔗 ${p.vinculos}</span>` : ""}${p.semelhantes_decididos ? `<span class="pilula decidido" title="Casos semelhantes já decididos pela vara">${ICONE_BALANCA} ${p.semelhantes_decididos}</span>` : ""}</span>
    </div>
    <div class="assunto">${esc(p.assunto)}</div>
    <div class="orgao">${ORGAO}</div>
    <div class="partes">${p.partes.map(esc).join(" · ") || "—"}</div>
    <div class="mov"><b>Sentinela:</b> ${esc(p.motivo_distribuicao)}</div>
    <div class="card-rodape">
      <span class="etiqueta" title="Etiqueta do servidor responsável"><select data-reatribuir="${esc(p.numero)}" aria-label="Servidor responsável">${opcoes}</select></span>
      <span class="orgao">recebido ${dataHoraBR(p.data_entrada)}</span>
    </div>
  </div>`;
}

function renderFila() {
  const q = semAcento($("#busca-fila").value);
  const visiveis = fila.filter((p) => !q || semAcento([p.numero, p.classe, p.assunto, p.servidor, ...p.partes].join(" ")).includes(q));
  $("#contador-fila").textContent = fila.length;
  $("#lista-fila").innerHTML = visiveis.length
    ? visiveis.map(card).join("")
    : `<p class="vazio">${fila.length ? "Nenhum processo encontrado para a pesquisa." : "Nenhum processo aguardando distribuição.<br>Use <b>Buscar processos do dia</b> para ler a tarefa de redistribuição."}</p>`;
}

function renderDuplicados(e) {
  const t = e.ultima_triagem;
  const itens = t && e.propostas ? [...t.duplicados, ...t.invalidos.map((i) => ({ ...i, classe: "Número inválido" }))] : [];
  $("#qtd-dup").textContent = itens.length ? `(${itens.length})` : "";
  $("#lista-duplicados").innerHTML = itens.length
    ? itens.map((d) => `<div class="card" data-numero="${esc(d.numero)}" tabindex="0">
        <div class="card-topo"><a href="#" class="num-link">${esc(sigla(d.classe))} ${esc(d.numero)}</a>
          <span class="pilulas"><span class="pilula cinza">Bloqueado</span></span></div>
        <div class="mov"><b>Sentinela:</b> ${esc(d.motivo)}</div></div>`).join("")
    : '<p class="vazio">Nenhum duplicado nesta extração.</p>';
}

async function atualizarTriagem() {
  const [e, lista] = await Promise.all([api("/api/estado"), api("/api/propostas")]);
  servidores = e.servidores;
  fila = lista;
  renderResumo(e);
  renderCarga(e);
  renderFila();
  renderDuplicados(e);
  const sel = $("#filtro-servidor");
  if (sel.options.length === 1) sel.innerHTML += servidores.map((s) => `<option>${esc(s.nome)}</option>`).join("");
}

// ---------- detalhe (painel da direita) ----------
function decisaoHtml(d) {
  return d
    ? `<div class="decisao"><span class="dec-tipo">${esc(d.tipo)}</span><span class="orgao">em ${dataBR(d.data)}</span><div class="dec-resumo">${esc(d.resumo)}</div></div>`
    : '<div class="decisao pendente">Ainda sem decisão registrada</div>';
}

function relacionado(v) {
  return `<div class="relacionado">
    <div class="cab"><a href="#" data-abrir="${esc(v.numero)}">${esc(sigla(v.classe))} ${esc(v.numero)}</a><span>etiqueta: ${esc(v.servidor || "—")}</span></div>
    ${v.criterios.map((c) => `<span class="criterio">${esc(c.detalhe)}</span>`).join("")}
    ${decisaoHtml(v.decisao)}
  </div>`;
}

// Barras de distribuição das decisões: uma série só, a magnitude é o que importa.
function barrasDecisao(distribuicao, total, assunto) {
  return `<div class="barras-dec">${distribuicao.map((d) => `
    <div class="linha-dec${assunto ? " clicavel" : ""}" data-tip="${esc(d.tipo)}: ${d.n} de ${total} (${Math.round((d.n / total) * 100)}%)"
      ${assunto ? `data-filtrar-assunto="${esc(assunto)}" data-filtrar-decisao="${esc(d.tipo)}" tabindex="0" role="button"` : ""}>
      <span class="nome">${esc(d.tipo)}</span>
      <div class="trilho"><div class="seg-barra s1 so" style="width:${(d.n / total) * 100}%"></div></div>
      <span class="total">${d.n}</span>
    </div>`).join("")}</div>`;
}

function padraoHtml(pd) {
  if (!pd) return '<p class="nada">Nenhum caso parecido com decisão registrada ainda.</p>';
  return `<div class="padrao">
    <p class="padrao-frase">Em <b>${pd.vezes} de ${pd.decididos}</b> casos parecidos já decididos, a vara decidiu: <b>${esc(pd.predominante)}</b>.</p>
    ${barrasDecisao(pd.distribuicao, pd.decididos)}
    <p class="aviso">Histórico da própria vara, para reaproveitar entendimento e minutas. Quem decide é o juiz.</p>
  </div>`;
}

async function abrirDetalhe(numero) {
  const p = await api(`/api/processos/${encodeURIComponent(numero)}`);
  selecionado = p.numero;
  $$(".card").forEach((c) => c.classList.toggle("selecionado", c.dataset.numero === selecionado));
  const pdf = `/api/pdf/${encodeURIComponent(p.numero)}`;
  const alertas = (p.alertas || []).map((a) => `<div class="evidencia">
      ${pilula(a)}<span class="fonte">${esc(a.rotulo)} · fonte: ${esc(a.fonte)}${a.pagina ? ` · <a href="${pdf}#page=${a.pagina}" target="_blank">página ${a.pagina}</a>` : ""}</span>
      <blockquote>${esc(a.trecho)}</blockquote></div>`).join("") || '<p class="nada">Nenhum indício de urgência encontrado na petição.</p>';
  const vinc = p.vinculos || [], sem = p.semelhantes || [];
  $("#detalhe").innerHTML = `
    <div class="det-cab">
      <div class="numero">${esc(sigla(p.classe))} ${esc(p.numero)}</div>
      <div class="sub">${esc(p.classe)} · ${esc(p.assunto)} · ${esc(p.competencia)}</div>
    </div>
    <div class="det-bloco"><h3>Prioridade</h3>${alertas}</div>
    <div class="det-bloco destaque"><h3>Casos semelhantes e o que a vara decidiu <span class="qtd">(${vinc.length + sem.length})</span></h3>
      ${padraoHtml(p.padrao)}
      <h4>Mesma parte ou mesmo local <span class="qtd">(${vinc.length})</span></h4>
      ${vinc.map(relacionado).join("") || '<p class="nada">Nenhum processo com a mesma parte ou o mesmo local.</p>'}
      <h4>Assunto semelhante <span class="qtd">(${sem.length})</span></h4>
      ${sem.map(relacionado).join("") || '<p class="nada">Nenhum caso com assunto semelhante.</p>'}
    </div>
    <div class="det-bloco"><h3>Distribuição${p.status === "proposta" ? " proposta" : ""}</h3>
      <dl class="grade-info">
        <dt>Etiqueta</dt><dd><span class="etiqueta fixa">${esc(p.servidor || "—")}</span></dd>
        <dt>Motivo</dt><dd>${esc(p.motivo_distribuicao || "Distribuição anterior")}</dd>
        ${p.apenso_de ? `<dt>Apenso de</dt><dd><a href="#" data-abrir="${esc(p.apenso_de)}">${esc(p.apenso_de)}</a></dd>` : ""}
        <dt>Recebido em</dt><dd>${dataHoraBR(p.data_entrada)}</dd>
        ${p.status === "acervo" ? `<dt>Decisão</dt><dd>${p.decisao ? `${esc(p.decisao.tipo)} em ${dataBR(p.decisao.data)}` : "Ainda sem decisão registrada"}</dd>` : ""}
        <dt>Local</dt><dd>${(p.locais || []).map(esc).join(", ") || "—"}</dd>
      </dl></div>
    <div class="det-bloco"><h3>Partes</h3>
      ${p.partes.map((x) => `<div>${esc(x.nome)}${x.documento ? ` <span class="orgao">(${esc(x.documento)})</span>` : ""} <span class="orgao">· polo ${esc(x.polo)}</span></div>`).join("")}</div>
    <div class="det-bloco"><h3>Síntese dos fatos (extraída da petição)</h3><p class="sintese">${esc(p.sintese)}</p></div>
    <div class="det-acoes"><a class="btn" href="${pdf}" target="_blank">Abrir petição (PDF)</a></div>`;
  $("#detalhe").scrollTop = 0;
}

// ---------- acervo e auditoria ----------
let acervoCache = [];
const SEM_DECISAO = "Ainda sem decisão";

function preencherOpcoes(sel, valores, primeira) {
  const atual = sel.value;
  sel.innerHTML = `<option value="">${primeira}</option>` + valores.map((v) => `<option>${esc(v)}</option>`).join("");
  sel.value = valores.includes(atual) ? atual : "";
}

async function carregarAcervo(filtro = {}) {
  acervoCache = await api("/api/acervo");
  const unicos = (f) => [...new Set(acervoCache.map(f))].sort((a, b) => a.localeCompare(b, "pt-BR"));
  preencherOpcoes($("#filtro-assunto"), unicos((p) => p.assunto), "Todos os assuntos");
  preencherOpcoes($("#filtro-decisao"), [...unicos((p) => p.decisao?.tipo || SEM_DECISAO)], "Todas as decisões");
  if (filtro.assunto !== undefined) $("#filtro-assunto").value = filtro.assunto;
  if (filtro.decisao !== undefined) $("#filtro-decisao").value = filtro.decisao;
  filtrarAcervo();
}
function filtrarAcervo() {
  const q = semAcento($("#busca-acervo").value);
  const srv = $("#filtro-servidor").value;
  const assunto = $("#filtro-assunto").value;
  const decisao = $("#filtro-decisao").value;
  const linhas = acervoCache.filter((p) => (!srv || p.servidor === srv) && (!assunto || p.assunto === assunto) &&
    (!decisao || (p.decisao?.tipo || SEM_DECISAO) === decisao) &&
    (!q || semAcento([p.numero, p.classe, p.assunto, ...p.partes, ...(p.locais || [])].join(" ")).includes(q)));
  $("#tabela-acervo tbody").innerHTML = linhas.slice(0, 300).map((p) => `<tr data-numero="${esc(p.numero)}">
    <td class="num">${esc(sigla(p.classe))} ${esc(p.numero)}</td><td>${esc(p.classe)}</td><td>${p.partes.map(esc).join("<br>")}</td>
    <td>${(p.locais || []).map(esc).join(", ") || "—"}</td>
    <td>${p.decisao ? `<b>${esc(p.decisao.tipo)}</b><br><span class="orgao">${dataBR(p.decisao.data)}</span>` : '<span class="orgao">—</span>'}</td>
    <td><span class="etiqueta fixa">${esc(p.servidor)}</span></td><td>${dataBR(p.data_entrada)}</td></tr>`).join("")
    || '<tr><td colspan="7" class="vazio">Nenhum processo encontrado com esses filtros.</td></tr>';
}
async function carregarPadroes() {
  const quadro = await api("/api/padroes");
  $("#grade-padroes").innerHTML = quadro.map((g) => `<div class="cartao-padrao">
    <h3>${esc(g.assunto)}</h3>
    <p class="meta">${g.total} processos · ${g.decididos} com decisão${g.dias_ate_decisao != null ? ` · metade decidida em até ${g.dias_ate_decisao} dias` : ""}</p>
    ${g.decididos ? barrasDecisao(g.distribuicao, g.decididos, g.assunto) : '<p class="nada">Nenhuma decisão registrada ainda.</p>'}
    ${g.recentes.length ? `<h4>Decisões mais recentes</h4>${g.recentes.map((r) => `<div class="rec">
      <div class="cab"><a href="#" data-abrir="${esc(r.numero)}">${esc(sigla(r.classe))} ${esc(r.numero)}</a><span>etiqueta: ${esc(r.servidor || "—")}</span></div>
      ${decisaoHtml(r)}</div>`).join("")}` : ""}
  </div>`).join("");
}

async function carregarAuditoria() {
  const linhas = await api("/api/auditoria");
  $("#tabela-auditoria tbody").innerHTML = linhas.map((l) =>
    `<tr><td>${dataHoraBR(l.quando)}</td><td>${esc(l.acao)}</td><td>${esc(l.detalhe)}</td></tr>`).join("");
}

function mostrarAba(nome, filtro) {
  $$(".lateral .item[data-aba]").forEach((x) => x.classList.toggle("ativo", x.dataset.aba === nome));
  $$("main > .aba").forEach((s) => (s.hidden = s.id !== "aba-" + nome));
  if (nome === "acervo") carregarAcervo(filtro);
  if (nome === "auditoria") carregarAuditoria();
  if (nome === "padroes") carregarPadroes();
  if (nome === "triagem") atualizarTriagem();
}

// ---------- eventos ----------
$$(".lateral .item[data-aba]").forEach((b) => b.addEventListener("click", () => mostrarAba(b.dataset.aba)));

$$(".seg").forEach((b) => b.addEventListener("click", () => {
  modo = b.dataset.modo;
  $$(".seg").forEach((x) => { x.classList.toggle("ativo", x === b); x.setAttribute("aria-checked", x === b); });
}));

$$(".aba-lista").forEach((b) => b.addEventListener("click", () => {
  $$(".aba-lista").forEach((x) => x.classList.toggle("ativa", x === b));
  $("#lista-fila").hidden = b.dataset.lista !== "processos";
  $("#lista-duplicados").hidden = b.dataset.lista !== "duplicados";
}));

async function comCarregando(botao, fn) {
  const texto = botao.innerHTML;
  botao.classList.add("carregando");
  botao.innerHTML = "Processando…";
  try { await fn(); } catch (e) { toast("Não foi possível concluir: " + esc(e.message), true); }
  finally { botao.classList.remove("carregando"); botao.innerHTML = texto; }
}

$("#btn-triagem").addEventListener("click", (ev) => {
  if (fila.length && !confirm("Há uma distribuição aguardando aprovação. Buscar de novo refaz a proposta e descarta as etiquetas alteradas à mão. Continuar?")) return;
  buscar(ev.currentTarget);
});

const buscar = (botao) => comCarregando(botao, async () => {
  const r = await api("/api/triagem", { method: "POST", body: JSON.stringify({ modo }) });
  await atualizarTriagem();
  if (fila.length) abrirDetalhe(fila[0].numero);
  const barrados = r.duplicados.length + r.invalidos.length;
  toast(r.novos
    ? `${r.novos} processos novos lidos no PJe. ${r.duplicados.length} duplicados bloqueados.`
    : barrados
      ? `Nenhum processo novo: ${barrados} já estavam distribuídos ou têm número inválido.`
      : "Nenhum processo novo desde a última triagem.");
});

$("#btn-aprovar").addEventListener("click", (ev) => comCarregando(ev.currentTarget, async () => {
  const r = await api("/api/aprovar", { method: "POST" });
  selecionado = null;
  $("#detalhe").innerHTML = '<p class="placeholder">Aqui será exibido o processo selecionado</p>';
  await atualizarTriagem();
  toast(`Distribuição aprovada: ${r.aprovados} processos etiquetados e planilha atualizada. <a href="/api/planilha">Baixar planilha</a>`);
}));

$("#btn-reiniciar").addEventListener("click", async () => {
  if (!confirm("Restaurar a base de demonstração?")) return;
  await api("/api/demo/reiniciar", { method: "POST" });
  selecionado = null;
  $("#detalhe").innerHTML = '<p class="placeholder">Aqui será exibido o processo selecionado</p>';
  mostrarAba("triagem");
  toast("Base de demonstração restaurada.");
});

document.addEventListener("change", async (ev) => {
  const sel = ev.target.closest("[data-reatribuir]");
  if (!sel) return;
  try {
    await api(`/api/propostas/${encodeURIComponent(sel.dataset.reatribuir)}`, { method: "PUT", body: JSON.stringify({ servidor: sel.value }) });
    await atualizarTriagem();
    if (selecionado === sel.dataset.reatribuir) abrirDetalhe(selecionado);
    toast(`Etiqueta alterada para ${esc(sel.value)}.`);
  } catch (e) { toast("Não foi possível alterar a etiqueta: " + esc(e.message), true); }
});

document.addEventListener("click", (ev) => {
  const link = ev.target.closest("[data-abrir]");
  if (link) {
    ev.preventDefault();
    if (link.closest("#aba-padroes")) mostrarAba("triagem");
    abrirDetalhe(link.dataset.abrir);
    return;
  }
  const barra = ev.target.closest("[data-filtrar-assunto]");
  if (barra) {
    $("#busca-acervo").value = "";
    $("#filtro-servidor").value = "";
    mostrarAba("acervo", { assunto: barra.dataset.filtrarAssunto, decisao: barra.dataset.filtrarDecisao });
    return;
  }
  if (ev.target.closest("select")) return;
  const alvo = ev.target.closest(".card[data-numero], tr[data-numero]");
  if (!alvo) return;
  ev.preventDefault();
  if (alvo.closest("#lista-duplicados")) return;
  if (alvo.matches("tr")) { mostrarAba("triagem"); }
  abrirDetalhe(alvo.dataset.numero);
});
document.addEventListener("keydown", (ev) => {
  const c = ev.target.closest?.(".card[data-numero]");
  if (c && ev.key === "Enter") abrirDetalhe(c.dataset.numero);
  const barra = ev.target.closest?.("[data-filtrar-assunto]");
  if (barra && ev.key === "Enter") barra.click();
});
$("#busca-fila").addEventListener("input", renderFila);
$("#busca-acervo").addEventListener("input", filtrarAcervo);
$("#filtro-servidor").addEventListener("change", filtrarAcervo);
$("#filtro-assunto").addEventListener("change", filtrarAcervo);
$("#filtro-decisao").addEventListener("change", filtrarAcervo);

atualizarTriagem().then(() => {
  const m = location.hash.match(/^#p=(.+)$/);
  if (m) abrirDetalhe(decodeURIComponent(m[1]));
  const aba = location.hash.match(/^#aba=(\w+)$/);  // atalho para a demonstração, ex.: #aba=padroes
  if (aba) mostrarAba(aba[1]);
});
