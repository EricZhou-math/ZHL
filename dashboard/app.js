/* eslint-disable */
(async function () {
  const chartsCore = document.getElementById('coreCharts');
  const chartsContainer = document.getElementById('chartsContainer');
  const indicatorPanel = document.getElementById('indicatorPanel');
  const extendCollapse = document.getElementById('extendCollapse');
  const startCycleInput = document.getElementById('startCycle');
  const endCycleInput = document.getElementById('endCycle');
  const showTrendInput = document.getElementById('showTrend');
  const pivotWrapper = document.getElementById('pivotTable');
  const tableToolbar = document.getElementById('tableToolbar');
  const toggleOrientationBtn = document.getElementById('toggleOrientation');
  const exportDropdown = document.getElementById('exportDropdown');
  const exportBtn = document.getElementById('exportBtn');
  const exportMenu = document.getElementById('exportMenu');
  let isTransposed = false;

  async function loadData() {
    const fallback = async () => {
      const resp2 = await fetch('./data.json');
      return await resp2.json();
    };
    // 仅在显式配置了 API 基址时才尝试后端（开发态）
    // 支持可配置 API 基址：window.__API_BASE__ 或 <meta name="api-base" content="...">
    let apiBase = window.__API_BASE__ || '';
    if (!apiBase) {
      const meta = document.querySelector('meta[name="api-base"]');
      if (meta && meta.content) apiBase = meta.content.trim();
    }
    if (apiBase) {
      const apiUrl = apiBase.replace(/\/$/, '') + '/api/data';
      try {
        const resp = await fetch(apiUrl, { mode: 'cors' });
        if (resp && resp.ok) {
          return await resp.json();
        }
      } catch (_) {}
    }
    // 未配置 API 或请求失败则回退到静态 data.json（适用于 GitHub Pages 发布）
    return await fallback();
  }
  const data = await loadData();

  const NAME_SYNONYMS = {
    '中性粒细胞绝对值': '中性粒细胞计数',
    '淋巴细胞绝对值': '淋巴细胞计数',
    '单核细胞绝对值': '单核细胞计数',
    '嗜酸性粒细胞绝对值': '嗜酸性粒细胞计数',
    '嗜碱性粒细胞绝对值': '嗜碱性粒细胞计数',
    '有核红细胞绝对值': '有核红细胞计数',
    '红细胞计数': '红细胞',
    '红细胞数': '红细胞',
    '血红蛋白': '血红蛋白浓度'
  };
  const canonicalName = (name) => NAME_SYNONYMS[name] || name;
  const normalizeIndicatorsObject = (indicators) => {
    const merged = {};
    Object.keys(indicators || {}).forEach((name) => {
      const canon = canonicalName(name);
      const src = indicators[name] || {};
      const unit = src.unit || '';
      const ref = src.ref || null;
      const series = Array.isArray(src.series) ? src.series.slice() : [];

      if (!merged[canon]) {
        merged[canon] = { unit, ref, series };
      } else {
        if (!merged[canon].unit && unit) merged[canon].unit = unit;
        const mref = merged[canon].ref;
        const mrefComplete = mref && mref.lower != null && mref.upper != null;
        const refComplete = ref && ref.lower != null && ref.upper != null;
        if (!mrefComplete && refComplete) merged[canon].ref = ref;
        const byDate = {};
        (merged[canon].series || []).forEach((pt) => { byDate[pt.date] = pt; });
        series.forEach((pt) => {
          const ex = byDate[pt.date];
          if (!ex) byDate[pt.date] = pt;
          else {
            const eNum = typeof ex.value === 'number';
            const sNum = typeof pt.value === 'number';
            let chooseSrc = false;
            if (sNum && !eNum) chooseSrc = true;
            else if (sNum && eNum) {
              const eScore = (ex.flag === '↑' || ex.flag === '↓') ? 1 : 0;
              const sScore = (pt.flag === '↑' || pt.flag === '↓') ? 1 : 0;
              if (sScore >= eScore) chooseSrc = true;
            }
            if (chooseSrc) byDate[pt.date] = pt;
          }
        });
        merged[canon].series = Object.keys(byDate).sort().map(d => byDate[d]);
      }
    });
    return merged;
  };

  data.indicators = normalizeIndicatorsObject(data.indicators || {});

  const startDate = new Date(data.start_date);
  const cycleLen = Number(data.cycle_length_days || 21);

  // 指标分类：核心与扩展
  const indNames = Object.keys(data.indicators);
  const CORE_INDICATORS = [
    '白细胞计数',
    '中性粒细胞计数',
    '血小板计数',
    '血红蛋白浓度'
  ];
  const coreNames = indNames.filter(n => CORE_INDICATORS.includes(n));
  const extNames = indNames.filter(n => !CORE_INDICATORS.includes(n));

  // 构建扩展指标勾选面板（默认不勾选）
  function buildIndicatorPanel() {
    indicatorPanel.innerHTML = '';
    extNames.forEach((name) => {
      const label = document.createElement('label');
      label.className = 'indicator-item';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.name = 'indicator';
      input.value = name;
      const span = document.createElement('span');
      span.textContent = name;
      label.appendChild(input);
      label.appendChild(span);
      indicatorPanel.appendChild(label);
    });
  }
  buildIndicatorPanel();

  // Compute max cycle based on dates
  const maxCycle = (function () {
    let m = 1;
    for (const d of data.dates) {
      const dt = new Date(d);
      const deltaDays = Math.floor((dt - startDate) / (24 * 3600 * 1000));
      if (deltaDays >= 0) {
        const c = Math.floor(deltaDays / cycleLen) + 1;
        m = Math.max(m, c);
      }
    }
    return m;
  })();
  startCycleInput.min = 1;
  endCycleInput.min = 1;
  startCycleInput.max = String(maxCycle);
  endCycleInput.max = String(maxCycle);
  endCycleInput.value = String(maxCycle);

  // Helpers
  function getSelectedIndicators() {
    const checked = Array.from(indicatorPanel.querySelectorAll('input[name="indicator"]:checked'));
    const arr = checked.map((el) => el.value);
    return arr;
  }

  function computePhaseLabel(dtStr) {
    try {
      const d = new Date(dtStr);
      const deltaDays = Math.floor((d - startDate) / (24 * 3600 * 1000));
      if (deltaDays < 0) return '首次化疗前';
      const cycle = Math.floor(deltaDays / cycleLen) + 1;
      const dayInCycle = (deltaDays % cycleLen) + 1;
      return `第${cycle}次化疗d${dayInCycle}`;
    } catch (e) {
      return '';
    }
  }

  function formatY(unit, v) {
    if (v == null || v === '') return '';
    const isNum = typeof v === 'number';
    const numStr = isNum ? String(v) : String(v);
    if (/^10\^[0-9]+\/[A-Za-z]+$/i.test(unit)) {
      return `${numStr} × ${unit}`;
    }
    return `${numStr} ${unit || ''}`.trim();
  }

  function formatDateDot(dtStr) {
    try {
      const d = new Date(dtStr);
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      return `${y}.${m}.${dd}`;
    } catch (e) {
      return dtStr;
    }
  }

  function computeRegression(xIdx, yVals) {
    const n = yVals.length;
    if (n < 2) return null;
    let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
    for (let i = 0; i < n; i++) {
      const x = xIdx[i];
      const y = yVals[i];
      if (typeof y !== 'number') return null;
      sumX += x; sumY += y; sumXY += x * y; sumXX += x * x;
    }
    const denom = n * sumXX - sumX * sumX;
    if (denom === 0) return null;
    const k = (n * sumXY - sumX * sumY) / denom;
    const b = (sumY - k * sumX) / n;
    return { k, b };
  }

  // 新增：趋势拟合（LOESS）
  function computeTrendLoess(seriesData) {
    const valid = seriesData.filter(pt => typeof pt.value === 'number');
    if (valid.length < 3) return seriesData.map(pt => [pt.date, null]);

    const baseDateStr = (seriesData && seriesData.length) ? seriesData[0].date : (data.dates && data.dates[0]);
    const dayDiff = (dateStr) => {
      const base = new Date(baseDateStr);
      const d = new Date(dateStr);
      return (d - base) / (24 * 3600 * 1000);
    };

    const xValid = valid.map(pt => dayDiff(pt.date));
    const yValid = valid.map(pt => pt.value);
    const span = 0.6;
    const k = Math.max(3, Math.floor(span * valid.length));

    function predictAt(x0) {
      const dist = xValid.map((x, idx) => ({ idx, d: Math.abs(x - x0) }));
      dist.sort((a, b) => a.d - b.d);
      const kIdxs = dist.slice(0, k);
      const dmax = kIdxs[kIdxs.length - 1].d || 1e-6;

      let Sw = 0, Swx = 0, Swx2 = 0, Swy = 0, Swxy = 0;
      for (const { idx, d } of kIdxs) {
        const u = d / dmax;
        const w = Math.pow(1 - Math.pow(u, 3), 3);
        const x = xValid[idx];
        const y = yValid[idx];
        Sw += w;
        Swx += w * x;
        Swx2 += w * x * x;
        Swy += w * y;
        Swxy += w * x * y;
      }
      const denom = (Sw * Swx2 - Swx * Swx);
      if (Math.abs(denom) < 1e-12) {
        const a = Swy / (Sw || 1e-12);
        return a;
      }
      const b = (Sw * Swxy - Swx * Swy) / denom;
      const a = (Swy - b * Swx) / Sw;
      return a + b * x0;
    }

    return seriesData.map(pt => {
      const x0 = dayDiff(pt.date);
      const yhat = predictAt(x0);
      return [pt.date, yhat];
    });
  }

  // Chart management（核心与扩展分别管理）
  let chartInstancesCore = [];
  let chartInstancesExt = [];
  function disposeChartsIn(container, instancesArr) {
    instancesArr.forEach((obj) => { try { obj.chart && obj.chart.dispose(); } catch (_) {} });
    instancesArr.length = 0;
    container.innerHTML = '';
  }

  // 响应式参数：根据窗口宽度调整字体、网格与交互
  function getResponsiveConf() {
    const w = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
    const isMobile = w <= 600;
    const isTablet = w > 600 && w <= 1024;
    const isDesktop = w > 1024;
    const axisFont = isMobile ? 10 : 12;
    const titleFont = isMobile ? 14 : (isTablet ? 14 : 16);
    const grid = isMobile
      ? { left: 36, right: 24, top: 36, bottom: 28 }
      : (isTablet ? { left: 40, right: 30, top: 40, bottom: 30 } : { left: 50, right: 35, top: 40, bottom: 32 });
    const rotate = isMobile ? 25 : 0;
    const symbolSize = isMobile ? 4 : 5;
    const lineWidth = isMobile ? 1.75 : 2;
    const dataZoom = isMobile ? [{ type: 'inside', moveOnMouseMove: true, zoomOnMouseWheel: false }] : [];
    return { isMobile, isTablet, isDesktop, axisFont, titleFont, grid, rotate, symbolSize, lineWidth, dataZoom };
  }

  function buildOption(indicatorName, seriesData, unit, ref) {
    const RS = getResponsiveConf();
    const xData = seriesData.map(d => d.date);
    const seriesPoints = seriesData.map(d => [d.date, (typeof d.value === 'number' ? d.value : null)]);

    // 记录当前吸附到的 x 类目索引
    let currentXIndex = -1;

    const option = {
      title: {
        text: indicatorName,
        left: 'center',
        textStyle: { fontSize: RS.titleFont }
      },
      tooltip: {
        trigger: 'axis',
        showContent: false,
        axisPointer: {
          type: 'cross',
          snap: true,
          lineStyle: { color: '#f4b400', type: 'dashed', width: 1.5 }
        }
      },
      grid: RS.grid,
      xAxis: {
        type: 'category',
        data: xData,
        axisLabel: { formatter: value => value, fontSize: RS.axisFont, rotate: RS.rotate, hideOverlap: true },
        axisPointer: {
          show: true,
          snap: true,
          label: {
            formatter: params => {
              const rawDate = params.value;
              const idx = xData.indexOf(rawDate);
              const phase = (idx >= 0 && seriesData[idx]) ? (seriesData[idx].phase || seriesData[idx].phaseLabel || computePhaseLabel(rawDate)) : computePhaseLabel(rawDate);
              return `${formatDateDot(rawDate)}\n${phase}`;
            }
          },
          lineStyle: { color: '#f4b400', type: 'dashed', width: 1.5 }
        }
      },
      yAxis: {
        type: 'value',
        axisPointer: {
          show: true,
          snap: true,
          label: {
            formatter: params => {
              // 优先显示当前吸附日期的精确数值
              let idx = currentXIndex;
              if (idx < 0 && params && params.seriesData && params.seriesData.length) {
                const d0 = params.seriesData[0].data;
                const xVal = Array.isArray(d0) ? d0[0] : null;
                if (xVal) idx = xData.indexOf(xVal);
              }
              const val = (idx >= 0 && seriesData[idx]) ? seriesData[idx].value : params.value;
              return formatY(unit, val);
            }
          },
          // 恢复水平指示线样式（黄色虚线）
          lineStyle: { color: '#f4b400', type: 'dashed', width: 1.5 }
        },
        axisLabel: { fontSize: RS.axisFont }
      },
      dataZoom: RS.dataZoom,
      series: (function () {
        const arr = [];
        // 参考下限虚线
        if (ref && typeof ref.lower === 'number') {
          const lowerData = xData.map(d => [d, ref.lower]);
          arr.push({
            name: '参考下限',
            type: 'line',
            data: lowerData,
            connectNulls: true,
            symbol: 'none',
            lineStyle: { width: 1.5, type: 'dashed', color: '#1a73e8' },
            silent: true,
            tooltip: { show: false },
            endLabel: {
              show: true,
              formatter: () => `下限 ${formatY(unit, ref.lower)}`,
              color: '#1a73e8',
              backgroundColor: 'rgba(255,255,255,0.8)',
              padding: [2, 4],
              borderRadius: 3
            },
            z: 0
          });
        }
        // 参考上限虚线
        if (ref && typeof ref.upper === 'number') {
          const upperData = xData.map(d => [d, ref.upper]);
          arr.push({
            name: '参考上限',
            type: 'line',
            data: upperData,
            connectNulls: true,
            symbol: 'none',
            lineStyle: { width: 1.5, type: 'dashed', color: '#d93025' },
            silent: true,
            tooltip: { show: false },
            endLabel: {
              show: true,
              formatter: () => `上限 ${formatY(unit, ref.upper)}`,
              color: '#d93025',
              backgroundColor: 'rgba(255,255,255,0.8)',
              padding: [2, 4],
              borderRadius: 3
            },
            z: 0
          });
        }
        // 主趋势折线
        arr.push({
          name: indicatorName,
          type: 'line',
          data: seriesPoints,
          connectNulls: true,
          symbolSize: RS.symbolSize,
          lineStyle: { width: RS.lineWidth },
          smooth: false,
          emphasis: {
            focus: 'series',
            scale: 1.5,
            itemStyle: {
              borderWidth: 2,
              borderColor: '#fff',
              shadowBlur: 5,
              shadowColor: 'rgba(0,0,0,0.3)'
            }
          },
          z: 2
        });
        // 新增：趋势拟合线（浅色虚线）
        if (showTrendInput && showTrendInput.checked) {
          const trend = computeTrendLoess(seriesData);
          arr.push({
            name: '趋势拟合',
            type: 'line',
            data: trend,
            connectNulls: true,
            symbol: 'none',
            lineStyle: { width: 1.5, type: 'dashed', color: 'rgba(120,120,120,0.55)' },
            smooth: true,
            emphasis: { focus: 'none' },
            tooltip: { show: false },
            silent: true,
            z: 0
          });
        }
        return arr;
      })()
    };

    // 事件钩子：同步当前 x 类目索引
    function onAxisPointerUpdate(event) {
      if (event && event.axesInfo && event.axesInfo.length) {
        const xInfo = event.axesInfo.find(info => info.axisDim === 'x');
        if (xInfo) {
          const xVal = xInfo.value;
          currentXIndex = xData.indexOf(xVal);
        }
      }
    }

    return { option, onAxisPointerUpdate };
  }

  function renderCoreCharts(names) {
    disposeChartsIn(chartsCore, chartInstancesCore);
    const startC = Number(startCycleInput.value);
    const endC = Number(endCycleInput.value);
    names.forEach((name) => {
      const ind = data.indicators[name];
      if (!ind) return;
      const unit = ind.unit || '';
      const seriesAll = ind.series || [];

      const filtered = seriesAll.filter((pt) => {
        const d = new Date(pt.date);
        const deltaDays = Math.floor((d - startDate) / (24 * 3600 * 1000));
        const cycle = deltaDays >= 0 ? Math.floor(deltaDays / cycleLen) + 1 : 0;
        return cycle >= startC && cycle <= endC;
      });

      const card = document.createElement('div');
      card.className = 'chart-card';
      const title = document.createElement('div');
      title.className = 'chart-title';
      title.textContent = name + (unit ? `（${unit}）` : '');
      const chartDiv = document.createElement('div');
      chartDiv.className = 'chart';
      card.appendChild(title);
      card.appendChild(chartDiv);
      chartsCore.appendChild(card);

      const chart = echarts.init(chartDiv);
      const built = buildOption(name, filtered, unit, ind.ref || null);
      chart.setOption(built.option);
      chart.on('updateAxisPointer', built.onAxisPointerUpdate);
      chart.resize();
      chartInstancesCore.push({ name, chart, el: chartDiv });
    });
  }

  function renderExtCharts(selectedInds) {
    disposeChartsIn(chartsContainer, chartInstancesExt);
    const startC = Number(startCycleInput.value);
    const endC = Number(endCycleInput.value);

    selectedInds.forEach((name) => {
      const ind = data.indicators[name];
      if (!ind) return;
      const unit = ind.unit || '';
      const seriesAll = ind.series || [];

      const filtered = seriesAll.filter((pt) => {
        const d = new Date(pt.date);
        const deltaDays = Math.floor((d - startDate) / (24 * 3600 * 1000));
        const cycle = deltaDays >= 0 ? Math.floor(deltaDays / cycleLen) + 1 : 0;
        return cycle >= startC && cycle <= endC;
      });

      const card = document.createElement('div');
      card.className = 'chart-card';
      const title = document.createElement('div');
      title.className = 'chart-title';
      title.textContent = name + (unit ? `（${unit}）` : '');
      const chartDiv = document.createElement('div');
      chartDiv.className = 'chart';
      card.appendChild(title);
      card.appendChild(chartDiv);
      chartsContainer.appendChild(card);

      const chart = echarts.init(chartDiv);
      const built = buildOption(name, filtered, unit, ind.ref || null);
      chart.setOption(built.option);
      chart.on('updateAxisPointer', built.onAxisPointerUpdate);
      chart.resize();
      chartInstancesExt.push({ name, chart, el: chartDiv });
    });
  }

  function renderPivotTable(selectedInds) {
    pivotWrapper.innerHTML = '';
    const table = document.createElement('table');
    table.className = 'pivot-table fade-in';
    const thead = document.createElement('thead');
    const tbody = document.createElement('tbody');

    if (!isTransposed) {
      const trh = document.createElement('tr');
      const h0 = document.createElement('th');
      h0.textContent = '检测指标';
      trh.appendChild(h0);
      const h1 = document.createElement('th');
      h1.textContent = '参考范围';
      trh.appendChild(h1);
      data.dates.forEach((dt) => {
        const th = document.createElement('th');
        th.textContent = formatDateDot(dt);
        trh.appendChild(th);
      });
      thead.appendChild(trh);

      const trh2 = document.createElement('tr');
      const phaseHeader = document.createElement('th');
      phaseHeader.textContent = '所属化疗周期';
      phaseHeader.setAttribute('colspan', '2');
      trh2.appendChild(phaseHeader);
      data.dates.forEach((dt) => {
        const th2 = document.createElement('th');
        th2.textContent = computePhaseLabel(dt);
        trh2.appendChild(th2);
      });
      thead.appendChild(trh2);

      selectedInds.forEach((name) => {
        const ind = data.indicators[name];
        if (!ind) return;
        const seriesAll = ind.series || [];
        const map = {};
        seriesAll.forEach((pt) => { map[pt.date] = pt; });
        const tr = document.createElement('tr');
        const td0 = document.createElement('td');
        td0.textContent = name;
        tr.appendChild(td0);
        const td1 = document.createElement('td');
        const ref = ind.ref || {};
        const unit = ind.unit || '';
        td1.textContent = (ref.lower != null && ref.upper != null) ? `${ref.lower} - ${ref.upper} (${unit})` : '';
        tr.appendChild(td1);
        data.dates.forEach((dt) => {
          const td = document.createElement('td');
          td.className = 'cell';
          const pt = map[dt];
          if (pt) {
            const v = typeof pt.value === 'number' ? pt.value : null;
            let flag = (pt.flag || '').trim();
            if (!flag && v != null) {
              const lower = ind.ref && typeof ind.ref.lower === 'number' ? ind.ref.lower : null;
              const upper = ind.ref && typeof ind.ref.upper === 'number' ? ind.ref.upper : null;
              if (lower != null && v < lower) flag = '↓';
              else if (upper != null && v > upper) flag = '↑';
              else if (lower != null || upper != null) flag = '-';
            }
            td.textContent = v != null ? String(v) + (flag === '↑' ? ' ↑' : flag === '↓' ? ' ↓' : '') : '';
            if (flag === '↑') td.classList.add('up');
            else if (flag === '↓') td.classList.add('down');
            else td.classList.add('normal');
          } else {
            td.textContent = '';
            td.classList.add('missing');
          }
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
    } else {
      const trh = document.createElement('tr');
      const h0 = document.createElement('th');
      h0.textContent = '检测日期';
      trh.appendChild(h0);
      const h1 = document.createElement('th');
      h1.textContent = '所属化疗周期';
      trh.appendChild(h1);
      selectedInds.forEach((name) => {
        const th = document.createElement('th');
        th.textContent = name;
        trh.appendChild(th);
      });
      thead.appendChild(trh);

      const trh2 = document.createElement('tr');
      const thEmpty1 = document.createElement('th');
      thEmpty1.textContent = '';
      trh2.appendChild(thEmpty1);
      const thEmpty2 = document.createElement('th');
      thEmpty2.textContent = '';
      trh2.appendChild(thEmpty2);
      selectedInds.forEach((name) => {
        const ind = data.indicators[name] || {};
        const ref = ind.ref || {};
        const unit = ind.unit || '';
        const th2 = document.createElement('th');
        th2.textContent = (ref.lower != null && ref.upper != null) ? `${ref.lower} - ${ref.upper} (${unit})` : (unit || '');
        trh2.appendChild(th2);
      });
      thead.appendChild(trh2);

      data.dates.forEach((dt) => {
        const tr = document.createElement('tr');
        const td0 = document.createElement('td');
        td0.textContent = formatDateDot(dt);
        tr.appendChild(td0);
        const td1 = document.createElement('td');
        td1.textContent = computePhaseLabel(dt);
        tr.appendChild(td1);
        selectedInds.forEach((name) => {
          const ind = data.indicators[name];
          const seriesAll = ind && ind.series ? ind.series : [];
          const map = {};
          for (let i = 0; i < seriesAll.length; i++) { const pt = seriesAll[i]; map[pt.date] = pt; }
          const td = document.createElement('td');
          td.className = 'cell';
          const pt = map[dt];
          if (pt) {
            const v = typeof pt.value === 'number' ? pt.value : null;
            let flag = (pt.flag || '').trim();
            if (!flag && v != null) {
              const lower = ind && ind.ref && typeof ind.ref.lower === 'number' ? ind.ref.lower : null;
              const upper = ind && ind.ref && typeof ind.ref.upper === 'number' ? ind.ref.upper : null;
              if (lower != null && v < lower) flag = '↓';
              else if (upper != null && v > upper) flag = '↑';
              else if (lower != null || upper != null) flag = '-';
            }
            td.textContent = v != null ? String(v) + (flag === '↑' ? ' ↑' : flag === '↓' ? ' ↓' : '') : '';
            if (flag === '↑') td.classList.add('up');
            else if (flag === '↓') td.classList.add('down');
            else td.classList.add('normal');
          } else {
            td.textContent = '';
            td.classList.add('missing');
          }
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
    }

    table.appendChild(thead);
    table.appendChild(tbody);
    pivotWrapper.appendChild(table);
  }

  function update() {
    const selected = getSelectedIndicators();
    renderCoreCharts(coreNames);
    renderExtCharts(selected);
    const allShown = coreNames.concat(selected);
    renderPivotTable(allShown);
  }

  indicatorPanel.addEventListener('change', update);
  startCycleInput.addEventListener('change', update);
  endCycleInput.addEventListener('change', update);
  showTrendInput.addEventListener('change', update);

  // 折叠面板交互：点击标题展开/收起
  if (extendCollapse) {
    const header = extendCollapse.querySelector('.collapse-header');
    if (header) {
      header.addEventListener('click', () => {
        const expanded = header.getAttribute('aria-expanded') === 'true';
        header.setAttribute('aria-expanded', expanded ? 'false' : 'true');
      });
    }
  }

  update();
  // 窗口尺寸变化时自适应图表大小
  window.addEventListener('resize', () => {
    chartInstancesCore.forEach((obj) => { try { obj.chart && obj.chart.resize(); } catch (_) {} });
    chartInstancesExt.forEach((obj) => { try { obj.chart && obj.chart.resize(); } catch (_) {} });
  });

  if (toggleOrientationBtn) {
    toggleOrientationBtn.addEventListener('click', () => {
      isTransposed = !isTransposed;
      toggleOrientationBtn.textContent = isTransposed ? '↕️' : '↔️';
      toggleOrientationBtn.setAttribute('title', isTransposed ? '切换为指标为行' : '切换为日期为行');
      update();
    });
  }
  if (exportBtn && exportDropdown && exportMenu) {
    exportBtn.addEventListener('click', () => {
      const opened = exportDropdown.classList.contains('open');
      exportDropdown.classList.toggle('open', !opened);
      exportBtn.setAttribute('aria-expanded', (!opened).toString());
    });
    document.addEventListener('click', (e) => {
      if (!exportDropdown.contains(e.target)) {
        exportDropdown.classList.remove('open');
        exportBtn.setAttribute('aria-expanded', 'false');
      }
    });
    exportMenu.addEventListener('click', async (e) => {
      const target = e.target;
      if (!target || !target.dataset || !target.dataset.format) return;
      const fmt = target.dataset.format;
      const selected = getSelectedIndicators();
      const allShown = coreNames.concat(selected);
      const now = new Date();
      const yyyy = String(now.getFullYear());
      const mm = String(now.getMonth() + 1).padStart(2, '0');
      const dd = String(now.getDate()).padStart(2, '0');
      const base = `pivot-${yyyy}-${mm}-${dd}`;
      try {
        if (fmt === 'csv') {
          const rows = collectPivotData(allShown);
          await exportCSV(rows, base + '.csv');
          showToast('CSV 导出完成');
        } else if (fmt === 'md') {
          const rows = collectPivotData(allShown);
          await exportMarkdown(rows, base + '.md');
          showToast('Markdown 导出完成');
        } else if (fmt === 'xlsx') {
          const rows = collectPivotData(allShown);
          await exportExcel(rows, base + '.xlsx');
          showToast('Excel 导出完成');
        } else if (fmt === 'pdf') {
          await exportPDF(base + '.pdf');
          showToast('PDF 导出完成');
        }
      } catch (err) {
        showError('导出失败：' + (err && err.message ? err.message : String(err)));
      } finally {
        exportDropdown.classList.remove('open');
        exportBtn.setAttribute('aria-expanded', 'false');
      }
    });
  }

  function collectPivotData(selectedInds) {
    const header1 = [];
    const header2 = [];
    const body = [];
    if (!isTransposed) {
      header1.push('检测指标');
      header1.push('参考范围');
      for (let i = 0; i < data.dates.length; i++) header1.push(formatDateDot(data.dates[i]));
      header2.push('所属化疗周期');
      header2.push('');
      for (let i = 0; i < data.dates.length; i++) header2.push(computePhaseLabel(data.dates[i]));
      for (let i = 0; i < selectedInds.length; i++) {
        const name = selectedInds[i];
        const ind = data.indicators[name];
        if (!ind) continue;
        const ref = ind.ref || {};
        const unit = ind.unit || '';
        const row = [];
        row.push(name);
        row.push((ref.lower != null && ref.upper != null) ? `${ref.lower} - ${ref.upper} (${unit})` : '');
        for (let j = 0; j < data.dates.length; j++) {
          const dt = data.dates[j];
          const pt = (ind.series || []).find((p) => p.date === dt);
          if (pt && typeof pt.value === 'number') {
            let flag = (pt.flag || '').trim();
            if (!flag) {
              const lower = ind.ref && typeof ind.ref.lower === 'number' ? ind.ref.lower : null;
              const upper = ind.ref && typeof ind.ref.upper === 'number' ? ind.ref.upper : null;
              if (lower != null && pt.value < lower) flag = '↓';
              else if (upper != null && pt.value > upper) flag = '↑';
              else if (lower != null || upper != null) flag = '-';
            }
            row.push(String(pt.value) + (flag === '↑' ? ' ↑' : flag === '↓' ? ' ↓' : ''));
          } else {
            row.push('');
          }
        }
        body.push(row);
      }
    } else {
      header1.push('检测日期');
      header1.push('所属化疗周期');
      for (let i = 0; i < selectedInds.length; i++) header1.push(selectedInds[i]);
      header2.push('');
      header2.push('');
      for (let i = 0; i < selectedInds.length; i++) {
        const ind = data.indicators[selectedInds[i]] || {};
        const ref = ind.ref || {};
        const unit = ind.unit || '';
        header2.push((ref.lower != null && ref.upper != null) ? `${ref.lower} - ${ref.upper} (${unit})` : (unit || ''));
      }
      for (let j = 0; j < data.dates.length; j++) {
        const dt = data.dates[j];
        const row = [];
        row.push(formatDateDot(dt));
        row.push(computePhaseLabel(dt));
        for (let i = 0; i < selectedInds.length; i++) {
          const name = selectedInds[i];
          const ind = data.indicators[name];
          const pt = ind && (ind.series || []).find((p) => p.date === dt);
          if (pt && typeof pt.value === 'number') {
            let flag = (pt.flag || '').trim();
            if (!flag) {
              const lower = ind && ind.ref && typeof ind.ref.lower === 'number' ? ind.ref.lower : null;
              const upper = ind && ind.ref && typeof ind.ref.upper === 'number' ? ind.ref.upper : null;
              if (lower != null && pt.value < lower) flag = '↓';
              else if (upper != null && pt.value > upper) flag = '↑';
              else if (lower != null || upper != null) flag = '-';
            }
            row.push(String(pt.value) + (flag === '↑' ? ' ↑' : flag === '↓' ? ' ↓' : ''));
          } else {
            row.push('');
          }
        }
        body.push(row);
      }
    }
    return [header1, header2].concat(body);
  }

  async function exportCSV(rows, filename) {
    const totalRows = rows.length;
    const needsProgress = totalRows >= 10000;
    if (needsProgress) showProgress('正在导出 CSV');
    let out = '\uFEFF';
    const chunk = 500;
    for (let i = 0; i < totalRows; i += chunk) {
      const end = Math.min(i + chunk, totalRows);
      for (let r = i; r < end; r++) {
        const line = rows[r].map((cell) => {
          const s = cell == null ? '' : String(cell);
          if (/[",\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
          return s;
        }).join(',');
        out += line + '\n';
      }
      if (needsProgress) {
        updateProgress(Math.round((end / totalRows) * 100));
        await new Promise((res) => setTimeout(res, 0));
      }
    }
    const blob = new Blob([out], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.target = '_blank';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 250);
    if (needsProgress) hideProgress();
  }

  async function exportMarkdown(rows, filename) {
    const totalRows = rows.length;
    const needsProgress = totalRows >= 10000;
    if (needsProgress) showProgress('正在导出 Markdown');
    const header = rows[0] || [];
    const md = [];
    md.push('| ' + header.map((x) => String(x || '')).join(' | ') + ' |');
    md.push('|' + header.map(() => ' --- ').join('|') + '|');
    const start = 2;
    const chunk = 500;
    for (let i = start; i < totalRows; i += chunk) {
      const end = Math.min(i + chunk, totalRows);
      for (let r = i; r < end; r++) {
        md.push('| ' + rows[r].map((x) => String(x || '').replace(/\n/g, ' ')).join(' | ') + ' |');
      }
      if (needsProgress) {
        updateProgress(Math.round((end / totalRows) * 100));
        await new Promise((res) => setTimeout(res, 0));
      }
    }
    const blob = new Blob([md.join('\n') + '\n'], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.target = '_blank';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 250);
    if (needsProgress) hideProgress();
  }

  async function exportExcel(rows, filename) {
    if (typeof ExcelJS === 'undefined') return;
    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('Pivot');
    const totalRows = rows.length;
    const needsProgress = totalRows >= 10000;
    if (needsProgress) showProgress('正在导出 Excel');
    const chunk = 500;
    for (let i = 0; i < totalRows; i += chunk) {
      const end = Math.min(i + chunk, totalRows);
      for (let r = i; r < end; r++) ws.addRow(rows[r]);
      if (needsProgress) {
        updateProgress(Math.round((end / totalRows) * 100));
        await new Promise((res) => setTimeout(res, 0));
      }
    }
    const headerRows = 2;
    for (let r = 1; r <= headerRows; r++) {
      const row = ws.getRow(r);
      row.font = { bold: true };
      row.alignment = { vertical: 'middle', horizontal: 'center' };
      row.eachCell({ includeEmpty: true }, (cell) => { cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFF9F9F9' } }; });
    }
    ws.views = [{ state: 'frozen', xSplit: 0, ySplit: 2 }];
    const widths = [];
    const colCount = rows[0] ? rows[0].length : 0;
    for (let c = 0; c < colCount; c++) {
      let max = 10;
      for (let r = 0; r < Math.min(rows.length, 100); r++) {
        const v = rows[r][c];
        const len = v == null ? 0 : String(v).length;
        if (len > max) max = len;
      }
      widths.push({ width: Math.min(40, Math.max(10, Math.ceil(max * 1.2))) });
    }
    ws.columns = widths;
    const buf = await wb.xlsx.writeBuffer();
    const blob = new Blob([buf], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.target = '_blank';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 250);
    if (needsProgress) hideProgress();
  }

  async function exportPDF(filename) {
    if (typeof html2pdf === 'undefined') return;
    const node = pivotWrapper.cloneNode(true);
    const ths = node.querySelectorAll('thead th');
    ths.forEach((el) => { el.style.position = 'static'; el.style.top = 'auto'; });
    const opt = { margin: 10, filename, image: { type: 'jpeg', quality: 0.98 }, html2canvas: { scale: 2 }, jsPDF: { unit: 'mm', format: 'a4', orientation: 'landscape' }, pagebreak: { mode: ['css','legacy'] } };
    await html2pdf().set(opt).from(node).save();
  }

  function ensureProgressDom() {
    let overlay = document.getElementById('progressOverlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'progressOverlay';
      overlay.className = 'progress-overlay';
      const card = document.createElement('div');
      card.className = 'progress-card';
      const title = document.createElement('div');
      title.className = 'progress-title';
      title.id = 'progressTitle';
      const bar = document.createElement('div');
      bar.className = 'progress-bar';
      const inner = document.createElement('div');
      inner.className = 'progress-bar-inner';
      inner.id = 'progressInner';
      bar.appendChild(inner);
      card.appendChild(title);
      card.appendChild(bar);
      overlay.appendChild(card);
      document.body.appendChild(overlay);
    }
    return overlay;
  }
  function showProgress(title) {
    const overlay = ensureProgressDom();
    const t = document.getElementById('progressTitle');
    if (t) t.textContent = title || '';
    const inner = document.getElementById('progressInner');
    if (inner) inner.style.width = '0%';
    overlay.style.display = 'flex';
  }
  function updateProgress(pct) {
    const inner = document.getElementById('progressInner');
    if (inner) inner.style.width = String(Math.max(0, Math.min(100, pct))) + '%';
  }
  function hideProgress() {
    const overlay = document.getElementById('progressOverlay');
    if (overlay) overlay.style.display = 'none';
  }
  function ensureErrorBanner() {
    let banner = document.getElementById('errorBanner');
    if (!banner) {
      banner = document.createElement('div');
      banner.id = 'errorBanner';
      banner.className = 'error-banner';
      const section = document.querySelector('.table-section');
      if (section) section.insertBefore(banner, section.firstChild);
    }
    return banner;
  }
  function showError(msg) {
    const banner = ensureErrorBanner();
    banner.textContent = msg || '发生错误';
    banner.style.display = 'block';
    setTimeout(() => { banner.style.display = 'none'; }, 5000);
  }
  function ensureToastDom() {
    let el = document.getElementById('toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'toast';
      el.className = 'toast';
      document.body.appendChild(el);
    }
    return el;
  }
  function showToast(text) {
    const el = ensureToastDom();
    el.textContent = text || '';
    el.classList.add('show');
    setTimeout(() => { el.classList.remove('show'); }, 2000);
  }
})();
