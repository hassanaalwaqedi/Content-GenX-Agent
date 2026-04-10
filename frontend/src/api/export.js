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
