// DOM Elements
const activeStockNameEl = document.getElementById("active-stock-name");
const tagInputEl = document.getElementById("tag-input");
const tagsBadgeListEl = document.getElementById("tags-badge-list");
const basePriceEl = document.getElementById("base-price");
const baseQtyEl = document.getElementById("base-qty");
const currentAvgPriceEl = document.getElementById("current-avg-price");
const targetPriceEl = document.getElementById("target-price");
const stopPriceEl = document.getElementById("stop-price");
const sellPriceEl = document.getElementById("sell-price");
const sellDateEl = document.getElementById("sell-date");
const btnSettleExecute = document.getElementById("btn-settle-execute");
const settlementResultsBox = document.getElementById("settlement-results-box");
const resHoldingPeriodEl = document.getElementById("res-holding-period");
const resYieldRateEl = document.getElementById("res-yield-rate");
const resBuyInfoEl = document.getElementById("res-buy-info");
const resSellInfoEl = document.getElementById("res-sell-info");
const commentTextEl = document.getElementById("comment-text");
const btnAddComment = document.getElementById("btn-add-comment");
const timelineContainerEl = document.getElementById("timeline-container");

const htsLinkToggleEl = document.getElementById("hts-link-toggle");
const htsLinkStatusEl = document.getElementById("hts-link-status");
const connectionStatusEl = document.getElementById("connection-status");

// App State
let activeStock = null;
let lastDetectedHTSStock = null; // Track HTS-specific changes
let currentData = null;
let saveTimeout = null;
let isSettlementEditMode = false;

// Default empty template matching backend DEFAULT_TEMPLATE
const DEFAULT_DATA = {
    trend_status: "",
    dynamic_tags: [],
    martin_calc: {
        base_qty: 1,
        base_price: 0,
        tiers: [
            { tier: 1, ratio: 1, price: 0, qty: 0, checked: false, date: "" },
            { tier: 2, ratio: 1, price: 0, qty: 0, checked: false, date: "" },
            { tier: 3, ratio: 2, price: 0, qty: 0, checked: false, date: "" },
            { tier: 4, ratio: 4, price: 0, qty: 0, checked: false, date: "" }
        ]
    },
    target_price: 0,
    stop_price: 0,
    settlement: {
        final_price: 0,
        is_settled: false,
        holding_period: "",
        yield_rate: "",
        stamp: "",
        sell_date: ""
    },
    timeline_logs: []
};

// Polling HTS Active Stock Status
async function pollHTSStatus() {
    // If HTS link is turned off, skip polling
    if (!htsLinkToggleEl.checked) return;
    
    try {
        const response = await fetch("/api/status");
        if (response.ok) {
            const data = await response.json();
            const newStock = data.active_stock;
            
            // Auto switch only when HTS active stock ACTUALLY changes to a new non-null stock
            if (newStock && newStock !== lastDetectedHTSStock) {
                // If there was an active stock loaded, save its state immediately before switching
                if (activeStock && currentData) {
                    await saveMemoData(true); // Save synchronously
                }
                
                lastDetectedHTSStock = newStock;
                activeStock = newStock;
                activeStockNameEl.textContent = activeStock;
                activeStockNameEl.parentElement.classList.add("active");
                
                // Highlight item in sidebar and load data
                highlightSidebarStock(activeStock);
                await loadMemoData(activeStock);
            }
        }
    } catch (e) {
        console.error("HTS Status polling failed:", e);
    }
}

// Start polling loop
setInterval(pollHTSStatus, 1000);

// Load Memo Data
async function loadMemoData(stockName) {
    try {
        const response = await fetch(`/api/memo?stock=${encodeURIComponent(stockName)}`);
        if (response.ok) {
            currentData = await response.json();
            
            // Defensive schema initialization
            if (!currentData.dynamic_tags) {
                currentData.dynamic_tags = [];
            }
            if (!currentData.martin_calc) {
                currentData.martin_calc = { tiers: [] };
            }
            if (!currentData.settlement) {
                currentData.settlement = {
                    final_price: 0,
                    is_settled: false,
                    holding_period: "",
                    yield_rate: "",
                    stamp: "",
                    sell_date: ""
                };
            }
            if (!currentData.settlement.sell_date) {
                currentData.settlement.sell_date = "";
            }
            if (!currentData.timeline_logs) {
                currentData.timeline_logs = [];
            }
            
            updateUIWithData();
        }
    } catch (e) {
        console.error("Error loading memo data:", e);
    }
}

// Auto Save Memo Data (Debounced)
function triggerAutoSave() {
    if (!activeStock || !currentData) return;
    
    // Clear existing timeout
    if (saveTimeout) {
        clearTimeout(saveTimeout);
    }
    
    // Set 500ms debounce
    saveTimeout = setTimeout(() => {
        saveMemoData();
    }, 500);
}

async function saveMemoData(immediate = false) {
    if (!activeStock || !currentData) return;
    
    const url = `/api/memo?stock=${encodeURIComponent(activeStock)}`;
    const options = {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(currentData)
    };
    
    if (immediate) {
        try {
            await fetch(url, options);
            loadStockList(); // Refresh stock list items metadata
        } catch (e) {
            console.error("Immediate save failed:", e);
        }
    } else {
        try {
            const response = await fetch(url, options);
            if (response.ok) {
                loadStockList(); // Refresh stock list items metadata
            } else {
                console.error("Save failed");
            }
        } catch (e) {
            console.error("Save error:", e);
        }
    }
}

function renderMartinTable() {
    const tableBody = document.getElementById("martin-table-body");
    tableBody.innerHTML = "";
    
    if (!currentData || !currentData.martin_calc || !currentData.martin_calc.tiers) return;
    
    const baseQty = currentData.martin_calc.base_qty || 1;
    
    currentData.martin_calc.tiers.forEach(tier => {
        const row = document.createElement("tr");
        row.setAttribute("data-tier", tier.tier);
        if (tier.checked) {
            row.className = "row-checked";
        }
        
        const targetQty = baseQty * tier.ratio;
        
        row.innerHTML = `
            <td class="tier-col">${tier.tier}차</td>
            <td class="ratio-col" style="font-size: 0.8rem; color: var(--color-text-muted);">${tier.ratio}배 (${targetQty}주)</td>
            <td class="qty-col">
                <input type="number" class="tier-qty" value="${tier.qty || 0}" min="0" style="width: 70px; background: rgba(0,0,0,0.3); border: 1px solid var(--border-color); color: #FFF; padding: 4px; border-radius: 4px; text-align: center;">
            </td>
            <td class="price-col">
                <input type="number" class="tier-price" value="${tier.price || ''}" placeholder="단가" style="width: 90px; background: rgba(0,0,0,0.3); border: 1px solid var(--border-color); color: #FFF; padding: 4px; border-radius: 4px; text-align: right;">
            </td>
            <td class="checkbox-col">
                <label class="checkbox-wrapper">
                    <input type="checkbox" class="tier-trigger" ${tier.checked ? 'checked' : ''}>
                    <span class="checkbox-custom"></span>
                    <span class="chk-lbl">양봉 확인</span>
                </label>
            </td>
            <td class="date-col">
                <input type="date" class="tier-date" value="${tier.date || ''}" style="background: rgba(0,0,0,0.3); border: 1px solid var(--border-color); color: #FFF; padding: 4px; border-radius: 4px;">
            </td>
            <td class="delete-col" style="text-align: center;">
                <button type="button" class="btn-delete-tier" data-tier="${tier.tier}" style="background: transparent; border: none; color: #FF5252; cursor: pointer; font-size: 1.15rem; padding: 2px 6px; line-height: 1; transition: color 0.2s;" title="삭제">&times;</button>
            </td>
        `;
        
        tableBody.appendChild(row);
    });
}

// Reset UI to default empty state
function resetUI() {
    currentData = JSON.parse(JSON.stringify(DEFAULT_DATA));
    activeStockNameEl.textContent = "선택된 종목 없음";
    activeStockNameEl.parentElement.classList.remove("active");
    updateUIWithData();
}

// Update UI Elements with loaded JSON data
function updateUIWithData() {
    if (!currentData) return;

    // 1. Trend Status Radios
    const radios = document.querySelectorAll('input[name="trend_status"]');
    radios.forEach(radio => {
        radio.checked = (radio.value === currentData.trend_status);
    });

    // 2. Tags
    renderTags();

    // 3. Target and Stop Prices
    targetPriceEl.value = currentData.target_price || "";
    stopPriceEl.value = currentData.stop_price || "";

    // 4. Martin Calculator Base Input
    basePriceEl.value = currentData.martin_calc.base_price || "";
    baseQtyEl.value = currentData.martin_calc.base_qty || 1;

    // 5. Martin Table Rows (Render dynamically)
    renderMartinTable();

    // Calculate Average Price
    calculateAveragePrice();

    // 6. Settlement Panel
    sellPriceEl.value = currentData.settlement.final_price || "";
    
    // Set sell date input
    if (currentData.settlement.sell_date) {
        sellDateEl.value = currentData.settlement.sell_date;
    } else {
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        sellDateEl.value = `${year}-${month}-${day}`;
    }
    
    if (currentData.settlement.is_settled) {
        // Parse buy and sell info MMDD formatting
        const tier1 = currentData.martin_calc.tiers.find(t => t.tier === 1);
        const avgPrice = calculateAveragePrice();
        
        let startMMDD = "-";
        if (tier1 && tier1.date) {
            const startDate = new Date(tier1.date);
            const m = String(startDate.getMonth() + 1).padStart(2, '0');
            const d = String(startDate.getDate()).padStart(2, '0');
            startMMDD = `${m}-${d}`;
        }
        
        let sellMMDD = "-";
        if (currentData.settlement.sell_date) {
            const sellDate = new Date(currentData.settlement.sell_date);
            const m = String(sellDate.getMonth() + 1).padStart(2, '0');
            const d = String(sellDate.getDate()).padStart(2, '0');
            sellMMDD = `${m}-${d}`;
        }
        
        resBuyInfoEl.value = `${startMMDD} (₩ ${avgPrice.toLocaleString()})`;
        resSellInfoEl.value = `${sellMMDD} (₩ ${(currentData.settlement.final_price || 0).toLocaleString()})`;
        resHoldingPeriodEl.value = currentData.settlement.holding_period || "";
        resYieldRateEl.value = currentData.settlement.yield_rate || "";
        
        // Reset Edit Mode
        isSettlementEditMode = false;
        const btnSettleEdit = document.getElementById("btn-settle-edit");
        if (btnSettleEdit) btnSettleEdit.textContent = "수정";
        
        resHoldingPeriodEl.readOnly = true;
        resYieldRateEl.readOnly = true;
        
        resHoldingPeriodEl.style.borderBottom = "none";
        resYieldRateEl.style.borderBottom = "none";
        
        // Color yield text
        if (currentData.settlement.yield_rate && currentData.settlement.yield_rate.startsWith("+")) {
            resYieldRateEl.style.color = "var(--green)";
        } else if (currentData.settlement.yield_rate && currentData.settlement.yield_rate.startsWith("-")) {
            resYieldRateEl.style.color = "var(--red)";
        } else {
            resYieldRateEl.style.color = "var(--color-text-primary)";
        }
        
        settlementResultsBox.style.display = "block";
    } else {
        settlementResultsBox.style.display = "none";
    }

    // 7. Timeline logs
    renderTimeline();
}

// Render Tags List
function renderTags() {
    tagsBadgeListEl.innerHTML = "";
    currentData.dynamic_tags.forEach((tag, index) => {
        const badge = document.createElement("div");
        badge.className = "tag-badge";
        badge.innerHTML = `
            <span>#${tag}</span>
            <span class="btn-remove-tag" data-index="${index}">&times;</span>
        `;
        tagsBadgeListEl.appendChild(badge);
    });
}

// Render Timeline Logs List
function renderTimeline() {
    timelineContainerEl.innerHTML = "";
    if (currentData.timeline_logs.length === 0) {
        timelineContainerEl.innerHTML = '<div class="timeline-item" style="text-align: center; color: var(--color-text-muted);">작성된 메모가 없습니다.</div>';
        return;
    }

    currentData.timeline_logs.forEach(log => {
        const item = document.createElement("div");
        item.className = "timeline-item";
        item.innerHTML = `
            <div class="timeline-time">${log.time}</div>
            <div class="timeline-content">${escapeHTML(log.text)}</div>
        `;
        timelineContainerEl.appendChild(item);
    });
}

// Helper to escape HTML to prevent XSS
function escapeHTML(str) {
    return str.replace(/[&<>'"]/g, 
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag] || tag)
    );
}

// Add Tag Event
tagInputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        const value = tagInputEl.value.trim();
        if (value && !currentData.dynamic_tags.includes(value)) {
            currentData.dynamic_tags.push(value);
            tagInputEl.value = "";
            renderTags();
            triggerAutoSave();
        }
    }
});

// Remove Tag Event (Delegation)
tagsBadgeListEl.addEventListener("click", (e) => {
    if (e.target.classList.contains("btn-remove-tag")) {
        const index = parseInt(e.target.getAttribute("data-index"));
        currentData.dynamic_tags.splice(index, 1);
        renderTags();
        triggerAutoSave();
    }
});

// Trend Status Change Event
document.querySelectorAll('input[name="trend_status"]').forEach(radio => {
    radio.addEventListener("change", (e) => {
        currentData.trend_status = e.target.value;
        triggerAutoSave();
    });
});

// Target/Stop Loss inputs
targetPriceEl.addEventListener("input", (e) => {
    currentData.target_price = parseFloat(e.target.value) || 0;
    triggerAutoSave();
});

stopPriceEl.addEventListener("input", (e) => {
    currentData.stop_price = parseFloat(e.target.value) || 0;
    triggerAutoSave();
});

// Martin Base Inputs change events
basePriceEl.addEventListener("input", (e) => {
    const val = parseFloat(e.target.value) || 0;
    currentData.martin_calc.base_price = val;
    
    // Set 1차 price automatically if not filled
    const firstRowPriceInput = document.querySelector('tr[data-tier="1"] .tier-price');
    if (firstRowPriceInput && !firstRowPriceInput.value) {
        firstRowPriceInput.value = val;
        currentData.martin_calc.tiers[0].price = val;
    }
    
    calculateAveragePrice();
    triggerAutoSave();
});

baseQtyEl.addEventListener("input", (e) => {
    const val = parseInt(e.target.value) || 1;
    currentData.martin_calc.base_qty = val;
    
    // Recalculate quantities for all rows
    currentData.martin_calc.tiers.forEach(tier => {
        tier.qty = val * tier.ratio;
    });
    
    renderMartinTable();
    calculateAveragePrice();
    triggerAutoSave();
});

// Tier specific inputs events (delegation)
const tableBody = document.getElementById("martin-table-body");

tableBody.addEventListener("input", (e) => {
    if (e.target.classList.contains("tier-price")) {
        const row = e.target.closest("tr");
        const tierNum = parseInt(row.getAttribute("data-tier"));
        const tier = currentData.martin_calc.tiers.find(t => t.tier === tierNum);
        if (tier) {
            tier.price = parseFloat(e.target.value) || 0;
            calculateAveragePrice();
            triggerAutoSave();
        }
    }
    
    if (e.target.classList.contains("tier-qty")) {
        const row = e.target.closest("tr");
        const tierNum = parseInt(row.getAttribute("data-tier"));
        const tier = currentData.martin_calc.tiers.find(t => t.tier === tierNum);
        if (tier) {
            tier.qty = parseInt(e.target.value) || 0;
            calculateAveragePrice();
            triggerAutoSave();
        }
    }
});

tableBody.addEventListener("change", (e) => {
    if (e.target.classList.contains("tier-trigger")) {
        const row = e.target.closest("tr");
        const tierNum = parseInt(row.getAttribute("data-tier"));
        const tier = currentData.martin_calc.tiers.find(t => t.tier === tierNum);
        
        if (tier) {
            tier.checked = e.target.checked;
            
            if (tier.checked) {
                // Record execution date as today's local date (YYYY-MM-DD)
                const now = new Date();
                const year = now.getFullYear();
                const month = String(now.getMonth() + 1).padStart(2, '0');
                const day = String(now.getDate()).padStart(2, '0');
                tier.date = `${year}-${month}-${day}`;
                
                row.querySelector(".tier-date").value = tier.date;
                row.classList.add("row-checked");
            } else {
                tier.date = "";
                row.querySelector(".tier-date").value = "";
                row.classList.remove("row-checked");
            }
            
            calculateAveragePrice();
            triggerAutoSave();
        }
    }

    if (e.target.classList.contains("tier-date")) {
        const row = e.target.closest("tr");
        const tierNum = parseInt(row.getAttribute("data-tier"));
        const tier = currentData.martin_calc.tiers.find(t => t.tier === tierNum);
        
        if (tier) {
            tier.date = e.target.value;
            
            // Auto-check checkbox if date is selected manually
            const checkboxEl = row.querySelector(".tier-trigger");
            if (tier.date) {
                tier.checked = true;
                checkboxEl.checked = true;
                row.classList.add("row-checked");
            } else {
                tier.checked = false;
                checkboxEl.checked = false;
                row.classList.remove("row-checked");
            }
            
            calculateAveragePrice();
            triggerAutoSave();
        }
    }
});

tableBody.addEventListener("click", (e) => {
    if (e.target.classList.contains("btn-delete-tier")) {
        if (!currentData || !currentData.martin_calc || !currentData.martin_calc.tiers) return;
        
        const tierNum = parseInt(e.target.getAttribute("data-tier"));
        const tiers = currentData.martin_calc.tiers;
        
        if (tiers.length <= 1) {
            alert("최소 1차수 이상의 분할매수 계획은 남아야 합니다.");
            return;
        }
        
        // Find index of the tier to delete
        const index = tiers.findIndex(t => t.tier === tierNum);
        if (index !== -1) {
            tiers.splice(index, 1);
            
            // Re-index remaining tiers
            tiers.forEach((t, i) => {
                t.tier = i + 1;
            });
            
            renderMartinTable();
            calculateAveragePrice();
            triggerAutoSave();
        }
    }
});

// Calculate Average Price Logic
function calculateAveragePrice() {
    let totalQty = 0;
    let totalAmount = 0;
    
    currentData.martin_calc.tiers.forEach(tier => {
        if (tier.checked) {
            const price = tier.price || 0;
            const qty = tier.qty || 0;
            totalQty += qty;
            totalAmount += price * qty;
        }
    });
    
    const avgPrice = totalQty > 0 ? Math.round(totalAmount / totalQty) : 0;
    
    // Update DOM summary elements
    const totalQtyEl = document.getElementById("total-qty-val");
    const totalAmountEl = document.getElementById("total-amount-val");
    
    if (totalQtyEl) totalQtyEl.textContent = `${totalQty.toLocaleString()} 주`;
    if (totalAmountEl) totalAmountEl.textContent = `₩ ${totalAmount.toLocaleString()}`;
    currentAvgPriceEl.textContent = `₩ ${avgPrice.toLocaleString()}`;
    
    // Calculate single weight analysis summary
    calculateWeightAnalysisSummary();
    
    return avgPrice;
}

// Global Weight Analysis Summary calculation
function calculateWeightAnalysisSummary() {
    const nextBuyEl = document.getElementById("next-buy-plan");
    if (!currentData || !currentData.martin_calc) return;
    
    const baseQty = currentData.martin_calc.base_qty || 1;
    
    // 1. Find the HIGHEST checked tier that is insufficient (shortfall)
    let highestShortfallTier = null;
    let checkedTiersCount = 0;
    
    currentData.martin_calc.tiers.forEach(tier => {
        if (tier.checked) {
            checkedTiersCount++;
            const targetQty = baseQty * tier.ratio;
            const actualQty = tier.qty || 0;
            if (actualQty < targetQty) {
                highestShortfallTier = tier; // updates to the highest checked tier with shortfall
            }
        }
    });
    
    // 2. Calculate suggestion text
    if (nextBuyEl) {
        if (highestShortfallTier) {
            const targetQty = baseQty * highestShortfallTier.ratio;
            const shortfall = targetQty - (highestShortfallTier.qty || 0);
            nextBuyEl.textContent = `${highestShortfallTier.tier}차 ${shortfall.toLocaleString()}주 부족분 채우기`;
            nextBuyEl.style.color = "#FFB300"; // warning color to fill shortfall
        } else {
            // Find the first unchecked tier
            const firstUnchecked = currentData.martin_calc.tiers.find(t => !t.checked);
            if (firstUnchecked) {
                const nextTargetQty = baseQty * firstUnchecked.ratio;
                nextBuyEl.textContent = `${firstUnchecked.tier}차 ${nextTargetQty.toLocaleString()}주`;
                nextBuyEl.style.color = "#64B5F6"; // planned next buy blue
            } else {
                if (checkedTiersCount === 0) {
                    nextBuyEl.textContent = "1차 진입 대기";
                    nextBuyEl.style.color = "#718096";
                } else {
                    nextBuyEl.textContent = "없음 (최종 완료)";
                    nextBuyEl.style.color = "var(--primary)";
                }
            }
        }
    }
}

// Settlement Trigger Event
btnSettleExecute.addEventListener("click", () => {
    if (!activeStock || !currentData) return;
    
    // Validate: 1차 buy must be checked to calculate holding period
    const tier1 = currentData.martin_calc.tiers.find(t => t.tier === 1);
    if (!tier1 || !tier1.checked || !tier1.date) {
        alert("최종 청산을 위해서는 최소 1차 매수 집행(양봉 확인 체크)이 완료되어야 합니다.");
        return;
    }
    
    const sellPrice = parseFloat(sellPriceEl.value) || 0;
    if (sellPrice <= 0) {
        alert("최종 매도 단가를 입력해 주세요.");
        return;
    }
    
    const avgPrice = calculateAveragePrice();
    if (avgPrice <= 0) {
        alert("매수 평단가가 0원입니다. 마틴 매수 단가를 확인해 주세요.");
        return;
    }
    
    // 1. Calculate holding period in days
    const startDate = new Date(tier1.date);
    const sellDateStr = sellDateEl.value || tier1.date;
    const sellDate = new Date(sellDateStr);
    
    // Set hours to 0 to compare exact dates
    startDate.setHours(0,0,0,0);
    sellDate.setHours(0,0,0,0);
    
    const diffTime = Math.abs(sellDate - startDate);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1; // +1 day to count inclusive (e.g. same day = 1D)
    
    const holdingPeriodStr = `${diffDays}D`;
    
    // 2. Calculate Yield Rate
    const yieldRate = ((sellPrice - avgPrice) / avgPrice) * 100;
    const sign = yieldRate >= 0 ? "+" : "";
    const yieldRateStr = `${sign}${yieldRate.toFixed(2)}%`;
    
    // 3. Format Date Formats for Stamp (e.g. 0611(5240) - 0612(6070) / (1D) / (+15.61%))
    const formatMMDD = (dateObj) => {
        const m = String(dateObj.getMonth() + 1).padStart(2, '0');
        const d = String(dateObj.getDate()).padStart(2, '0');
        return `${m}${d}`;
    };
    
    const startStr = `${formatMMDD(startDate)}(${avgPrice})`;
    const endStr = `${formatMMDD(sellDate)}(${sellPrice})`;
    const stampStr = `${startStr} - ${endStr} / (${holdingPeriodStr}) / (${yieldRateStr})`;
    
    // Update state
    currentData.settlement.final_price = sellPrice;
    currentData.settlement.sell_date = sellDateStr;
    currentData.settlement.is_settled = true;
    currentData.settlement.holding_period = holdingPeriodStr;
    currentData.settlement.yield_rate = yieldRateStr;
    currentData.settlement.stamp = stampStr;
    
    // Render Settlement Display
    const formatMMDD_label = (dateObj) => {
        const m = String(dateObj.getMonth() + 1).padStart(2, '0');
        const d = String(dateObj.getDate()).padStart(2, '0');
        return `${m}-${d}`;
    };
    resBuyInfoEl.value = `${formatMMDD_label(startDate)} (₩ ${avgPrice.toLocaleString()})`;
    resSellInfoEl.value = `${formatMMDD_label(sellDate)} (₩ ${sellPrice.toLocaleString()})`;
    resHoldingPeriodEl.value = holdingPeriodStr;
    resYieldRateEl.value = yieldRateStr;
    
    if (yieldRate >= 0) {
        resYieldRateEl.style.color = "var(--green)";
    } else {
        resYieldRateEl.style.color = "var(--red)";
    }
    
    settlementResultsBox.style.display = "block";
    
    // Automatically add this settlement stamp to daily timeline log
    const now = new Date();
    const formattedTime = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;
    
    const logText = `[최종 청산 완료] 결산기록: ${currentData.settlement.stamp}`;
    currentData.timeline_logs.unshift({
        time: formattedTime,
        text: logText
    });
    
    renderTimeline();
    
    // Save state
    saveMemoData();
});

// Toggle Edit/Save Settlement Event
const btnSettleEdit = document.getElementById("btn-settle-edit");
if (btnSettleEdit) {
    btnSettleEdit.addEventListener("click", () => {
        if (!activeStock || !currentData) return;
        
        if (!isSettlementEditMode) {
            // Enter edit mode
            isSettlementEditMode = true;
            btnSettleEdit.textContent = "완료";
            
            resHoldingPeriodEl.readOnly = false;
            resYieldRateEl.readOnly = false;
            
            resHoldingPeriodEl.style.borderBottom = "1px dashed var(--primary)";
            resYieldRateEl.style.borderBottom = "1px dashed var(--primary)";
        } else {
            // Exit edit mode and Save
            isSettlementEditMode = false;
            btnSettleEdit.textContent = "수정";
            
            resHoldingPeriodEl.readOnly = true;
            resYieldRateEl.readOnly = true;
            
            resHoldingPeriodEl.style.borderBottom = "none";
            resYieldRateEl.style.borderBottom = "none";
            
            // Save modified values to state (directly overridden by user)
            currentData.settlement.holding_period = resHoldingPeriodEl.value.trim();
            currentData.settlement.yield_rate = resYieldRateEl.value.trim();
            
            // Regenerate the background stamp string for logging & HTS format compatibility
            regenerateStampFromState();
            
            // Adjust yield rate text color
            if (currentData.settlement.yield_rate.startsWith("+")) {
                resYieldRateEl.style.color = "var(--green)";
            } else if (currentData.settlement.yield_rate.startsWith("-")) {
                resYieldRateEl.style.color = "var(--red)";
            } else {
                resYieldRateEl.style.color = "var(--color-text-primary)";
            }
            
            // Update the timeline log to match the new values
            const logIndex = currentData.timeline_logs.findIndex(log => log.text.includes("[최종 청산 완료]"));
            if (logIndex !== -1) {
                currentData.timeline_logs[logIndex].text = `[최종 청산 완료] 결산기록: ${currentData.settlement.stamp}`;
            }
            
            renderTimeline();
            triggerAutoSave();
        }
    });
}

// Regenerate legacy stamp string in background to keep data compatibility
function regenerateStampFromState() {
    if (!currentData || !currentData.martin_calc || !currentData.settlement) return;
    const tier1 = currentData.martin_calc.tiers.find(t => t.tier === 1);
    if (!tier1 || !tier1.date) return;
    
    const avgPrice = calculateAveragePrice();
    const sellPrice = currentData.settlement.final_price || 0;
    const sellDateStr = currentData.settlement.sell_date || tier1.date;
    
    const startDate = new Date(tier1.date);
    const sellDate = new Date(sellDateStr);
    
    const formatMMDD = (dateObj) => {
        const m = String(dateObj.getMonth() + 1).padStart(2, '0');
        const d = String(dateObj.getDate()).padStart(2, '0');
        return `${m}${d}`;
    };
    
    const startStr = `${formatMMDD(startDate)}(${avgPrice})`;
    const endStr = `${formatMMDD(sellDate)}(${sellPrice})`;
    const holdingPeriod = currentData.settlement.holding_period;
    const yieldRate = currentData.settlement.yield_rate;
    
    currentData.settlement.stamp = `${startStr} - ${endStr} / (${holdingPeriod}) / (${yieldRate})`;
}

// Recalculate settlement details from price/date input fields
function recalculateSettlementFromInputs() {
    if (!currentData || !currentData.martin_calc || !currentData.settlement) return;
    const tier1 = currentData.martin_calc.tiers.find(t => t.tier === 1);
    if (!tier1 || !tier1.checked || !tier1.date) return;
    
    const sellPrice = parseFloat(sellPriceEl.value) || 0;
    const sellDateStr = sellDateEl.value || tier1.date;
    
    const startDate = new Date(tier1.date);
    const sellDate = new Date(sellDateStr);
    
    startDate.setHours(0,0,0,0);
    sellDate.setHours(0,0,0,0);
    
    const diffTime = Math.abs(sellDate - startDate);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
    
    const holdingPeriodStr = `${diffDays}D`;
    const avgPrice = calculateAveragePrice();
    
    const yieldRate = avgPrice > 0 ? ((sellPrice - avgPrice) / avgPrice) * 100 : 0;
    const sign = yieldRate >= 0 ? "+" : "";
    const yieldRateStr = `${sign}${yieldRate.toFixed(2)}%`;
    
    const formatMMDD = (dateObj) => {
        const m = String(dateObj.getMonth() + 1).padStart(2, '0');
        const d = String(dateObj.getDate()).padStart(2, '0');
        return `${m}${d}`;
    };
    
    const startStr = `${formatMMDD(startDate)}(${avgPrice})`;
    const endStr = `${formatMMDD(sellDate)}(${Math.round(sellPrice)})`;
    const stampStr = `${startStr} - ${endStr} / (${holdingPeriodStr}) / (${yieldRateStr})`;
    
    // Update display inputs
    resHoldingPeriodEl.value = holdingPeriodStr;
    resYieldRateEl.value = yieldRateStr;
    resStampBox.value = stampStr;
    
    // Update state
    currentData.settlement.final_price = sellPrice;
    currentData.settlement.sell_date = sellDateStr;
    currentData.settlement.holding_period = holdingPeriodStr;
    currentData.settlement.yield_rate = yieldRateStr;
    currentData.settlement.stamp = stampStr;
    
    // Adjust text color
    if (yieldRate >= 0) {
        resYieldRateEl.style.color = "var(--green)";
    } else {
        resYieldRateEl.style.color = "var(--red)";
    }
}

// Auto recalculate live when typing price or changing date
function handleSellInputUpdate() {
    if (!currentData || !currentData.settlement || !currentData.settlement.is_settled) return;
    recalculateSettlementFromInputs();
    
    // Update the timeline log to match the new values
    const logIndex = currentData.timeline_logs.findIndex(log => log.text.includes("[최종 청산 완료]"));
    if (logIndex !== -1) {
        currentData.timeline_logs[logIndex].text = `[최종 청산 완료] 결산기록: ${currentData.settlement.stamp}`;
        renderTimeline();
    }
    triggerAutoSave();
}

sellPriceEl.addEventListener("input", handleSellInputUpdate);
sellDateEl.addEventListener("change", handleSellInputUpdate);

// Timeline Comments adding
function addTimelineComment() {
    if (!activeStock || !currentData) return;
    
    const text = commentTextEl.value.trim();
    if (!text) return;
    
    const now = new Date();
    const formattedTime = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}:${String(now.getSeconds()).padStart(2,'0')}`;
    
    currentData.timeline_logs.unshift({
        time: formattedTime,
        text: text
    });
    
    commentTextEl.value = "";
    renderTimeline();
    triggerAutoSave();
}

btnAddComment.addEventListener("click", addTimelineComment);

commentTextEl.addEventListener("keydown", (e) => {
    // Submit on Enter, unless Shift is pressed
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        addTimelineComment();
    }
});

// --- STOCK LIST SIDEBAR LOGIC ---
let allStocksList = [];
let currentFilter = "all";
let searchKeyword = "";

async function loadStockList() {
    try {
        const response = await fetch("/api/list");
        if (response.ok) {
            const data = await response.json();
            allStocksList = data.stocks || [];
            renderStockList();
        }
    } catch (e) {
        console.error("Error loading stock list:", e);
    }
}

function highlightSidebarStock(name) {
    const items = document.querySelectorAll(".stock-list-item");
    items.forEach(item => {
        if (item.getAttribute("data-name") === name) {
            item.classList.add("selected");
            item.scrollIntoView({ block: "nearest", behavior: "smooth" });
        } else {
            item.classList.remove("selected");
        }
    });
}

function renderStockList() {
    const container = document.getElementById("stock-list-container");
    if (!container) return;
    
    container.innerHTML = "";
    
    const filtered = allStocksList.filter(stock => {
        const matchesSearch = stock.name.toLowerCase().includes(searchKeyword.toLowerCase());
        if (!matchesSearch) return false;
        
        if (currentFilter === "active") {
            return !stock.is_settled;
        } else if (currentFilter === "settled") {
            return stock.is_settled;
        }
        return true;
    });
    
    if (filtered.length === 0) {
        container.innerHTML = '<div style="color: var(--color-text-muted); font-size: 0.78rem; text-align: center; padding: 20px;">결과가 없습니다.</div>';
        return;
    }
    
    filtered.forEach(stock => {
        const item = document.createElement("div");
        item.className = "stock-list-item";
        item.setAttribute("data-name", stock.name);
        if (stock.is_settled) {
            item.classList.add("settled-item");
        } else {
            item.classList.add("active-item");
        }
        if (stock.name === activeStock) {
            item.classList.add("selected");
        }
        
        const top = document.createElement("div");
        top.className = "stock-item-top";
        
        const nameEl = document.createElement("span");
        nameEl.className = "stock-item-name";
        nameEl.textContent = stock.name;
        
        top.appendChild(nameEl);
        
        if (stock.is_settled && stock.yield_rate) {
            const yieldEl = document.createElement("span");
            const isProfit = stock.yield_rate.startsWith("+");
            yieldEl.className = `stock-item-yield ${isProfit ? "profit" : "loss"}`;
            yieldEl.textContent = stock.yield_rate;
            top.appendChild(yieldEl);
        }
        
        // Add Delete Button to top row of Stock list card
        const deleteBtn = document.createElement("button");
        deleteBtn.className = "stock-delete-btn";
        deleteBtn.innerHTML = "&times;";
        deleteBtn.title = "종목 삭제";
        deleteBtn.addEventListener("click", async (e) => {
            e.stopPropagation(); // Prevent selection trigger
            if (confirm(`'${stock.name}' 종목 기록을 정말 삭제하시겠습니까?`)) {
                try {
                    const response = await fetch(`/api/delete?stock=${encodeURIComponent(stock.name)}`, {
                        method: "POST"
                    });
                    if (response.ok) {
                        if (activeStock === stock.name) {
                            activeStock = null;
                            currentData = null;
                            resetUI();
                        }
                        await loadStockList();
                    } else {
                        alert("종목 삭제에 실패했습니다.");
                    }
                } catch (err) {
                    console.error("Error deleting stock:", err);
                }
            }
        });
        top.appendChild(deleteBtn);
        
        item.appendChild(top);
        
        item.addEventListener("click", async () => {
            if (activeStock && currentData) {
                await saveMemoData(true);
            }
            activeStock = stock.name;
            activeStockNameEl.textContent = activeStock;
            activeStockNameEl.parentElement.classList.add("active");
            
            highlightSidebarStock(activeStock);
            await loadMemoData(activeStock);
        });
        
        container.appendChild(item);
    });
}

// Bind Sidebar Event Listeners
const stockSearchEl = document.getElementById("stock-search");
if (stockSearchEl) {
    stockSearchEl.addEventListener("input", (e) => {
        searchKeyword = e.target.value;
        renderStockList();
    });
}

const filterTabs = document.querySelectorAll(".filter-tab");
filterTabs.forEach(tab => {
    tab.addEventListener("click", (e) => {
        filterTabs.forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        currentFilter = tab.getAttribute("data-filter");
        renderStockList();
    });
});

// HTS Link Toggle Logic
function updateHTSLinkStatus() {
    if (htsLinkToggleEl.checked) {
        htsLinkStatusEl.textContent = "HTS 연동 ON";
        connectionStatusEl.classList.remove("offline");
    } else {
        htsLinkStatusEl.textContent = "HTS 연동 OFF";
        connectionStatusEl.classList.add("offline");
    }
}

htsLinkToggleEl.addEventListener("change", () => {
    updateHTSLinkStatus();
    if (htsLinkToggleEl.checked) {
        pollHTSStatus(); // Immediately trigger sync
    }
});

// Initial Startup Calls
updateHTSLinkStatus();
loadStockList();

// Add Tier Event Listener
const btnAddTier = document.getElementById("btn-add-tier");
if (btnAddTier) {
    btnAddTier.addEventListener("click", () => {
        if (!currentData || !currentData.martin_calc || !currentData.martin_calc.tiers) return;
        
        const nextTier = currentData.martin_calc.tiers.length + 1;
        
        // Calculate default ratio
        let nextRatio = 1;
        const len = currentData.martin_calc.tiers.length;
        if (len > 0) {
            const lastTier = currentData.martin_calc.tiers[len - 1];
            nextRatio = lastTier.ratio * 2;
        }
        
        const baseQty = currentData.martin_calc.base_qty || 1;
        const nextQty = baseQty * nextRatio;
        
        currentData.martin_calc.tiers.push({
            tier: nextTier,
            ratio: nextRatio,
            price: 0,
            qty: nextQty,
            checked: false,
            date: ""
        });
        
        renderMartinTable();
        calculateAveragePrice();
        triggerAutoSave();
    });
}
