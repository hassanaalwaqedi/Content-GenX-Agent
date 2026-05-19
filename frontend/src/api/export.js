/**
 * Export data as a professional branded PDF report.
 * Uses jsPDF + AutoTable for clean table rendering.
 */
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';

/**
 * Generate and download a professional PDF report.
 *
 * @param {string} filename - e.g. "top_videos_report.pdf"
 * @param {string} title - Report title, e.g. "Top Videos Report"
 * @param {string} subtitle - e.g. "AI for business — Last 365 days"
 * @param {string[]} headers - Column headers
 * @param {Array<Array<string|number>>} rows - Data rows
 */
export function exportToPDF(filename, title, subtitle, headers, rows) {
  const doc = new jsPDF({
    orientation: rows[0]?.length > 8 ? 'landscape' : 'portrait',
    unit: 'mm',
    format: 'a4',
  });

  const pageWidth = doc.internal.pageSize.getWidth();
  const now = new Date().toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });

  // ── Header Bar ──
  doc.setFillColor(15, 17, 23);
  doc.rect(0, 0, pageWidth, 32, 'F');

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(16);
  doc.setTextColor(212, 168, 67); // Golden brand color
  doc.text('GenX Leadership Academy', 14, 14);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(139, 144, 160);
  doc.text('CONTENT INTELLIGENCE PLATFORM', 14, 20);

  doc.setFontSize(8);
  doc.setTextColor(139, 144, 160);
  doc.text(`Generated: ${now}`, pageWidth - 14, 14, { align: 'right' });
  doc.text(`${rows.length} records`, pageWidth - 14, 20, { align: 'right' });

  // ── Report Title ──
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(14);
  doc.setTextColor(40, 40, 40);
  doc.text(title, 14, 42);

  if (subtitle) {
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(9);
    doc.setTextColor(120, 120, 120);
    doc.text(subtitle, 14, 49);
  }

  // ── Data Table ──
  autoTable(doc, {
    startY: subtitle ? 55 : 50,
    head: [headers],
    body: rows,
    theme: 'grid',
    styles: {
      font: 'helvetica',
      fontSize: 7.5,
      cellPadding: 3,
      lineColor: [220, 220, 220],
      lineWidth: 0.2,
      textColor: [40, 40, 40],
      valign: 'middle',
    },
    headStyles: {
      fillColor: [15, 17, 23],
      textColor: [232, 234, 240],
      fontStyle: 'bold',
      fontSize: 7.5,
      halign: 'left',
    },
    alternateRowStyles: {
      fillColor: [248, 249, 252],
    },
    columnStyles: {
      0: { halign: 'center', cellWidth: 8 },
    },
    margin: { left: 14, right: 14 },
    didDrawPage: () => {
      const pageHeight = doc.internal.pageSize.getHeight();
      doc.setFontSize(7);
      doc.setTextColor(160, 160, 160);
      doc.text(
        `GenX Leadership Academy  •  Content Intelligence  •  Page ${doc.internal.getCurrentPageInfo().pageNumber}`,
        pageWidth / 2,
        pageHeight - 8,
        { align: 'center' }
      );
    },
  });

  // ── Force proper filename download ──
  const safeName = filename.endsWith('.pdf') ? filename : filename + '.pdf';
  const pdfBlob = doc.output('blob');
  const url = URL.createObjectURL(pdfBlob);

  const a = document.createElement('a');
  a.style.display = 'none';
  a.href = url;
  a.download = safeName;
  a.type = 'application/pdf';
  document.body.appendChild(a);
  a.click();

  // Cleanup
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 200);
}


/**
 * Generate a modern, branded PDF report for a video transcript.
 * Includes video details, AI insights, and the full transcript text.
 *
 * @param {Object} video - The full video object from the API
 */
export function exportTranscriptPDF(video) {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const pw = doc.internal.pageSize.getWidth();  // page width
  const ph = doc.internal.pageSize.getHeight(); // page height
  const mx = 16; // margin x
  const contentWidth = pw - mx * 2;

  const now = new Date().toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  });
  const wc = video.transcript ? video.transcript.trim().split(/\s+/).filter(Boolean).length : 0;

  // ── Color Palette ──
  const dark  = [15, 17, 23];
  const gold  = [212, 168, 67];
  const muted = [139, 144, 160];
  const accent = [99, 102, 241]; // indigo
  const green = [52, 211, 153];
  const white = [255, 255, 255];

  // ===================================================================
  // PAGE 1: Cover + Video Details
  // ===================================================================

  // ── Top gradient bar ──
  doc.setFillColor(...dark);
  doc.rect(0, 0, pw, 52, 'F');

  // Gold accent line
  doc.setFillColor(...gold);
  doc.rect(0, 52, pw, 1.5, 'F');

  // Brand name
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(20);
  doc.setTextColor(...gold);
  doc.text('GenX', mx, 18);

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(7);
  doc.setTextColor(...muted);
  doc.text('LEADERSHIP ACADEMY', mx, 24);

  // Right side header info
  doc.setFontSize(8);
  doc.setTextColor(...muted);
  doc.text('CONTENT INTELLIGENCE REPORT', pw - mx, 15, { align: 'right' });
  doc.setFontSize(7);
  doc.text(`Generated: ${now}`, pw - mx, 21, { align: 'right' });

  // Report type badge
  doc.setFillColor(99, 102, 241);
  doc.roundedRect(pw - mx - 38, 28, 38, 8, 2, 2, 'F');
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(7);
  doc.setTextColor(...white);
  doc.text('TRANSCRIPT REPORT', pw - mx - 19, 33.5, { align: 'center' });

  // ── Video Title ──
  let y = 64;
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(14);
  doc.setTextColor(30, 30, 30);
  const titleLines = doc.splitTextToSize(video.title || 'Untitled Video', contentWidth);
  doc.text(titleLines, mx, y);
  y += titleLines.length * 7 + 4;

  // Channel + Niche tags
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(9);
  doc.setTextColor(...muted);
  const channelText = video.channel ? `by ${video.channel}` : '';
  const platformIcon = { youtube: 'YouTube', reddit: 'Reddit', tiktok: 'TikTok', instagram: 'Instagram' }[video.platform] || video.platform || 'Unknown';
  doc.text(`${platformIcon}  •  ${video.niche}  •  ${channelText}`, mx, y);
  y += 10;

  // ── Metrics Cards (modern rounded boxes) ──
  const metrics = [
    { label: 'Views', value: fmtNum(video.views), color: [59, 130, 246] },
    { label: 'Likes', value: fmtNum(video.likes), color: [34, 197, 94] },
    { label: 'Comments', value: fmtNum(video.comments), color: [249, 115, 22] },
    { label: 'Engagement', value: (video.engagement_rate * 100).toFixed(2) + '%', color: [168, 85, 247] },
    { label: 'Score', value: video.score?.toFixed(3) || '—', color: [...gold] },
  ];

  const cardW = (contentWidth - 4 * 3) / 5;
  metrics.forEach((m, i) => {
    const cx = mx + i * (cardW + 3);
    // Card background
    doc.setFillColor(248, 249, 252);
    doc.roundedRect(cx, y, cardW, 20, 2, 2, 'F');
    // Colored top accent
    doc.setFillColor(...m.color);
    doc.roundedRect(cx, y, cardW, 3, 2, 2, 'F');
    doc.rect(cx, y + 1.5, cardW, 1.5, 'F');
    // Value
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(11);
    doc.setTextColor(30, 30, 30);
    doc.text(m.value, cx + cardW / 2, y + 12, { align: 'center' });
    // Label
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(6.5);
    doc.setTextColor(...muted);
    doc.text(m.label.toUpperCase(), cx + cardW / 2, y + 17.5, { align: 'center' });
  });
  y += 28;

  // ── AI Insights Section ──
  const isPending = (val) => !val || val === 'Analysis pending';

  if (!isPending(video.target_audience) || !isPending(video.strategic_advice) || !isPending(video.content_gap)) {
    // Section header
    doc.setFillColor(248, 249, 252);
    doc.roundedRect(mx, y, contentWidth, 7, 2, 2, 'F');
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(8);
    doc.setTextColor(...accent);
    doc.text('AI-POWERED INSIGHTS', mx + 4, y + 5);
    y += 12;

    const insights = [
      { label: 'Target Audience', value: video.target_audience },
      { label: 'Content Gap', value: video.content_gap },
      { label: 'Strategic Advice', value: video.strategic_advice },
    ];

    for (const ins of insights) {
      if (isPending(ins.value)) continue;
      if (y > ph - 30) { addFooter(doc, pw, ph); doc.addPage(); y = 20; }

      doc.setFont('helvetica', 'bold');
      doc.setFontSize(7.5);
      doc.setTextColor(...accent);
      doc.text(ins.label.toUpperCase(), mx, y);
      y += 5;

      doc.setFont('helvetica', 'normal');
      doc.setFontSize(8);
      doc.setTextColor(60, 60, 60);
      const lines = doc.splitTextToSize(ins.value, contentWidth - 4);
      doc.text(lines, mx + 2, y);
      y += lines.length * 4 + 6;
    }
  }

  // ── Transcript Section ──
  if (video.transcript) {
    if (y > ph - 50) { addFooter(doc, pw, ph); doc.addPage(); y = 20; }

    // Transcript header bar
    doc.setFillColor(...dark);
    doc.roundedRect(mx, y, contentWidth, 10, 2, 2, 'F');
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(9);
    doc.setTextColor(...gold);
    doc.text('TRANSCRIPT', mx + 5, y + 7);

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(7);
    doc.setTextColor(...muted);
    doc.text(`${wc.toLocaleString()} words  •  ${video.transcript.length.toLocaleString()} characters`, pw - mx - 5, y + 7, { align: 'right' });
    y += 16;

    // Transcript body
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8.5);
    doc.setTextColor(50, 50, 50);

    const textLines = doc.splitTextToSize(video.transcript, contentWidth - 8);
    const lineH = 4.2;

    for (let i = 0; i < textLines.length; i++) {
      if (y > ph - 20) {
        addFooter(doc, pw, ph);
        doc.addPage();
        y = 20;
        // Continuation header on new pages
        doc.setFillColor(248, 249, 252);
        doc.roundedRect(mx, y - 4, contentWidth, 7, 1, 1, 'F');
        doc.setFont('helvetica', 'italic');
        doc.setFontSize(7);
        doc.setTextColor(...muted);
        doc.text('TRANSCRIPT (continued)', mx + 4, y);
        y += 8;
        doc.setFont('helvetica', 'normal');
        doc.setFontSize(8.5);
        doc.setTextColor(50, 50, 50);
      }
      doc.text(textLines[i], mx + 4, y);
      y += lineH;
    }
  }

  // ── Final footer ──
  addFooter(doc, pw, ph);

  // ── Download ──
  const safeName = `transcript_${video.video_id}.pdf`;
  const pdfBlob = doc.output('blob');
  const url = URL.createObjectURL(pdfBlob);
  const a = document.createElement('a');
  a.style.display = 'none';
  a.href = url;
  a.download = safeName;
  a.type = 'application/pdf';
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 200);
}


// ── Helper: number formatter ──
function fmtNum(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n ?? 0);
}


// ── Helper: branded footer on every page ──
function addFooter(doc, pw, ph) {
  // Bottom accent bar
  doc.setFillColor(212, 168, 67);
  doc.rect(0, ph - 12, pw, 0.5, 'F');

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(6.5);
  doc.setTextColor(160, 160, 160);
  doc.text(
    `GenX Leadership Academy  •  Content Intelligence Platform  •  Page ${doc.internal.getCurrentPageInfo().pageNumber}`,
    pw / 2,
    ph - 6,
    { align: 'center' }
  );
}
