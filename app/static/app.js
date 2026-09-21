/**
 * FinOps Cloud Waste Hunter & Auto-Remediator - Client Logic
 * ISWE309L Cloud Computing - Course Project Review-1
 * Team: Vivek Pandey (24MIS0216) & S. Hemal (24MIS0050)
 */

let currentReport = null;
let donutChart = null;
let barChart = null;

document.addEventListener("DOMContentLoaded", () => {
  initCharts();
  loadInitialData();

  document.getElementById("runPipelineBtn").addEventListener("click", () => {
    const scenario = document.getElementById("scenarioSelect").value;
    executePipeline(scenario);
  });

  document.getElementById("scenarioSelect").addEventListener("change", (e) => {
    executePipeline(e.target.value);
  });
});

function initCharts() {
  const donutCtx = document.getElementById("wasteDonutChart").getContext("2d");
  donutChart = new Chart(donutCtx, {
    type: "doughnut",
    data: {
      labels: ["Compute", "Storage", "Serverless", "Networking"],
      datasets: [{
        data: [0, 0, 0, 0],
        backgroundColor: ["#f59e0b", "#3b82f6", "#a855f7", "#14b8a6"],
        borderWidth: 0,
        hoverOffset: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      cutout: "75%"
    }
  });

  const barCtx = document.getElementById("costBarChart").getContext("2d");
  barChart = new Chart(barCtx, {
    type: "bar",
    data: {
      labels: ["Current Spend", "Optimized Spend"],
      datasets: [{
        data: [0, 0],
        backgroundColor: ["#f43f5e", "#10b981"],
        borderRadius: 8,
        barThickness: 32
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#94a3b8" } },
        y: { grid: { color: "rgba(51, 65, 85, 0.4)" }, ticks: { color: "#94a3b8", callback: v => `$${v}` } }
      }
    }
  });
}

async function loadInitialData() {
  executePipeline("enterprise");
}

async function executePipeline(scenario = "enterprise") {
  const btn = document.getElementById("runPipelineBtn");
  const spinner = document.getElementById("pipelineSpinner");
  const btnText = document.getElementById("pipelineBtnText");

  btn.disabled = true;
  spinner.classList.remove("hidden");
  btnText.textContent = "Executing Pipeline...";

  try {
    const res = await fetch("/api/pipeline/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario, use_live_aws: false })
    });
    const result = await res.json();
    if (result.status === "SUCCESS") {
      currentReport = result.report;
      renderAllModules(currentReport);
    }
  } catch (err) {
    console.error("Pipeline run failed:", err);
  } finally {
    btn.disabled = false;
    spinner.classList.add("hidden");
    btnText.textContent = "⚡ Run 7-Module Pipeline";
  }
}

function renderAllModules(report) {
  // 1. Executive Metrics
  const monthlySav = report.total_monthly_savings || 0;
  const annualSav = report.total_annualized_savings || 0;
  const carbonSav = report.total_carbon_savings_kg || 0;
  const wasteCount = (report.waste_findings || []).length;
  const currentCost = report.total_current_monthly_cost || (monthlySav + report.total_optimized_monthly_cost);
  const optCost = report.total_optimized_monthly_cost || 0;

  document.getElementById("metricMonthlySavings").textContent = `$${monthlySav.toFixed(2)}`;
  document.getElementById("metricAnnualSavings").textContent = `$${annualSav.toFixed(2)}`;
  document.getElementById("metricWasteCount").textContent = wasteCount;
  document.getElementById("metricCarbonSavings").textContent = `${carbonSav.toFixed(1)} kg`;

  const savingsRate = currentCost > 0 ? ((monthlySav / currentCost) * 100).toFixed(1) : 0;
  document.getElementById("metricMonthlySavingsRate").textContent = `${savingsRate}%`;

  const critCount = (report.waste_findings || []).filter(w => w.severity === "CRITICAL").length;
  document.getElementById("metricSeverityPill").textContent = `${critCount} Critical`;

  document.getElementById("savingsBadge").textContent = `-$${monthlySav.toFixed(2)} / mo`;
  document.getElementById("currSpendText").textContent = `$${currentCost.toFixed(2)}`;
  document.getElementById("optSpendText").textContent = `$${optCost.toFixed(2)}`;

  // Update Charts
  updateCharts(report, currentCost, optCost);

  // Render Module 1: Monitoring
  renderModule1(report.monitored_resources || []);

  // Render Module 2: Waste Detection
  renderModule2(report.waste_findings || []);

  // Render Module 3: Cost Estimation
  renderModule3(report.cost_findings || []);

  // Render Module 4: Bedrock AI
  renderModule4(report.ai_recommendations || []);

  // Render Module 5: Storage & Audit
  renderModule5(report);

  // Render Module 6: Terraform Patches
  renderModule6(report.terraform_patches || []);

  // Render Module 7: GitOps Review
  renderModule7(report.gitops_pr);
}

function updateCharts(report, currentCost, optCost) {
  // Group findings by resource category
  let comp = 0, stor = 0, serv = 0, net = 0;
  (report.waste_findings || []).forEach(f => {
    if (f.resource_type === "EC2") comp++;
    else if (f.resource_type === "EBS") stor++;
    else if (f.resource_type === "LAMBDA") serv++;
    else net++;
  });

  donutChart.data.datasets[0].data = [comp, stor, serv, net];
  donutChart.update();

  const legendContainer = document.getElementById("donutLegend");
  legendContainer.innerHTML = `
    <div class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-amber-500"></span> Compute (${comp})</div>
    <div class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-blue-500"></span> Storage (${stor})</div>
    <div class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-purple-500"></span> Serverless (${serv})</div>
    <div class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-teal-500"></span> Network (${net})</div>
  `;

  barChart.data.datasets[0].data = [currentCost, optCost];
  barChart.update();
}

function renderModule1(resources) {
  document.getElementById("monitoredCountBadge").textContent = `${resources.length} Resources`;
  const tbody = document.getElementById("monitoringTableBody");
  tbody.innerHTML = resources.map(r => {
    const specsStr = Object.entries(r.specs || {})
      .map(([k, v]) => `<span class="text-slate-400">${k}:</span> <span class="text-slate-200">${v}</span>`)
      .join(" &bull; ");
    
    const tagsStr = Object.entries(r.tags || {})
      .map(([k, v]) => `<span class="bg-slate-800 text-[10px] px-1.5 py-0.5 rounded text-slate-400 font-mono">${k}=${v}</span>`)
      .join(" ");

    let metricHighlight = "";
    if (r.resource_type === "EC2") {
      const avg = r.metrics.cpu_utilization_avg || 0;
      const color = avg < 10 ? "text-amber-400" : "text-emerald-400";
      metricHighlight = `CPU: <strong class="${color}">${avg}%</strong> (Peak: ${r.metrics.cpu_utilization_max}%)`;
    } else if (r.resource_type === "EBS") {
      const days = r.metrics.days_unattached || 0;
      metricHighlight = `<span class="text-rose-400 font-bold">${days} days unattached</span>`;
    } else if (r.resource_type === "LAMBDA") {
      metricHighlight = `<span class="text-purple-400 font-bold">0 invocations</span> (Last: ${r.metrics.last_invoked_days_ago}d ago)`;
    } else {
      metricHighlight = `<span class="text-teal-400">Idle allocation</span>`;
    }

    return `
      <tr class="hover:bg-slate-900/40 transition">
        <td class="py-3 px-4 font-mono font-bold text-white">
          ${r.name}
          <div class="text-[10px] text-slate-500 font-normal">${r.id}</div>
        </td>
        <td class="py-3 px-4">
          <span class="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-800 text-slate-300">${r.resource_type}</span>
        </td>
        <td class="py-3 px-4">
          <span class="inline-flex items-center gap-1 text-[11px] font-medium ${r.state === 'running' || r.state === 'active' ? 'text-emerald-400' : 'text-amber-400'}">
            <span class="w-1.5 h-1.5 rounded-full ${r.state === 'running' || r.state === 'active' ? 'bg-emerald-400' : 'bg-amber-400'}"></span>
            ${r.state}
          </span>
        </td>
        <td class="py-3 px-4 text-slate-300 font-mono text-[11px]">${specsStr}</td>
        <td class="py-3 px-4 font-mono text-[11px]">${metricHighlight}</td>
        <td class="py-3 px-4 flex flex-wrap gap-1">${tagsStr || '<span class="text-slate-600">None</span>'}</td>
      </tr>
    `;
  }).join("");
}

function renderModule2(findings) {
  document.getElementById("wasteCountBadge").textContent = `${findings.length} Findings`;
  const container = document.getElementById("wasteFindingsContainer");

  container.innerHTML = findings.map(f => {
    const sevColor = f.severity === "CRITICAL"
      ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
      : f.severity === "HIGH"
      ? "bg-orange-500/10 text-orange-400 border-orange-500/20"
      : "bg-amber-500/10 text-amber-400 border-amber-500/20";

    return `
      <div class="bg-slate-900/60 rounded-xl p-4 border border-slate-800 hover:border-slate-700 transition space-y-3">
        <div class="flex items-start justify-between gap-2">
          <div>
            <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${sevColor}">${f.severity}</span>
            <h3 class="text-sm font-bold text-white mt-1.5">${f.resource_name}</h3>
            <div class="text-[11px] font-mono text-slate-400">${f.waste_category} &bull; ${f.resource_type}</div>
          </div>
          <span class="text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
            ${(f.confidence_score * 100).toFixed(0)}% Conf.
          </span>
        </div>

        <p class="text-xs text-slate-300 leading-relaxed">${f.description}</p>

        <div class="bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-xs font-mono space-y-1">
          <div class="text-slate-400">Current: <span class="text-rose-400 font-semibold">${f.current_specs}</span></div>
          <div class="text-slate-400">Target:  <span class="text-emerald-400 font-semibold">${f.recommended_specs}</span></div>
        </div>
      </div>
    `;
  }).join("");
}

function renderModule3(costs) {
  const tbody = document.getElementById("costTableBody");
  tbody.innerHTML = costs.map(c => `
    <tr class="hover:bg-slate-900/40 transition">
      <td class="py-3 px-4 font-mono font-bold text-white">${c.resource_name}</td>
      <td class="py-3 px-4 font-mono text-slate-400">${c.resource_type}</td>
      <td class="py-3 px-4 text-slate-300 font-mono text-[11px]">${c.pricing_breakdown}</td>
      <td class="py-3 px-4 font-mono text-rose-400 font-bold">$${c.current_monthly_cost.toFixed(2)}</td>
      <td class="py-3 px-4 font-mono text-slate-400">$${c.optimized_monthly_cost.toFixed(2)}</td>
      <td class="py-3 px-4 font-mono text-emerald-400 font-bold">+$${c.monthly_savings.toFixed(2)}/mo</td>
      <td class="py-3 px-4 font-mono text-teal-400 text-[11px]">${c.carbon_savings_kg_co2e.toFixed(1)} kg CO2e</td>
    </tr>
  `).join("");
}

function renderModule4(recs) {
  const container = document.getElementById("aiRecommendationsContainer");
  container.innerHTML = recs.map((r, idx) => `
    <div class="bg-slate-900/60 rounded-xl p-5 border border-slate-800 space-y-3">
      <div class="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-800/80">
        <div class="flex items-center gap-2">
          <span class="w-6 h-6 rounded-full bg-purple-600/30 text-purple-300 text-xs font-bold font-mono flex items-center justify-center">${idx + 1}</span>
          <h3 class="text-sm font-bold text-white">${r.title}</h3>
        </div>
        <span class="px-2.5 py-0.5 rounded text-xs font-mono font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          ${r.risk_level}
        </span>
      </div>

      <p class="text-xs text-slate-300 leading-relaxed">${r.executive_summary}</p>

      <div class="bg-slate-950/80 p-3 rounded-lg border border-slate-800 text-xs space-y-2">
        <div>
          <span class="text-purple-400 font-semibold">Nova Lite Rationale:</span>
          <p class="text-slate-300 text-[11px] mt-0.5">${r.rationale}</p>
        </div>
        <div>
          <span class="text-emerald-400 font-semibold">Action Steps:</span>
          <ul class="list-disc list-inside text-slate-300 text-[11px] mt-0.5 space-y-0.5">
            ${(r.steps_to_remediate || []).map(s => `<li>${s}</li>`).join("")}
          </ul>
        </div>
        <div>
          <span class="text-amber-400 font-semibold">Rollback Safety Plan:</span>
          <p class="text-slate-400 text-[11px] mt-0.5">${r.rollback_plan}</p>
        </div>
      </div>
    </div>
  `).join("");
}

function renderModule5(report) {
  const s3List = document.getElementById("s3FileList");
  s3List.innerHTML = `
    <div class="flex items-center justify-between py-1 border-b border-slate-800">
      <span class="text-slate-200">📄 finops-audit-${report.run_id}.json</span>
      <button onclick="downloadReport('json')" class="text-amber-400 hover:underline">Download</button>
    </div>
    <div class="flex items-center justify-between py-1 border-b border-slate-800">
      <span class="text-slate-200">📝 finops-report-${report.run_id}.md</span>
      <button onclick="downloadReport('markdown')" class="text-amber-400 hover:underline">Download</button>
    </div>
    <div class="flex items-center justify-between py-1">
      <span class="text-slate-200">📊 finops-waste-${report.run_id}.csv</span>
      <button onclick="downloadReport('csv')" class="text-amber-400 hover:underline">Download</button>
    </div>
  `;

  // Fetch DynamoDB table records
  fetch("/api/modules/5")
    .then(res => res.json())
    .then(data => {
      const records = data.audit_history || [];
      const tbody = document.getElementById("dynamoDbTableBody");
      tbody.innerHTML = records.map(rec => `
        <tr class="hover:bg-slate-900 transition">
          <td class="p-2 text-slate-300">${rec.run_id.substring(0, 18)}...</td>
          <td class="p-2 text-rose-400">${rec.total_findings} items</td>
          <td class="p-2 text-emerald-400 font-bold">$${rec.monthly_savings.toFixed(2)}</td>
          <td class="p-2"><span class="px-1.5 py-0.5 rounded text-[10px] bg-blue-500/10 text-blue-400">${rec.gitops_status}</span></td>
        </tr>
      `).join("");
    })
    .catch(() => {});
}

function renderModule6(patches) {
  document.getElementById("patchCountBadge").textContent = `${patches.length} Patches`;
  const viewer = document.getElementById("terraformDiffViewer");

  if (!patches.length) {
    viewer.textContent = "# No Terraform modifications required. Infrastructure is optimal.";
    return;
  }

  let html = "";
  patches.forEach(p => {
    const lines = p.unified_diff.split("\n");
    lines.forEach(line => {
      if (line.startsWith("---") || line.startsWith("+++") || line.startsWith("@@")) {
        html += `<span class="diff-header">${escapeHtml(line)}</span>`;
      } else if (line.startsWith("-")) {
        html += `<span class="diff-del">${escapeHtml(line)}</span>`;
      } else if (line.startsWith("+")) {
        html += `<span class="diff-add">${escapeHtml(line)}</span>`;
      } else {
        html += `<span>${escapeHtml(line)}</span>\n`;
      }
    });
  });

  viewer.innerHTML = html;
}

function renderModule7(pr) {
  if (!pr) {
    document.getElementById("prTitle").textContent = "No active pull requests (Environment is optimal)";
    return;
  }

  document.getElementById("quickPRStatus").textContent = pr.status;
  document.getElementById("quickPRDesc").textContent = `PR #${pr.pr_number}: ${pr.title}`;
  document.getElementById("quickBranchName").textContent = pr.branch_name;

  document.getElementById("prStatusBadge").textContent = pr.status;
  const badge = document.getElementById("prStatusBadge");
  if (pr.status === "MERGED") {
    badge.className = "px-2.5 py-1 rounded-full text-xs font-bold font-mono bg-purple-500/20 text-purple-300 border border-purple-500/30";
  } else if (pr.status === "APPROVED") {
    badge.className = "px-2.5 py-1 rounded-full text-xs font-bold font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
  } else {
    badge.className = "px-2.5 py-1 rounded-full text-xs font-bold font-mono bg-blue-500/20 text-blue-300 border border-blue-500/30";
  }

  document.getElementById("prTitle").textContent = pr.title;
  document.getElementById("prMetaHeader").innerHTML = `#PR-${pr.pr_number} on branch <span class="text-amber-400 font-mono">${pr.branch_name}</span> &rarr; <span class="text-slate-300 font-mono">main</span>`;

  // Render CI Checks
  const checksList = document.getElementById("prChecksList");
  checksList.innerHTML = (pr.checks || []).map(c => {
    const isSuccess = c.status === "SUCCESS";
    const icon = isSuccess ? "✅" : "⏳";
    const color = isSuccess ? "text-emerald-400" : "text-amber-400";
    return `
      <div class="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
        <div class="flex items-center justify-between">
          <span class="text-slate-300 font-semibold">${icon} ${c.name}</span>
          <span class="${color} font-bold">${c.status}</span>
        </div>
        <p class="text-[10px] text-slate-500 mt-1">${c.details}</p>
      </div>
    `;
  }).join("");

  // Render Audit Trail
  const auditDiv = document.getElementById("prAuditTrail");
  auditDiv.innerHTML = (pr.audit_trail || []).map(msg => `<div>${msg}</div>`).join("");
}

async function approveCurrentPR() {
  if (!currentReport || !currentReport.gitops_pr) return;
  const prId = currentReport.gitops_pr.pr_id;
  try {
    const res = await fetch(`/api/gitops/pr/${prId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewer: "Vivek Pandey (Lead FinOps Engineer)" })
    });
    const data = await res.json();
    if (data.status === "SUCCESS") {
      currentReport.gitops_pr = data.pr;
      renderModule7(data.pr);
    }
  } catch (err) {
    console.error("Approve failed:", err);
  }
}

async function mergeCurrentPR() {
  if (!currentReport || !currentReport.gitops_pr) return;
  const prId = currentReport.gitops_pr.pr_id;
  try {
    const res = await fetch(`/api/gitops/pr/${prId}/merge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewer: "Vivek Pandey (Lead FinOps Engineer)" })
    });
    const data = await res.json();
    if (data.status === "SUCCESS") {
      currentReport.gitops_pr = data.pr;
      renderModule7(data.pr);
    }
  } catch (err) {
    console.error("Merge failed:", err);
  }
}

function switchTab(modId) {
  // Update nav buttons
  const buttons = document.querySelectorAll("#modulePipelineNav .nav-step");
  buttons.forEach(b => b.classList.remove("active"));
  
  const activeBtn = document.querySelector(`#modulePipelineNav [data-tab="${modId}"]`);
  if (activeBtn) {
    activeBtn.classList.add("active");
  }

  // Show selected tab
  document.querySelectorAll(".module-tab-content").forEach(el => el.classList.remove("active"));
  const target = document.getElementById(`tab-${modId}`);
  if (target) {
    target.classList.add("active");
  }
}

function downloadReport(fmt) {
  window.open(`/api/reports/download/${fmt}`, "_blank");
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
