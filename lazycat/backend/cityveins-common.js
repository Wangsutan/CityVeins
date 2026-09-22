/**
 * 记录袋 / 文件清单 两个页面共用的部分。
 *
 * 这两页本来各写了一份几乎一样的工具函数与文件行渲染（格式化大小、转义、
 * toast、下载、站内预览……），重复得厉害。这里抽成公共模块：
 *   records.html        —— 云端已保存数据的列表（每条记录一行）
 *   record_files.html   —— 单条记录的文件清单（每个文件一行）
 *
 * 注意：抽的是**共用**的东西，不是把两页合成一页。
 * 「一个页面管一类实体」的结构保持独立 —— 记录行由 records.html 自己渲染，
 * 文件行两边共用 fileRows()。
 *
 * 用法：<script src="/static/cityveins-common.js"></script>
 * 必须在页面自己的脚本之前引入。
 */
(function () {
  'use strict';

  var API = '';   // 同源

  /* ---------------- DOM / 文本 ---------------- */

  function $(id) { return document.getElementById(id); }

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function fmtSize(bytes) {
    if (!bytes && bytes !== 0) return '—';
    var units = ['B', 'KB', 'MB', 'GB'];
    var i = 0, v = Number(bytes);
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
    return (i === 0 ? v : v.toFixed(v >= 100 ? 0 : 1)) + ' ' + units[i];
  }

  function fmtScore(v) {
    var n = Number(v);
    return Number.isFinite(n) ? n.toFixed(2) + ' 分' : '—';
  }

  function toast(msg, ms) {
    var el = $('toast');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.classList.remove('show'); }, ms || 2200);
  }

  function showErr(msg) {
    var el = $('err');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('open');
  }

  function clearErr() {
    var el = $('err');
    if (el) el.classList.remove('open');
  }

  /* ---------------- 下载 ---------------- */

  // 按懒猫官方「文件选择器 / 下载拦截」标准写法触发下载。
  // 标准注入脚本（lazycat/content/lazycat-injects/lzc-file-chooser-inject.js，
  // 与 quotations 同一份）钩住 HTMLAnchorElement.prototype.click，命中条件是
  //   anchor instanceof HTMLAnchorElement && Boolean(anchor.download)
  //   && anchor.href.startsWith("blob:")
  // 命中后就地弹出「保存至本地 / 保存至懒猫微服」的选择弹层。
  // 因此这里只负责按标准产出 blob: + download 锚点，拦截交由官方脚本完成。
  async function triggerDownload(url, filename) {
    toast('正在取回文件…', 60000);
    try {
      var res = await fetch(url);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var blob = await res.blob();
      var blobUrl = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename || 'download';
      a.style.display = 'none';
      document.body.appendChild(a);
      try {
        a.click();
        toast('已发起下载：' + a.download);
      } finally {
        document.body.removeChild(a);
        setTimeout(function () { try { URL.revokeObjectURL(blobUrl); } catch (e) {} }, 60000);
      }
    } catch (e) {
      toast('下载失败：' + (e && e.message ? e.message : e), 4000);
    }
  }

  /* ---------------- 站内预览弹层 ---------------- */

  // 不用 window.open：安卓上会把当前 WebView 顶掉/重载，页面里的结果就丢了。
  var previewCtx = null;

  function openPreview(url, title, downloadUrl) {
    previewCtx = { url: url, title: title, downloadUrl: downloadUrl || url };
    var t = $('preview-title');
    if (t) t.textContent = title || '预览';
    var f = $('preview-frame');
    if (f) f.src = url;
    var o = $('preview-overlay');
    if (o) o.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function closePreview() {
    var o = $('preview-overlay');
    if (o) o.classList.remove('open');
    var f = $('preview-frame');
    if (f) f.src = 'about:blank';
    document.body.style.overflow = '';
    previewCtx = null;
  }

  function initPreview() {
    var o = $('preview-overlay');
    if (!o) return;
    var c = $('preview-close');
    if (c) c.addEventListener('click', closePreview);
    var d = $('preview-download');
    if (d) {
      d.addEventListener('click', function () {
        if (previewCtx) triggerDownload(previewCtx.downloadUrl, previewCtx.title);
      });
    }
    o.addEventListener('click', function (ev) { if (ev.target === o) closePreview(); });
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') closePreview();
    });
  }

  /* ---------------- 文件清单渲染（两页共用） ---------------- */

  var PREVIEWABLE = ['.html', '.htm', '.md', '.csv', '.json', '.txt'];

  function canPreview(f) {
    return PREVIEWABLE.indexOf(String(f.ext || '').toLowerCase()) !== -1;
  }

  function downloadUrlFor(f) {
    return f.download_url || String(f.preview_url || '').replace('/preview/', '/download/');
  }

  function previewUrlFor(f) {
    return f.preview_url || String(f.download_url || '').replace('/download/', '/preview/');
  }

  /**
   * 把一个文件数组渲染成文件行 HTML。
   * 两页共用，所以只产出 data-* 属性，由各页自己的事件委托处理点击
   * （或者直接调用 bindFileRowClicks）。
   */
  function fileRows(files, opts) {
    opts = opts || {};
    if (!files || !files.length) {
      return '<div class="empty">' + (opts.emptyText || '这个目录里没有文件。') + '</div>';
    }
    return files.map(function (f) {
      var isReport = f.kind === 'report' || f.kind === 'ai_report';
      var prev = canPreview(f) ? previewUrlFor(f) : '';
      return '' +
        '<div class="file-row">' +
          '<div class="file-info">' +
            '<div class="file-name">' + esc(f.display_name || f.name) + '</div>' +
            '<div class="file-meta">' + esc(f.name) + ' · ' + fmtSize(f.size_bytes) +
              ' · ' + esc(f.mtime) + '</div>' +
          '</div>' +
          '<div class="file-ops">' +
            (prev
              ? '<button type="button" class="' + (isReport ? 'amber' : '') +
                '" data-fprev="' + esc(prev) + '" data-fname="' + esc(f.name) + '">预览</button>'
              : '') +
            '<button type="button" data-fdl="' + esc(downloadUrlFor(f)) +
              '" data-fname="' + esc(f.name) + '">下载</button>' +
          '</div>' +
        '</div>';
    }).join('');
  }

  /** 文件行的点击约定：data-fprev 预览、data-fdl 下载。两页都可直接用。 */
  function bindFileRowClicks(container) {
    if (!container) return;
    container.addEventListener('click', function (ev) {
      var btn = ev.target.closest ? ev.target.closest('button') : null;
      if (!btn) return;
      if (btn.dataset.fprev) {
        openPreview(btn.dataset.fprev, btn.dataset.fname,
                    btn.dataset.fprev.replace('/preview/', '/download/'));
      } else if (btn.dataset.fdl) {
        triggerDownload(btn.dataset.fdl, btn.dataset.fname);
      }
    });
  }

  /** 文件表的表头统计，两页共用的措辞 */
  function fileSummary(r, files) {
    files = files || [];
    return 'ID ' + (r.rid || '') + ' · 保存于 ' + (r.created || '') +
           ' · ' + files.length + ' 个文件 · ' + fmtSize(r.total_bytes);
  }

  /* ---------------- 「从哪进回哪」 ---------------- */

  /**
   * 页头返回按钮：优先按浏览器历史回退（从哪进来就回哪），
   * 没有同源来路时才退回 fallback。
   *
   * 以前是写死的 href（比如记录/文件页一律回首页），
   * 从记录袋点进文件清单再返回就跳错了地方。
   */
  function initBackButton() {
    var btn = document.querySelector('.back');
    if (!btn) return;
    var fallback = btn.getAttribute('href') || '/';
    btn.addEventListener('click', function (ev) {
      var sameOriginFrom = false;
      try {
        sameOriginFrom = Boolean(document.referrer) &&
          document.referrer.indexOf(location.origin) === 0;
      } catch (e) {
        sameOriginFrom = false;
      }
      if (sameOriginFrom && window.history && window.history.length > 1) {
        ev.preventDefault();
        window.history.back();
      }
      // 否则按 href 走（= fallback 目标）
    });
  }

  window.CV = {
    API: API, $: $, esc: esc, fmtSize: fmtSize, fmtScore: fmtScore,
    toast: toast, showErr: showErr, clearErr: clearErr,
    triggerDownload: triggerDownload,
    openPreview: openPreview, closePreview: closePreview, initPreview: initPreview,
    fileRows: fileRows, bindFileRowClicks: bindFileRowClicks,
    canPreview: canPreview, previewUrlFor: previewUrlFor, downloadUrlFor: downloadUrlFor,
    fileSummary: fileSummary,
    initBackButton: initBackButton,
  };
})();
