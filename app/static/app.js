/**
 * FinOps Cloud Waste Hunter & Auto-Remediator - Client Logic
 * Handles Live AWS mode, AWS Status, Real Resource Discovery,
 * Demo Simulation, and Human-in-the-Loop Terraform & GitOps safety gates.
 */

let currentMode = "live"; // "live" or "demo"
let currentReport = null;
let currentAwsStatus = null;
let currentAwsResources = null;
let activePlanId = "";
let donutChart = null;
let barChart = null;

document.addEventListener("DOMContentLoaded", async () => {
  initCharts();
  initEventListeners();

  // Load live AWS status and resources first to determine default mode
  await refreshAwsStatusAndResources();

  // If AWS is connected, default to Live AWS mode; otherwise fall back to Demo mode
  if (currentAwsStatus && currentAwsStatus.status === "CONNECTED") {
    setMode("live", false);
  } else {
    setMode("demo", false);
  }

  // Run the initial pipeline for the selected mode
  await executePipeline();
});

function initCharts() {
  const donutCtx = document.getElementById("wasteDonutChart").getContext("2d");
  donutChart = new Chart(donutCtx, {
    type: "doughnut",
    data: {
      labels: ["Compute", "Storage", "Serverless", "Network"],
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

function initEventListeners() {
  // Mode selection buttons
  document.getElementById("modeLiveBtn").addEventListener("click", () => {
    if (currentMode !== "live") {
      setMode("live", true);
    }
  });

  document.getElementById("modeDemoBtn").addEventListener("click", () => {
    if (currentMode !== "demo") {
      setMode("demo", true);
    }
  });

  // Run pipeline button
  document.getElementById("runPipelineBtn").addEventListener("click", () => {
    executePipeline();
  });

  // Demo scenario change
  document.getElementById("scenarioSelect").addEventListener("change", () => {
    if (currentMode === "demo") {
      executePipeline();
    }
  });

  // Terraform approval checkbox safety gate
  const chkApprove = document.getElementById("chkApproveTerraform");
  const btnApply = document.getElementById("btnApplyTerraform");
  const helperText = document.getElementById("tfApplyHelperText");

  chkApprove.addEventListener("change", (e) => {
    const isApproved = e.target.checked;
    if (isApproved) {
      if (activePlanId) {
        btnApply.disabled = false;
        helperText.textContent = "Plan approved by engineer. Ready for execution.";
        helperText.className = "text-[11px] text-emerald-400 font-medium";
      } else {
        btnApply.disabled = true;
        helperText.textContent = "Cannot approve: No valid Terraform plan artifact found for this run.";
        helperText.className = "text-[11px] text-rose-400 font-medium";
      }
    } else {
      btnApply.disabled = true;
      helperText.textContent = activePlanId
        ? `Plan approval required to enable apply.`
        : "Approval checkbox required to enable apply.";
      helperText.className = "text-[11px] text-slate-500";
    }
  });
}

function setMode(mode, triggerPipeline = true) {
  currentMode = mode;
  const liveBtn = document.getElementById("modeLiveBtn");
  const demoBtn = document.getElementById("modeDemoBtn");
  const liveDot = document.getElementById("liveDot");
  const demoDot = document.getElementById("demoDot");
  const liveBanner = document.getElementById("liveModeBanner");
  const demoBanner = document.getElementById("demoModeBanner");
  const targetPill = document.getElementById("targetAccountPill");
  const scenarioSelect = document.getElementById("scenarioSelect");
  const pipelineBtnText = document.getElementById("pipelineBtnText");
  const headerStatus = document.getElementById("headerLiveStatus");

  if (mode === "live") {
    // Live AWS button styling
    liveBtn.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition bg-blue-600 text-white shadow-sm shadow-blue-500/30";
    demoBtn.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200 transition";
    liveDot.classList.remove("hidden");
    demoDot.classList.add("hidden");

    // Banner visibility
    liveBanner.classList.remove("hidden");
    demoBanner.classList.add("hidden");

    // Controls
    targetPill.classList.remove("hidden");
    scenarioSelect.classList.add("hidden");
    pipelineBtnText.textContent = "⚡ Run Live AWS Pipeline";
    headerStatus.textContent = "v1.0 Live AWS";
    headerStatus.className = "px-2 py-0.5 text-xs font-semibold rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20";
  } else {
    // Demo button styling
    demoBtn.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition bg-amber-600 text-white shadow-sm shadow-amber-500/30";
    liveBtn.className = "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200 transition";
    demoDot.classList.remove("hidden");
    liveDot.classList.add("hidden");

    // Banner visibility
    demoBanner.classList.remove("hidden");
    liveBanner.classList.add("hidden");

    // Controls
    targetPill.classList.add("hidden");
    scenarioSelect.classList.remove("hidden");
    pipelineBtnText.textContent = "⚡ Run Demo Pipeline";
    headerStatus.textContent = "v1.0 Demo Mode";
    headerStatus.className = "px-2 py-0.5 text-xs font-semibold rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20";
  }

  if (triggerPipeline) {
    executePipeline();
  }
}

async function refreshAwsStatusAndResources() {
  const refreshIcon = document.getElementById("refreshIcon");
  refreshIcon.classList.add("animate-spin");

  try {
    // 1. Fetch AWS connection status
    const statusRes = await fetch("/api/aws/status");
    if (statusRes.ok) {
      currentAwsStatus = await statusRes.json();
      renderAwsConnection(currentAwsStatus);
    }

    // 2. Fetch live AWS resources inventory
    const resRes = await fetch("/api/aws/resources");
    if (resRes.ok) {
      currentAwsResources = await resRes.json();
      renderAwsResources(currentAwsResources);
    }
  } catch (err) {
    console.error("Error refreshing AWS status:", err);
  } finally {
    refreshIcon.classList.remove("animate-spin");
  }
}

function renderAwsConnection(data) {
  const badge = document.getElementById("awsConnectionBadge");
  const stateText = document.getElementById("connStateText");
  const acctText = document.getElementById("connAccountText");
  const regionText = document.getElementById("connRegionText");
  const arnText = document.getElementById("connArnText");
  const targetText = document.getElementById("targetAccountText");
  const bannerRegion = document.getElementById("bannerRegionName");
  const servicesList = document.getElementById("awsServicesList");
  const ceNotice = document.getElementById("costExplorerNotice");
  const errNotice = document.getElementById("awsErrorNotice");
  const errNoticeText = document.getElementById("awsErrorNoticeText");

  const isConnected = data.status === "CONNECTED";
  const region = data.region || "ap-southeast-2";
  const acct = data.account_id || "N/A";
  const arn = data.arn || "N/A";

  // Update text values
  stateText.textContent = data.status || "UNKNOWN";
  acctText.textContent = acct;
  regionText.textContent = region;
  arnText.textContent = arn;
  arnText.title = arn;
  bannerRegion.textContent = region;
  targetText.textContent = isConnected ? `AWS: ${acct} (${region})` : `AWS: ${data.status}`;

  // Badge styling
  if (isConnected) {
    badge.textContent = "CONNECTED";
    badge.className = "px-2.5 py-1 rounded-full text-xs font-bold font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30";
    stateText.className = "text-emerald-400 font-bold text-sm";
    errNotice.classList.add("hidden");
  } else if (data.status === "CREDENTIALS_MISSING") {
    badge.textContent = "CREDENTIALS MISSING";
    badge.className = "px-2.5 py-1 rounded-full text-xs font-bold font-mono bg-amber-500/10 text-amber-400 border border-amber-500/30";
    stateText.className = "text-amber-400 font-bold text-sm";
    errNotice.classList.remove("hidden");
    errNoticeText.textContent = "Live AWS unavailable: AWS credentials are missing or not discovered in standard chain (~/.aws/credentials or environment variables).";
  } else {
    badge.textContent = data.status;
    badge.className = "px-2.5 py-1 rounded-full text-xs font-bold font-mono bg-rose-500/10 text-rose-400 border border-rose-500/30";
    stateText.className = "text-rose-400 font-bold text-sm";
    errNotice.classList.remove("hidden");
    errNoticeText.textContent = `AWS Connection issue: ${data.summary || "Authentication or permission check failed."}`;
  }

  // Render individual services
  const services = data.services || {};
  let ceAvailable = true;
  let servicesHtml = "";

  const serviceKeys = [
    { key: "ec2", label: "EC2" },
    { key: "cloudwatch", label: "CloudWatch" },
    { key: "s3", label: "S3" },
    { key: "bedrock", label: "Bedrock" },
    { key: "cost_explorer", label: "Cost Explorer" },
  ];

  serviceKeys.forEach(({ key, label }) => {
    const sInfo = services[key] || { status: "UNKNOWN", message: "" };
    let statusPill = "";

    if (sInfo.status === "CONNECTED") {
      statusPill = `<span class="text-emerald-400 font-bold flex items-center gap-1">✓ OK</span>`;
    } else if (sInfo.status === "NOT_AVAILABLE") {
      statusPill = `<span class="text-amber-400 font-bold flex items-center gap-1" title="${escapeHtml(sInfo.message)}">⚠ UNAVAIL</span>`;
      if (key === "cost_explorer") ceAvailable = false;
    } else if (sInfo.status === "NO_PERMISSION") {
      statusPill = `<span class="text-rose-400 font-bold flex items-center gap-1" title="${escapeHtml(sInfo.message)}">✗ NO PERM</span>`;
    } else {
      statusPill = `<span class="text-slate-500 font-bold" title="${escapeHtml(sInfo.message)}">${sInfo.status}</span>`;
    }

    servicesHtml += `
      <div class="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 flex items-center justify-between" title="${escapeHtml(sInfo.message || '')}">
        <span class="text-slate-300 font-medium">${label}</span>
        ${statusPill}
      </div>
    `;
  });

  servicesList.innerHTML = servicesHtml;

  // Cost Explorer notice
  if (!ceAvailable) {
    ceNotice.classList.remove("hidden");
  } else {
    ceNotice.classList.add("hidden");
  }
}

function renderAwsResources(data) {
  const counts = data.resource_counts || { ec2: 0, ebs: 0, eip: 0, lambda: 0, s3: 0, total: 0 };
  const countEc2 = counts.ec2 || 0;
  const countEbs = counts.ebs || 0;
  const countEip = counts.eip || 0;
  const countLambda = counts.lambda || 0;
  const countS3 = counts.s3 || 0;
  const countTotal = counts.total || (countEc2 + countEbs + countEip + countLambda + countS3);

  document.getElementById("countEc2").textContent = countEc2;
  document.getElementById("countEbs").textContent = countEbs;
  document.getElementById("countEip").textContent = countEip;
  document.getElementById("countLambda").textContent = countLambda;
  document.getElementById("countS3").textContent = countS3;
  document.getElementById("countTotal").textContent = countTotal;

  const zeroNotice = document.getElementById("zeroResourcesNotice");
  if (countTotal === 0 && data.status === "CONNECTED") {
    zeroNotice.classList.remove("hidden");
  } else {
    zeroNotice.classList.add("hidden");
  }

  // Real AWS badge indicator
  const badge = document.getElementById("realAwsBadge");
  if (data.is_real_aws) {
    badge.textContent = "is_real_aws: true";
    badge.className = "px-2.5 py-1 rounded-full text-xs font-bold font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30";
  } else {
    badge.textContent = "is_real_aws: false";
    badge.className = "px-2.5 py-1 rounded-full text-xs font-bold font-mono bg-slate-800 text-slate-400 border border-slate-700";
  }
}

async function executePipeline() {
  const btn = document.getElementById("runPipelineBtn");
  const spinner = document.getElementById("pipelineSpinner");
  const btnText = document.getElementById("pipelineBtnText");

  btn.disabled = true;
  spinner.classList.remove("hidden");
  const originalText = currentMode === "live" ? "⚡ Run Live AWS Pipeline" : "⚡ Run Demo Pipeline";
  btnText.textContent = "Executing Pipeline...";

  try {
    let payload = {};
    if (currentMode === "live") {
      payload = { use_live_aws: true };
    } else {
      const scenario = document.getElementById("scenarioSelect").value || "enterprise";
      payload = { scenario: scenario, use_live_aws: false };
    }

    const res = await fetch("/api/pipeline/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: "Pipeline execution failed" }));
      alert(`Pipeline error: ${errData.detail || "Request failed"}`);
      return;
    }

    const result = await res.json();
    if (result.status === "SUCCESS" || result.report) {
      currentReport = result.report;
      renderAllModules(currentReport);
    }
  } catch (err) {
    console.error("Pipeline run failed:", err);
    alert(`Error executing pipeline: ${err.message}`);
  } finally {
    btn.disabled = false;
    spinner.classList.add("hidden");
    btnText.textContent = originalText;
  }
}

function renderAllModules(report) {
  // 1. Executive Metrics
  const monthlySav = typeof report.total_monthly_savings === "number" ? report.total_monthly_savings : null;
  const annualSav = typeof report.total_annualized_savings === "number" ? report.total_annualized_savings : null;
  const carbonSav = typeof report.total_carbon_savings_kg === "number" ? report.total_carbon_savings_kg : null;
  const wasteCount = Array.isArray(report.waste_findings) ? report.waste_findings.length : 0;
  const currentCost = typeof report.total_current_monthly_cost === "number" ? report.total_current_monthly_cost : null;
  const optCost = typeof report.total_optimized_monthly_cost === "number" ? report.total_optimized_monthly_cost : null;

  document.getElementById("metricMonthlySavings").textContent = monthlySav !== null ? `$${monthlySav.toFixed(2)}` : "N/A";
  document.getElementById("metricAnnualSavings").textContent = annualSav !== null ? `$${annualSav.toFixed(2)}` : "N/A";
  document.getElementById("metricWasteCount").textContent = wasteCount;
  document.getElementById("metricCarbonSavings").textContent = carbonSav !== null ? `${carbonSav.toFixed(1)} kg` : "N/A";

  if (currentCost !== null && currentCost > 0 && monthlySav !== null) {
    const savingsRate = ((monthlySav / currentCost) * 100).toFixed(1);
    document.getElementById("metricMonthlySavingsRate").textContent = `${savingsRate}%`;
  } else if (currentCost === 0) {
    document.getElementById("metricMonthlySavingsRate").textContent = "0%";
  } else {
    document.getElementById("metricMonthlySavingsRate").textContent = "N/A";
  }

  const critCount = (report.waste_findings || []).filter(w => w.severity === "CRITICAL").length;
  document.getElementById("metricSeverityPill").textContent = `${critCount} Critical`;

  document.getElementById("savingsBadge").textContent = monthlySav !== null ? `-$${monthlySav.toFixed(2)} / mo` : "N/A";
  document.getElementById("currSpendText").textContent = currentCost !== null ? `$${currentCost.toFixed(2)}` : "N/A";
  document.getElementById("optSpendText").textContent = optCost !== null ? `$${optCost.toFixed(2)}` : "N/A";

  const wasteSub = document.getElementById("wasteSubtext");
  if (wasteCount === 0) {
    wasteSub.textContent = "Zero cloud waste detected in scanned infrastructure";
  } else {
    wasteSub.textContent = "Unattached EBS, idle Lambdas & oversized VMs";
  }

  // Update Charts
  updateCharts(report, currentCost, optCost);

  // Map cost findings by finding_id for direct lookups in modules 2 and 4
  const costMap = new Map((report.cost_findings || []).map(c => [c.finding_id, c]));

  // Render Module 1: Monitoring
  renderModule1(report.monitored_resources || []);

  // Render Module 2: Waste Detection
  renderModule2(report.waste_findings || [], costMap);

  // Render Module 3: Cost Estimation
  renderModule3(report.cost_findings || []);

  // Render Module 4: Google Gemini AI
  renderModule4(report.ai_recommendations || [], costMap);

  // Render Module 5: Storage & Audit
  renderModule5(report);

  // Render Module 6: Terraform Patches & Plan
  activePlanId = report.terraform_plan_id || "";
  renderModule6(report.terraform_patches || [], report);

  // Render Module 7: GitOps Review
  renderModule7(report.gitops_pr);
}

function updateCharts(report, currentCost, optCost) {
  if (!donutChart || !barChart) return;

  let comp = 0, stor = 0, serv = 0, net = 0;
  (report.waste_findings || []).forEach(f => {
    if (f.resource_type === "EC2") comp++;
    else if (f.resource_type === "EBS") stor++;
    else if (f.resource_type === "LAMBDA") serv++;
    else net++;
  });

  const totalWaste = comp + stor + serv + net;
  const overlay = document.getElementById("emptyWasteChartOverlay");
  const legendContainer = document.getElementById("donutLegend");

  if (totalWaste === 0) {
    donutChart.data.datasets[0].data = [1];
    donutChart.data.datasets[0].backgroundColor = ["#334155"];
    donutChart.update();
    overlay.classList.remove("hidden");
    legendContainer.innerHTML = `
      <div class="col-span-2 text-center text-xs text-slate-400">All scanned resources are optimal.</div>
    `;
  } else {
    overlay.classList.add("hidden");
    donutChart.data.datasets[0].data = [comp, stor, serv, net];
    donutChart.data.datasets[0].backgroundColor = ["#f59e0b", "#3b82f6", "#a855f7", "#14b8a6"];
    donutChart.update();
    legendContainer.innerHTML = `
      <div class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-amber-500"></span> Compute (${comp})</div>
      <div class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-blue-500"></span> Storage (${stor})</div>
      <div class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-purple-500"></span> Serverless (${serv})</div>
      <div class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-teal-500"></span> Network (${net})</div>
    `;
  }

  barChart.data.datasets[0].data = [
    typeof currentCost === "number" ? currentCost : 0,
    typeof optCost === "number" ? optCost : 0
  ];
  barChart.update();
}

function renderModule1(resources) {
  document.getElementById("monitoredCountBadge").textContent = `${resources.length} Resources`;
  const tbody = document.getElementById("monitoringTableBody");

  if (!resources.length) {
    const region = (currentAwsStatus && currentAwsStatus.region) || "ap-southeast-2";
    const acct = (currentAwsStatus && currentAwsStatus.account_id) || "";
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="py-8 text-center text-slate-400">
          <div class="flex flex-col items-center justify-center gap-2">
            <span class="text-2xl">☁️</span>
            <span class="font-medium text-slate-300">0 Resources Discovered</span>
            <span class="text-xs text-slate-500">No supported EC2, EBS, EIP, Lambda, or S3 resources currently exist in account ${acct} (${region}).</span>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = resources.map(r => {
    const specsStr = Object.entries(r.specs || {})
      .map(([k, v]) => `<span class="text-slate-400">${escapeHtml(k)}:</span> <span class="text-slate-200">${escapeHtml(v)}</span>`)
      .join(" &bull; ");
    
    const tagsStr = Object.entries(r.tags || {})
      .map(([k, v]) => `<span class="bg-slate-800 text-[10px] px-1.5 py-0.5 rounded text-slate-400 font-mono">${escapeHtml(k)}=${escapeHtml(v)}</span>`)
      .join(" ");

    let metricHighlight = "";
    if (r.resource_type === "EC2") {
      const avg = typeof r.metrics.cpu_utilization_avg === "number" ? r.metrics.cpu_utilization_avg : null;
      const max = typeof r.metrics.cpu_utilization_max === "number" ? r.metrics.cpu_utilization_max : null;
      if (avg !== null) {
        const color = avg < 10 ? "text-amber-400" : "text-emerald-400";
        metricHighlight = `CPU: <strong class="${color}">${avg}%</strong> (Peak: ${max !== null ? max + '%' : 'N/A'})`;
      } else {
        metricHighlight = `<span class="text-slate-400">Telemetry collecting</span>`;
      }
    } else if (r.resource_type === "EBS") {
      const days = typeof r.metrics.days_unattached === "number" ? r.metrics.days_unattached : null;
      if (days !== null) {
        metricHighlight = `<span class="text-rose-400 font-bold">${days} days unattached</span>`;
      } else {
        metricHighlight = `<span class="text-amber-400 font-bold">Unattached (No active I/O)</span>`;
      }
    } else if (r.resource_type === "LAMBDA") {
      const invocations = typeof r.metrics.invocations === "number" ? r.metrics.invocations : 0;
      const lastInv = r.metrics.last_invoked_days_ago != null ? `${r.metrics.last_invoked_days_ago}d ago` : "N/A";
      metricHighlight = `<span class="text-purple-400 font-bold">${invocations} invocations</span> (Last: ${lastInv})`;
    } else {
      metricHighlight = `<span class="text-teal-400">Idle allocation</span>`;
    }

    return `
      <tr class="hover:bg-slate-900/40 transition">
        <td class="py-3 px-4 font-mono font-bold text-white">
          ${escapeHtml(r.name || r.id)}
          <div class="text-[10px] text-slate-500 font-normal">${escapeHtml(r.id)}</div>
        </td>
        <td class="py-3 px-4">
          <span class="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-800 text-slate-300">${escapeHtml(r.resource_type)}</span>
        </td>
        <td class="py-3 px-4">
          <span class="inline-flex items-center gap-1 text-[11px] font-medium ${r.state === 'running' || r.state === 'active' ? 'text-emerald-400' : 'text-amber-400'}">
            <span class="w-1.5 h-1.5 rounded-full ${r.state === 'running' || r.state === 'active' ? 'bg-emerald-400' : 'bg-amber-400'}"></span>
            ${escapeHtml(r.state)}
          </span>
        </td>
        <td class="py-3 px-4 text-slate-300 font-mono">${specsStr || '<span class="text-slate-600">Standard</span>'}</td>
        <td class="py-3 px-4 font-mono">${metricHighlight}</td>
        <td class="py-3 px-4">${tagsStr || '<span class="text-slate-600 font-mono">none</span>'}</td>
      </tr>
    `;
  }).join("");
}

function renderModule2(findings, costMap) {
  document.getElementById("wasteCountBadge").textContent = `${findings.length} Findings`;
  const container = document.getElementById("wasteFindingsContainer");

  if (!findings.length) {
    container.innerHTML = `
      <div class="col-span-1 md:col-span-2 p-8 text-center rounded-xl bg-slate-900/60 border border-slate-800 text-slate-400">
        <div class="text-2xl mb-1">✅</div>
        <div class="font-bold text-white text-sm mb-1">No Waste Detected</div>
        <div class="text-xs text-slate-400">All scanned resources comply with FinOps efficiency guidelines. Zero idle, unattached, or oversized assets.</div>
      </div>
    `;
    return;
  }

  container.innerHTML = findings.map(f => {
    const sevColor = f.severity === "CRITICAL"
      ? "bg-rose-500/10 text-rose-400 border-rose-500/20"
      : f.severity === "HIGH"
      ? "bg-orange-500/10 text-orange-400 border-orange-500/20"
      : "bg-amber-500/10 text-amber-400 border-amber-500/20";

    const cost = costMap instanceof Map ? costMap.get(f.id) : null;
    let savingsVal = null;
    if (cost && typeof cost.monthly_savings === "number") {
      savingsVal = cost.monthly_savings;
    } else if (typeof f.estimated_monthly_savings === "number") {
      savingsVal = f.estimated_monthly_savings;
    } else if (typeof f.estimated_monthly_waste === "number") {
      savingsVal = f.estimated_monthly_waste;
    }

    const savingsBadge = savingsVal !== null
      ? `<span class="text-xs font-mono font-bold text-emerald-400 shrink-0">-$${savingsVal.toFixed(2)}/mo</span>`
      : `<span class="text-xs font-mono text-slate-500 shrink-0">Cost pending</span>`;

    const confDisplay = typeof f.confidence_score === "number"
      ? `${(f.confidence_score * 100).toFixed(0)}% Conf.`
      : "N/A";

    return `
      <div class="glass-card rounded-xl p-4 border border-slate-800 hover:border-slate-700 transition space-y-3">
        <div class="flex items-start justify-between gap-2">
          <div>
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${sevColor}">${escapeHtml(f.severity || "INFO")}</span>
              <span class="font-mono text-xs text-white font-bold">${escapeHtml(f.resource_name || f.resource_id || "Unknown Resource")}</span>
              <span class="text-[10px] font-mono text-slate-400">(${escapeHtml(f.resource_type || "AWS")})</span>
            </div>
            <p class="text-xs text-slate-300 mt-1 leading-relaxed">${escapeHtml(f.description || f.rule_description || "Potential cloud inefficiency identified.")}</p>
          </div>
          ${savingsBadge}
        </div>
        <div class="bg-slate-950 p-2.5 rounded-lg border border-slate-800/80 text-[11px] font-mono text-slate-400 space-y-1">
          <div><span class="text-slate-500">Resource ID:</span> <span class="text-slate-300">${escapeHtml(f.resource_id || "N/A")}</span></div>
          <div><span class="text-slate-500">Category:</span> <span class="text-slate-300">${escapeHtml(f.waste_category || f.category || "GENERAL_WASTE")}</span> &bull; <span class="text-emerald-400">${confDisplay}</span></div>
          <div><span class="text-slate-500">Current Specs:</span> <span class="text-slate-300">${escapeHtml(f.current_specs || "Standard")}</span></div>
          <div><span class="text-slate-500">Remediation:</span> <span class="text-amber-400">${escapeHtml(f.recommended_specs || f.remediation_action || "Manual inspection")}</span></div>
        </div>
      </div>
    `;
  }).join("");
}

function renderModule3(costs) {
  const tbody = document.getElementById("costTableBody");

  if (!costs.length) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="py-8 text-center text-slate-400">
          <div class="text-slate-300 font-medium">Zero Cost Inefficiencies Found</div>
          <div class="text-xs text-slate-500 mt-1">Cloud infrastructure requires no SKU downsizing or volume deletions.</div>
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = costs.map(c => {
    const currCostStr = typeof c.current_monthly_cost === "number" ? `$${c.current_monthly_cost.toFixed(2)}` : "N/A";
    const optCostStr = typeof c.optimized_monthly_cost === "number" ? `$${c.optimized_monthly_cost.toFixed(2)}` : "N/A";
    const savingsStr = typeof c.monthly_savings === "number" ? `-$${c.monthly_savings.toFixed(2)}` : "N/A";
    const carbonStr = typeof c.carbon_savings_kg_co2e === "number" ? `-${c.carbon_savings_kg_co2e.toFixed(1)} kg` : "N/A";

    return `
      <tr class="hover:bg-slate-900/40 transition">
        <td class="py-3 px-4 font-mono font-bold text-white">${escapeHtml(c.resource_name || c.resource_id || "Unknown")}</td>
        <td class="py-3 px-4"><span class="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-800 text-slate-300">${escapeHtml(c.resource_type || c.category || "AWS")}</span></td>
        <td class="py-3 px-4 font-mono text-slate-400 text-[11px]">${escapeHtml(c.pricing_breakdown || c.pricing_basis || "")}</td>
        <td class="py-3 px-4 font-mono text-rose-400">${currCostStr}</td>
        <td class="py-3 px-4 font-mono text-emerald-400">${optCostStr}</td>
        <td class="py-3 px-4 font-mono font-bold text-emerald-400">${savingsStr}</td>
        <td class="py-3 px-4 font-mono text-teal-400">${carbonStr}</td>
      </tr>
    `;
  }).join("");
}

function renderModule4(recommendations, costMap) {
  const container = document.getElementById("aiRecommendationsContainer");

  if (!recommendations.length) {
    const errMsg = currentReport ? (currentReport.ai_error || currentReport.bedrock_error) : null;
    if (currentReport && errMsg) {
      const errStatus = currentReport.ai_status || currentReport.bedrock_status || "UNAVAILABLE";
      const count = Array.isArray(currentReport.waste_findings) ? currentReport.waste_findings.length : 0;
      container.innerHTML = `
        <div class="p-6 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200 space-y-3">
          <div class="flex items-center gap-2 font-bold text-amber-300">
            <svg class="w-5 h-5 shrink-0 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
            <span class="text-sm font-sans">Google Gemini AI Advisory Notice: ${escapeHtml(errStatus)}</span>
          </div>
          <p class="text-xs leading-relaxed font-mono bg-slate-950/60 p-3 rounded-lg border border-slate-800 text-slate-300">${escapeHtml(errMsg)}</p>
          <p class="text-xs text-slate-400">
            The pipeline evaluated the infrastructure and identified ${count} waste item(s).
            Google Gemini generative AI recommendations are paused because GEMINI_API_KEY is not configured or lacks permission.
            Resource monitoring telemetry, cost modeling, and Terraform remediation remain fully active.
          </p>
        </div>
      `;
      return;
    }

    container.innerHTML = `
      <div class="p-8 text-center rounded-xl bg-slate-900/60 border border-slate-800 text-slate-400 space-y-1">
        <div class="text-2xl mb-1">🤖</div>
        <div class="font-bold text-white text-sm">No Recommendations Required</div>
        <div class="text-xs text-slate-400">Google Gemini advisor audited the environment and confirmed zero waste findings.</div>
      </div>
    `;
    return;
  }

  container.innerHTML = recommendations.map(rec => {
    const riskStr = (rec.risk_level || "Low Risk").toUpperCase();
    const riskColor = riskStr.includes("LOW")
      ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
      : riskStr.includes("HIGH")
      ? "text-rose-400 bg-rose-500/10 border-rose-500/20"
      : "text-amber-400 bg-amber-500/10 border-amber-500/20";

    const cost = costMap instanceof Map ? costMap.get(rec.finding_id) : null;
    let savingsVal = null;
    if (cost && typeof cost.monthly_savings === "number") {
      savingsVal = cost.monthly_savings;
    } else if (typeof rec.estimated_monthly_savings === "number") {
      savingsVal = rec.estimated_monthly_savings;
    }

    const savingsBadge = savingsVal !== null
      ? `<span class="text-xs font-mono font-bold text-emerald-400 shrink-0">-$${savingsVal.toFixed(2)}/mo</span>`
      : `<span class="text-xs font-mono text-slate-500 shrink-0">N/A</span>`;

    const rationale = rec.rationale || rec.technical_rationale || "Optimization recommendation grounded on CloudWatch utilization metrics.";
    const summary = rec.executive_summary || rec.impact_analysis || "Reduces provisioned infrastructure capacity without service interruption.";
    const rollback = rec.rollback_plan || rec.rollback_procedure || "Revert GitOps pull request or redeploy prior Terraform configuration.";
    const steps = Array.isArray(rec.steps_to_remediate) ? rec.steps_to_remediate : [];

    const stepsHtml = steps.length ? `
      <div class="mt-2.5 pt-2 border-t border-slate-800/60">
        <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Prescriptive Remediation Steps</span>
        <ul class="list-disc list-inside text-slate-300 text-[11px] space-y-0.5 font-mono">
          ${steps.map(s => `<li>${escapeHtml(s)}</li>`).join("")}
        </ul>
      </div>
    ` : "";

    return `
      <div class="glass-card rounded-xl p-5 border border-slate-800 space-y-3">
        <div class="flex items-start justify-between gap-3">
          <div>
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${riskColor}">${escapeHtml(rec.risk_level || "Low Risk")}</span>
              <h3 class="font-bold text-white text-sm">${escapeHtml(rec.title || "Remediation Recommendation")}</h3>
            </div>
            <p class="text-xs text-slate-300 mt-1.5 leading-relaxed">${escapeHtml(rationale)}</p>
          </div>
          ${savingsBadge}
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs bg-slate-950 p-3 rounded-lg border border-slate-800/80">
          <div>
            <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Impact Analysis &amp; Summary</span>
            <p class="text-slate-300 text-[11px]">${escapeHtml(summary)}</p>
          </div>
          <div>
            <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Zero-Downtime Rollback Procedure</span>
            <p class="text-slate-400 text-[11px] font-mono">${escapeHtml(rollback)}</p>
          </div>
        </div>
        ${stepsHtml}
      </div>
    `;
  }).join("");
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
      tbody.innerHTML = records.map(rec => {
        const savDisplay = typeof rec.monthly_savings === "number" ? `$${rec.monthly_savings.toFixed(2)}` : "N/A";
        return `
          <tr class="hover:bg-slate-900 transition">
            <td class="p-2 text-slate-300 font-mono">${escapeHtml((rec.run_id || "").substring(0, 18))}...</td>
            <td class="p-2 text-rose-400 font-mono">${rec.total_findings || 0} items</td>
            <td class="p-2 text-emerald-400 font-bold font-mono">${savDisplay}</td>
            <td class="p-2"><span class="px-1.5 py-0.5 rounded text-[10px] bg-blue-500/10 text-blue-400 font-mono">${escapeHtml(rec.gitops_status || "N/A")}</span></td>
          </tr>
        `;
      }).join("");
    })
    .catch(() => {});
}

function renderModule6(patches, report) {
  document.getElementById("patchCountBadge").textContent = `${patches.length} Patches`;
  const viewer = document.getElementById("terraformDiffViewer");
  const planBadge = document.getElementById("tfPlanStatusBadge");
  const chkApprove = document.getElementById("chkApproveTerraform");
  const btnApply = document.getElementById("btnApplyTerraform");
  const helperText = document.getElementById("tfApplyHelperText");

  // Reset checkboxes
  chkApprove.checked = false;
  btnApply.disabled = true;

  const planId = (report && report.terraform_plan_id) ? report.terraform_plan_id : activePlanId;
  const planStatus = (report && report.terraform_plan_status) ? report.terraform_plan_status : "PLAN_READY";
  activePlanId = planId || "";

  if (!patches.length) {
    viewer.textContent = "# No Terraform modifications required. Infrastructure matches desired state.";
    planBadge.textContent = "NO_CHANGES_REQUIRED";
    planBadge.className = "text-[11px] font-mono text-slate-400 bg-slate-800 px-2 py-0.5 rounded border border-slate-700";
    if (helperText) {
      helperText.textContent = "No modifications to apply.";
      helperText.className = "text-[11px] text-slate-500";
    }
    return;
  }

  if (activePlanId) {
    planBadge.textContent = `${planStatus}: ${activePlanId}`;
    planBadge.className = "text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20";
    if (helperText) {
      helperText.textContent = `Plan ${activePlanId} ready for review. Approval checkbox required to enable apply.`;
      helperText.className = "text-[11px] text-slate-400";
    }
  } else {
    planBadge.textContent = "NO_PLAN_ARTIFACT";
    planBadge.className = "text-[11px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20";
    if (helperText) {
      helperText.textContent = "Plan artifact missing. Run analysis to create a validated plan.";
      helperText.className = "text-[11px] text-amber-400";
    }
  }

  let html = "";
  patches.forEach(p => {
    const lines = p.unified_diff.split("\n");
    lines.forEach(line => {
      if (line.startsWith("---") || line.startsWith("+++") || line.startsWith("@@")) {
        html += `<span class="diff-header">${escapeHtml(line)}</span>\n`;
      } else if (line.startsWith("-")) {
        html += `<span class="diff-del">${escapeHtml(line)}</span>\n`;
      } else if (line.startsWith("+")) {
        html += `<span class="diff-add">${escapeHtml(line)}</span>\n`;
      } else {
        html += `<span>${escapeHtml(line)}</span>\n`;
      }
    });
  });

  viewer.innerHTML = html;
}

async function applyTerraformPlan() {
  const chkApprove = document.getElementById("chkApproveTerraform");
  const chkDestructive = document.getElementById("chkConfirmDestructive");
  const resultBox = document.getElementById("tfApplyResultBox");
  const btn = document.getElementById("btnApplyTerraform");
  const helperText = document.getElementById("tfApplyHelperText");
  const planBadge = document.getElementById("tfPlanStatusBadge");

  if (!chkApprove.checked) {
    alert("Explicit human approval is required before running terraform apply.");
    return;
  }

  if (!activePlanId) {
    resultBox.classList.remove("hidden");
    resultBox.innerHTML = `
      <div class="text-rose-400 font-bold mb-1">✗ Terraform apply stopped by safety gate:</div>
      <div class="text-slate-300">Status: PLAN_NOT_FOUND</div>
      <div class="text-rose-300 mt-1">Terraform plan not found or expired. A valid plan artifact must be generated and approved before apply can execute.</div>
    `;
    return;
  }

  btn.disabled = true;
  btn.textContent = "Applying Plan...";
  resultBox.classList.remove("hidden");
  resultBox.innerHTML = `<span class="text-slate-400">Executing terraform apply for plan ${escapeHtml(activePlanId)} with explicit approval...</span>`;

  try {
    const res = await fetch("/api/terraform/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan_id: activePlanId,
        approved: true,
        confirm_destructive: chkDestructive.checked,
        reviewer: "Authorized Lead FinOps Engineer",
        use_live_aws: currentMode === "live"
      })
    });

    const data = await res.json();
    if (data.success) {
      resultBox.innerHTML = `
        <div class="text-emerald-400 font-bold mb-1">✓ Terraform apply completed successfully!</div>
        <div class="text-slate-300">Status: ${data.status}</div>
        <div class="text-slate-400 mt-1">${escapeHtml(data.stdout || "Cloud resources synchronized.")}</div>
      `;
      planBadge.textContent = "PLAN_APPLIED";
      planBadge.className = "text-[11px] font-mono text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20";
      chkApprove.checked = false;
      btn.disabled = true;
      if (helperText) {
        helperText.textContent = "Plan applied successfully. Cloud state synchronized.";
        helperText.className = "text-[11px] text-blue-400";
      }
      activePlanId = "";
    } else {
      resultBox.innerHTML = `
        <div class="text-rose-400 font-bold mb-1">✗ Terraform apply stopped by safety gate:</div>
        <div class="text-slate-300">Status: ${data.status}</div>
        <div class="text-rose-300 mt-1">${escapeHtml(data.stderr || (data.errors || []).join(", ") || "Safety validation failed")}</div>
      `;
    }
  } catch (err) {
    resultBox.innerHTML = `<span class="text-rose-400">Error: ${err.message}</span>`;
  } finally {
    if (activePlanId) {
      btn.disabled = false;
      btn.textContent = "🚀 Execute Approved Terraform Apply";
    }
  }
}

function renderModule7(pr) {
  const quickPRStatus = document.getElementById("quickPRStatus");
  const quickPRDesc = document.getElementById("quickPRDesc");
  const quickBranch = document.getElementById("quickBranchName");
  const badge = document.getElementById("prStatusBadge");
  const title = document.getElementById("prTitle");
  const meta = document.getElementById("prMetaHeader");
  const checksList = document.getElementById("prChecksList");
  const auditDiv = document.getElementById("prAuditTrail");

  if (!pr) {
    quickPRStatus.textContent = "NO PR NEEDED";
    quickPRDesc.textContent = "Zero cloud waste detected. Environment is optimal.";
    quickBranch.textContent = "none";
    badge.textContent = "OPTIMAL";
    badge.className = "px-2.5 py-1 rounded-full text-xs font-bold font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30";
    title.textContent = "No Pull Request Required";
    meta.innerHTML = `<span class="text-slate-400 font-mono">Infrastructure contains 0 inefficiencies.</span>`;
    checksList.innerHTML = `<div class="col-span-3 p-3 text-center text-xs text-slate-400 bg-slate-950 rounded-lg">Zero changes proposed. CI/CD checks skipped.</div>`;
    auditDiv.innerHTML = `<div class="text-slate-500">No active audit trail for clean state.</div>`;
    return;
  }

  quickPRStatus.textContent = pr.status;
  quickPRDesc.textContent = `PR #${pr.pr_number}: ${pr.title}`;
  quickBranch.textContent = pr.branch_name;

  badge.textContent = pr.status;
  if (pr.status === "MERGED") {
    badge.className = "px-2.5 py-1 rounded-full text-xs font-bold font-mono bg-purple-500/20 text-purple-300 border border-purple-500/30";
  } else if (pr.status === "APPROVED") {
    badge.className = "px-2.5 py-1 rounded-full text-xs font-bold font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
  } else {
    badge.className = "px-2.5 py-1 rounded-full text-xs font-bold font-mono bg-blue-500/20 text-blue-300 border border-blue-500/30";
  }

  title.textContent = pr.title;
  meta.innerHTML = `#PR-${pr.pr_number} on branch <span class="text-amber-400 font-mono">${escapeHtml(pr.branch_name)}</span> &rarr; <span class="text-slate-300 font-mono">main</span>`;

  checksList.innerHTML = (pr.checks || []).map(c => {
    const isSuccess = c.status === "SUCCESS";
    const icon = isSuccess ? "✅" : "⏳";
    const color = isSuccess ? "text-emerald-400" : "text-amber-400";
    return `
      <div class="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
        <div class="flex items-center justify-between">
          <span class="text-slate-300 font-semibold">${icon} ${escapeHtml(c.name)}</span>
          <span class="${color} font-bold">${c.status}</span>
        </div>
        <p class="text-[10px] text-slate-500 mt-1">${escapeHtml(c.details || '')}</p>
      </div>
    `;
  }).join("");

  auditDiv.innerHTML = (pr.audit_trail || []).map(msg => `<div>${escapeHtml(msg)}</div>`).join("");
}

async function approveCurrentPR() {
  if (!currentReport || !currentReport.gitops_pr) {
    alert("No pull request is currently active.");
    return;
  }
  const prId = currentReport.gitops_pr.pr_id;
  try {
    const res = await fetch(`/api/gitops/pr/${prId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewer: "Lead FinOps Engineer" })
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

function switchTab(modId) {
  const buttons = document.querySelectorAll("#modulePipelineNav .nav-step");
  buttons.forEach(b => b.classList.remove("active"));
  
  const activeBtn = document.querySelector(`#modulePipelineNav [data-tab="${modId}"]`);
  if (activeBtn) {
    activeBtn.classList.add("active");
  }

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
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
