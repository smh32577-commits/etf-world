/* ETF 월드 (서울 WM센터) — 정적 SPA. 데이터는 data/*.json (파이프라인이 10분마다 갱신) */
(() => {
  "use strict";

  const $app = document.getElementById("app");
  const cache = {};
  const state = { hotDir: "up", homeHot: "up", today: "gainers", trendKey: "w1", usKey: "d10", find: { q: "", tag: "전체", sort: "am", limit: 40 }, chartRange: "3M", holdAll: false };

  // ── 데이터 ─────────────────────────────────────────────
  async function getJSON(path, { fresh = false } = {}) {
    if (!fresh && cache[path]) return cache[path];
    const r = await fetch(`data/${path}?t=${fresh ? Date.now() : ""}`, { cache: fresh ? "no-store" : "default" });
    if (!r.ok) throw new Error(`${path} ${r.status}`);
    return (cache[path] = await r.json());
  }
  let universeMap = null;
  async function base() {
    const [live, uni] = await Promise.all([getJSON("live.json"), getJSON("universe.json")]);
    if (!universeMap) universeMap = Object.fromEntries(uni.etfs.map(e => [e.c, e]));
    return { live, uni, U: universeMap };
  }
  const briefCache = {};
  const bust = () => Math.floor(Date.now() / 600000);
  const getBriefFile = id => (briefCache[id] ||= fetch(`briefs/${id}.json?t=${bust()}`)
    .then(r => r.ok ? r.json() : null).catch(() => null));
  const getBrief = () => getBriefFile("latest");
  const getBriefIndex = () => getBriefFile("index").then(x => x?.briefs || []);
  const getTrends = () => getBriefFile("trends");

  setInterval(async () => {                       // 2분마다 최신 live.json 확인
    try {
      const prev = cache["live.json"]?.updated;
      const live = await getJSON("live.json", { fresh: true });
      if (live.updated !== prev && !document.activeElement?.matches("input")) render();
    } catch (_) { /* ignore */ }
  }, 120000);

  // ── 저장소 (즐겨찾기, 보유수량) ──────────────────────────
  const store = {
    get(k, d) { try { return JSON.parse(localStorage.getItem("etfworld." + k)) ?? d; } catch (_) { return d; } },
    set(k, v) { try { localStorage.setItem("etfworld." + k, JSON.stringify(v)); } catch (_) { /* ignore */ } },
  };
  const favs = () => store.get("fav", []);
  const isFav = c => favs().includes(c);
  function toggleFav(c) {
    const f = favs();
    store.set("fav", f.includes(c) ? f.filter(x => x !== c) : [...f, c]);
  }

  // ── 포맷 ───────────────────────────────────────────────
  const nf = new Intl.NumberFormat("ko-KR");
  const fmt = (n, d = 0) => n == null || isNaN(n) ? "—" : n.toLocaleString("ko-KR", { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (x, d = 2) => x == null || isNaN(x) ? "—" : `${x > 0 ? "+" : ""}${x.toFixed(d)}%`;
  const cls = x => x == null || Math.abs(x) < 0.005 ? "flat" : x > 0 ? "up" : "down";
  const eok = v => {            // 억 단위 숫자 → "1.2조" / "3,450억"
    if (v == null) return "—";
    if (v >= 10000) return `${(v / 10000).toFixed(v >= 100000 ? 0 : 1)}조`;
    return `${nf.format(Math.round(v))}억`;
  };
  const amEok = am => eok(am / 100);  // 거래대금(백만원) → 억
  const esc = s => String(s ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  const josa = (w, a, b) => { const c = (w || "").charCodeAt(w.length - 1) - 0xac00; return c >= 0 && c <= 11171 && c % 28 ? a : b; };
  const ticker = r => (r || "").split(".")[0];
  const hhmm = iso => { if (!iso) return ""; const d = new Date(iso); return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
  const BRANDS = ["KODEX", "TIGER", "ACE", "RISE", "SOL", "PLUS", "HANARO", "KIWOOM", "KoAct", "TIME", "1Q", "WON", "BNK", "TRUSTON", "UNICORN", "FOCUS", "마이다스", "에셋플러스", "HK", "DAISHIN343", "ITF", "VITA", "파워", "마이티"];
  function avatar(name) {
    const b = BRANDS.find(x => name.startsWith(x)) || name.split(" ")[0];
    const t = b.length > 5 ? b.slice(0, 4) : b;
    return `<div class="avatar" aria-hidden="true">${esc(t)}</div>`;
  }

  // ── 공통 조각 ──────────────────────────────────────────
  function statusPill(live) {
    const dot = live.mode === "live" ? "live" : live.mode === "official" ? "official" : "";
    return `<span class="status"><span class="dot ${dot}"></span>${esc(live.label)} · ${hhmm(live.updated)}</span>`;
  }
  function etfRow(e, { idx, meta, side, plain } = {}) {
    return `<a class="row" href="#/etf/${e.c}">
      ${idx != null ? `<span class="rank">${idx}</span>` : ""}
      ${plain ? "" : avatar(e.n)}
      <div class="row-main"><div class="row-name">${esc(e.n)}</div><div class="row-meta">${meta ?? ""}</div></div>
      <div class="row-side">${side}</div></a>`;
  }
  const priceSide = (p, ch) => `<div class="row-price">${fmt(p)}원</div><div class="row-chg ${cls(ch)}">${pct(ch)}</div>`;
  const badgeSide = x => `<span class="badge-chg ${cls(x)}">${pct(x)}</span>`;
  const contribText = top => (top || []).map(([r, , ri]) => `${esc(ticker(r))} <span class="${cls(ri)}">${pct(ri, 1)}</span>`).join(" · ");
  const seg = (name, opts, cur) => `<div class="seg" role="tablist">${opts.map(([v, l]) => `<button role="tab" data-seg="${name}" data-v="${v}" class="${v === cur ? "on" : ""}">${l}</button>`).join("")}</div>`;
  const skeleton = n => Array.from({ length: n }, () => '<div class="skeleton"></div>').join("");

  function hotExplain(live) {
    if (live.mode === "live") return `미국 ${esc(live.usSession)} 시세와 환율을 반영한 추정 iNAV 기준이에요.`;
    const at = live.rank.hotAt ? `${hhmm(live.rank.hotAt)} 기준 마지막 추정 순위예요. ` : "";
    if (live.mode === "official") return `${at}지금은 KRX 정규장이라 공식 iNAV가 실시간으로 나와요.`;
    return `${at}휴장 구간이라 추정을 잠시 멈췄어요.`;
  }

  // ── 브리핑 ─────────────────────────────────────────────
  const toneCls = t => t === "up" ? "up" : t === "down" ? "down" : "flat";
  const toneTxt = t => t === "up" ? "강세" : t === "down" ? "약세" : "혼조";
  function briefMeta(b) {
    return `${b.session ? esc(b.session) + " · " : ""}${hhmm(b.dataAsOf)} 데이터 · AI 요약, 참고용`;
  }
  function briefItem(it, U, { open = false } = {}) {
    const links = it.codes.filter(c => U[c]).map(c => `<a class="tag accent" href="#/etf/${c}">${esc(U[c].n)}</a>`).join(" ");
    return `<details class="bitem" ${open ? "open" : ""}>
      <summary><div class="bhead"><span class="btone ${toneCls(it.tone)}">${toneTxt(it.tone)}</span><span class="btitle">${esc(it.title)}</span></div>
        <div class="bsum">${esc(it.summary)}</div></summary>
      <ul class="bpoints">${it.points.map(p => `<li>${esc(p)}</li>`).join("")}</ul>
      ${it.watch ? `<div class="bwatch"><b>볼 포인트</b> ${esc(it.watch)}</div>` : ""}
      <div class="blinks">${links}</div>
      <div class="bsrc">${it.sources.map(x => `<a href="${esc(x.u)}" target="_blank" rel="noopener">${esc(x.t)}</a>`).join("")}</div>
    </details>`;
  }
  function briefCard(b, U) {
    if (!b) return "";
    return `<section class="card brief">
      <div class="card-head"><div><div class="card-title">오늘의 브리핑</div><div class="card-sub">${briefMeta(b)}</div></div></div>
      <div class="bheadline">${esc(b.market.headline)}</div>
      <ul class="bpoints">${b.market.points.slice(0, 2).map(p => `<li>${esc(p)}</li>`).join("")}</ul>
      <div class="list" style="margin-top:6px">${b.items.map(it => `<a class="row" href="#/brief">
        <span class="btone ${toneCls(it.tone)}">${toneTxt(it.tone)}</span>
        <div class="row-main"><div class="row-name">${esc(it.title)}</div><div class="row-meta">${esc(it.summary)}</div></div></a>`).join("")}</div>
      <div style="margin-top:10px"><a class="more" href="#/brief">브리핑 전체 보기</a></div>
    </section>`;
  }
  async function brief(params) {
    const [{ live, U }, idx] = await Promise.all([base(), getBriefIndex()]);
    const id = params.get("id") || idx[0]?.id || "latest";
    const b = await getBriefFile(id);
    if (!b) { $app.innerHTML = `<div class="card" style="margin-top:20px"><div class="empty">아직 작성된 브리핑이 없어요.</div></div>`; return; }
    const day = (idx.find(x => x.id === id) || idx[0] || {}).date;
    const sameDay = idx.filter(x => x.date === day).slice().reverse();
    const days = [...new Set(idx.map(x => x.date))].slice(0, 7);
    const tabs = sameDay.length > 1 ? `<div class="seg" style="margin-top:14px">${sameDay.map(x =>
      `<button class="${x.id === id ? "on" : ""}" data-go="#/brief?id=${x.id}">${esc(x.session)}</button>`).join("")}</div>` : "";
    const past = days.length > 1 ? `<div class="chips" style="margin-top:12px">${days.map(d => {
      const first = idx.find(x => x.date === d);
      return `<button class="chip ${d === day ? "on" : ""}" data-go="#/brief?id=${first.id}">${d.slice(5).replace("-", "/")}</button>`;
    }).join("")}</div>` : "";
    $app.innerHTML = `
      <div class="hero"><h1>${esc(b.market.headline)}</h1><p>${briefMeta(b)}</p>${tabs}${past}</div>
      <section class="card"><div class="card-title" style="margin-bottom:10px">오늘의 시황</div>
        <ul class="bpoints">${b.market.points.map(p => `<li>${esc(p)}</li>`).join("")}</ul></section>
      <section class="card"><div class="card-title" style="margin-bottom:6px">많이 움직인 ETF</div>
        ${b.items.map(it => briefItem(it, U, { open: true })).join("")}</section>
      ${await (async () => { const tr = await getTrends(); return tr ? `<section class="card"><div class="card-title" style="margin-bottom:2px">요즘 트렌드</div>
        <div class="card-sub" style="margin-bottom:6px">${esc(tr.note || "")}</div>
        ${tr.items.map(it => briefItem({ ...it, title: `${it.title} · ${it.period}` }, U, { open: false })).join("")}</section>` : ""; })()}
      <p class="foot">거래대금·등락률·거래량 급증 상위 ETF를 골라 Claude가 관련 뉴스를 읽고 정리했어요. 원인 해석은 틀릴 수 있으니 출처 기사를 함께 확인하세요. '(추정)'은 기사로 확인되지 않은 해석이에요.</p>
      ${footer(live)}`;
  }

  // ── 요즘 트렌드 ───────────────────────────────────────
  function trendWhy(tr, key) {
    const want = key === "w1" ? "1주" : "1개월";
    const map = {};
    for (const it of tr?.items || []) if (it.period.includes(want)) for (const c of it.codes) map[c] = it;
    return map;
  }
  function trendBody(live, tr, key) {
    const t = live.rank.trend?.[key];
    if (!t) return `<div class="empty">추세 데이터가 아직 없어요.</div>`;
    const why = trendWhy(tr, key);
    const th = t.themes.slice(0, 8);
    const shown = new Set();                       // 같은 테마 이유는 처음 한 번만
    const row = (e, i) => {
      let w = why[e.c];
      if (w && shown.has(w.title)) w = null; else if (w) shown.add(w.title);
      return `<a class="row" href="#/etf/${e.c}"><span class="rank">${i + 1}</span>
        <div class="row-main"><div class="row-name">${esc(e.n)}</div>
          <div class="row-meta">${esc(e.top.slice(0, 3).join(" · "))}</div>
          ${w ? `<div class="why-news"><span>${esc(w.title)}</span>${esc(w.summary)}</div>` : ""}</div>
        <div class="row-side">${badgeSide(e.r)}</div></a>`;
    };
    const stories = (tr?.items || []).filter(it => it.period.includes(key === "w1" ? "1주" : "1개월"));
    return `
      <div class="tthemes">${th.map(x => `<a class="tchip" href="#/find?tag=${encodeURIComponent(x.t)}" style="background:${heatBg(x.avg / (key === "w1" ? 2 : 4))}">
        <span>${esc(x.t)}</span><b>${pct(x.avg, 1)}</b></a>`).join("")}</div>
      <div class="tsub up">많이 오른 ETF</div>
      <div class="list">${t.up.slice(0, 5).map(row).join("")}</div>
      <div class="tsub down">많이 내린 ETF</div>
      <div class="list">${t.down.slice(0, 5).map(row).join("")}</div>
      ${stories.length ? `<details class="tstories"><summary>왜 이런 흐름일까? · ${stories.length}개 테마</summary>
        ${stories.map(it => briefItem({ ...it, title: `${it.title} · ${it.period}` }, universeMap, { open: false })).join("")}</details>` : ""}`;
  }

  // ── 미국 ETF ──────────────────────────────────────────
  const US_TABS = [["d10", "10일 상승률"], ["up", "오늘 급등"], ["down", "오늘 급락"]];
  function usBody(live, key) {
    const us = live.rank.us;
    const list = (us?.[key] || []).slice(0, 5);
    if (!list.length) return `<div class="empty">데이터가 없어요.</div>`;
    const rows = list.map((e, i) => {
      if (key === "d10") return etfRow(e, { idx: i + 1, plain: true, meta: esc((e.top || []).join(" · ")), side: badgeSide(e.r) });
      let meta = `거래대금 ${amEok(e.am)}`;
      if (e.dr?.length) meta += `<div class="why-dr">${drText(e.dr)}</div>`;
      return etfRow(e, { idx: i + 1, plain: true, meta, side: badgeSide(e.ch) });
    }).join("");
    const note = key === "d10"
      ? `${live.rank.trend?.asOf ? fmtDate(live.rank.trend.asOf) + " 종가 기준 " : ""}최근 10거래일 수익률이에요.`
      : "오늘 등락률이에요. 거래대금 1억 이상만 넣었어요.";
    return `<div class="list">${rows}</div><p class="note">${note} 미국 상장 종목 비중 50% 이상이거나 이름에 '미국'이 들어간 ETF ${fmt(us.n)}개 중, 레버리지·인버스·채권형과 시총 100억 미만은 제외했어요.</p>`;
  }

  // ── 홈 ────────────────────────────────────────────────
  const RANK_TABS = [
    ["gainers", "상승"], ["losers", "하락"], ["amount", "거래대금"], ["surge", "거래량 급증"], ["up", "내일 HOT ↑"], ["down", "내일 HOT ↓"],
  ];
  const drText = dr => (dr || []).map(([n, r]) => `${esc(n)} <span class="${cls(r)}">${pct(r, 1)}</span>`).join(" · ");
  function rankRows(live, key, why = {}) {
    const list = (live.rank[key] || []).slice(0, 5);
    if (!list.length) return `<div class="empty">${key === "up" || key === "down" ? "아직 추정 순위가 없어요.<br>미국 프리마켓(17:00)부터 계산해요." : "데이터가 없어요."}</div>`;
    return list.map((e, i) => {
      let meta, side;
      if (key === "up" || key === "down") { meta = contribText(e.top); side = badgeSide(e.ex); }
      else if (key === "surge") { meta = `평소의 <b>${e.sr}배</b> · 거래대금 ${amEok(e.am)}`; side = badgeSide(e.ch); }
      else if (key === "amount") { meta = `거래대금 <b>${amEok(e.am)}</b>`; side = badgeSide(e.ch); }
      else { meta = `거래대금 ${amEok(e.am)}`; side = badgeSide(e.ch); }
      if (e.dr?.length && key !== "up" && key !== "down") meta += `<div class="why-dr">${drText(e.dr)}</div>`;
      if (why[e.c]) meta += `<div class="why-news"><span>뉴스</span>${esc(why[e.c])}</div>`;
      return etfRow(e, { idx: i + 1, meta, side, plain: true });
    }).join("");
  }
  function rankNote(live, key) {
    if (key === "up" || key === "down") return hotExplain(live) + " 종가 대비 예상 등락이에요.";
    if (key === "surge") return "최근 20일 평균 거래량 대비 오늘 거래량이에요. 금리형 제외.";
    if (key === "amount") return "금리·채권형 파킹 ETF는 제외했어요.";
    return "레버리지·인버스와 소형 ETF(시총 100억 미만)는 제외했어요.";
  }
  function heatBg(v) {
    if (v == null || Math.abs(v) < 0.05) return "var(--fill)";
    const k = Math.min(Math.abs(v) / 4, 1);          // ±4%에서 최대 농도
    return `color-mix(in srgb, var(--${v > 0 ? "up" : "down"}) ${Math.round(10 + k * 45)}%, var(--card))`;
  }

  async function home() {
    const [{ live, U }, b, bIdx, tr] = await Promise.all([base(), getBrief(), getBriefIndex(), getTrends()]);
    state.trends = tr;
    const r = live.rank;
    if (!state.rankTab) state.rankTab = live.mode === "live" ? "up" : "gainers";
    const today = (live.updated || "").slice(0, 10);

    // 시장 폭: 금리·채권형, 레버리지·인버스 제외
    let upN = 0, dnN = 0, flN = 0;
    for (const [c, e] of Object.entries(live.etfs)) {
      const u = U[c];
      if (!u || u.tab === 6 || u.tags.includes("채권") || u.f.includes("lev") || u.f.includes("inv") || e.ch == null) continue;
      if (e.ch > 0.05) upN++; else if (e.ch < -0.05) dnN++; else flN++;
    }
    const tot = upN + dnN + flN || 1;
    const upP = upN / tot * 100, dnP = dnN / tot * 100;
    const briefToday = b && (b.generatedAt || "").slice(0, 10) === today;
    const headline = briefToday ? b.market.headline
      : dnP > 60 ? `ETF ${fmt(tot)}개 중 ${Math.round(dnP)}%가 내리고 있어요`
      : upP > 60 ? `ETF ${fmt(tot)}개 중 ${Math.round(upP)}%가 오르고 있어요`
      : "오르는 ETF와 내리는 ETF가 엇갈리고 있어요";
    const themes = r.themes.filter(t => t.t !== "채권").slice(0, 9);
    const why = {};                                  // 오늘 브리핑의 ETF별 한 줄 요약
    if (briefToday) for (const it of b.items) for (const c of it.codes) why[c] = it.summary;
    state.why = why;

    const ticker = live.indices.map(i => `<div class="tk"><span class="n">${esc(i.n)}</span>
      <span class="v">${fmt(i.v, i.fx ? 1 : 2)}</span><span class="c ${cls(i.c)}">${pct(i.c)}</span></div>`).join("");

    const favList = favs().filter(c => U[c]);
    const myCard = favList.length ? `<section class="card">
      <div class="card-head"><div class="card-title">내 ETF</div><a class="more" href="#/my">계좌 보기</a></div>
      <div class="list">${favList.slice(0, 5).map(c => {
        const e = live.etfs[c] || {}, u = U[c];
        return etfRow({ c, n: u.n }, {
          plain: true,
          meta: e.ex != null ? `추정 iNAV · 종가 대비` : `${fmt(e.p)}원`,
          side: badgeSide(e.ex != null ? e.ex : e.ch),
        });
      }).join("")}</div></section>` : "";

    const latestId = bIdx[0]?.id || "latest";
    const todayBriefs = bIdx.filter(x => x.date === (b?.generatedAt || "").slice(0, 10));
    const briefCardC = b ? `<section class="card">
      <div class="card-head"><div><div class="card-title">브리핑</div><div class="card-sub">${briefMeta(b)}</div></div>
        <a class="more" href="#/brief">전체</a></div>
      ${todayBriefs.length > 1 ? `<div class="chips mini">${todayBriefs.slice().reverse().map(x =>
        `<button class="chip ${x.id === latestId ? "on" : ""}" data-go="#/brief?id=${x.id}">${esc(x.session)}</button>`).join("")}</div>` : ""}
      <div class="blist">${b.items.map(it => `<a class="bline" href="#/brief?id=${latestId}">
        <span class="bdot ${toneCls(it.tone)}"></span><span class="bt">${esc(it.title)}</span>
        <span class="bs">${esc(it.summary)}</span></a>`).join("")}</div>
    </section>` : "";

    $app.innerHTML = `
      <div class="topline">${statusPill(live)}</div>
      <div class="ticker">${ticker}</div>

      <section class="card market">
        <div class="card-sub">지금 시장</div>
        <h2 class="mk-head">${esc(headline)}</h2>
        <div class="breadth" role="img" aria-label="상승 ${upN}개, 보합 ${flN}개, 하락 ${dnN}개">
          <span class="bu" style="width:${upP}%"></span><span class="bf" style="width:${100 - upP - dnP}%"></span><span class="bd" style="width:${dnP}%"></span>
        </div>
        <div class="breadth-lbl"><span>상승 ETF <b class="up">${fmt(upN)}</b>개</span><span>보합 ${fmt(flN)}개</span><span>하락 ETF <b class="down">${fmt(dnN)}</b>개</span></div>
        <div class="card-sub" style="margin-top:2px">금리·채권형, 레버리지·인버스 제외</div>
        <div class="heat">${themes.map(t => `<a class="hc" href="#/find?tag=${encodeURIComponent(t.t)}" style="background:${heatBg(t.avg)}" title="${esc(t.t)} ${t.n}개 · 거래대금 ${amEok(t.am)}">
          <span class="ht">${esc(t.t)}</span><span class="hv">${pct(t.avg, 1)}</span></a>`).join("")}</div>
        <div class="card-sub" style="margin-top:10px">테마별 시가총액 가중 평균 · 많이 움직인 테마 순 · 색이 진할수록 큰 변동</div>
      </section>

      <section class="card">
        <div class="card-head" style="margin-bottom:10px"><div class="card-title">순위</div>
          <a class="more" id="rankMore" href="${state.rankTab === "up" || state.rankTab === "down" ? "#/hot" : "#/find"}">더 보기</a></div>
        <div class="chips mini" role="tablist">${RANK_TABS.map(([k, l]) =>
          `<button class="chip ${k === state.rankTab ? "on" : ""}" data-rank="${k}">${l}</button>`).join("")}</div>
        <div class="list" id="rankList">${rankRows(live, state.rankTab, why)}</div>
        <p class="note" id="rankNote">${rankNote(live, state.rankTab)}</p>
      </section>

      ${r.us ? `<section class="card">
        <div class="card-head" style="margin-bottom:12px"><div class="card-title">미국 ETF</div>
          ${seg("usKey", US_TABS, state.usKey)}</div>
        <div id="usBody">${usBody(live, state.usKey)}</div>
      </section>` : ""}

      <section class="card">
        <div class="card-head" style="margin-bottom:12px"><div><div class="card-title">요즘 트렌드</div>
          <div class="card-sub">${live.rank.trend?.asOf ? fmtDate(live.rank.trend.asOf) + " 종가 기준 · " : ""}시총 300억 이상 · 레버리지·인버스 제외</div></div>
          ${seg("trendKey", [["w1", "1주"], ["m1", "1개월"]], state.trendKey)}</div>
        <div id="trendBody">${trendBody(live, tr, state.trendKey)}</div>
      </section>

      ${briefCardC}
      ${myCard}
      ${footer(live)}`;
  }

  function footer(live) {
    return `<p class="foot">모든 iNAV 추정값은 공개 시세(네이버 금융·Yahoo Finance)로 계산한 참고용이며 공식 발표값이 아니에요. 투자 판단의 근거로 쓰지 마세요.<br>데이터 갱신 ${hhmm(live.updated)} · 10분 간격</p>`;
  }

  // ── 내일의 HOT ─────────────────────────────────────────
  async function hot() {
    const { live } = await base();
    const list = state.hotDir === "up" ? live.rank.up : live.rank.down;
    $app.innerHTML = `
      <div class="hero"><h1>내일의 HOT ETF</h1>
        <p>장 마감 후 구성종목과 환율이 움직인 만큼, 내일 아침 시초가가 달라질 수 있어요.</p>
        <div style="margin-top:14px">${statusPill(live)}</div></div>
      <section class="card">
        <div style="margin-bottom:14px">${seg("hotDir", [["up", "상승 예상 TOP 15"], ["down", "하락 예상 TOP 15"]], state.hotDir).replace('class="seg"', 'class="seg wide"')}</div>
        <div class="list">${list.length ? list.map((e, i) => etfRow(e, {
          idx: i + 1, meta: contribText(e.top) || "—", side: badgeSide(e.ex),
        })).join("") : `<div class="empty">아직 추정 순위가 없어요.</div>`}</div>
        <p class="note">${hotExplain(live)} 시가총액 100억 이상, 미국 종목 비중 30% 이상 ETF만 계산해요. 레버리지·인버스·합성형은 제외해요.</p>
      </section>
      <section class="card">
        <div class="card-title" style="margin-bottom:8px">어떻게 계산하나요?</div>
        <div class="formula">
          KRX가 닫힌 15:30의 공식 iNAV를 기준점으로 삼고, 그 뒤 미국 구성종목 가격(프리·정규·애프터마켓)과 원/달러 환율 변동을 비중대로 더해요.<br><br>
          <code>추정 iNAV = iNAV(15:30) × (1 + Σ 비중 × [(1+종목 변동)(1+환율 변동) − 1])</code><br><br>
          환헤지(H) ETF는 환율 변동을 빼고, 국내 종목·현금은 변동 0으로 봐요.
        </div>
      </section>
      ${footer(live)}`;
  }

  // ── 찾기 ──────────────────────────────────────────────
  const CHIPS = ["전체", "해외주식", "국내주식", "반도체", "AI", "전력·원자력", "2차전지", "방산·우주", "조선", "바이오", "로봇", "배당", "커버드콜", "나스닥", "S&P500", "금·원자재", "채권", "중국", "일본", "인도·신흥국", "밸류업", "액티브", "레버리지", "인버스"];
  const SORTS = [["am", "거래대금 많은 순"], ["mc", "시가총액 큰 순"], ["r1m", "1개월 수익률 높은 순"], ["r1y", "1년 수익률 높은 순"], ["fee", "총보수 낮은 순"], ["div", "배당수익률 높은 순"]];
  const norm = s => (s || "").toLowerCase().replace(/\s+/g, "");

  async function find(params) {
    const { live, uni } = await base();
    const f = state.find;
    if (params.has("q")) f.q = params.get("q");
    if (params.has("tag")) f.tag = params.get("tag");
    $app.innerHTML = `
      <label class="searchbox">
        <svg viewBox="0 0 24 24" width="20" height="20"><circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="2" fill="none"/><path d="M20 20l-3.5-3.5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
        <input id="q" type="search" placeholder="ETF 이름, 종목코드, 담고 있는 종목 (예: 엔비디아)" value="${esc(f.q)}" autocomplete="off" enterkeyhint="search">
      </label>
      <div class="chips">${CHIPS.map(c => `<button class="chip ${c === f.tag ? "on" : ""}" data-tag="${esc(c)}">${esc(c)}</button>`).join("")}</div>
      <div id="stockHits"></div>
      <section class="card" id="results">${skeleton(5)}</section>`;
    const input = document.getElementById("q");
    if (!params.has("tag")) input.focus({ preventScroll: true });
    let tmr;
    input.addEventListener("input", () => { clearTimeout(tmr); tmr = setTimeout(() => { f.q = input.value; f.limit = 40; drawResults(live, uni); drawStockHits(live); }, 120); });
    drawResults(live, uni);
    drawStockHits(live);
  }

  function filterUniverse(uni, live) {
    const f = state.find, q = norm(f.q);
    let list = uni.etfs.filter(e => {
      if (q && !(norm(e.n).includes(q) || e.c.toLowerCase().startsWith(q) || e.top.some(t => norm(t).includes(q)))) return false;
      switch (f.tag) {
        case "전체": return true;
        case "해외주식": return e.tab === 4;
        case "국내주식": return e.tab === 1 || e.tab === 2;
        default: return e.tags.includes(f.tag);
      }
    });
    const val = e => {
      const l = live.etfs[e.c] || {};
      switch (f.sort) {
        case "am": return -(l.am || 0);
        case "mc": return -(l.mc || 0);
        case "r1m": return -(e.r1m ?? -1e9);
        case "r1y": return -(e.r1y ?? -1e9);
        case "fee": return e.fee ?? 1e9;
        case "div": return -(e.div ?? -1);
      }
      return 0;
    };
    return list.sort((a, b) => val(a) - val(b));
  }

  function drawResults(live, uni) {
    const f = state.find, el = document.getElementById("results");
    if (!el) return;
    const list = filterUniverse(uni, live);
    const metaOf = e => {
      const l = live.etfs[e.c] || {};
      switch (f.sort) {
        case "r1m": return `1개월 <span class="${cls(e.r1m)}">${pct(e.r1m)}</span> · 시총 ${eok(l.mc)}`;
        case "r1y": return `1년 <span class="${cls(e.r1y)}">${pct(e.r1y)}</span> · 시총 ${eok(l.mc)}`;
        case "fee": return `총보수 ${e.fee != null ? e.fee.toFixed(3) + "%" : "—"} · ${esc(e.is || "")}`;
        case "div": return `배당 ${e.div != null ? e.div.toFixed(2) + "%" : "—"} · 시총 ${eok(l.mc)}`;
        case "mc": return `시총 ${eok(l.mc)} · ${esc(e.top.slice(0, 2).join(", "))}`;
        default: return `거래대금 ${amEok(l.am || 0)} · ${esc(e.top.slice(0, 2).join(", "))}`;
      }
    };
    el.innerHTML = `
      <div class="toolbar"><span class="count">${fmt(list.length)}개</span>
        <select class="sort" id="sort" aria-label="정렬">${SORTS.map(([v, l]) => `<option value="${v}" ${v === f.sort ? "selected" : ""}>${l}</option>`).join("")}</select></div>
      <div class="list">${list.length ? list.slice(0, f.limit).map(e => {
        const l = live.etfs[e.c] || {};
        return etfRow(e, { meta: metaOf(e), side: priceSide(l.p, l.ch) });
      }).join("") : `<div class="empty">조건에 맞는 ETF가 없어요.</div>`}</div>
      ${list.length > f.limit ? `<button class="btn-more" data-act="more">더 보기 (${fmt(list.length - f.limit)}개)</button>` : ""}`;
    el.querySelector("#sort").addEventListener("change", ev => { f.sort = ev.target.value; drawResults(live, uni); });
  }

  async function drawStockHits(live) {
    const el = document.getElementById("stockHits");
    const q = norm(state.find.q);
    if (!el) return;
    if (q.length < 2) { el.innerHTML = ""; return; }
    const { s } = await getJSON("stocks.json");
    if (norm(state.find.q) !== q) return;
    const hits = Object.entries(s).filter(([k, v]) => norm(v.n).includes(q) || k.toLowerCase() === q || ticker(k).toLowerCase() === q)
      .sort((a, b) => b[1].e.length - a[1].e.length).slice(0, 2);
    el.innerHTML = hits.map(([k, v]) => `<section class="card">
      <div class="card-head"><div><div class="card-title">‘${esc(v.n)}’${josa(v.n, "을", "를")} 담은 ETF</div><div class="card-sub">${v.e.length}개 · 비중 높은 순</div></div></div>
      <div class="list">${v.e.slice(0, 8).map(([c, w]) => {
        const u = universeMap[c]; const l = live.etfs[c] || {};
        return u ? etfRow(u, { meta: `비중 <b>${w.toFixed(2)}%</b> · 시총 ${eok(l.mc)}`, side: priceSide(l.p, l.ch) }) : "";
      }).join("")}</div></section>`).join("");
  }

  // ── 상세 ──────────────────────────────────────────────
  async function detail(code) {
    $app.innerHTML = `<div style="padding-top:24px">${skeleton(6)}</div>`;
    const [{ live, U }, d, quotes, b] = await Promise.all([base(), getJSON(`etf/${code}.json`), getJSON("quotes.json").catch(() => ({ q: {} })), getBrief()]);
    const bItem = b?.items.find(it => it.codes.includes(code));
    const e = live.etfs[code] || {};
    const u = U[code] || {};
    const m = d.meta || {};
    const prem = e.p && e.nav ? (e.p / e.nav - 1) * 100 : null;
    document.title = `${d.name} — ETF 월드`;

    $app.innerHTML = `
      <div class="d-head">
        <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
          <div style="min-width:0">
            <div class="d-sub">${code} · ${esc(m.issuer || "")}${d.tags.slice(0, 3).map(t => ` <span class="tag">${esc(t)}</span>`).join("")}</div>
            <h1 class="d-name">${esc(d.name)}</h1>
          </div>
          <button class="star ${isFav(code) ? "on" : ""}" data-act="fav" data-code="${code}" aria-label="즐겨찾기"><svg viewBox="0 0 24 24"><path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/></svg></button>
        </div>
        <div class="d-price">${fmt(e.p)}원</div>
        <div class="d-chg ${cls(e.ch)}">${pct(e.ch)} <span style="color:var(--text-3);font-weight:500;font-size:14px">오늘</span></div>
      </div>
      ${bItem ? `<section class="card"><div class="card-head"><div><div class="card-title">오늘 왜 움직였나</div><div class="card-sub">${briefMeta(b)}</div></div></div>${briefItem(bItem, U, { open: true })}</section>` : ""}
      ${inavCard(d, e, live, prem)}
      <section class="card">
        <div class="card-head"><div class="card-title">차트</div>${seg("range", [["1M", "1개월"], ["3M", "3개월"], ["6M", "6개월"], ["1Y", "1년"]], state.chartRange)}</div>
        <div id="chart"></div>
      </section>
      <section class="card">
        <div class="card-title" style="margin-bottom:12px">기간 수익률</div>
        <div class="returns">${[["W1", "1주"], ["M1", "1개월"], ["M3", "3개월"], ["M6", "6개월"], ["YTD", "올해"], ["Y1", "1년"], ["Y3", "3년"], ["Y5", "5년"]].map(([k, l]) =>
          `<div><div class="k">${l}</div><div class="v ${cls(d.returns?.[k])}">${d.returns?.[k] != null ? pct(d.returns[k], 1) : "—"}</div></div>`).join("")}</div>
      </section>
      <section class="card">
        <div class="card-title" style="margin-bottom:16px">기본 정보</div>
        <div class="kv">
          ${kv("총보수", m.fee != null ? `${m.fee.toFixed(4).replace(/0+$/, "")}%` : "—")}
          ${kv("순자산", eok(m.aum))}
          ${kv("시가총액", eok(e.mc))}
          ${kv("거래대금", amEok(e.am || 0))}
          ${kv("배당수익률", m.divYield != null ? `${m.divYield}%` : "—")}
          ${kv("올해 분배월", m.divMonths ? `${esc(m.divMonths)}월` : "—")}
          ${kv("기초지수", esc(m.base || "—"))}
          ${kv("상장일", m.listed ? `${m.listed.slice(0, 4)}.${m.listed.slice(4, 6)}.${m.listed.slice(6)}` : "—")}
        </div>
        ${m.summary ? `<p class="note summary" data-act="summary" title="눌러서 펼치기">${esc(m.summary)}</p>` : ""}
      </section>
      <section class="card" id="holdings"></section>
      ${footer(live)}`;
    drawChart(d);
    drawHoldings(d, quotes.q);
  }
  const kv = (k, v) => `<div><div class="k">${k}</div><div class="v">${v}</div></div>`;

  function inavCard(d, e, live, prem) {
    const f = d.flags || {};
    let body, note = "";
    if (e.est != null) {
      body = `<div class="inav-grid">
        <div class="inav-box"><div class="k">공식 iNAV · 15:30</div><div class="v">${fmt(e.nav)}원</div><div class="s" style="color:var(--text-3)">종가 ${fmt(e.p)}원</div></div>
        <div class="inav-box hl"><div class="k">추정 iNAV <span class="conf ${e.cf}">${e.cf}</span></div><div class="v">${fmt(e.est)}원</div>
          <div class="s ${cls(e.ex)}">종가 대비 ${pct(e.ex)}</div></div></div>`;
      note = `미국 ${esc(live.usSession)} 시세 · 원/달러 ${fmt(live.fx.now, 2)}원 (<span class="${cls(live.fx.chg)}">${pct(live.fx.chg)}</span>)${f.hedged ? " · 환헤지라 환율 미반영" : ""}<br>
        영향이 큰 종목: ${contribText(e.top)}`;
    } else {
      body = `<div class="inav-grid">
        <div class="inav-box"><div class="k">${live.mode === "official" ? "현재가" : "종가"}</div><div class="v">${fmt(e.p)}원</div></div>
        <div class="inav-box hl"><div class="k">${live.mode === "official" ? "공식 iNAV · 실시간" : "공식 iNAV"}</div><div class="v">${fmt(e.nav)}원</div>
          <div class="s flat">괴리율 ${pct(prem)}</div></div></div>`;
      const u = universeMap[d.code] || {};
      if (f.lev || f.inv || f.synthetic || f.futures) note = "레버리지·인버스·합성·선물형은 구성종목만으로 가격을 설명하기 어려워 추정하지 않아요.";
      else if ((u.usW || 0) < 30) note = "미국 종목 비중이 낮아 장 마감 후 추정을 하지 않아요. 국내 종목은 15:30 이후 가격이 고정돼요.";
      else if (live.mode === "official") note = "KRX 정규장 중에는 거래소가 발표하는 공식 iNAV를 보여줘요. 15:30 이후 추정이 시작돼요.";
      else note = "휴장 구간이라 추정을 잠시 멈췄어요.";
    }
    return `<section class="card">
      <div class="card-head"><div class="card-title">iNAV</div>${statusPill(live)}</div>
      ${body}
      <p class="note">${note}</p>
      <details class="how"><summary>iNAV가 뭔가요?</summary>
        <div class="formula">iNAV는 ETF에 담긴 자산을 지금 시세로 계산한 1주당 가치예요. 시장가가 iNAV보다 높으면 비싸게(프리미엄), 낮으면 싸게(디스카운트) 거래되는 중이에요.<br><br>
        장 마감 후에는 <code>iNAV(15:30) × (1 + Σ 비중 × [(1+종목 변동)(1+환율 변동) − 1])</code> 로 추정해요.</div>
      </details>
    </section>`;
  }

  function drawChart(d) {
    const el = document.getElementById("chart");
    if (!el) return;
    const days = { "1M": 22, "3M": 66, "6M": 128, "1Y": 260 }[state.chartRange];
    const pts = (d.chart || []).slice(-days);
    if (pts.length < 2) { el.innerHTML = '<div class="empty">차트 데이터가 없어요.</div>'; return; }
    const W = 600, H = 200, P = 8;
    const ys = pts.map(p => p[1]);
    const min = Math.min(...ys), max = Math.max(...ys), span = max - min || 1;
    const x = i => (i / (pts.length - 1)) * W;
    const y = v => P + (1 - (v - min) / span) * (H - P * 2);
    const path = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[1]).toFixed(1)}`).join("");
    const chg = (ys[ys.length - 1] / ys[0] - 1) * 100;
    const color = chg >= 0 ? "var(--up)" : "var(--down)";
    const by = y(ys[0]).toFixed(1);
    el.innerHTML = `<div class="chart-wrap">
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="${state.chartRange} 종가 차트">
        <defs><linearGradient id="g" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".16"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
        <line x1="0" x2="${W}" y1="${by}" y2="${by}" stroke="var(--line)" stroke-width="1" stroke-dasharray="3 4" vector-effect="non-scaling-stroke"/>
        <path d="${path}L${W},${H}L0,${H}Z" fill="url(#g)"/>
        <path d="${path}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
        <line id="cx" y1="0" y2="${H}" stroke="var(--text-3)" stroke-width="1" vector-effect="non-scaling-stroke" visibility="hidden"/>
      </svg>
      <div id="cdot" style="position:absolute;width:10px;height:10px;border-radius:50%;background:${color};border:2px solid var(--card);transform:translate(-50%,-50%);visibility:hidden;pointer-events:none"></div>
      <div class="chart-tip" id="ctip" style="visibility:hidden"></div>
    </div>
    <div class="chart-foot"><span class="count">${fmtDate(pts[0][0])} ~ ${fmtDate(pts[pts.length - 1][0])}</span>
      <span class="${cls(chg)}" style="font-weight:700">${pct(chg)}</span></div>`;
    const wrap = el.querySelector(".chart-wrap"), svg = wrap.querySelector("svg");
    const cx = svg.querySelector("#cx"), dot = wrap.querySelector("#cdot"), tip = wrap.querySelector("#ctip");
    const move = ev => {
      const rect = svg.getBoundingClientRect();
      const rx = Math.min(Math.max(ev.clientX - rect.left, 0), rect.width);
      const i = Math.round((rx / rect.width) * (pts.length - 1));
      const px = (x(i) / W) * rect.width, py = (y(pts[i][1]) / H) * rect.height;
      cx.setAttribute("x1", x(i)); cx.setAttribute("x2", x(i)); cx.setAttribute("visibility", "visible");
      dot.style.left = px + "px"; dot.style.top = py + "px"; dot.style.visibility = "visible";
      tip.innerHTML = `${fmtDate(pts[i][0])} <b>${fmt(pts[i][1])}원</b>`;
      tip.style.left = Math.min(Math.max(px, 70), rect.width - 70) + "px"; tip.style.visibility = "visible";
    };
    const leave = () => { cx.setAttribute("visibility", "hidden"); dot.style.visibility = tip.style.visibility = "hidden"; };
    wrap.addEventListener("pointermove", move);
    wrap.addEventListener("pointerdown", move);
    wrap.addEventListener("pointerleave", leave);
  }
  const fmtDate = s => `${s.slice(2, 4)}.${s.slice(4, 6)}.${s.slice(6, 8)}`;

  function drawHoldings(d, q) {
    const el = document.getElementById("holdings");
    if (!el) return;
    const hs = d.holdings.filter(h => h.w > 0);
    const shown = state.holdAll ? hs : hs.slice(0, 10);
    const maxW = Math.max(...hs.map(h => h.w), 1);
    el.innerHTML = `<div class="card-head"><div><div class="card-title">구성종목</div>
      <div class="card-sub">${hs.length}종목 · ${d.hDate || ""} 기준${d.holdings.some(h => h.r && q[h.r]) ? " · 해외 종목은 기준점 이후 변동" : ""}</div></div></div>
      ${shown.map(h => {
        const qq = h.r ? q[h.r] : null;
        const sub = h.r ? `${esc(ticker(h.r))}${qq ? ` · <span class="${cls(qq[1])}">${pct(qq[1])}</span>` : ""}` : esc(h.k || h.t);
        return `<div class="hrow"><div style="flex:1;min-width:0"><div class="hname">${esc(h.n)}</div><div class="hsub">${sub}</div>
          <div class="hbar" style="width:${(h.w / maxW) * 100}%"></div></div><div class="hw">${h.w.toFixed(2)}%</div></div>`;
      }).join("")}
      ${hs.length > 10 ? `<button class="btn-more" data-act="holdAll">${state.holdAll ? "접기" : `전체 ${hs.length}종목 보기`}</button>` : ""}`;
    el._data = [d, q];
  }

  // ── 내 ETF ─────────────────────────────────────────────
  async function my() {
    const { live, U } = await base();
    const list = favs().filter(c => U[c]);
    const qty = store.get("qty", {});
    let value = 0, delta = 0, hasEst = false;
    for (const c of list) {
      const e = live.etfs[c] || {}, n = +qty[c] || 0;
      value += n * (e.p || 0);
      if (e.est != null && n) { delta += n * (e.est - e.p); hasEst = true; }
    }
    const dpct = value ? (delta / value) * 100 : null;
    $app.innerHTML = `
      <div class="hero"><h1>내일 나의 계좌는?</h1><p>보유 수량을 넣으면 추정 iNAV로 내일 아침 예상 손익을 계산해요.</p></div>
      ${list.length ? `<section class="card">
        <div class="card-sub">보유 ETF 평가금액 · 종가 기준</div>
        <div class="summary-big">${fmt(value)}원</div>
        <div class="d-chg ${cls(hasEst ? dpct : null)}" style="margin-top:4px">${hasEst ? `${delta >= 0 ? "+" : ""}${fmt(delta)}원 (${pct(dpct)}) 예상` : "추정 가능한 시간이 되면 예상 손익을 보여드려요"}</div>
        <p class="note">${hotExplain(live)}</p>
      </section>
      <section class="card"><div class="card-head"><div class="card-title">즐겨찾기</div><span class="count">수량 입력</span></div>
        <div class="list">${list.map(c => {
          const e = live.etfs[c] || {}, u = U[c];
          return `<div class="row">${avatar(u.n)}<a class="row-main" href="#/etf/${c}"><div class="row-name">${esc(u.n)}</div>
            <div class="row-meta">${fmt(e.p)}원 ${e.ex != null ? `· 추정 <span class="${cls(e.ex)}">${pct(e.ex)}</span>` : `· 오늘 <span class="${cls(e.ch)}">${pct(e.ch)}</span>`}</div></a>
            <input class="qty" inputmode="numeric" data-qty="${c}" value="${qty[c] || ""}" placeholder="0주" aria-label="${esc(u.n)} 보유 수량"></div>`;
        }).join("")}</div></section>`
      : `<section class="card"><div class="empty">아직 즐겨찾기한 ETF가 없어요.<br>ETF 상세 화면에서 ☆를 눌러 추가해 보세요.</div>
        <div class="list">${live.rank.amount.slice(0, 5).map(e => etfRow(e, { meta: "많이 거래되는 ETF", side: priceSide(e.p, e.ch) })).join("")}</div></section>`}
      ${footer(live)}`;
  }

  // ── 라우터 & 이벤트 ────────────────────────────────────
  async function render() {
    const [path, qs] = (location.hash.slice(1) || "/").split("?");
    const params = new URLSearchParams(qs || "");
    const parts = path.split("/").filter(Boolean);
    const tab = parts[0] === "hot" ? "hot" : parts[0] === "find" ? "find" : parts[0] === "my" ? "my" : parts[0] === "etf" ? "" : "home";
    document.querySelectorAll(".tabbar a").forEach(a => a.classList.toggle("on", a.dataset.tab === tab));
    if (parts[0] !== "etf") document.title = "ETF 월드 · 서울 WM센터";
    try {
      if (parts[0] === "hot") await hot();
      else if (parts[0] === "find") await find(params);
      else if (parts[0] === "my") await my();
      else if (parts[0] === "brief") await brief(params);
      else if (parts[0] === "etf" && parts[1]) await detail(parts[1]);
      else await home();
    } catch (err) {
      console.error(err);
      $app.innerHTML = `<div class="card" style="margin-top:20px"><div class="empty">데이터를 불러오지 못했어요.<br>잠시 후 다시 시도해 주세요.</div></div>`;
    }
  }

  let lastPath = null;
  window.addEventListener("hashchange", () => {
    const p = location.hash.split("?")[0];
    if (p !== lastPath) { state.holdAll = false; window.scrollTo(0, 0); }
    lastPath = p;
    render();
  });

  document.addEventListener("click", ev => {
    const t = ev.target.closest("[data-seg],[data-act],[data-tag],[data-go],[data-rank]");
    if (!t) return;
    if (t.dataset.go) { location.hash = t.dataset.go; return; }
    if (t.dataset.seg) {
      if (t.dataset.seg === "trendKey") {
        state.trendKey = t.dataset.v;
        t.parentElement.querySelectorAll("button").forEach(b => b.classList.toggle("on", b === t));
        base().then(({ live }) => { document.getElementById("trendBody").innerHTML = trendBody(live, state.trends, state.trendKey); });
        return;
      }
      if (t.dataset.seg === "usKey") {
        state.usKey = t.dataset.v;
        t.parentElement.querySelectorAll("button").forEach(b => b.classList.toggle("on", b === t));
        base().then(({ live }) => { document.getElementById("usBody").innerHTML = usBody(live, state.usKey); });
        return;
      }
      if (t.dataset.seg === "range") {
        state.chartRange = t.dataset.v;
        t.parentElement.querySelectorAll("button").forEach(b => b.classList.toggle("on", b === t));
        const d = cache[`etf/${location.hash.split("/")[2]}.json`];
        if (d) drawChart(d);
        return;
      }
      state[t.dataset.seg] = t.dataset.v;
      render();
      return;
    }
    if (t.dataset.rank) {
      state.rankTab = t.dataset.rank;
      t.parentElement.querySelectorAll(".chip").forEach(c => c.classList.toggle("on", c === t));
      base().then(({ live }) => {
        document.getElementById("rankList").innerHTML = rankRows(live, state.rankTab, state.why || {});
        document.getElementById("rankNote").innerHTML = rankNote(live, state.rankTab);
        document.getElementById("rankMore").setAttribute("href", state.rankTab === "up" || state.rankTab === "down" ? "#/hot" : "#/find");
      });
      return;
    }
    if (t.dataset.tag) {
      state.find.tag = t.dataset.tag; state.find.limit = 40;
      document.querySelectorAll(".chip").forEach(c => c.classList.toggle("on", c === t));
      base().then(({ live, uni }) => drawResults(live, uni));
      return;
    }
    const act = t.dataset.act;
    if (act === "summary") t.classList.toggle("open");
    else if (act === "fav") { toggleFav(t.dataset.code); t.classList.toggle("on", isFav(t.dataset.code)); }
    else if (act === "more") { state.find.limit += 40; base().then(({ live, uni }) => drawResults(live, uni)); }
    else if (act === "holdAll") { state.holdAll = !state.holdAll; const [d, q] = document.getElementById("holdings")._data; drawHoldings(d, q); }
  });

  document.addEventListener("input", ev => {
    const c = ev.target.dataset?.qty;
    if (!c) return;
    const v = ev.target.value.replace(/[^\d]/g, "");
    ev.target.value = v;
    const qty = store.get("qty", {}); qty[c] = v ? +v : 0; store.set("qty", qty);
  });
  document.addEventListener("change", ev => { if (ev.target.dataset?.qty) my(); });

  lastPath = location.hash.split("?")[0];
  render();
})();
