const state = {
  page: "home",
  operator: "Desktop",
  health: null,
  summary: null,
  priorities: [],
  pending: [],
  certificates: [],
  ncs: [],
  documents: [],
  documentsMeta: null,
  selectedDocument: null,
  selectedPending: null,
  selectedCertificate: null,
  selectedNc: null,
  scans: [],
  documentFilters: {
    page: 1,
    page_size: 25,
    sort_by: "modified_at",
    sort_direction: "desc",
    search: "",
    extension: "",
    status: "",
    duplicate: "",
    error: "",
  },
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "Erro na requisição");
    throw new Error(text || `Erro ${response.status}`);
  }
  const contentType = response.headers.get("content-type") || "";
  return contentType.includes("application/json") ? response.json() : response.text();
}

function escapeHtml(value = "") {
  return String(value).replace(/[&<>'"]/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  })[char]);
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("pt-BR");
}

function formatDate(value) {
  if (!value) return "Não identificado";
  const date = new Date(String(value).includes("T") ? value : `${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleDateString("pt-BR");
}

function formatDateTime(value) {
  if (!value) return "Ainda não atualizado";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function formatBytes(value = 0) {
  const size = Number(value || 0);
  if (size < 1024) return `${formatNumber(size)} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} KB`;
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`;
  return `${(size / 1024 / 1024 / 1024).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} GB`;
}

function severityClass(value = "") {
  const text = String(value).toLowerCase();
  if (text.includes("crít") || text.includes("vencido") || text.includes("falha")) return "red";
  if (text.includes("aten") || text.includes("vence em") || text.includes("aguard")) return "amber";
  if (text.includes("vigente") || text.includes("encerrada") || text.includes("lido")) return "green";
  if (text.includes("análise") || text.includes("detectado")) return "blue";
  return "gray";
}

function pill(value) {
  return `<span class="pill ${severityClass(value)}">${escapeHtml(value || "Não identificado")}</span>`;
}

function fileIcon(extension = "") {
  if (extension === ".pdf") return "PDF";
  if ([".doc", ".docx"].includes(extension)) return "DOC";
  if ([".xls", ".xlsx", ".xlsm"].includes(extension)) return "XLS";
  if (extension === ".csv") return "CSV";
  if ([".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff"].includes(extension)) return "IMG";
  if ([".dwg", ".dxf", ".odg"].includes(extension)) return "CAD";
  if (extension === "temporario") return "TMP";
  if (extension === "sem extensao") return "SEM";
  return "ARQ";
}

function shortPath(path = "") {
  const parts = String(path).split(/[\\/]+/).filter(Boolean);
  if (parts.length <= 4) return path;
  return `${parts[0]}\\...\\${parts.slice(-3).join("\\")}`;
}

function toast(message, type = "") {
  const element = $("#toast");
  element.textContent = message;
  element.className = `toast ${type}`;
  element.classList.remove("hidden");
  setTimeout(() => element.classList.add("hidden"), 3500);
}

async function loadOperator() {
  try {
    const data = await api("/api/v1/system/operator");
    state.operator = data.display || data.username;
  } catch {
    state.operator = "Operador Windows não identificado";
  }
  $("#sidebar-operator").textContent = state.operator;
  $("#operator-display").textContent = state.operator;
}

async function loadBase() {
  const [summary, health] = await Promise.all([
    api("/api/v1/dashboard/summary"),
    api("/api/v1/health"),
  ]);
  state.summary = summary;
  state.health = health;
  $("#demo-banner").classList.toggle("hidden", health.data_mode !== "demo");
  const count = summary.needs_attention + summary.due_soon + summary.awaiting_confirmation;
  $("#nav-pending-count").textContent = formatNumber(count);
  const status = $("#share-status");
  status.className = `status-chip ${summary.share_accessible ? "ok" : "warn"}`;
  status.innerHTML = `<i></i><span>${summary.share_accessible ? "Pasta ISO: acessível" : "Pasta ISO: usando última leitura"}</span>`;
}

async function setPage(page) {
  state.page = page;
  $$(".nav-item").forEach(button => button.classList.toggle("active", button.dataset.page === page));
  $("#page-container").innerHTML = '<div class="loading">Carregando informações...</div>';
  try {
    if (!state.summary || !state.health) await loadBase();
    if (page === "home") await renderHome();
    if (page === "pending") await renderPending();
    if (page === "certificates") await renderCertificates();
    if (page === "ncs") await renderNcs();
    if (page === "documents") await renderDocuments();
    if (page === "assistant") renderSearch();
    if (page === "history") await renderHistory();
  } catch (error) {
    $("#page-container").innerHTML = `<div class="panel"><div class="empty"><h3>Não foi possível carregar</h3><p>${escapeHtml(error.message)}</p><button class="btn" onclick="location.reload()">Tentar novamente</button></div></div>`;
  }
}

function metricCard(tone, label, value, hint) {
  return `<article class="metric-card ${tone}"><div><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong><small>${escapeHtml(hint || "")}</small></div></article>`;
}

async function renderHome() {
  const summary = state.summary;
  const executive = await api("/api/v1/dashboard/executive").catch(() => null);
  state.priorities = executive?.decisions?.length ? executive.decisions : await api("/api/v1/dashboard/priorities?limit=6").catch(() => []);
  const brief = executive?.brief || "A Central ISO está organizando as situações reais da pasta ISO.";
  $("#page-container").innerHTML = `
    <div class="page-header">
      <div><h1>Central ISO</h1><p>${escapeHtml(brief)}</p></div>
      <div class="header-actions">
        <button class="btn primary" onclick="runScan('incremental')">Atualizar agora</button>
        <button class="btn" onclick="openQualitySummary()">Resumo da Qualidade</button>
      </div>
    </div>
    <div class="cards">
      ${metricCard("red", "Precisa da sua decisão", formatNumber(summary.decisions_needed ?? summary.needs_attention), "Somente casos que exigem confirmação humana")}
      ${metricCard("blue", "O sistema está cuidando", formatNumber(summary.automatic_tracking ?? summary.in_order), "Situações em acompanhamento automático")}
      ${metricCard("green", "Resolvido automaticamente", formatNumber(summary.auto_resolved ?? 0), "Encerramentos administrativos sem intervenção")}
      ${metricCard(summary.overall_status === "Situação crítica" ? "red" : summary.overall_status === "Atenção necessária" ? "amber" : "green", "Situação geral", escapeHtml(summary.overall_status || "Em organização"), "Visão executiva da Qualidade")}
    </div>
    <div class="info-strip">
      <span>Última atualização: <b>${formatDateTime(summary.last_updated)}</b></span>
      <span>Certificados acompanhados: <b>${formatNumber(summary.certificates_tracked ?? 0)}</b></span>
      <span>NCs acompanhadas: <b>${formatNumber(summary.ncs_tracked ?? 0)}</b></span>
      <span>Documentos analisados: <b>${formatNumber(summary.documents_analyzed ?? 0)}</b> de ${formatNumber(summary.documents_tracked)}</span>
      <span>Operador: <b>${escapeHtml(state.operator)}</b></span>
    </div>
    <div class="grid-2">
      <section class="panel">
        <div class="panel-header"><h2>Prioridades de hoje</h2><button class="btn small" onclick="setPage('pending')">Ver todas</button></div>
        <div class="table-wrap"><table class="table"><thead><tr><th>Item</th><th>Área</th><th>Prioridade</th><th>Situação</th><th>Ação</th></tr></thead><tbody>${priorityRows(state.priorities)}</tbody></table></div>
      </section>
      <aside class="panel">
        <div class="panel-header"><h2>Situação do sistema</h2></div>
        <div class="panel-body">
          ${systemItem("Pasta ISO", summary.share_accessible ? "Acessível" : "Indisponível, usando última leitura", summary.share_accessible ? "OK" : "Atenção")}
          ${systemItem("Busca nos documentos", "Local, sem IA externa", "Ativa")}
          ${systemItem("Automação", "Certificados e NCs extraídos da pasta ISO", "Ativa")}
          ${systemItem("Modo", state.health.data_mode === "demo" ? "Demonstração" : "Produção", state.health.maintenance_mode ? "Manutenção ativa" : "Apresentação")}
        </div>
      </aside>
    </div>`;
}

function priorityRows(items) {
  if (!items.length) return '<tr><td colspan="5"><div class="empty">Nenhuma prioridade real criada até o momento.</div></td></tr>';
  return items.map(item => `<tr>
    <td><div class="item-title">${escapeHtml(item.title)}</div><div class="item-sub">${escapeHtml(item.description).slice(0, 130)}</div></td>
    <td>${escapeHtml(item.area || "Não identificada")}</td>
    <td>${pill(item.severity)}</td>
    <td>${pill(item.status)}</td>
    <td><button class="btn small" onclick="openPendingFromHome(${item.id})">Ver detalhes</button></td>
  </tr>`).join("");
}

function systemItem(title, subtitle, stateText) {
  return `<div class="system-item"><div><strong>${escapeHtml(title)}</strong><small>${escapeHtml(subtitle)}</small></div><span class="system-state">${escapeHtml(stateText)}</span></div>`;
}

async function renderPending() {
  state.pending = await api("/api/v1/pending-items");
  state.selectedPending = state.selectedPending || state.pending[0] || null;
  $("#page-container").innerHTML = `
    <div class="page-header"><div><h1>Pendências</h1><p>Itens que precisam de análise, confirmação ou ação.</p></div></div>
    <div class="filter-row"><button class="filter active" onclick="filterPending('all', this)">Todas</button><button class="filter" onclick="filterPending('crítico', this)">Críticas</button><button class="filter" onclick="filterPending('atenção', this)">Atenção</button><button class="filter" onclick="filterPending('aguardando', this)">Aguardando revisão</button></div>
    <div class="grid-2">
      <section class="panel"><div class="table-wrap"><table class="table"><thead><tr><th>Pendência</th><th>Área</th><th>Responsável</th><th>Prazo</th><th>Situação</th><th></th></tr></thead><tbody id="pending-body">${pendingRows(state.pending)}</tbody></table></div></section>
      <aside id="pending-detail" class="panel detail-card">${pendingDetail(state.selectedPending)}</aside>
    </div>`;
}

function pendingRows(items) {
  if (!items.length) return '<tr><td colspan="6"><div class="empty">Nenhuma pendência real criada até o momento.</div></td></tr>';
  return items.map(item => `<tr data-severity="${escapeHtml(item.severity)}" data-status="${escapeHtml(item.status)}" class="${state.selectedPending?.id === item.id ? "selected" : ""}">
    <td><div class="item-title">${escapeHtml(item.title)}</div><div class="item-sub">${escapeHtml(item.kind.replace("regra:", ""))}</div></td>
    <td>${escapeHtml(item.area || "Não identificada")}</td>
    <td>${escapeHtml(item.responsible_role || "Aguardando definição de responsável")}</td>
    <td>${formatDate(item.due_date)}</td>
    <td>${pill(item.status)}</td>
    <td><button class="btn small" onclick="openPending(${item.id})">Detalhes</button></td>
  </tr>`).join("");
}

function pendingDetail(item) {
  if (!item) return '<div class="empty"><h3>Sem pendência selecionada</h3><p>Quando existirem pendências reais, os detalhes aparecerão aqui.</p></div>';
  return `<div class="panel-header"><div><h3>${escapeHtml(item.title)}</h3><div class="item-sub">Detectado automaticamente - aguardando revisão</div></div>${pill(item.severity)}</div>
    <div class="panel-body">
      <div class="detail-section"><h4>O que foi encontrado</h4><p>${escapeHtml(item.description || "Não descrito")}</p></div>
      <div class="detail-section"><h4>Por que merece atenção</h4><p>${escapeHtml(item.risk || "Revisão humana necessária antes de qualquer decisão oficial.")}</p></div>
      <div class="detail-meta"><div class="meta-box"><small>Função responsável</small><strong>${escapeHtml(item.responsible_role || "Aguardando definição de responsável")}</strong></div><div class="meta-box"><small>Prazo</small><strong>${formatDate(item.due_date)}</strong></div></div>
      <div class="detail-section"><h4>Evidência</h4><div class="source-path">${escapeHtml(item.source_path || "Fonte ainda não vinculada")}</div><p>${escapeHtml(item.source_excerpt || "").slice(0, 500)}</p></div>
      <div class="row-actions"><button class="btn" onclick="showEvidence('${encodeURIComponent(item.source_path || "")}')">Abrir evidência</button><button class="btn" onclick="addNote(${item.id})">Adicionar observação</button></div>
      <button class="btn primary block" style="margin-top:10px" onclick="markAnalysing(${item.id})">Marcar em análise</button>
    </div>`;
}

window.openPendingFromHome = async id => {
  await setPage("pending");
  openPending(id);
};

window.openPending = id => {
  state.selectedPending = state.pending.find(item => item.id === id) || null;
  $("#pending-detail").innerHTML = pendingDetail(state.selectedPending);
};

window.filterPending = (filter, button) => {
  $$(".filter").forEach(item => item.classList.remove("active"));
  button.classList.add("active");
  $$("#pending-body tr").forEach(row => {
    const text = `${row.dataset.severity || ""} ${row.dataset.status || ""}`.toLowerCase();
    row.style.display = filter === "all" || text.includes(filter) ? "" : "none";
  });
};

window.addNote = async id => {
  const note = prompt("Observação (salva apenas na Central ISO):");
  if (!note) return;
  await api(`/api/v1/pending-items/${id}/notes`, { method: "POST", body: JSON.stringify({ author: state.operator, note }) });
  toast("Observação adicionada.", "success");
};

window.markAnalysing = async id => {
  const justification = prompt("Por que este item está sendo analisado?");
  if (!justification) return;
  await api(`/api/v1/pending-items/${id}/status`, { method: "POST", body: JSON.stringify({ status: "em análise", justification }) });
  toast("Status interno atualizado.", "success");
  await renderPending();
};

async function renderCertificates() {
  state.certificates = await api("/api/v1/certificates");
  state.selectedCertificate = state.selectedCertificate || state.certificates[0] || null;
  const expired = state.certificates.filter(item => item.status === "vencido").length;
  const due = state.certificates.filter(item => String(item.status).startsWith("vence em")).length;
  $("#page-container").innerHTML = `
    <div class="page-header"><div><h1>Certificados</h1><p>Certificados estruturados a partir de evidências reais.</p></div></div>
    <div class="cards">${metricCard("red", "Vencidos", formatNumber(expired), "Não declarar não conformidade automaticamente")}${metricCard("amber", "Vencendo", formatNumber(due), "Exigem confirmação")}${metricCard("blue", "Aguardando revisão", formatNumber(state.certificates.length), "Detectado automaticamente")}${metricCard("green", "Confirmados", "0", "Ainda sem confirmação humana")}</div>
    <div class="grid-2"><section class="panel"><div class="table-wrap"><table class="table"><thead><tr><th>Certificado</th><th>Fornecedor</th><th>Produto</th><th>Validade</th><th>Status</th><th></th></tr></thead><tbody>${certificateRows(state.certificates)}</tbody></table></div></section><aside id="certificate-detail" class="panel detail-card">${certificateDetail(state.selectedCertificate)}</aside></div>`;
}

function certificateRows(items) {
  if (!items.length) return '<tr><td colspan="6"><div class="empty">Nenhum certificado real estruturado até o momento. Use Documentos para abrir evidências já inventariadas.</div></td></tr>';
  return items.map(item => `<tr class="${state.selectedCertificate?.id === item.id ? "selected" : ""}"><td><strong>${escapeHtml(item.number)}</strong></td><td>${escapeHtml(item.supplier || "Não identificado no documento")}</td><td>${escapeHtml(item.component_or_product || "Não identificado no documento")}</td><td>${formatDate(item.valid_until)}</td><td>${pill(item.status)}</td><td><button class="btn small" onclick="openCertificate(${item.id})">Detalhes</button></td></tr>`).join("");
}

function certificateDetail(item) {
  if (!item) return '<div class="empty"><h3>Nenhum certificado estruturado</h3><p>O sistema não vai inventar certificados; registros aparecerão quando houver evidência suficiente.</p></div>';
  return `<div class="panel-header"><div><h3>${escapeHtml(item.number)}</h3><div class="item-sub">Detectado automaticamente - aguardando revisão</div></div>${pill(item.status)}</div><div class="panel-body"><div class="detail-section"><h4>Validade</h4><p>${formatDate(item.valid_until)}</p></div><div class="detail-section"><h4>Perguntas obrigatórias</h4><ul><li>O componente ainda é utilizado?</li><li>Existe certificado substituto?</li><li>Existe estoque?</li><li>Quais produtos utilizam?</li></ul></div><div class="source-path">${escapeHtml(item.source_path || "")}</div><button class="btn block" onclick="showEvidence('${encodeURIComponent(item.source_path || "")}')">Abrir evidência</button></div>`;
}

window.openCertificate = id => {
  state.selectedCertificate = state.certificates.find(item => item.id === id) || null;
  $("#certificate-detail").innerHTML = certificateDetail(state.selectedCertificate);
};

async function renderNcs() {
  state.ncs = await api("/api/v1/nonconformities");
  state.selectedNc = state.selectedNc || state.ncs[0] || null;
  const open = state.ncs.filter(item => item.status !== "encerrada").length;
  const waitingEffectiveness = state.ncs.filter(item => item.status === "ação concluída" && !item.effectiveness_verified).length;
  $("#page-container").innerHTML = `
    <div class="page-header"><div><h1>Não conformidades</h1><p>Registros reais extraídos e ainda sujeitos a revisão humana.</p></div></div>
    <div class="cards">${metricCard("red", "Abertas", formatNumber(open), "Registros não encerrados")}${metricCard("amber", "Aguardando eficácia", formatNumber(waitingEffectiveness), "Ação concluída não encerra NC")}${metricCard("blue", "Aguardando revisão", formatNumber(state.ncs.length), "Detectado automaticamente")}${metricCard("green", "Confirmadas", "0", "Ainda sem validação humana")}</div>
    <div class="grid-2"><section class="panel"><div class="table-wrap"><table class="table"><thead><tr><th>NC</th><th>Área</th><th>Origem</th><th>Prazo</th><th>Status</th><th></th></tr></thead><tbody>${ncRows(state.ncs)}</tbody></table></div></section><aside id="nc-detail" class="panel detail-card">${ncDetail(state.selectedNc)}</aside></div>`;
}

function ncRows(items) {
  if (!items.length) return '<tr><td colspan="6"><div class="empty">Nenhuma não conformidade real estruturada até o momento. O sistema não usa dados demo em produção.</div></td></tr>';
  return items.map(item => `<tr><td><strong>${escapeHtml(item.code)}</strong></td><td>${escapeHtml(item.area || "Não identificada")}</td><td>${escapeHtml(item.origin || "Não identificada")}</td><td>${formatDate(item.due_date)}</td><td>${pill(item.status)}</td><td><button class="btn small" onclick="openNc(${item.id})">Detalhes</button></td></tr>`).join("");
}

function ncDetail(item) {
  if (!item) return '<div class="empty"><h3>Nenhuma NC estruturada</h3><p>Registros aparecerão quando houver evidência suficiente no conteúdo dos documentos.</p></div>';
  return `<div class="panel-header"><div><h3>${escapeHtml(item.code)}</h3><div class="item-sub">Detectado automaticamente - aguardando revisão</div></div>${pill(item.status)}</div><div class="panel-body"><div class="detail-section"><h4>Descrição</h4><p>${escapeHtml(item.description || "Não identificada")}</p></div><div class="detail-section"><h4>Ação e eficácia</h4><p>Ação: ${escapeHtml(item.action || "Não identificada")}</p><p>Eficácia: ${item.effectiveness_verified ? "verificada" : "não verificada"}</p></div><div class="source-path">${escapeHtml(item.source_path || "")}</div><button class="btn block" onclick="showEvidence('${encodeURIComponent(item.source_path || "")}')">Abrir evidência</button></div>`;
}

window.openNc = id => {
  state.selectedNc = state.ncs.find(item => item.id === id) || null;
  $("#nc-detail").innerHTML = ncDetail(state.selectedNc);
};

async function renderDocuments() {
  const params = new URLSearchParams();
  Object.entries(state.documentFilters).forEach(([key, value]) => {
    if (value !== "" && value !== null && value !== undefined) params.set(key, value);
  });
  const [docs, inventory, duplicates, scans] = await Promise.all([
    api(`/api/v1/documents?${params.toString()}`),
    api("/api/v1/inventory/summary"),
    api("/api/v1/inventory/duplicates").catch(() => []),
    api("/api/v1/scans").catch(() => []),
  ]);
  state.documents = docs.items || [];
  state.documentsMeta = docs;
  if (state.selectedDocument && !state.documents.some(item => item.id === state.selectedDocument.id)) state.selectedDocument = null;
  const latestInventory = scans.find(scan => scan.mode === "inventory");
  const limitedDirs = latestInventory?.files_failed || 0;
  $("#page-container").innerHTML = `
    <div class="page-header">
      <div><h1>Documentos</h1><p>Inventário real da ISO com filtros, evidências e revisão.</p></div>
      <div class="header-actions"><button class="btn primary" onclick="runScan('incremental')">Ler alterações</button><button class="btn" onclick="openQualitySummary()">Resumo da Qualidade</button></div>
    </div>
    <div class="cards">
      ${metricCard("blue", "Documentos acompanhados", formatNumber(inventory.total_files), "Total acessível do inventário")}
      ${metricCard("amber", "Resultados encontrados", formatNumber(docs.total_items), activeDocumentFilterLabel())}
      ${metricCard("red", "Com erro", formatNumber(inventory.errors_count), `${formatNumber(limitedDirs)} diretórios com acesso limitado`)}
      ${metricCard("green", "Duplicidades confirmadas", `${formatNumber(duplicates.length)} grupos`, "Confirmadas por hash até o momento")}
    </div>
    <div class="documents-layout">
      <section class="panel documents-panel">
        <div class="panel-header documents-header">
          <h2>Lista de documentos</h2>
          <div class="document-tools">
            <input class="inline-search" value="${escapeHtml(state.documentFilters.search)}" placeholder="Pesquisar documento" oninput="setDocumentSearch(this.value)" />
            <select onchange="setDocumentPageSize(this.value)"><option ${docs.page_size === 25 ? "selected" : ""}>25</option><option ${docs.page_size === 50 ? "selected" : ""}>50</option><option ${docs.page_size === 100 ? "selected" : ""}>100</option></select>
          </div>
        </div>
        <div class="filter-row compact">
          ${documentFilterButton("Todos", {})}
          ${documentFilterButton("PDFs", { extension: ".pdf" })}
          ${documentFilterButton("Word", { extension: ".docx" })}
          ${documentFilterButton("Excel", { extension: ".xlsx" })}
          ${documentFilterButton("Com erro", { error: "true" })}
          ${documentFilterButton("Protegidos", { status: "protegido" })}
          ${documentFilterButton("Duplicados", { duplicate: "true" })}
          ${documentFilterButton("Recentes", { sort_by: "modified_at", sort_direction: "desc" })}
        </div>
        <div class="document-status-line">${formatNumber(inventory.total_files)} arquivos acessíveis foram organizados. Existem ${formatNumber(limitedDirs)} diretórios com acesso limitado ou erro de leitura.</div>
        ${maintenancePanel()}
        <div class="table-wrap documents-table-wrap">
          <table class="table compact-table"><thead><tr><th>Tipo</th><th>Documento</th><th>Tamanho</th><th>Data</th><th>Situação</th><th>Ação</th></tr></thead><tbody id="docs-body">${documentRows(state.documents)}</tbody></table>
        </div>
        ${documentPagination(docs)}
      </section>
      <aside id="document-drawer" class="panel document-drawer">${documentDetail(state.selectedDocument)}</aside>
    </div>`;
}

function activeDocumentFilterLabel() {
  if (state.documentFilters.search) return `Pesquisa: ${state.documentFilters.search}`;
  if (state.documentFilters.extension) return `${state.documentFilters.extension} encontrados`;
  if (state.documentFilters.status) return `Status: ${state.documentFilters.status}`;
  if (state.documentFilters.error === "true") return "Arquivos com erro";
  if (state.documentFilters.duplicate === "true") return "Duplicados por hash";
  return "Sem filtro aplicado";
}

function documentFilterButton(label, patch) {
  const active = Object.entries(patch).every(([key, value]) => String(state.documentFilters[key] || "") === String(value || ""));
  return `<button class="filter ${active && Object.keys(patch).length ? "active" : ""}" onclick='setDocumentFilter(${JSON.stringify(patch)})'>${escapeHtml(label)}</button>`;
}

function maintenancePanel() {
  if (!state.health?.maintenance_mode) return "";
  return `<details class="maintenance-panel"><summary>Manutenção do sistema</summary><div class="maintenance-actions"><button class="btn small" onclick="runInventory()">Inventário completo</button><button class="btn small" onclick="selectSample()">Selecionar amostra</button><button class="btn small" onclick="extractSample()">Extrair amostra</button><button class="btn small" onclick="runHashProgress()">Hash progressivo</button></div></details>`;
}

function documentRows(items) {
  if (!items.length) return '<tr><td colspan="6"><div class="empty">Nenhum documento encontrado com estes filtros.</div></td></tr>';
  return items.map(item => `<tr class="${state.selectedDocument?.id === item.id ? "selected" : ""}" onclick="openDocument(${item.id})">
    <td><span class="file-type">${escapeHtml(fileIcon(item.extension))}</span></td>
    <td><div class="item-title truncate" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</div><div class="item-sub truncate" title="${escapeHtml(item.path)}">${escapeHtml(shortPath(item.path))}</div></td>
    <td>${formatBytes(item.size_bytes)}</td>
    <td>${formatDateTime(item.modified_at)}</td>
    <td>${pill(item.status)}</td>
    <td><button class="btn small" onclick="event.stopPropagation(); openDocument(${item.id})">Ver detalhes</button></td>
  </tr>`).join("");
}

function documentPagination(meta) {
  return `<div class="pagination"><button class="btn small" ${meta.page <= 1 ? "disabled" : ""} onclick="setDocumentPage(${meta.page - 1})">Anterior</button><span>${formatNumber(meta.page_size)} por página · página <b>${formatNumber(meta.page)}</b> de <b>${formatNumber(meta.total_pages)}</b> · ${formatNumber(meta.total_items)} resultados</span><button class="btn small" ${meta.page >= meta.total_pages ? "disabled" : ""} onclick="setDocumentPage(${meta.page + 1})">Próxima</button></div>`;
}

function documentDetail(item) {
  if (!item) return '<div class="empty"><h3>Selecione um documento</h3><p>Os detalhes aparecem aqui sem sair da lista.</p></div>';
  return `<div class="panel-header"><div><h3>${escapeHtml(item.name)}</h3><div class="item-sub">Detectado automaticamente - aguardando revisão</div></div>${pill(item.status)}</div>
    <div class="panel-body">
      <div class="detail-section"><h4>Caminho completo</h4><div class="source-path">${escapeHtml(item.path)}</div></div>
      <div class="detail-meta"><div class="meta-box"><small>Tipo</small><strong>${escapeHtml(item.extension || "sem extensão")}</strong></div><div class="meta-box"><small>Tamanho</small><strong>${formatBytes(item.size_bytes)}</strong></div></div>
      <div class="detail-meta" style="margin-top:12px"><div class="meta-box"><small>Criação</small><strong>Não registrada</strong></div><div class="meta-box"><small>Modificação</small><strong>${formatDateTime(item.modified_at)}</strong></div></div>
      <div class="detail-section"><h4>Hash</h4><p>${escapeHtml(item.sha256 || "Ainda não calculado")}</p></div>
      ${item.last_error ? `<div class="detail-section"><h4>Erro</h4><p>${escapeHtml(item.last_error)}</p></div>` : ""}
      <div class="detail-section"><h4>Extração</h4><p>${escapeHtml(item.excerpt || "Conteúdo ainda não extraído ou aguardando revisão.")}</p></div>
      <button class="btn block" onclick="showEvidence('${encodeURIComponent(item.path)}')">Abrir evidência</button>
    </div>`;
}

window.openDocument = id => {
  state.selectedDocument = state.documents.find(item => item.id === id) || null;
  $("#document-drawer").innerHTML = documentDetail(state.selectedDocument);
};

window.setDocumentPage = async page => {
  state.documentFilters.page = page;
  await renderDocuments();
};

window.setDocumentPageSize = async size => {
  state.documentFilters.page = 1;
  state.documentFilters.page_size = Number(size);
  await renderDocuments();
};

let documentSearchTimer;
window.setDocumentSearch = value => {
  clearTimeout(documentSearchTimer);
  documentSearchTimer = setTimeout(async () => {
    state.documentFilters.search = value.trim();
    state.documentFilters.page = 1;
    await renderDocuments();
  }, 300);
};

window.setDocumentFilter = async patch => {
  state.documentFilters = { ...state.documentFilters, page: 1, search: "", extension: "", status: "", duplicate: "", error: "", ...patch };
  await renderDocuments();
};

function renderSearch() {
  $("#page-container").innerHTML = `<div class="page-header"><div><h1>Busca nos documentos</h1><p>Consulta textual local com fontes. Não é IA avançada nem aprovação automática.</p></div></div>
    <div class="ask-layout"><div><div class="ask-box"><textarea id="question" placeholder="Pergunte sobre certificados, NCs, procedimentos ou documentos..."></textarea><button class="btn primary" onclick="askQuality()">Buscar</button></div>
    <div class="suggestions">${["Qual é o escopo atual do SGQ?", "Política e Objetivos da Qualidade", "Quais certificados estão vencidos?", "Quais documentos não foram lidos?"].map(text => `<button class="suggestion" onclick="useSuggestion('${text}')">${text}</button>`).join("")}</div>
    <div id="answer-area" class="answer-card"><div class="empty"><h3>Consulta baseada nos documentos</h3><p>As respostas devem mostrar fontes e limitações.</p></div></div></div>
    <aside class="panel"><div class="panel-header"><h3>Limite operacional</h3></div><div class="panel-body"><p>A Central ISO localiza evidências, mas não aprova documentos, não encerra NCs e não libera Produto Ex.</p></div></aside></div>`;
}

window.useSuggestion = question => {
  $("#question").value = question;
  askQuality();
};

window.askQuality = async () => {
  const question = $("#question").value.trim();
  if (!question) return;
  const area = $("#answer-area");
  area.innerHTML = '<div class="loading">Buscando nos documentos...</div>';
  try {
    const result = await api("/api/v1/assistant/query", { method: "POST", body: JSON.stringify({ question }) });
    area.innerHTML = `<div class="answer-section"><h3>Resposta</h3><p>${escapeHtml(result.answer)}</p></div><div class="answer-section"><h3>Evidências</h3><ul>${(result.evidence || []).map(item => `<li>${escapeHtml(item)}</li>`).join("") || "<li>Nenhuma evidência conclusiva.</li>"}</ul></div><div class="answer-section"><h3>Arquivos utilizados</h3>${(result.sources || []).map(source => `<div class="source-card"><strong>${escapeHtml(source.name)}</strong><small>${escapeHtml(source.path)}</small><button class="btn small" onclick="showEvidence('${encodeURIComponent(source.path)}')">Abrir evidência</button></div>`).join("") || "<p>Nenhum arquivo localizado.</p>"}</div><div class="answer-section"><h3>Confirmação necessária</h3><ul>${(result.confirmation_needed || []).map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul><p><b>Confiança:</b> ${escapeHtml(result.confidence)} · ${escapeHtml(result.mode)}</p></div>`;
  } catch (error) {
    area.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  }
};

async function renderHistory() {
  state.scans = await api("/api/v1/scans");
  $("#page-container").innerHTML = `<div class="page-header"><div><h1>Histórico</h1><p>Varreduras, inventários e execução local.</p></div></div><div class="history-list">${state.scans.map(scan => `<div class="history-row"><b>#${scan.id}</b><div>${pill(scan.status)}</div><div><strong>${escapeHtml(scan.mode)}</strong><div class="item-sub">${escapeHtml(scan.message)}</div></div><div><b>${formatNumber(scan.files_found)}</b> arquivos<br><small>${formatDateTime(scan.finished_at)}</small></div></div>`).join("") || '<div class="panel empty">Nenhuma varredura registrada.</div>'}</div>`;
}

window.runScan = async mode => {
  toast("Atualização iniciada...");
  try {
    const result = await api(`/api/v1/scans?mode=${mode}`, { method: "POST" });
    toast(`${result.message} ${formatNumber(result.files_processed)} arquivo(s) processado(s).`, result.status === "failed" ? "error" : "success");
    state.summary = null;
    await loadBase();
    await setPage(state.page);
  } catch (error) {
    toast(error.message, "error");
  }
};

window.runInventory = async () => {
  const result = await api("/api/v1/inventory/run", { method: "POST" });
  toast(`Inventário: ${formatNumber(result.files_processed)} arquivo(s) mapeados.`, result.status === "failed" ? "error" : "success");
  await renderDocuments();
};

window.selectSample = async () => {
  const result = await api("/api/v1/sample/select", { method: "POST" });
  toast(`Amostra selecionada: ${formatNumber(result.items.length)} documento(s).`, "success");
};

window.extractSample = async () => {
  const result = await api("/api/v1/sample/extract", { method: "POST" });
  toast(`Amostra extraída: ${formatNumber(result.items.length)} documento(s).`, "success");
};

window.runHashProgress = async () => {
  const result = await api("/api/v1/hash/run", { method: "POST" });
  toast(`Hash: ${formatNumber(result.processed || 0)} processado(s), ${formatNumber(result.errors || 0)} erro(s).`, result.status === "disabled" ? "error" : "success");
};

window.showEvidence = encoded => {
  const path = decodeURIComponent(encoded || "");
  if (!path) {
    toast("Origem não encontrada.", "error");
    return;
  }
  window.open(`/api/v1/evidence?path=${encodeURIComponent(path)}`, "_blank");
};

window.openQualitySummary = () => {
  window.open("/api/v1/reports/quality-summary.html", "_blank");
};

$$(".nav-item").forEach(button => button.addEventListener("click", () => setPage(button.dataset.page)));

let globalSearchTimer;
$("#global-search").addEventListener("input", event => {
  clearTimeout(globalSearchTimer);
  const query = event.target.value.trim();
  const box = $("#global-search-results");
  if (query.length < 2) {
    box.classList.add("hidden");
    return;
  }
  globalSearchTimer = setTimeout(async () => {
    try {
      const results = await api(`/api/v1/search?q=${encodeURIComponent(query)}`);
      box.innerHTML = results.length ? results.map(result => `<div class="search-result" onclick="showEvidence('${encodeURIComponent(result.path)}')"><strong>${escapeHtml(result.name)}</strong><small>${escapeHtml(result.category)}</small></div>`).join("") : '<div class="search-result">Nenhum resultado.</div>';
      box.classList.remove("hidden");
    } catch {
      box.classList.add("hidden");
    }
  }, 250);
});

document.addEventListener("click", event => {
  if (!event.target.closest(".global-search-wrap")) $("#global-search-results").classList.add("hidden");
});

(async function init() {
  try {
    await loadBase();
    await loadOperator();
    await renderHome();
  } catch (error) {
    $("#page-container").innerHTML = `<div class="panel"><div class="empty"><h3>Não foi possível carregar</h3><p>${escapeHtml(error.message)}</p><button class="btn" onclick="location.reload()">Tentar novamente</button></div></div>`;
  }
})();
