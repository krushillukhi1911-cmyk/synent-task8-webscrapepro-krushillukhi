import os
import json
import csv
import zipfile
from io import BytesIO
import xlsxwriter
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

class Exporter:
    """Service to format and generate export files in various formats."""
    
    @staticmethod
    def export_to_json(records, file_path):
        """Saves scraped records to a formatted JSON file."""
        data = [r.data_content for r in records]
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True

    @staticmethod
    def export_to_csv(records, file_path):
        """Saves a flattened view of scraped records into a CSV file."""
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Headers
            writer.writerow([
                "Record ID", "Page URL", "Page Title", "Meta Description", 
                "Emails Found", "Phones Found", "Total Headings", 
                "Total Links", "Total Images", "Custom Fields"
            ])
            
            for idx, r in enumerate(records):
                content = r.data_content
                meta = content.get('meta', {})
                contacts = content.get('contacts', {})
                headings = content.get('headings', {})
                links = content.get('links', [])
                media = content.get('media', {})
                custom = content.get('custom_fields', {})
                
                # Flatten lists
                emails_str = ", ".join(contacts.get('emails', []))
                phones_str = ", ".join(contacts.get('phones', []))
                
                heading_count = sum(len(lst) for lst in headings.values()) if isinstance(headings, dict) else 0
                image_count = len(media.get('images', []))
                
                writer.writerow([
                    r.id,
                    content.get('url', r.url),
                    meta.get('title', ''),
                    meta.get('description', ''),
                    emails_str,
                    phones_str,
                    heading_count,
                    len(links),
                    image_count,
                    json.dumps(custom) if custom else ""
                ])
        return True

    @staticmethod
    def export_to_excel(records, file_path):
        """Creates a professional multi-tab Excel spreadsheet from scraped records."""
        workbook = xlsxwriter.Workbook(file_path)
        
        # Formats
        header_format = workbook.add_format({
            'bold': True, 'font_color': 'white', 'bg_color': '#4F46E5', 'border': 1
        })
        cell_format = workbook.add_format({'border': 1})
        title_format = workbook.add_format({'bold': True, 'font_size': 14, 'font_color': '#1E1B4B'})
        
        # 1. SUMMARY SHEET
        summary_sheet = workbook.add_worksheet('Overview')
        summary_sheet.write('A1', 'WebScrape Pro - Extraction Summary', title_format)
        summary_sheet.write('A3', 'Total Pages Scraped:', workbook.add_format({'bold': True}))
        summary_sheet.write('B3', len(records))
        summary_sheet.write('A4', 'Export Date:', workbook.add_format({'bold': True}))
        from datetime import datetime
        summary_sheet.write('B4', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        headers = ["URL", "Title", "Meta Description", "Email Matches", "Phone Matches"]
        for col_num, header in enumerate(headers):
            summary_sheet.write(5, col_num, header, header_format)
            
        for row_num, r in enumerate(records):
            content = r.data_content
            meta = content.get('meta', {})
            contacts = content.get('contacts', {})
            
            emails_str = ", ".join(contacts.get('emails', []))
            phones_str = ", ".join(contacts.get('phones', []))
            
            summary_sheet.write(row_num + 6, 0, content.get('url', r.url), cell_format)
            summary_sheet.write(row_num + 6, 1, meta.get('title', ''), cell_format)
            summary_sheet.write(row_num + 6, 2, meta.get('description', ''), cell_format)
            summary_sheet.write(row_num + 6, 3, emails_str, cell_format)
            summary_sheet.write(row_num + 6, 4, phones_str, cell_format)
            
        # Autofit columns
        summary_sheet.set_column('A:E', 25)
        
        # 2. LINKS TAB
        link_sheet = workbook.add_worksheet('Extracted Links')
        link_headers = ["Source URL", "Destination URL", "Anchor Text"]
        for col_num, header in enumerate(link_headers):
            link_sheet.write(0, col_num, header, header_format)
            
        link_row = 1
        for r in records:
            content = r.data_content
            source_url = content.get('url', r.url)
            for link in content.get('links', []):
                link_sheet.write(link_row, 0, source_url, cell_format)
                link_sheet.write(link_row, 1, link.get('url', ''), cell_format)
                link_sheet.write(link_row, 2, link.get('text', ''), cell_format)
                link_row += 1
        link_sheet.set_column('A:C', 30)

        # 3. IMAGES & MEDIA TAB
        media_sheet = workbook.add_worksheet('Media Assets')
        media_headers = ["Source URL", "Asset URL", "Alt Text"]
        for col_num, header in enumerate(media_headers):
            media_sheet.write(0, col_num, header, header_format)
            
        media_row = 1
        for r in records:
            content = r.data_content
            source_url = content.get('url', r.url)
            for img in content.get('media', {}).get('images', []):
                media_sheet.write(media_row, 0, source_url, cell_format)
                media_sheet.write(media_row, 1, img.get('url', ''), cell_format)
                media_sheet.write(media_row, 2, img.get('alt', ''), cell_format)
                media_row += 1
        media_sheet.set_column('A:C', 30)
        
        workbook.close()
        return True

    @staticmethod
    def export_to_pdf(records, file_path, task):
        """Generates a structured PDF report summarising the task data results."""
        doc = SimpleDocTemplate(file_path, pagesize=letter,
                                rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1E1B4B'),
            spaceAfter=15
        )
        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#4B5563'),
            spaceAfter=25
        )
        section_heading = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#4F46E5'),
            spaceBefore=15,
            spaceAfter=10
        )
        body_style = styles['Normal']
        
        elements = []
        
        # Title and Header
        elements.append(Paragraph("WebScrape Pro - Extraction Report", title_style))
        elements.append(Paragraph(f"Generated for task runs on URL: {task.url}", subtitle_style))
        elements.append(Spacer(1, 10))
        
        # Meta task table
        task_info_data = [
            [Paragraph("<b>Task ID</b>", body_style), f"{task.id}"],
            [Paragraph("<b>Status</b>", body_style), f"{task.status}"],
            [Paragraph("<b>Started At</b>", body_style), f"{task.started_at.strftime('%Y-%m-%d %H:%M:%S') if task.started_at else 'N/A'}"],
            [Paragraph("<b>Completed At</b>", body_style), f"{task.completed_at.strftime('%Y-%m-%d %H:%M:%S') if task.completed_at else 'N/A'}"],
            [Paragraph("<b>Total Pages</b>", body_style), f"{len(records)}"],
            [Paragraph("<b>Records Extracted</b>", body_style), f"{task.total_extracted}"]
        ]
        
        task_table = Table(task_info_data, colWidths=[150, 350])
        task_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F3F4F6')),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#E5E7EB')),
            ('PADDING', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
        ]))
        
        elements.append(task_table)
        elements.append(Spacer(1, 20))
        
        # Records Summary Section
        elements.append(Paragraph("Scraped Page Details", section_heading))
        
        for idx, r in enumerate(records[:10]):  # Limit to first 10 rows to fit PDF limits nicely
            content = r.data_content
            meta = content.get('meta', {})
            contacts = content.get('contacts', {})
            
            p_title = meta.get('title', 'No Title')
            p_desc = meta.get('description', 'No meta description found.')
            p_emails = ", ".join(contacts.get('emails', [])) or "None"
            
            elements.append(Paragraph(f"<b>Page {idx+1}: {content.get('url', r.url)}</b>", body_style))
            page_info = [
                [Paragraph("<b>Title:</b>", body_style), Paragraph(p_title, body_style)],
                [Paragraph("<b>Description:</b>", body_style), Paragraph(p_desc, body_style)],
                [Paragraph("<b>Emails Found:</b>", body_style), Paragraph(p_emails, body_style)]
            ]
            page_table = Table(page_info, colWidths=[100, 400])
            page_table.setStyle(TableStyle([
                ('PADDING', (0,0), (-1,-1), 4),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('LINEBELOW', (0,-1), (-1,-1), 0.5, colors.HexColor('#E5E7EB'))
            ]))
            elements.append(page_table)
            elements.append(Spacer(1, 10))
            
        if len(records) > 10:
            elements.append(Spacer(1, 5))
            elements.append(Paragraph(f"<i>... and {len(records) - 10} more records. Export to CSV/JSON to view all.</i>", body_style))
            
        doc.build(elements)
        return True

    @staticmethod
    def package_to_zip(records, zip_file_path):
        """Packages all text assets or data payloads into a ZIP archive."""
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Write global JSON file inside ZIP
            data = [r.data_content for r in records]
            zip_file.writestr("scraped_data_full.json", json.dumps(data, indent=4))
            
            # Write a separate text file per page scraped
            for idx, r in enumerate(records):
                content = r.data_content
                paragraphs = content.get('paragraphs', [])
                
                # Compile paragraphs to flat text
                page_text = f"URL: {content.get('url', r.url)}\n"
                page_text += f"TITLE: {content.get('meta', {}).get('title', '')}\n"
                page_text += "="*40 + "\n\n"
                page_text += "\n\n".join(paragraphs)
                
                zip_file.writestr(f"page_{idx+1}_content.txt", page_text)
        return True
